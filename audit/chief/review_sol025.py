"""Chief review of exact SOL-025 receipt; generated inputs only, no outcomes."""
from datetime import datetime, timezone
from fractions import Fraction as F
import csv, io, json, math, os
from pathlib import Path
import subprocess, sys, time
from verify_canonical_receipt import verify, git, sha

ROOT = Path(__file__).resolve().parents[2]


def main():
    commit = sys.argv[1]
    work = ROOT / '.runtime/review-SOL-025'
    info = verify('SOL-025', commit)
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=work).decode().strip() == commit
    for name, expected in info['source_hashes_checked'].items():
        assert sha(git('show','HEAD:' + name)) == expected, name
    old = json.loads((ROOT/'audit/chief/SOL-023-failure-review.json').read_bytes())
    source = 'src/safeinvest/policy_cases.py'
    current = git('show',commit + ':' + source)
    assert sha(current) == '84d96454e31ecf4a103fbd17e4498dfbd56f453d3911beaeac43583f56f82ca7'
    assert sha(current) == old['artifacts_sha256'][source]
    assert old['chief_independent_comparisons'] == 3310
    predecessor = next(q for q in json.loads((ROOT/'ops/queue.json').read_bytes())['tasks'] if q['id']=='SOL-023')
    assert predecessor['state']=='cancelled' and predecessor['reviewed_commit']==old['reviewed_commit']
    task = json.loads((ROOT/'ops/tasks/SOL-025.json').read_bytes())
    env = {k:v for k,v in os.environ.items() if k.upper()!='PYTHONPATH'}
    snapshot = lambda: {p:sha((work/p).read_bytes()) for p in info['accepted_paths']}
    before = snapshot()
    commands=[]
    for command in task['validation_commands']:
        argv=[sys.executable if a=='{python}' else a for a in command]
        start=time.monotonic()
        result=subprocess.run(argv,cwd=work,env=env,capture_output=True,text=True,timeout=240)
        commands.append(dict(argv=argv,exit_code=result.returncode,seconds=time.monotonic()-start,stdout=result.stdout,stderr=result.stderr))
        assert result.returncode==0, commands[-1]
    assert snapshot()==before
    saved=json.loads((work/'audit/SOL-025/verification.json').read_bytes())
    assert saved['regression']['tests_run']==90 and saved['regression']['focused_tests']==14
    assert saved['regression']['generated_mode_fee_cases']==24
    assert saved['numeric']['independent_comparisons']==13976
    scratch=ROOT/'.runtime/review-SOL-025-corrupt';scratch.mkdir(exist_ok=False)
    corruptions=[]
    for label,path,value in [('wrong-number',('numeric','forced_scalar_facts','fee_sum'),1.0),
                             ('wrong-source',('identity','source_sha256_lf','src/safeinvest/accounting.py'),'0'*64),
                             ('tiny-fee-zero',('numeric','tiny_fee_facts','fee'),0.0)]:
        changed=json.loads(json.dumps(saved));item=changed
        for key in path[:-1]:item=item[key]
        oldvalue=item[path[-1]];item[path[-1]]=value
        target=scratch/(label+'.json');target.write_text(json.dumps(changed,allow_nan=False),encoding='utf-8')
        initial=sha(target.read_bytes())
        argv=[sys.executable,'-B',str(work/'audit/SOL-025/verify.py'),'--check','--evidence',str(target)]
        result=subprocess.run(argv,cwd=work,env=env,capture_output=True,text=True,timeout=240)
        assert result.returncode==1 and path[-1] in result.stderr,result.stderr
        assert sha(target.read_bytes())==initial and snapshot()==before
        corruptions.append(dict(case=label,mutated_path=path,original=oldvalue,changed=value,exit_code=result.returncode,
            scratch_sha256=initial,original_and_scratch_unchanged=True,stderr=result.stderr))
    sys.path.insert(0,str(work/'src'))
    from safeinvest import policy_cases
    from safeinvest.policy_calibration import FIELDS, build_synthetic_calibrations
    assert Path(policy_cases.__file__).resolve()==(work/source).resolve()
    rows=[dict(zip(FIELDS,(s,t,.125,.125,.125,.25))) for s in range(1,5) for t in range(1,7)]
    stream=io.StringIO(newline=''); writer=csv.DictWriter(stream,fieldnames=FIELDS,lineterminator='\n');writer.writeheader();writer.writerows(rows)
    cal=build_synthetic_calibrations(stream.getvalue().encode(),scenario_count=4,periods=6)
    checks=0; cases=[]
    def close(observed, expected):
        nonlocal checks
        checks+=1
        assert math.isclose(observed,float(expected),rel_tol=1e-10,abs_tol=1e-9),(observed,expected)
    modes=('conservative_cost','balanced_cost','growth_cost','balanced_context','balanced_adaptive','bills_keep','equal_weight_annual','equal_weight_buy_hold')
    for mode in modes:
        for fee in (.0025,.005):
            out=policy_cases.build_case_tables(rows,calibrations=cal,mode=mode,fee_rate=fee,split='synthetic',horizons=(2,3,4,6))
            is_policy=mode in modes[:5]
            first_fee=F(0) if is_policy or mode=='bills_keep' else F(200,3)*F(str(fee))
            for row in out.scenario_metrics:
                h=row['horizon']; terminal=(100-first_fee)*F(9,10)**h
                close(row['terminal_real_wealth'],terminal)
                close(row['max_real_drawdown_pct'],100-terminal)
                close(row['nominal_fee_sum'],first_fee)
                if is_policy:
                    assert row['first_latch_year']==(4 if h>=4 else None)
                    assert row['human_review_count']==max(0,h-3)
                    assert row['first_deployment_year'] is None
                    assert row['initial_allocation_deferred'] is True
                else:
                    assert all(row[k] is None for k in ('human_review_count','first_latch_year','first_deployment_year','target_change_count','initial_allocation_deferred'))
            for row in out.annual_ledgers:
                t=row['period']
                close(row['cpi_end'],F(5,4)**t)
                close(row['real_wealth_end'],(100-first_fee)*F(9,10)**t)
                close(row['wealth_before']-row['fee'],row['wealth_after_fee'])
            for row in out.decisions:
                assert row['action']==('keep' if row['period']<=3 else 'human_review')
            if not is_policy: assert not out.decisions and not out.target_scores
            cases.append(dict(mode=mode,fee_rate=fee,counts=out.counts,first_fee=str(first_fee)))
    assert snapshot()==before
    info.update(schema_version=1,checked_at=datetime.now(timezone.utc).isoformat(),decision='accept_portable_case_engine_repair',code_verdict='approve',
        implementation_sha256=sha(current),exact_clean_environment_commands=commands,PYTHONPATH_absent=True,
        worker_replayed_tests=90,worker_replayed_comparisons=13976,chief_corruption_rejections=corruptions,chief_independent_numeric_comparisons=checks,chief_synthetic_cases=cases,audit_and_source_bytes_unchanged=True,
        inherited_independent_evidence=dict(path='audit/chief/SOL-023-failure-review.json',reviewed_commit=old['reviewed_commit'],comparisons=3310,case_source_identity_verified=True,
            scope='Previously executed 3310 independent comparisons apply to identical case implementation bytes. Predecessor task remains failed; new receipt and commands separately validated.'),
        competition_outcomes_read=False,final_data_open=False,production_execution_authorized=False,
        limitations=['Writer source/configuration/input authentication and production outcome review remain separate.','No strategy benefit, customer assignment or final access is accepted.'])
    with (ROOT/'audit/chief/SOL-025-review.json').open('x',encoding='utf-8',newline='\n') as handle:
        json.dump(info,handle,indent=2,allow_nan=False);handle.write('\n')
    print(json.dumps(dict(reviewed_commit=commit,code_verdict='approve',artifact_count=len(info['accepted_paths']),source_pins=len(info['source_hashes_checked']),fresh_numeric_checks=checks,inherited_comparisons=3310)))

if __name__=='__main__':main()
