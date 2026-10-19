"""Chief independent acceptance of SOL-022; generated fixtures only."""
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from fractions import Fraction as Q
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from verify_canonical_receipt import verify, git, sha

ROOT = Path(__file__).resolve().parents[2]
COMMIT = '21ad493707d71240f83d7f01ed6d133e1380e8fb'


def independent(work):
    sys.path.insert(0, str(work / 'src'))
    from safeinvest.policy_calibration import build_synthetic_calibrations
    fields = ['scenario_id','period','equity_return','bond_return','bill_proxy_return','inflation']
    rows = [(s,t,Q(s-4,8),Q(t-1,4),Q(0),Q(s%3-1,8)) for s in range(1,9) for t in range(1,3)]
    def encode(rs, ending='\n'):
        return (ending.join([','.join(fields)] + [','.join(map(str,r[:2]))+','+','.join(str(float(x)) for x in r[2:]) for r in rs])+ending).encode()
    def digest(value):
        return sha(json.dumps(value, sort_keys=True, separators=(',',':'), ensure_ascii=True).encode())
    data = encode(rows)
    bundle = build_synthetic_calibrations(data, scenario_count=8, periods=2)
    assert bundle.input_sha256 == sha(data) and bundle.input_bytes == len(data)
    facts=[]
    for fold in range(4):
        evaluation = tuple(range(fold+1,9,4))
        selected = [r for r in rows if r[0] not in evaluation]
        got = bundle.folds[fold]
        keys = tuple(r[:2] for r in selected)
        gross = tuple(tuple(float((1+x)/(1+r[5])) for x in r[2:5]) for r in selected)
        assert got.evaluation_ids == evaluation
        assert got.training_ids == tuple(s for s in range(1,9) if s not in evaluation)
        assert got.training_keys == keys and len(keys) == 12
        assert got.prior.gross == gross
        source_payload = {'schema':'training-annual-simple-v1','fields':fields,
            'rows':[[*r[:2],*(float(x).hex() for x in r[2:])] for r in selected]}
        derived_payload = {'schema':'training-real-gross-v1','asset_order':fields[2:5],
            'rows':[[*k,*(x.hex() for x in g)] for k,g in zip(keys,gross)]}
        assert got.training_rows_sha256 == digest(source_payload)
        assert got.real_gross_sha256 == digest(derived_payload)
        # Independent high-precision inverse-cube moment with prior:recent mass 15:n.
        weights=(Q(1,4),Q(1,4),Q(1,2)); recent=((0.75,1.,1.25),(1.5,1.,0.5))
        inv=lambda g: sum(w*Q(x) for w,x in zip(weights,g))**-3
        ces=[]
        for n in (0,2):
            moment=(15*sum(inv(g) for g in gross)/12+sum(inv(g) for g in recent[:n]))/(15+n)
            with localcontext() as ctx:
                ctx.prec=90
                m=Decimal(moment.numerator)/Decimal(moment.denominator)
                expected=float((-m.ln()/3).exp())
            observed=got.prior.certainty_equivalent(tuple(map(float,weights)),recent[:n])
            assert math.isclose(expected,observed,rel_tol=3e-13,abs_tol=0)
            ces.append({'recent_count':n,'inverse_cube_moment':str(moment),'expected':expected,'observed':observed})
        changed=[(*r[:2],r[2]+Q(1,4),*r[3:]) if r[0] in evaluation else r for r in rows]
        modified=build_synthetic_calibrations(encode(changed),scenario_count=8,periods=2)
        assert modified.folds[fold]==got and modified.input_sha256!=bundle.input_sha256
        for other in range(4):
            if other!=fold:
                assert modified.folds[other].training_rows_sha256!=bundle.folds[other].training_rows_sha256
                assert modified.folds[other].real_gross_sha256!=bundle.folds[other].real_gross_sha256
        invalid=[(*r[:2],Q(-1),*r[3:]) if r[0] in evaluation else r for r in rows]
        try:
            build_synthetic_calibrations(encode(invalid),scenario_count=8,periods=2)
        except ValueError:
            pass
        else:
            raise AssertionError('invalid held-out observation was not rejected')
        facts.append({'fold':fold,'evaluation_ids':evaluation,'training_keys':keys,'annual_weight':'1/12',
            'first_rational_real_gross':[str((1+x)/(1+selected[0][5])) for x in selected[0][2:5]],
            'training_sha256':digest(source_payload),'gross_sha256':digest(derived_payload),'CE':ces,
            'heldout_perturbation_unchanged':True,'other_fold_hashes_changed':True,'invalid_heldout_rejected':True})
    crlf=build_synthetic_calibrations(encode(rows,'\r\n'),scenario_count=8,periods=2)
    assert crlf.folds==bundle.folds and crlf.input_sha256!=bundle.input_sha256
    before=bundle.manifest(); returned=bundle.manifest();returned['folds'][0]['training_row_keys'][0][0]=999
    assert bundle.manifest()==before
    zero=[(s,t,Q(0),Q(0),Q(0),Q(0)) for s,t,*_ in rows]
    one=[(s,t,Q(1),Q(1),Q(1),Q(1)) for s,t,*_ in rows]
    left=build_synthetic_calibrations(encode(zero),scenario_count=8,periods=2)
    right=build_synthetic_calibrations(encode(one),scenario_count=8,periods=2)
    assert all(a.training_rows_sha256!=b.training_rows_sha256 and a.real_gross_sha256==b.real_gross_sha256 for a,b in zip(left.folds,right.folds))
    return {'fixture':'generated 8 scenarios x 2 years; exact dyadic nominal inputs', 'folds':facts,
        'LF_CRLF_separation':True,'fresh_manifest_mutation_safe':True,'nominal_derived_distinction':True}


def main():
    info=verify('SOL-022',COMMIT)
    work=ROOT/'.runtime/review-SOL-022'
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=work).decode().strip()==COMMIT
    for name,expected in info['source_hashes_checked'].items():
        assert sha(git('show','HEAD:'+name))==expected
    queue=json.loads((ROOT/'ops/queue.json').read_bytes())['tasks']
    kernel=next(q for q in queue if q['id']=='SOL-021')
    accepted=json.loads((ROOT/kernel['acceptance_evidence']).read_bytes())
    assert kernel['state']=='accepted' and kernel['code_verdict']==accepted['code_verdict']=='approve'
    assert accepted['reviewed_commit']==kernel['reviewed_commit']=='d154f90d1c50b37990b75ec0a45aa01a38252343'
    assert accepted['source_hashes_checked']['src/safeinvest/policy_pilot.py']==info['source_hashes_checked']['src/safeinvest/policy_pilot.py']
    out=work/'audit/SOL-022'
    snapshot=lambda:{str(p.relative_to(out)):sha(p.read_bytes()) for p in out.rglob('*') if p.is_file()}
    before=snapshot(); saved=json.loads((out/'verification.json').read_bytes())
    facts=saved['facts']
    assert facts['code_verdict']=='approve' and facts['failures']==[] and facts['check_count']==87166
    scratch=ROOT/'.runtime/review-SOL-022-corrupt';scratch.mkdir(exist_ok=False)
    bad=json.loads(json.dumps(saved));bad['facts']['fixtures'][0]['folds'][0]['ce']['expected']+=0.01
    (scratch/'wrong-number.json').write_text(json.dumps(bad),encoding='utf-8')
    bad=json.loads(json.dumps(saved));bad['facts']['fixtures'][0]['folds'][0]['manifest']['training_rows_sha256']='0'*64
    (scratch/'wrong-source.json').write_text(json.dumps(bad),encoding='utf-8')
    replay=[]
    for path,expected in [(out/'verification.json',0),(scratch/'wrong-number.json',1),(scratch/'wrong-source.json',1)]:
        initial=sha(path.read_bytes())
        result=subprocess.run([sys.executable,'-B',str(out/'verify.py'),'--check','--evidence',str(path)],cwd=work,capture_output=True,text=True,timeout=180)
        replay.append({'case':path.name,'expected_exit':expected,'exit_code':result.returncode,'stdout':result.stdout.strip(),'stderr':result.stderr.strip()})
        assert result.returncode==expected,replay[-1]
        assert sha(path.read_bytes())==initial
    assert snapshot()==before
    chief=independent(work)
    info.update(schema_version=1,checked_at=datetime.now(timezone.utc).isoformat(),decision='accept_calibration_seam_review',code_verdict='approve',
        worker_replay_comparisons=87166,worker_replay_checks=replay,audit_files_unchanged=True,chief_independent_checks=chief,
        dependency_gate_resolution={'finding':'RELEASE-1','resolved':True,'accepted_kernel_commit':kernel['reviewed_commit'],
            'accepted_kernel_evidence':kernel['acceptance_evidence'],'matching_kernel_sha256':info['source_hashes_checked']['src/safeinvest/policy_pilot.py'],
            'note':'Pinned task source predates later acceptance; coordinator verifies current accepted evidence without changing historical worker findings.'},
        competition_outcomes_read=False,final_data_open=False,production_execution_authorized=False,
        limitations=['Production loader must bind fixed development path, exact consumed bytes and shape.',
            'Synthetic calibration labels are not production provenance. Correct excluded-fold binding, fresh scenario state and prefix-only decisions remain writer/driver obligations.',
            'No strategy benefit or final-data authorization follows from synthetic calibration review.'])
    with (ROOT/'audit/chief/SOL-022-review.json').open('x',encoding='utf-8',newline='\n') as f:
        json.dump(info,f,indent=2);f.write('\n')
    print(json.dumps({'reviewed_commit':COMMIT,'code_verdict':'approve','comparisons':87166,'chief_folds':4,'chief_CE_values':8,'corruptions_rejected':2,'RELEASE-1':'resolved'}))

if __name__=='__main__':main()
