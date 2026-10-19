"""Generated-input diagnosis of exact-rational versus binary64 boundary."""
import importlib.util
import json
from fractions import Fraction as F
from pathlib import Path
spec=importlib.util.spec_from_file_location('verification',Path(__file__).resolve().parents[1]/'verify.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
fx=v.load_tests();rows=v.numeric_fixture(fx);t=fx.build(rows)
by={(r['mode'],r['fee_rate'],r['horizon'],r['scenario_id']):r for r in rows}
records=[]
for g in t.comparison_gates:
    aa=[by[g['candidate_mode'],g['fee_rate'],g['horizon'],s]['max_real_drawdown_pct'] for s in range(1,9)]
    bb=[by[g['reference_mode'],g['fee_rate'],g['horizon'],s]['max_real_drawdown_pct'] for s in range(1,9)]
    ideal=v.quantile(aa,F(9,10))-v.quantile(bb,F(9,10))
    if (ideal<=1)!=g['flags']['tail_loss_at_most_1_00']:
        records.append({'candidate':g['candidate_mode'],'reference':g['reference_mode'],'fee_rate':g['fee_rate'],
          'horizon':g['horizon'],'candidate_losses':aa,'reference_losses':bb,
          'rational_difference':str(ideal),'stored_binary64_difference':g['marginal_p90_loss_difference_pp'],
          'binary64_gate_pass':g['flags']['tail_loss_at_most_1_00']})
print(json.dumps({'cause':'audit expected ideal-rational threshold decisions, but contract uses stored finite float statistics with no tolerance',
 'policy_implementation_changed':False,'boundary_observations':records},indent=2))
