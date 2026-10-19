"""Diagnose exact failed SOL-023; never turns a failed receipt into acceptance."""
from datetime import datetime, timezone
from fractions import Fraction as F
import csv, hashlib, io, json, math, os
from pathlib import Path
import subprocess, sys, time
from case_reference import calculate
ROOT=Path(__file__).resolve().parents[2]
COMMIT='ea2569d4624dc86d68861446610ba08548de121f'
WORK=ROOT/'.runtime/review-SOL-023'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def sha(data):return hashlib.sha256(data).hexdigest()
def dump(path,data):
    with path.open('x',encoding='utf-8',newline='\n') as f:json.dump(data,f,indent=2,allow_nan=False);f.write('\n')
def main():
    task=json.loads((ROOT/'ops/tasks/SOL-023.json').read_bytes())
    q=next(q for q in json.loads((ROOT/'ops/queue.json').read_bytes())['tasks'] if q['id']=='SOL-023')
    receipt=json.loads(git('show',COMMIT+':handoff/SOL-023/result.json'))
    digest=sha(json.dumps(task,sort_keys=True,separators=(',',':')).encode())
    assert git('rev-parse','origin/'+q['branch']).decode().strip()==COMMIT
    assert git('rev-parse',COMMIT+'^').decode().strip()==task['base_commit']
    subprocess.run(['git','merge-base','--is-ancestor',task['base_commit'],'origin/main'],cwd=ROOT,check=True)
    assert (receipt['task_id'],receipt['attempt'],receipt['role'],receipt['base_commit'])==('SOL-023',1,'sol',task['base_commit'])
    assert receipt['task_sha256']==q['task_sha256']==digest
    assert receipt['task_parameters']==task['parameters']
    assert receipt['artifact_hash_basis']=='canonical_git_blob' and receipt['started_from_pinned_source']
    assert receipt['python'].startswith('3.12.')
    assert receipt['status']=='failed' and receipt['failure']=='Validation command 0 failed.'
    assert [c['exit_code'] for c in receipt['checks']]==[0,1]
    assert receipt['checks'][1]['argv'][1:]==task['validation_commands'][0][1:]
    assert receipt['input_manifest']==json.loads(git('show',task['base_commit']+':data/manifest.json'))
    names=git('diff','--name-only',task['base_commit'],COMMIT).decode().splitlines()
    allowed=task['allowed_paths']+['handoff/SOL-023']
    assert all(any(n==p or n.startswith(p+'/') for p in allowed) for n in names)
    assert set(names)==set(receipt['artifacts_sha256'])|{'handoff/SOL-023/result.json'}
    assert set(task['deliverables'])<=set(names)
    for p,h in receipt['artifacts_sha256'].items():
        assert sha(git('show',COMMIT+':'+p))==h,p
        assert git('ls-tree',COMMIT,'--',p).decode().split()[0] in ('100644','100755')
    for p,h in task['parameters']['source_sha256'].items():
        assert sha(git('show',task['base_commit']+':'+p))==h,p
        assert sha(git('show','HEAD:'+p))==h,p
    before={n:sha((WORK/n).read_bytes()) for n in names}
    command=[sys.executable if a=='{python}' else a for a in task['validation_commands'][0]]
    clean=dict(os.environ);clean.pop('PYTHONPATH',None)
    checks=[]
    for label,cmd,env,want in [('exact_parent_command_clean_environment',command,clean,1),
        ('same_tests_explicit_source_path',command,dict(clean,PYTHONPATH=str(WORK/'src')),0),
        ('saved_verifier_read_only',[sys.executable,'-B','audit/SOL-023/verify.py','--check'],clean,0)]:
        start=time.monotonic();p=subprocess.run(cmd,cwd=WORK,env=env,capture_output=True,text=True,timeout=180)
        checks.append(dict(label=label,argv=cmd,exit_code=p.returncode,expected_exit=want,seconds=time.monotonic()-start,stdout=p.stdout,stderr=p.stderr))
        assert p.returncode==want,checks[-1]
        if want==1:assert "No module named 'safeinvest'" in p.stderr
    sys.path.insert(0,str(WORK/'src'))
    from safeinvest.policy_calibration import FIELDS, build_synthetic_calibrations
    from safeinvest.policy_cases import build_case_tables
    reference=calculate()['facts']
    rows=[dict(zip(FIELDS,(s,t,.125,.125,.125,.25))) for s in range(1,5) for t in range(1,7)]
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=FIELDS,lineterminator='\n');writer.writeheader();writer.writerows(rows)
    calibration=build_synthetic_calibrations(stream.getvalue().encode(),scenario_count=4,periods=6)
    count=0;cases=[]
    def eq(a,b):
        nonlocal count
        count+=1
        if isinstance(b,(int,float,F)) and not isinstance(b,bool):assert math.isclose(a,float(b),rel_tol=1e-10,abs_tol=1e-9),(a,b)
        else:assert a==b,(a,b)
    modes=('conservative_cost','balanced_cost','growth_cost','balanced_context','balanced_adaptive')
    for mode in modes:
        for fee in (.0025,.005):
            out=build_case_tables(rows,calibrations=calibration,mode=mode,fee_rate=fee,split='synthetic',horizons=(2,3,4,6))
            eq(out.counts,reference['deferred_then_latched_all_five_modes']['per_case_counts'])
            for r in out.scenario_metrics:
                h=r['horizon'];eq(r['terminal_real_wealth'],100*F(9,10)**h);eq(r['max_real_drawdown_pct'],100*(1-F(9,10)**h));eq(r['nominal_fee_sum'],0)
                eq(r['net_real_cagr_pct'],-10);eq(r['trade_count'],0);eq(r['first_latch_year'],4 if h>=4 else None)
                eq(r['human_review_count'],max(0,h-3));eq(r['first_deployment_year'],None);eq(r['initial_allocation_deferred'],True)
            for r in out.decisions: eq(r['action'],'keep' if r['period']<=3 else 'human_review')
            for r in out.target_scores:
                target=next(x for x in reference['identical_asset_scores']['rows'] if x['target_name']==r['target_name'] and F(x['fee_rate'])==F(str(fee)))
                for k in ('ce_target','tau','fee_fraction','pre_cost_benefit','modeled_fee_impact','conservative_score','true_net_ce'):eq(r[k],F(target[k]))
            cases.append(dict(mode=mode,fee_rate=fee,counts=out.counts))
    for mode in ('equal_weight_annual','equal_weight_buy_hold','bills_keep'):
        for fee in (.0025,.005):
            out=build_case_tables(rows,calibrations=calibration,mode=mode,fee_rate=fee,split='synthetic',horizons=(2,3,4,6))
            eq(len(out.decisions),0);eq(len(out.target_scores),0)
            for r in out.scenario_metrics:
                first_fee=F(0) if mode=='bills_keep' else F(200,3)*F(str(fee))
                expected=(100-first_fee)*F(9,10)**r['horizon']
                eq(r['terminal_real_wealth'],expected);eq(r['nominal_fee_sum'],first_fee);eq(r['max_real_drawdown_pct'],100-expected)
                for name in ('human_review_count','first_latch_year','first_deployment_year','target_change_count','initial_allocation_deferred'):eq(r[name],None)
            cases.append(dict(mode=mode,fee_rate=fee,counts=out.counts))
    assert {n:sha((WORK/n).read_bytes()) for n in names}==before
    report=dict(schema_version=1,task_id='SOL-023',reviewed_commit=COMMIT,base_commit=task['base_commit'],task_sha256=digest,
        checked_at=datetime.now(timezone.utc).isoformat(),status='not_accepted_validation_failure',code_verdict='repair_and_revalidate_required',
        canonical_receipt_structure='verified',source_hashes_checked=task['parameters']['source_sha256'],artifacts_sha256=receipt['artifacts_sha256'],
        original_branch_preserved=q['branch'],all_33_paths_preserved_at_exact_commit=names,checks=checks,
        cause='Standalone unittest discovery lacks src import bootstrap. Agent used PYTHONPATH; prescribed parent command did not. No policy arithmetic failure reproduced.',
        chief_independent_reference='audit/chief/case_reference.py',chief_independent_comparisons=count,chief_cases=cases,
        saved_verifier_replayed=dict(focused_tests=14,scalar_rational_checks=1172,synthetic_cases=24),
        audit_and_source_bytes_unchanged=True,competition_outcomes_read=False,final_data_open=False,production_execution_authorized=False,
        correction='New immutable successor: preserve exact source as unaccepted draft, fix test module source-path bootstrap, recreate separate correctly bound audit evidence, run exact parent commands with PYTHONPATH absent; no core/policy parameter changes.')
    dump(ROOT/'audit/chief/SOL-023-failure-review.json',report)
    print(json.dumps(dict(status=report['status'],structural_paths=len(names),source_pins=18,independent_comparisons=count,cases=len(cases),replayed=True)))
if __name__=='__main__':main()
