"""Chief acceptance of the exact SOL-027 independent component review."""
from datetime import datetime, timezone
from fractions import Fraction as Q
import copy
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from verify_canonical_receipt import verify, git, sha
ROOT=Path(__file__).resolve().parents[2]
COMMIT='3d5e965e45f18cf79023dde69189ce987c17e56b'


def independent(work):
    sys.path.insert(0,str(work/'src'))
    from safeinvest.policy_personalized import build_personalized_case_tables as build, _outcome_screen
    from safeinvest.policy_calibration import build_synthetic_calibrations
    fields=('scenario_id','period','equity_return','bond_return','bill_proxy_return','inflation')
    raw=(',' .join(fields)+'\n'+''.join(f'{s},{t},0,0,0,0\n' for s in range(1,9) for t in range(1,31))).encode()
    priors=build_synthetic_calibrations(raw,scenario_count=8,periods=30)
    profiles={'A':(5,10),'B':(15,25),'C':(30,40),'D':(25,15),'E':(6,35)}
    rows=[dict(zip(fields,(s,t,.0625,.0625,.0625,.25))) for s in range(1,9) for t in range(1,31)]
    facts=[]; checks=0
    for p,(h,tolerance) in profiles.items():
        for k in (.0025,.005):
            result=build(rows,calibrations=priors,profile_id=p,proposed_class='conservative',fee_rate=k,split='synthetic')
            expected=100*Q(17,20)**h
            expected_latch=next((t for t in range(2,h+1) if 100*(1-Q(17,20)**(t-1))>=tolerance),None)
            for r in result.case.annual_ledgers:
                t=r['period']; value=100*Q(17,20)**t
                assert math.isclose(r['real_wealth_end'],float(value),rel_tol=1e-10,abs_tol=1e-9)
                assert r['fee']==r['intended_transfer']==0
                checks+=3
            for r in result.case.scenario_metrics:
                assert math.isclose(r['terminal_real_wealth'],float(expected),abs_tol=1e-9,rel_tol=1e-10)
                assert math.isclose(r['max_real_drawdown_pct'],float(100*(1-Q(17,20)**h)),abs_tol=1e-9,rel_tol=1e-10)
                assert r['first_latch_year']==expected_latch
                checks+=3
            assert result.rescreen['source_verified'] is False
            facts.append({'profile':p,'horizon':h,'fee':k,'expected_terminal_rational':str(expected),'first_latch_year':expected_latch,'row_count':len(result.case.annual_ledgers)})
    screen=_outcome_screen([0.]*120,[10.]*119+[11.],10.)
    assert screen['risk_pass'] and screen['purchasing_power_pass'] and screen['exceedance_count']==1 and screen['exceedance_fraction']==1/120
    assert not _outcome_screen([math.nextafter(0.,-math.inf)],[10.],10.)['purchasing_power_pass']
    assert not _outcome_screen([0.],[math.nextafter(10.,math.inf)],10.)['risk_pass']
    checks+=6
    return {'comparisons':checks,'facts':facts,'p90_not_guarantee':screen,'adjacent_float_checks':'passed','competition_inputs_read':False}


def main():
    info=verify('SOL-027',COMMIT)
    work=ROOT/'.runtime/review-SOL-027'
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=work).decode().strip()==COMMIT
    for name,pin in info['source_hashes_checked'].items():
        assert sha(git('show','HEAD:'+name))==pin,name
    task=json.loads((ROOT/'ops/tasks/SOL-027.json').read_bytes())
    queue=json.loads((ROOT/'ops/queue.json').read_bytes())['tasks']
    for name,commit in task['parameters']['accepted_dependencies'].items():
        q=next(q for q in queue if q['id']==name)
        assert q['state']=='accepted' and q['reviewed_commit']==commit
    audit=work/'audit/SOL-027'
    findings=json.loads((audit/'findings.json').read_bytes())
    assert findings['code_verdict']=='approve' and not findings['blockers'] and not findings['required_fixes']
    assert findings['reviewed_sources']==info['source_hashes_checked']
    snapshot=lambda:{str(p.relative_to(work)):sha(p.read_bytes()) for folder in (audit,work/'src',work/'tests') for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    before=snapshot()
    env={k:v for k,v in os.environ.items() if k.lower()!='pythonpath'}
    env['PYTHONDONTWRITEBYTECODE']='1'
    runs=[]
    for command in task['validation_commands']:
        argv=[sys.executable if a=='{python}' else a for a in command]
        start=time.monotonic()
        r=subprocess.run(argv,cwd=work,env=env,capture_output=True,text=True,timeout=180)
        runs.append({'argv':command,'exit_code':r.returncode,'seconds':time.monotonic()-start,'stdout':r.stdout,'stderr':r.stderr})
        assert r.returncode==0,runs[-1]
    saved=json.loads((audit/'verification.json').read_bytes())
    assert saved['numeric']['checks']==97118 and len(saved['numeric']['cases'])==35 and len(saved['numeric']['invalid_inputs'])==40
    scratch=ROOT/'.runtime'/('review-SOL-027-corrupt-'+uuid.uuid4().hex[:8]);scratch.mkdir()
    bads=[('wrong-number',('numeric','cases',0,'first_metric','terminal_real_wealth'),999.),('wrong-source',('identity','source_pins','src/safeinvest/policy_personalized.py','canonical_sha256'),'0'*64),('wrong-count',('numeric','generated_120x30','counts','annual_ledgers'),601)]
    corruptions=[]
    for label,keys,new in bads:
        bad=copy.deepcopy(saved);node=bad
        for key in keys[:-1]:node=node[key]
        old=node[keys[-1]];node[keys[-1]]=new
        target=scratch/(label+'.json');target.write_text(json.dumps(bad),encoding='utf-8')
        original=sha(target.read_bytes())
        r=subprocess.run([sys.executable,'-B','audit/SOL-027/verify.py','--check','--evidence',str(target)],cwd=work,env=env,capture_output=True,text=True,timeout=180)
        assert r.returncode!=0 and sha(target.read_bytes())==original
        corruptions.append({'case':label,'path':keys,'original':old,'mutated':new,'exit_code':r.returncode,'stderr':r.stderr,'scratch_unchanged':True})
    missing=scratch/'missing.json'
    r=subprocess.run([sys.executable,'-B','audit/SOL-027/verify.py','--check','--evidence',str(missing)],cwd=work,env=env,capture_output=True,text=True,timeout=180)
    assert r.returncode!=0 and not missing.exists()
    corruptions.append({'case':'missing-evidence','exit_code':r.returncode,'remains_absent':True})
    chief=independent(work)
    assert snapshot()==before
    info.update(schema_version=1,checked_at=datetime.now(timezone.utc).isoformat(),decision='accept_pure_personalized_component_review',code_verdict='approve',worker_replay_comparisons=97118,worker_replay_cases=35,worker_replay_invalid_input_cases=40,worker_replay_checks=runs,chief_corruption_rejections=corruptions,chief_independent_checks=chief,source_and_audit_bytes_unchanged=True,PYTHONPATH_absent=True,competition_outcomes_read=False,final_data_open=False,production_execution_authorized=False,limitations=findings['remaining_gates'][1:],provenance_boundary=findings['scope_assessment'])
    with (ROOT/'audit/chief/SOL-027-review.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(info,f,indent=2);f.write('\n')
    print(json.dumps({'commit':COMMIT,'verdict':'approve','replayed_checks':97118,'chief_comparisons':chief['comparisons'],'corruptions_and_missing_rejected':len(corruptions)}))

if __name__=='__main__':main()
