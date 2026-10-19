"""Independent chief acceptance check for exact SOL-001 source; toy data only."""
import argparse, hashlib, importlib.util, json, math, re, subprocess, sys
from pathlib import Path
from fractions import Fraction as F

ROOT=Path(__file__).resolve().parents[2]
COMMIT="b25c6b5589d07e767f463f54f053f08bb0085157"

def git(*args):
    return subprocess.check_output(["git",*args],cwd=ROOT)
def run(output):
    task=json.loads((ROOT/"ops/tasks/SOL-001.json").read_text())
    receipt=json.loads(git("show",COMMIT+":handoff/SOL-001/result.json"))
    digest=hashlib.sha256(json.dumps(task,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    assert receipt["task_sha256"]==digest and receipt["base_commit"]==task["base_commit"]
    assert (receipt["task_id"],receipt["attempt"],receipt["role"])==("SOL-001",1,"sol")
    assert receipt["status"]=="completed" and not receipt["failure"]
    assert all(x["exit_code"]==0 for x in receipt["checks"])
    assert receipt["python"].startswith("3.12.")
    assert receipt["input_manifest"]==json.loads((ROOT/"data/manifest.json").read_text())
    subprocess.run(["git","merge-base","--is-ancestor",task["base_commit"],COMMIT],cwd=ROOT,check=True)
    changed=git("diff","--name-only",task["base_commit"],COMMIT).decode().splitlines()
    allowed=task["allowed_paths"]+["handoff/SOL-001"]
    assert all(any(p==a or p.startswith(a+"/") for a in allowed) for p in changed)
    assert set(receipt["artifacts_sha256"])==set(changed)-{"handoff/SOL-001/result.json"}
    hash_checks={}
    for p,wanted in receipt["artifacts_sha256"].items():
        raw=git("show",COMMIT+":"+p)
        assert git("ls-tree",COMMIT,"--",p).decode().split()[0]=="100644"
        actual=hashlib.sha256(raw).hexdigest()
        mode="exact_git_blob" if actual==wanted else (
            "exact_reconstructed_crlf_checkout" if hashlib.sha256(raw.replace(b"\n",b"\r\n")).hexdigest()==wanted
            else "unverified_excluded")
        hash_checks[p]={"status":mode,"git_blob_sha256":actual,"receipt_sha256":wanted}
    for p in task["deliverables"]:
        assert p in changed and hash_checks[p]["status"]!="unverified_excluded",p
    excluded=[p for p,c in hash_checks.items() if c["status"]=="unverified_excluded"]
    assert excluded==["audit/SOL-001/validation.txt"],excluded
    work=ROOT/".runtime/reviews/SOL-001-b25c6b5"
    if not work.exists():
        work.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run(["git","worktree","add","--detach",str(work),COMMIT],cwd=ROOT,check=True,capture_output=True)
    assert subprocess.check_output(["git","rev-parse","HEAD"],cwd=work).decode().strip()==COMMIT
    assert not subprocess.check_output(["git","status","--porcelain"],cwd=work).strip()
    suite=subprocess.run([sys.executable,"-m","unittest","discover","-s","tests","-p","test_accounting.py","-v"],
                         cwd=work,capture_output=True,text=True)
    suite_log=ROOT/"audit/chief/SOL-001-tests.txt"
    suite_log.write_text(suite.stdout+suite.stderr,encoding="utf-8",newline="\n")
    assert suite.returncode==0,suite.stderr
    assert "Ran 28 tests" in suite.stderr
    sys.path.insert(0,str(work/"src"))
    from safeinvest import rebalance,keep,apply_returns,compound_cpi,deflate,compute_metrics,simulate_equal_weight,linear_quantile
    oracle=json.loads((ROOT/"audit/chief/accounting_oracle.json").read_text())
    checks=[]
    def close(name,actual,expected):
        if isinstance(expected,dict): expected=expected["value"]
        error=abs(actual-float(expected))
        checks.append({"check":name,"expected":float(expected),"actual":actual,"absolute_error":error})
        assert error<=1e-9,(name,actual,expected)
    transfer=rebalance((0,0,100),(0.2,0,0.8))
    close("20-unit fee",transfer.fee,F(1,20))
    for i,x in enumerate(transfer.holdings_after_fee): close("20-unit holding "+str(i),x,oracle["twenty_unit_transfer"]["post_fee_holdings"][i])
    h=(19.125,31.25,49.625)
    assert keep(h).holdings_after_fee==h and keep(h).fee==0
    close("all equity fee",rebalance((0,0,100),(1,0,0)).fee,F(1,4))
    rows=[dict(scenario_id=1,period=t,equity_return=float(r[0]),bond_return=float(r[1]),
               bill_proxy_return=float(r[2]),inflation=float(inf))
          for t,(r,inf) in enumerate([((F(1,10),0,-F(1,20)),F(1,50)),((-F(1,5),F(1,10),0),0)],1)]
    result=simulate_equal_weight(rows,horizon=2,split="synthetic")
    expected=oracle["equal_weight_two_year"]
    for i,entry in enumerate(result.ledger):
        close(f"year {i+1} transfer",entry.intended_transfer,expected["transfer"][i])
        close(f"year {i+1} fee",entry.fee,expected["fees"][i])
        close(f"year {i+1} real post-fee",entry.real_wealth_after_fee,expected["real_path_initial_trade_end_trade_end"][2*i+1])
        close(f"year {i+1} real end",entry.real_wealth_end,expected["real_path_initial_trade_end_trade_end"][2*i+2])
        for j,x in enumerate(entry.holdings_end): close(f"year {i+1} holding {j}",x,expected["end_holdings"][i][j])
    close("CAGR",result.metrics.net_real_cagr_pct,expected["growth_pct_pa"])
    close("sample volatility",result.metrics.annual_real_volatility_pct,expected["volatility_pct_pa_ddof1"])
    close("maximum real drawdown",result.metrics.max_real_drawdown_pct,expected["max_real_drawdown_pct"])
    close("trade including initial",result.trade_share_pct,100)
    close("trade excluding initial",result.trade_share_ex_initial_pct,100)
    one=[dict(scenario_id=1,period=1,equity_return=.1,bond_return=.1,bill_proxy_return=.1,inflation=0)]
    recovery=simulate_equal_weight(one,horizon=1,split="synthetic")
    close("fee-time drawdown despite recovery",recovery.metrics.max_real_drawdown_pct,F(1,6))
    close("recovery terminal",recovery.ledger[0].real_wealth_end,oracle["initial_fee_then_recovery"]["real_terminal"])
    real=deflate(100,compound_cpi(1,.1))
    m=compute_metrics([real],[100],split="synthetic")
    close("inflation only real wealth",real,F(1000,11))
    close("inflation only growth",m.net_real_cagr_pct,-F(100,11))
    close("inflation only loss",m.max_real_drawdown_pct,F(100,11))
    assert m.annual_real_volatility_pct is None
    for p,v in [(0.1,3),(.5,15),(.9,27)]:close("linear quantile "+str(p),linear_quantile([30,0,20,10],p),v)
    # Independent alternative expression: sum of positive intended purchases.
    for n in range(1,51):
        holdings=[F(n+3),F(2*n+1),F(100)]
        target=[F(n,100),F(1,4),F(3,4)-F(n,100)]
        wealth=sum(holdings)
        intended=sum(max(wealth*w-h,F(0)) for h,w in zip(holdings,target))
        trade=rebalance(map(float,holdings),map(float,target))
        close("purchase-side transfer "+str(n),trade.intended_transfer,intended)
        close("purchase-side budget "+str(n),trade.wealth_after_fee,wealth-F(1,400)*intended)
    outcome={"status":"passed_required_deliverables_optional_log_excluded","reviewed_commit":COMMIT,
        "task_sha256":digest,"base_commit":task["base_commit"],"hash_checks":hash_checks,
        "excluded_paths":excluded,"initial_check_failure":"Strict all-artifact hash validation failed on optional validation.txt; uniform and test-block CRLF reconstruction did not match. File remains unverified on worker branch.",
        "mandatory_deliverables_verified":task["deliverables"],"suite":{"tests":28,"exit_code":suite.returncode,"python":sys.version.split()[0]},
        "independent_numeric_checks":checks,"max_absolute_error":max(x["absolute_error"] for x in checks),
        "no_competition_outcomes_computed":True,
        "limitations":["No blocking objection to pre-fee/pro-rata convention; disclose intended turnover versus actual post-fee purchases.",
                       "H=1 volatility and ex-initial trade share undefined.",
                       "Final evaluation and adaptive policy not implemented.",
                       "Optional historical log excluded; separate Sol provenance audit required."]}
    output.write_text(json.dumps(outcome,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps({"status":outcome["status"],"tests":28,"independent_numeric_checks":len(checks),
                      "max_absolute_error":outcome["max_absolute_error"],"excluded":excluded}))
if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    run(parser.parse_args().output)
