"""Chief acceptance of exact SOL-017 negative numerical evidence; synthetic only."""
from datetime import datetime, timezone
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from verify_canonical_receipt import verify

ROOT = Path(__file__).resolve().parents[2]
COMMIT = '90f5c8d3fe9b76861f9e302ce23d2e5cd6f2e839'

def main():
    assert sys.version_info[:2] == (3, 12)
    info = verify('SOL-017', COMMIT)
    work = ROOT / '.runtime/review-SOL-017'
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=work).decode().strip() == COMMIT
    out = work / 'audit/SOL-017'
    snapshot = lambda: {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()}
    before = snapshot()
    evidence = json.loads((out / 'verification.json').read_bytes())
    bad = json.loads(json.dumps(evidence))
    case = next(c for c in bad['facts']['checks'] if c['name'] == 'K2 exact midpoint n=0')
    case['observed'] = case['expected']
    scratch = ROOT / '.runtime/review-SOL-017-midpoint-corrupted.json'
    with scratch.open('x', encoding='utf-8') as f:
        json.dump(bad, f)
    replay = []
    for path, expected in [(out / 'verification.json', 0), (scratch, 1)]:
        result = subprocess.run([sys.executable, '-B', str(out / 'verify.py'), '--check', '--evidence', str(path)], cwd=work, capture_output=True, text=True, timeout=180)
        replay.append(dict(evidence=path.name, expected_exit=expected, exit_code=result.returncode, stdout=result.stdout.strip(), stderr=result.stderr.strip()))
        assert result.returncode == expected, replay[-1]
    assert snapshot() == before
    facts = evidence['facts']
    assert facts['corrected_design_verdict'] == 'approve'
    assert facts['code_verdict'] == 'changes_required'
    assert len(facts['checks']) == 3581
    assert sum(not c['passed'] for c in facts['checks']) == 487
    sys.path.insert(0, str(work / 'src'))
    from safeinvest.policy_pilot import EmpiricalPrior, simulate_synthetic
    tiny = float.fromhex('0x0.0000000000001p-1022')
    weights = (.25, .25, .5)
    support = (tiny, tiny, 4 * tiny)
    exact = sum(F(w) * F(g) for w, g in zip(weights, support))
    assert exact / F(tiny) == F(5, 2)
    confirmations = []
    for n in range(6):
        observed = EmpiricalPrior((support,)).certainty_equivalent(weights, (support,) * n)
        assert float(exact) == 2 * tiny and observed == 3 * tiny
        confirmations.append(dict(n=n, exact_units=str(exact/F(tiny)), rounded_expected_hex=float(exact).hex(), observed_hex=observed.hex()))
    row = dict(scenario_id=9001, period=1, equity_return=.1, bond_return=.02, bill_proxy_return=0., inflation=0.)
    result, reviews = simulate_synthetic([row], mode='balanced_cost', prior=EmpiricalPrior(((1.1, 1.02, 1.),)), horizon=1, fee_rate=.0025)
    entry = result.ledger[0]
    expected = {'fee': F(1,6), 'transfer': F(200,3), 'each_post_fee': F(599,18), 'wealth_end': F(7787,75), 'buffered_score': F(3887,3750)}
    actual = {'fee':entry.fee, 'transfer':entry.intended_transfer, 'each_post_fee':entry.holdings_after_fee[0], 'wealth_end':entry.wealth_end, 'buffered_score':reviews[0].scores[0].conservative_score}
    assert all(abs(actual[k]-float(v)) < 1e-12 for k,v in expected.items())
    info.update(schema_version=1, checked_at=datetime.now(timezone.utc).isoformat(), decision='accept_review_evidence_only', corrected_design_verdict='approve', code_verdict='changes_required', replay_checks=replay, audit_files_unchanged=True, independent_check_count=len(facts['checks']), failed_comparison_count=487, chief_k2_confirmation=confirmations, chief_rational_fixture={'expected':{k:str(v) for k,v in expected.items()}, 'observed':actual}, final_data_open=False, production_policy_accepted=False, note='K1 closed; K2 midpoint rounding independently reproduced. Preserve all negative and audit-tool trial evidence. No competition outcomes read. Generic skill evidence principles applied within the authoritative SafeInvest protocol; no unrelated paper_output workflow introduced.')
    with (ROOT / 'audit/chief/SOL-017-review.json').open('x', encoding='utf-8', newline='\n') as f:
        json.dump(info, f, indent=2); f.write('\n')
    print(json.dumps({'reviewed_commit': COMMIT, 'checks': len(facts['checks']), 'failed_comparisons': 487, 'code': 'changes_required', 'chief_k2_reproduced': True, 'read_only': True, 'corruption_rejected': True}))

if __name__ == '__main__':
    main()
