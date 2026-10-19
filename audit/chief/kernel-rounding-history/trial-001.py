"""Chief independent rounding-cell certificates for K2; no competition input.

This oracle checks that the root lies in the observed float's nearest-even cell.
It neither searches for the root nor calls the production rounding helper.
"""
import argparse
from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE = '79a9a63d939c14d4af242d86ceeaa42c044803c4'
PATHS = ('src/safeinvest/policy_pilot.py', 'src/safeinvest/accounting.py',
         'src/safeinvest/backtest.py', 'src/safeinvest/metrics.py',
         'src/safeinvest/__init__.py')


def exact_moment(weights, prior, recent):
    # Reproduce the documented public normalization, without importing it.
    total = math.fsum(weights)
    w = tuple(F(x / total) for x in weights)
    scale = sum(w)
    w = tuple(x / scale for x in w)
    def term(row):
        return sum(x * F(y) for x, y in zip(w, row)) ** -3
    return (15 * sum(map(term, prior)) / len(prior) + sum(map(term, recent))) / (15 + len(recent))


def cell_contains_root(value, moment):
    if not math.isfinite(value) or value <= 0:
        return False
    previous, following = math.nextafter(value, 0.), math.nextafter(value, math.inf)
    assert math.isfinite(following)
    lower = ((F(previous) + F(value)) / 2) ** 3 * moment
    upper = ((F(value) + F(following)) / 2) ** 3 * moment
    even = struct.unpack('>Q', struct.pack('>d', value))[0] % 2 == 0
    return (lower < 1 or lower == 1 and even) and (upper > 1 or upper == 1 and even)


def run(work=ROOT):
    assert sys.version_info[:2] == (3, 12)
    hashes = {}
    for name in PATHS:
        raw = subprocess.check_output(['git', 'show', SOURCE + ':' + name], cwd=ROOT)
        local = (work / name).read_bytes().replace(b'\r\n', b'\n')
        assert local == raw, name
        hashes[name] = hashlib.sha256(raw).hexdigest()
    sys.path.insert(0, str(work / 'src'))
    from safeinvest.policy_pilot import EmpiricalPrior, simulate_synthetic
    import safeinvest.policy_pilot as module
    assert Path(module.__file__).resolve() == (work / PATHS[0]).resolve()
    tiny = float.fromhex('0x0.0000000000001p-1022')
    normal = sys.float_info.min
    cases = [
        ('tie_down', (.25,.25,.5), ((tiny,tiny,4*tiny),)),
        ('tie_up', (.25,.25,.5), ((tiny,tiny,6*tiny),)),
        ('heterogeneous', (.25,.25,.5), ((tiny,7*tiny,3*tiny),(11*tiny,2*tiny,5*tiny))),
        ('zero_weight', (0.,.5,.5), ((sys.float_info.max,tiny,5*tiny),)),
        ('tiny_weight', (tiny,.25,.75), ((sys.float_info.max,tiny,3*tiny),)),
        ('normal_edge', (.25,.25,.5), ((normal,normal/2,normal*2),)),
        ('roundoff_weights', (.25,.25,.5+2e-13), ((tiny,5*tiny,3*tiny),)),
    ]
    results = []
    for name, weights, prior in cases:
        for n in range(6):
            recent = tuple(prior[i % len(prior)] for i in range(n))
            observed = EmpiricalPrior(prior).certainty_equivalent(weights, recent)
            moment = exact_moment(weights, prior, recent)
            assert cell_contains_root(observed, moment), (name,n,observed.hex())
            for direction in (0., math.inf):
                assert not cell_contains_root(math.nextafter(observed, direction), moment), (name,n,'adjacent incorrect value accepted')
            if name == 'tie_down':
                assert observed == 2*tiny
            if name == 'tie_up':
                assert observed == 4*tiny
            results.append(dict(case=name, recent_count=n, observed_hex=observed.hex(),
                                exact_rounding_cell_pass=True, both_adjacent_values_rejected=True))
    row = dict(scenario_id=9001, period=1, equity_return=.1, bond_return=.02, bill_proxy_return=0., inflation=0.)
    result, reviews = simulate_synthetic([row], mode='balanced_cost', prior=EmpiricalPrior(((1.1,1.02,1.),)), horizon=1)
    ledger = result.ledger[0]
    expected = dict(transfer=F(200,3), fee=F(1,6), each_post_fee=F(599,18),
                    buffered_score=F(3887,3750), true_net_ce=F(7787,7500), wealth_end=F(7787,75))
    observed = dict(transfer=ledger.intended_transfer, fee=ledger.fee,
                    each_post_fee=ledger.holdings_after_fee[0], buffered_score=reviews[0].scores[0].conservative_score,
                    true_net_ce=reviews[0].scores[0].true_net_ce, wealth_end=ledger.wealth_end)
    assert all(abs(observed[k]-float(v)) < 1e-12 for k,v in expected.items())
    return dict(schema_version=1, source_commit=SOURCE, source_sha256=hashes,
                oracle='Exact rational inverse-cube moment; independent nearest-even rounding-cell containment, no root search or production rounding helper',
                check_count=len(results), incorrect_neighbor_rejections=2*len(results), checks=results,
                ordinary_rational_fixture=dict(expected={k:str(v) for k,v in expected.items()}, observed=observed),
                scope='Chief acceptance preparation; synthetic only. Remote SOL-021 remains an independent gate.',
                competition_outcomes_read=False, final_data_open=False)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--check', action='store_true'); args=parser.parse_args()
    evidence=ROOT/'audit/chief/kernel-rounding-certificates.json'
    facts=run()
    if args.check:
        assert json.loads(evidence.read_bytes()) == facts
    else:
        with evidence.open('x', encoding='utf-8', newline='\n') as out:
            json.dump(facts,out,indent=2); out.write('\n')
    print(json.dumps(dict(check_count=facts['check_count'], incorrect_neighbor_rejections=facts['incorrect_neighbor_rejections'], read_only=args.check)))

if __name__ == '__main__':
    main()
