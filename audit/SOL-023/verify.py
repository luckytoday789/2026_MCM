"""Repeatable generated-only SOL-023 evidence; --check never writes or repairs.

Creation is exclusive. Source objects are explicit, independent of current HEAD.
Text artifacts allow CRLF -> LF normalization. No competition data is opened.
"""
import argparse
import copy
from dataclasses import asdict
from fractions import Fraction as F
import hashlib
import importlib
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import unittest

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BASE = "79a9a63d939c14d4af242d86ceeaa42c044803c4"
RELEASE = "812fadfee82a10cda89233df75a50d4afc0512a3"
TASK_BLOB_SHA256 = "0d50d741fff358c8f5dfd72f15b03322b8eb5b4d5d640606f035f817faee1f6e"
ACCEPTED = {"SOL-021":"d154f90d1c50b37990b75ec0a45aa01a38252343",
            "SOL-022":"21ad493707d71240f83d7f01ed6d133e1380e8fb"}
ARTIFACTS = ("src/safeinvest/policy_cases.py", "tests/test_policy_cases.py",
             "audit/SOL-023/verify.py", "audit/SOL-023/implementation.md",
             "audit/SOL-023/findings.json", "audit/SOL-023/task-binding.json",
             "audit/SOL-023/schemas.json",
             "audit/SOL-023/history/failed-trial-002-test_policy_cases.py",
             "audit/SOL-023/history/infrastructure-initial.json",
             "audit/SOL-023/history/infrastructure.json",
             "audit/SOL-023/history/trial-001-tests.json",
             "audit/SOL-023/history/trial-002-diagnosis-note.json",
             "audit/SOL-023/history/trial-002-diagnosis.json",
             "audit/SOL-023/history/trial-002-tests.json",
             "audit/SOL-023/history/trial-003-tests.json",
             "audit/SOL-023/history/trial-004-tests.json",
             "audit/SOL-023/history/trial-005-tests.json")


def sha(data):return hashlib.sha256(data).hexdigest()
def lf(data):return data.replace(b"\r\n", b"\n")
def canonical(value):return json.dumps(value, sort_keys=True, separators=(",",":"), allow_nan=False).encode()
def git(*args):return subprocess.check_output(["git",*args],cwd=ROOT)


def bindings():
    task_data=git("show",RELEASE+":ops/tasks/SOL-023.json")
    if sha(task_data)!=TASK_BLOB_SHA256:raise RuntimeError("immutable task object mismatch")
    task=json.loads(task_data)
    if task["base_commit"]!=BASE:raise RuntimeError("wrong immutable base")
    queue=json.loads(git("show",RELEASE+":ops/queue.json"))["tasks"]
    records={r["id"]:r for r in queue}
    upstream={}
    paths=dict(task["parameters"]["source_sha256"])
    paths["src/safeinvest/__init__.py"]=sha(git("show",BASE+":src/safeinvest/__init__.py"))
    for path,expected in paths.items():
        data=git("show",BASE+":"+path)
        if sha(data)!=expected or sha(lf((ROOT/path).read_bytes()))!=expected:
            raise RuntimeError("upstream bytes changed: "+path)
        upstream[path]={"commit":BASE,"blob":git("rev-parse",BASE+":"+path).decode().strip(),"sha256_lf":expected}
    reviews={}
    for task_id,commit in ACCEPTED.items():
        r=records[task_id]
        p="audit/chief/"+task_id+"-review.json"
        data=git("show",RELEASE+":"+p);review=json.loads(data)
        if (r["state"]!="accepted" or r["reviewed_commit"]!=commit
                or r["code_verdict"]!="approve" or review["code_verdict"]!="approve"
                or review["reviewed_commit"]!=commit):
            raise RuntimeError("positive accepted dependency gate missing")
        reviews[task_id]={"commit":RELEASE,"reviewed_commit":commit,"path":p,
                          "blob":git("rev-parse",RELEASE+":"+p).decode().strip(),"sha256":sha(data)}
    if (records["SOL-013"]["corrected_design_verdict"]!="approve"
            or records["SOL-023"]["state"]!="ready"):
        raise RuntimeError("design/release gate missing")
    artifacts={p:sha(lf((ROOT/p).read_bytes())) for p in ARTIFACTS}
    return {"base_commit":BASE,"release_commit":RELEASE,"task_sha256_git_blob":TASK_BLOB_SHA256,
            "upstream":upstream,"accepted_reviews":reviews,"delivered_sha256_lf":artifacts,
            "hash_basis":"explicit Git blob bytes; delivered/checkouts CRLF normalized to LF; no HEAD/branch requirement"}


def same(expected, observed, at="root"):
    """Exact type/keys/strings/integers; relative numeric tolerance with zero floor.

    Zero absolute tolerance ensures tiny nonzero fees cannot pass as zero.
    Rational oracle tests use the independently declared 1e-9 accounting tolerance.
    """
    if type(expected)!=type(observed):raise RuntimeError("type mismatch at "+at)
    if isinstance(expected,dict):
        if expected.keys()!=observed.keys():raise RuntimeError("key mismatch at "+at)
        for k in expected:same(expected[k],observed[k],at+"."+k)
    elif isinstance(expected,list):
        if len(expected)!=len(observed):raise RuntimeError("length mismatch at "+at)
        for i,(a,b) in enumerate(zip(expected,observed)):same(a,b,at+"["+str(i)+"]")
    elif isinstance(expected,float):
        if not math.isfinite(expected) or not math.isfinite(observed) or not math.isclose(expected,observed,rel_tol=2e-12,abs_tol=0):
            raise RuntimeError("numeric mismatch at "+at)
    elif expected!=observed:raise RuntimeError("exact mismatch at "+at)


def facts():
    if sys.version_info[:2]!=(3,12):raise RuntimeError("Python 3.12 required")
    bound=bindings()
    sys.path[:0]=[str(ROOT/"src"),str(ROOT/"tests")]
    tests=importlib.import_module("test_policy_cases")
    for name in ("safeinvest", "safeinvest.accounting", "safeinvest.backtest", "safeinvest.metrics",
                 "safeinvest.baselines", "safeinvest.experiments", "safeinvest.policy_pilot",
                 "safeinvest.policy_calibration", "safeinvest.policy_cases"):
        module=importlib.import_module(name)
        expected=ROOT/"src"/(name.replace(".","/")+("/__init__.py" if name=="safeinvest" else ".py"))
        if Path(module.__file__).resolve()!=expected.resolve():raise RuntimeError("wrong imported source "+name)
    capture=io.StringIO()
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(tests.CaseTests)
    result=unittest.TextTestRunner(stream=capture,verbosity=0).run(suite)
    if not result.wasSuccessful():raise RuntimeError("focused tests failed: "+capture.getvalue())
    checks=[]
    def check(label,want,actual,exact=False):
        ok=(want==actual if exact else math.isfinite(actual) and math.isclose(want,actual,rel_tol=1e-10,abs_tol=1e-9))
        checks.append({"name":label,"expected":want,"observed":actual,"exact":exact})
        if not ok:raise RuntimeError("scalar/rational oracle failed: "+label)
    cases=[]
    for (mode,fee),case in tests.CaseTests.cases.items():
        tables={name:getattr(case,name) for name in case.counts}
        key_hashes={}
        schemas={}
        for name,rows in tables.items():
            schemas[name]=list(rows[0]) if rows else []
            keys=[[r["horizon"]] if name=="summary" else
                  [r["scenario_id"],r.get("period",r.get("horizon"))]+([r["target_name"]] if name=="target_scores" else []) for r in rows]
            key_hashes[name]=sha(canonical(keys))
        cases.append({"mode":mode,"fee_rate":fee,"counts":case.counts,"schemas":schemas,
                      "exact_key_sha256":key_hashes,"scenario_metrics":list(case.scenario_metrics),"summary":list(case.summary)})
        if mode in tests.POLICIES:
            for r in case.scenario_metrics:
                s=r["scenario_id"];h=r["horizon"]
                expected,_=tests.rational_baseline(tests.CaseTests.rows[(s-1)*30:s*30],mode,fee,h)
                for key,value in expected.items():
                    if key.startswith("drawdown_"):continue  # exact float convention tested separately
                    check(mode+"/"+str(fee)+"/"+str(s)+"/"+str(h)+"/"+key,value,r[key],not isinstance(value,float))
    # Independent rational one-review actual-versus-buffer accounting in all
    # cost-aware modes: normative target weights are written explicitly here.
    weights={"conservative_cost":(F(15,100),F(20,100),F(65,100)),
             "balanced_cost":(F(1,3),)*3,"growth_cost":(F(60,100),F(30,100),F(10,100)),
             "balanced_context":(F(1,3),)*3,"balanced_adaptive":(F(1,3),)*3}
    data=tests.generated(6,kind="flat")
    for r in data:r.update(equity_return=.125,bond_return=.0625,bill_proxy_return=.03125,inflation=.015625)
    calibration=tests.calibrate(data,((1.3,1.02,1.),))
    for mode,w in weights.items():
        for fee in tests.FEES:
            out=tests.tables(data,calibration,mode,fee,horizons=(1,6))
            e=out.annual_ledgers[0]
            transfer=100*(1-w[2]);cost=F(fee)*transfer
            check(mode+" initial transfer "+str(fee),float(transfer),e["intended_transfer"])
            check(mode+" one actual fee "+str(fee),float(cost),e["fee"])
            for asset,weight in zip(("equity","bond","bill_proxy"),w):
                check(mode+" rational holding "+str(fee)+asset,float((100-cost)*weight),e["holdings_after_fee_"+asset])
            real=(100-cost)*sum(a*(1+F(v)) for a,v in zip(w,(.125,.0625,.03125)))/(1+F(.015625))
            check(mode+" rational first growth "+str(fee),100*(float(real)/100-1),out.scenario_metrics[0]["net_real_cagr_pct"])
    tiny=tests.generated(8,kind="flat")
    for r in tiny:
        if r["period"]==1:
            for key in tests.FIELDS[2:]:r[key]=-1+1e-13
    tiny_out=tests.tables(tiny,tests.calibrate(tiny,((1.3,1.02,1.),)),horizons=(5,6,8))
    tiny_decision=tiny_out.decisions[5]
    check("tiny executed request is target change",True,tiny_decision["executed_target_change"],True)
    check("tiny request below trade threshold",False,tiny_decision["is_trade"],True)
    if not 0<tiny_decision["actual_fee"]<1e-10:raise RuntimeError("missing tiny positive fee")
    return {"schema_version":1,"task_id":"SOL-023","split":"synthetic","required_python":[3,12],
            "competition_outcomes_read":False,"production_performance_claimed":False,
            "bindings":bound,"focused_tests":{"tests_run":result.testsRun,"failures":0,"errors":0},
            "fixture":{"scenarios":4,"periods":30,"modes":8,"fees":[0.,.0025,.005],"case_count":24,
                       "input_sha256":sha(canonical(tests.CaseTests.rows)),"calibration_refit_during_case_build":False},
            "cases":cases,"scalar_rational_checks":checks,"scalar_rational_check_count":len(checks),
            "tiny_executed_change":tiny_decision,"units":tests.CaseTests.cases["balanced_adaptive",.0025].units,
            "comparison_tolerance":{"saved_relative":2e-12,"saved_absolute":0.,"oracle_relative":1e-10,"oracle_absolute":1e-9},
            "limitations":["Generated evidence is not development performance.",
                           "Pure API cannot authenticate original input/source provenance.",
                           "Primary development baseline runs are refused; exact HY3-003 imports belong to a future writer.",
                           "Chief exact-commit review and acceptance remain required.",
                           "Exact severe locations follow accepted binary64 convention, not rational plateau ties."]}


def check_saved(evidence):
    # This path reads saved facts and computes new facts. No directories/files are
    # created, and no source or evidence is rewritten, including on mismatch.
    before=evidence.read_bytes()
    saved=json.loads(before)
    observed=facts()
    same(saved,observed)
    if evidence.read_bytes()!=before:raise RuntimeError("evidence changed during check")
    return observed


def integrity_self_test(evidence):
    original=evidence.read_bytes();base=json.loads(original)
    records=[]
    for label,mutate in (
        ("wrong-number",lambda d:d["scalar_rational_checks"][0].update(observed=999.)),
        ("wrong-source",lambda d:d["bindings"]["delivered_sha256_lf"].update({"src/safeinvest/policy_cases.py":"0"*64})),
        ("missing-key",lambda d:d["cases"][0].pop("counts")),
        ("tiny-fee-zero",lambda d:d["tiny_executed_change"].update(actual_fee=0.))):
        data=copy.deepcopy(base);mutate(data)
        scratch=HERE/"history"/(label+".json")
        with scratch.open("x",encoding="utf-8",newline="\n") as stream:json.dump(data,stream,indent=2,allow_nan=False)
        before=scratch.read_bytes()
        try:
            check_saved(scratch)
        except RuntimeError as exc:
            records.append({"case":label,"rejected":True,"reason":str(exc),"sha256_before":sha(before),
                            "sha256_after":sha(scratch.read_bytes()),"bytes_preserved":scratch.read_bytes()==before})
        else:raise RuntimeError("corruption was accepted: "+label)
    if evidence.read_bytes()!=original:raise RuntimeError("original evidence overwritten")
    report={"original_sha256":sha(original),"original_bytes_preserved":True,"corruptions":records}
    with (HERE/"integrity-self-tests.json").open("x",encoding="utf-8",newline="\n") as stream:
        json.dump(report,stream,indent=2,allow_nan=False);stream.write("\n")
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--check",action="store_true")
    parser.add_argument("--self-test",action="store_true")
    parser.add_argument("--evidence",type=Path,default=HERE/"verification.json")
    args=parser.parse_args()
    if args.self_test:
        if args.check:parser.error("self-test writes scratch evidence; use separately from --check")
        result=integrity_self_test(args.evidence)
        print(json.dumps({"corruptions_rejected":len(result["corruptions"]),"original_bytes_preserved":True}))
    elif args.check:
        result=check_saved(args.evidence)
        print(json.dumps({"status":"passed","read_only":True,"tests":result["focused_tests"]["tests_run"],
                          "scalar_rational_checks":result["scalar_rational_check_count"],"synthetic_cases":24}))
    else:
        result=facts()
        with args.evidence.open("x",encoding="utf-8",newline="\n") as stream:
            json.dump(result,stream,indent=2,sort_keys=True,allow_nan=False);stream.write("\n")
        print(json.dumps({"status":"created_exclusively","tests":result["focused_tests"]["tests_run"],
                          "scalar_rational_checks":result["scalar_rational_check_count"],"synthetic_cases":24}))


if __name__=="__main__":main()
