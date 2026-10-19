"""Chief synthetic analysis reference prepared before SOL-016 delivery.

Fractions and explicit scalar expectations; no policy/analysis imports or data CSVs.
This certifies the reference arithmetic only, not an unreceived implementation.
"""
import argparse
from fractions import Fraction as F
import hashlib
import itertools
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT / 'audit/chief/analysis-reference.json'
PINS = {
    'specs/POLICY_ANALYSIS.md': 'a2220482c861799280815b4e65d73e79e53666816ac9e7e72a38d5f48a6e53b8',
    'specs/development_policy_pilot_v2.json': 'd7b20f38196831befc80dfdcc69c6653d1ae8352d1c87c79e19bcc09d5c84df3',
    'specs/policy_driver_layout_v2.json': 'f431e661c260f7f6e40330661e77724dc3ddcafeafed1a3f0b6c31781a4e8329',
}


def quantile(values, p):
    ordered = sorted(map(F, values))
    rank = (len(ordered) - 1) * F(p)
    lower = rank.numerator // rank.denominator
    fraction = rank - lower
    return ordered[lower] if fraction == 0 else ordered[lower] + fraction * (ordered[lower + 1] - ordered[lower])


def gate(gain, tail_growth, tail_loss, positive_folds):
    return [gain >= .10, tail_growth >= -.10, tail_loss <= 1., positive_folds >= 3]


def calculate():
    for name, expected in PINS.items():
        assert hashlib.sha256((ROOT / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest() == expected, name
    config = json.loads((ROOT / 'specs/development_policy_pilot_v2.json').read_bytes())
    layout = json.loads((ROOT / 'specs/policy_driver_layout_v2.json').read_bytes())
    facts = {}
    # Pairing deliberately differs from sorting. Marginal tail is not paired tail.
    ref = list(map(F, [0, 10, 20, 30]))
    candidate = list(map(F, [11, 21, 31, -1]))
    paired = [x-y for x,y in zip(candidate, ref)]
    med = quantile(paired, F(1, 2))
    tail = quantile(candidate, F(1, 10)) - quantile(ref, F(1, 10))
    paired_tail = quantile(paired, F(1, 10))
    marginal_med = quantile(candidate, F(1, 2)) - quantile(ref, F(1, 2))
    assert (med, tail, paired_tail, marginal_med) == (F(11), F(-2, 5), F(-92, 5), F(1))
    facts['paired_vs_marginal'] = dict(reference=list(map(str, ref)), candidate=list(map(str, candidate)),
        paired=list(map(str, paired)), median_paired=str(med), marginal_p10_difference=str(tail),
        paired_p10_not_used=str(paired_tail), marginal_median_difference_not_used=str(marginal_med))
    gains = [F(0), F(1,10), F(1,10), F(1,10)] * 2
    folds = [quantile(gains[f::4], F(1,2)) for f in range(4)]
    assert folds == [F(0), F(1,10), F(1,10), F(1,10)]
    assert quantile(gains,F(1,2)) == F(1,10) and sum(x>0 for x in folds)==3
    facts['zero_fold_excluded'] = dict(gains=list(map(str,gains)),fold_medians=list(map(str,folds)),positive_fold_count=3,median_paired='1/10')
    boundary = [.1, -.1, 1., 3]
    assert gate(*boundary) == [True]*4
    rows=[]
    for index, direction in itertools.product(range(3), (-1,1)):
        vector=boundary.copy()
        vector[index]=math.nextafter(vector[index], math.inf if direction>0 else -math.inf)
        flags=gate(*vector)
        expected = not ((index<2 and direction<0) or (index==2 and direction>0))
        assert all(flags)==expected
        rows.append(dict(statistic_index=index,direction=direction,values=vector,flags=flags,pass_all=expected))
    assert gate(.1,-.1,1.,2)==[True,True,True,False]
    facts['binary64_boundary_neighbors'] = dict(exact=boundary,exact_pass=True,neighbors=rows,two_folds_pass=False)
    # Exhaust the three direct-control booleans; never change comparator by eligibility.
    choices=[]
    for context, against_context, against_fixed in itertools.product((False,True), repeat=3):
        selected='balanced_adaptive' if against_context and against_fixed else ('balanced_context' if context else 'balanced_cost')
        choices.append(dict(context_vs_fixed=context,adaptive_vs_context=against_context,adaptive_vs_fixed=against_fixed,selected=selected))
    assert [r['selected'] for r in choices] == ['balanced_cost','balanced_cost','balanced_cost','balanced_adaptive','balanced_context','balanced_context','balanced_context','balanced_adaptive']
    facts['all_control_truth_combinations']=choices
    # Exact declared-threshold equality passes; strict exceedance still counts tails.
    losses=[F(10)]*110+[F(20)]*10
    assert quantile(losses,F(9,10))==10 and sum(x>10 for x in losses)==10
    facts['p90_not_a_loss_bound']=dict(scenario_count=120,p90='10',tolerance='10',risk_pass=True,strict_exceedance_count=10,strict_exceedance_fraction='1/12')
    # Isolation of the 0.10 indifference boundary with representable stored floats.
    medians={'conservative':0.,'balanced':.1,'growth':math.nextafter(.1,math.inf)}
    best=max(medians.values()); eligible=[k for k,v in medians.items() if best-v<=.1]
    assert eligible==['balanced','growth']
    medians_equal={'conservative':0.,'balanced':.1,'growth':.1}
    equal=[k for k,v in medians_equal.items() if max(medians_equal.values())-v<=.1]
    assert equal==['conservative','balanced','growth']
    facts['inclusive_indifference']=dict(exact_medians=medians_equal,exact_candidates=equal,exact_choice=equal[0],neighbor_medians=medians,neighbor_candidates=eligible,neighbor_choice=eligible[0])
    eligibility={'A':['conservative'],'B':['conservative','balanced'],'C':['conservative','balanced','growth'],'D':['conservative','balanced'],'E':['conservative']}
    assert config['suitability']['eligible_classes_before_outcome_screens']==eligibility
    profiles={key:dict(horizon=value['horizon'],tolerance=value['loss_tolerance_pct'],liquidity=value['liquidity'],eligible_classes=eligibility[key]) for key,value in config['profiles'].items()}
    assert [v['horizon'] for v in profiles.values()]==[5,15,30,25,6]
    facts['own_horizon_and_eligibility']=profiles
    counts=dict(cases=8*2,summary_gates=10*2*5,paired_rows=10*2*5*120,profile_candidates=5*3*2,recommendations=5*2)
    assert counts==dict(cases=16,summary_gates=100,paired_rows=12000,profile_candidates=30,recommendations=10)
    assert layout['paired_rows_all_contrasts_fees']==counts['paired_rows']
    facts['structural_counts']=counts
    return dict(schema_version=1,scope='Chief independent scalar/rational synthetic reference; no implementation acceptance or strategy results',source_sha256=PINS,
        script_sha256_lf=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),reference_groups=len(facts),facts=facts,
        competition_outcomes_read=False,implementation_executed=False,final_data_open=False)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--evidence',type=Path,default=DEFAULT)
    args=parser.parse_args(); result=calculate()
    if args.check:
        assert json.loads(args.evidence.read_bytes())==result,'Reference evidence mismatch; refusing to repair'
    else:
        with args.evidence.open('x',encoding='utf-8',newline='\n') as f:
            json.dump(result,f,indent=2,allow_nan=False); f.write('\n')
    print(json.dumps(dict(reference_groups=result['reference_groups'],read_only=args.check,implementation_executed=False)))


if __name__=='__main__': main()
