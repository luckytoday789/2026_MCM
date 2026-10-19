"""Chief verification of exact SOL-013 negative kernel evidence; synthetic only."""
from datetime import datetime, timezone
from fractions import Fraction as F
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from verify_canonical_receipt import verify

ROOT = Path(__file__).resolve().parents[2]
COMMIT = '1908813ef2627ca6e15591278ec15ccf2f9e9cff'

def main():
    assert sys.version_info[:2] == (3, 12)
    info = verify('SOL-013', COMMIT)
    work = ROOT / '.runtime/review-SOL-013'
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=work).decode().strip() == COMMIT
    out = work / 'audit/SOL-013'
    snapshot = lambda: {str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()}
    before = snapshot()
    evidence = json.loads((out/'verification.json').read_bytes())
    bad = json.loads(json.dumps(evidence))
    check = next(c for c in bad['facts']['checks'] if c['name']=='REAL tiny independent transfer/fee')
    assert check['observed']['fee'] > 0
    check['observed']['fee'] = 0
    scratch = ROOT / '.runtime/review-SOL-013-tiny-fee-corrupted.json'
    with scratch.open('x',encoding='utf-8') as f: json.dump(bad,f)
    replay = []
    for path, expected in [(out/'verification.json',0),(scratch,1)]:
        result = subprocess.run([sys.executable,'-B',str(out/'verify.py'),'--check','--evidence',str(path)],cwd=work,capture_output=True,text=True,timeout=120)
        replay.append(dict(evidence=path.name,expected_exit=expected,exit_code=result.returncode,stdout=result.stdout.strip(),stderr=result.stderr.strip()))
        assert result.returncode == expected, replay[-1]
    assert snapshot() == before
    facts = evidence['facts']
    assert facts['corrected_design_verdict'] == 'approve'
    assert facts['code_verdict'] == 'changes_required'
    assert facts['code_failures'] == ['finite extreme constant 5e-324']
    assert [c['name'] for c in facts['checks'] if not c['passed']] == facts['code_failures']
    # Independently reproduce K1 using only the exact pinned production module.
    sys.path.insert(0,str(work/'src'))
    from safeinvest.policy_pilot import EmpiricalPrior, simulate_synthetic
    tiny = float.fromhex('0x0.0000000000001p-1022')
    weights = (.2,.3,.5)
    exact_gross = sum(F(w)*F(tiny) for w in weights)
    assert float(exact_gross) == tiny and sum(F(w) for w in weights) == 1
    try:
        EmpiricalPrior(((tiny,tiny,tiny),)).certainty_equivalent(weights)
    except ValueError as exc:
        observed = str(exc)
    else: raise AssertionError('K1 was not reproduced')
    assert observed == 'portfolio gross factor must be positive'
    row = dict(scenario_id=9001,period=1,equity_return=.1,bond_return=.02,bill_proxy_return=0.,inflation=0.)
    result,reviews = simulate_synthetic([row],mode='balanced_cost',prior=EmpiricalPrior(((1.1,1.02,1.),)),horizon=1,fee_rate=.0025)
    entry=result.ledger[0]
    expected={'fee':F(1,6),'transfer':F(200,3),'each_post_fee':F(599,18),'wealth_end':F(7787,75),'buffered_score':F(3887,3750)}
    actual={'fee':entry.fee,'transfer':entry.intended_transfer,'each_post_fee':entry.holdings_after_fee[0],'wealth_end':entry.wealth_end,'buffered_score':reviews[0].scores[0].conservative_score}
    assert all(abs(actual[k]-float(v))<1e-12 for k,v in expected.items())
    info.update(schema_version=1,checked_at=datetime.now(timezone.utc).isoformat(),decision='accept_review_evidence_only',corrected_design_verdict='approve',code_verdict='changes_required',replay_checks=replay,audit_files_unchanged=True,independent_check_count=len(facts['checks']),expected_negative_checks=facts['code_failures'],chief_k1_confirmation={'constant_gross_hex':tiny.hex(),'exact_gross_hex':float(exact_gross).hex(),'rounded_products':[w*tiny for w in weights],'observed_error':observed},chief_rational_fixture={'expected':{k:str(v) for k,v in expected.items()},'observed':actual},final_data_open=False,production_policy_accepted=False,note='K1 is a genuine finite positive extreme rejection. Design approved; kernel approval withheld. All negative and failed trial evidence retained. No competition outcomes read.')
    with (ROOT/'audit/chief/SOL-013-review.json').open('x',encoding='utf-8',newline='\n') as f: json.dump(info,f,indent=2);f.write('\n')
    print(json.dumps({'reviewed_commit':COMMIT,'checks':len(facts['checks']),'design':'approve','code':'changes_required','chief_k1_reproduced':True,'read_only':True,'corruption_rejected':True}))

if __name__=='__main__': main()
