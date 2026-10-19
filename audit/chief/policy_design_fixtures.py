"""Synthetic chief design arithmetic only; no production/data imports or policy run."""
import argparse
from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
REPORT=ROOT/'audit/chief/policy-design-fixtures.json'

def calculate():
    config=json.loads((ROOT/'specs/development_policy_pilot_v1.json').read_bytes())
    assert config['gamma']==4 and config['fee_buffer_multiplier']==2
    checks=[]
    def close(name,a,b):
        assert math.isfinite(a) and math.isclose(a,b,abs_tol=1e-12,rel_tol=1e-12),(name,a,b)
        checks.append(dict(name=name,actual=a,expected=b,absolute_residual=abs(a-b)))
    def ce(xs,weights):
        return sum(p*x**(-3) for p,x in zip(weights,xs))**(-1/3)
    # One deterministic real outcome; CE equals its gross return at any gamma.
    target_gross=(F(11,10)+F(51,50)+F(1))/3
    tau=F(2,3); fee_fraction=F(1,400)*tau
    true_gross=(1-fee_fraction)*target_gross
    score=(1-2*fee_fraction)*target_gross
    close('deterministic_CE',ce([float(target_gross)],[1.]),float(F(26,25)))
    close('initial_fee_nominal',float(100*fee_fraction),float(F(1,6)))
    close('true_end_wealth',float(100*true_gross),float(F(7787,75)))
    close('decision_score',float(score),float(F(3887,3750)))
    assert score>1 and true_gross>score
    checks.append(dict(name='positive_trade_gate',passed=True))
    # Equal returns cannot justify an initial transfer merely to match a target.
    gross=F(51,50)
    assert (1-2*fee_fraction)*gross<gross
    checks.append(dict(name='equal_returns_keep',passed=True))
    assert not float(gross)>float(gross)+config['decision_epsilon']
    checks.append(dict(name='zero_fee_equal_score_keep',passed=True))
    # Exact inflation deflation and distribution mixture, no annualization.
    close('exact_deflation',float(F(11,10)/F(51,50)),float(F(55,51)))
    prior=[.90,1.10]; recent=[.80,1.05,1.00,1.20,1.02]
    xs=prior+recent; probs=[15/20/2]*2+[1/20]*5
    close('mixture_mass',sum(probs),1.)
    close('prior_mass_at_five',sum(probs[:2]),.75)
    q=ce(xs,probs); f=.0025*.4
    close('CE_positive_homogeneity',ce([(1-f)*x for x in xs],probs),(1-f)*q)
    close('actual_fee_CE_loss',q-ce([(1-f)*x for x in xs],probs),f*q)
    expected={s:tuple(x for x in range(1,121) if (x-1)%4!=(s-1)%4) for s in range(1,121)}
    assert all(len(ids)==90 and s not in ids for s,ids in expected.items())
    checks.append(dict(name='four_fold_train_excludes_evaluation_fold',passed=True,scenario_count=120,training_count=90))
    for value in config['targets'].values():
        vals=[F(x) if isinstance(x,str) else F(str(x)) for x in value]
        assert sum(vals)==1 and min(vals)>=0
    checks.append(dict(name='all_five_targets_simplex_exact',passed=True))
    return dict(status='passed',scope='Synthetic chief design arithmetic only; no policy implementation acceptance or strategy outcome',
      contract_sha256=hashlib.sha256((ROOT/'specs/DEVELOPMENT_POLICY_PILOT.md').read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
      config_sha256=hashlib.sha256((ROOT/'specs/development_policy_pilot_v1.json').read_bytes()).hexdigest(),
      script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),checks=checks,check_count=len(checks),
      final_data_accessed=False,competition_outcomes_computed=False)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    result=calculate()
    if args.check:
        assert json.loads(REPORT.read_bytes())==result,'Saved fixture evidence mismatch; do not overwrite it'
    else:
        assert not REPORT.exists(),'Preserve prior evidence'
        REPORT.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(status=result['status'],check_count=result['check_count'],read_only=args.check)))
if __name__=='__main__': main()
