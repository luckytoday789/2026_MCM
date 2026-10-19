"""Verify SOL-009 exact receipt and replay its preserved synthetic design rejection."""
from datetime import datetime, timezone
from decimal import Decimal as D
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from verify_canonical_receipt import verify

ROOT = Path(__file__).resolve().parents[2]
COMMIT = '3f79e07b87ec92a4a74049da6166093ba4e88e6f'

def main():
    assert sys.version_info[:2] == (3, 12)
    info = verify('SOL-009', COMMIT)
    work = ROOT / '.runtime/reviews/SOL-009-acceptance'
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=work).decode().strip() == COMMIT
    out = work / 'audit/SOL-009'
    snapshot = lambda: {str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()}
    before = snapshot()
    checks = []
    for evidence, expected in [(None,0),('history/intentional-corrupt-verification.json',1),('history/intentional-wrong-arithmetic.json',1),('history/rounding-variant-verification.json',0)]:
        command = [sys.executable,'-B','audit/SOL-009/verify.py','--check']
        if evidence:
            command += ['--evidence', 'audit/SOL-009/' + evidence]
        result = subprocess.run(command,cwd=work,capture_output=True,text=True,timeout=60)
        checks.append({'evidence': evidence or 'verification.json','exit_code':result.returncode,'expected_exit_code':expected,'stdout':result.stdout.strip(),'stderr':result.stderr.strip()})
        assert result.returncode == expected, checks[-1]
    assert snapshot() == before
    evidence = json.loads((out/'verification.json').read_bytes())
    assert evidence['check_count'] == 97 and all(x['passed'] for x in evidence['checks'])
    # Chief independently confirms both blockers without running policy outcomes.
    eps = D('1e-12'); keep = D(1)
    scores = [('active',keep+D('.75')*eps),('defensive',keep+D('1.5')*eps)]
    eligible = [(name,score) for name,score in scores if score > keep+eps]
    peak = max(score for _,score in eligible)
    chosen = next(name for name,score in eligible if peak-score <= eps)
    assert chosen == 'defensive' and not scores[0][1] > keep+eps
    def q(values,p):
        ys=sorted(values); index=F(len(ys)-1)*p; low=index.numerator//index.denominator
        return ys[low] if low == len(ys)-1 else ys[low]+(index-low)*(ys[low+1]-ys[low])
    a=list(map(F,[0,3,10])); b=list(map(F,[1,2,100])); paired=[x-y for x,y in zip(a,b)]
    facts={'eligible_first_target':chosen,'median_paired':str(q(paired,F(1,2))),
           'difference_of_medians':str(q(a,F(1,2))-q(b,F(1,2))),
           'paired_p10':str(q(paired,F(1,10))),
           'marginal_p10_difference':str(q(a,F(1,10))-q(b,F(1,10)))}
    assert facts == {'eligible_first_target':'defensive','median_paired':'-1','difference_of_medians':'1','paired_p10':'-361/5','marginal_p10_difference':'-3/5'}
    info.update(schema_version=1,checked_at=datetime.now(timezone.utc).isoformat(),
                decision='accept_review_evidence_only',design_verdict='changes_required',
                replay_checks=checks,independent_check_count=97,audit_files_unchanged=True,
                chief_blocker_confirmation=facts,required_fixes=['D1','D2'],
                final_data_open=False,production_policy_accepted=False,
                note='Negative design review is valid evidence. Pending SOL-011/SOL-012 cannot be released unchanged; preserve their immutable definitions and publish corrected successors. No competition data read or strategy outcomes computed.')
    path=ROOT/'audit/chief/SOL-009-review.json'
    with path.open('x',encoding='utf-8',newline='\n') as f: json.dump(info,f,indent=2); f.write('\n')
    print(json.dumps({'accepted_evidence':COMMIT,'design_verdict':'changes_required','independent_checks':97,'read_only_replay':True,'chief_confirmed':['D1','D2']}))

if __name__ == '__main__': main()
