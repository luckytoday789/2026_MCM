import argparse
import csv
from dataclasses import fields
import importlib.util
import io
import json
import math
from pathlib import Path
from fractions import Fraction
import sys
sys.path.insert(0, str(Path.cwd()/'src'))
from safeinvest.backtest import Decision, simulate_policy
from safeinvest.baselines import POLICIES
root = Path.cwd()
parser = argparse.ArgumentParser()
parser.add_argument('--check',action='store_true')
args = parser.parse_args()
spec = importlib.util.spec_from_file_location('chief_reference',root/'audit/chief/final_path_reference.py')
ref = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ref)
expected = json.loads((ref.OUT/'expected.json').read_bytes())
rows = list(csv.DictReader(io.StringIO((ref.OUT/'fixture.csv').read_text())))
checks, worst = 0, 0.0

def number(value):
    return float(Fraction(value)) if '/' in str(value) else float(value)

def close(observed, saved):
    global checks, worst
    if saved is None:
        assert observed is None
    else:
        value = number(saved)
        error = abs(observed-value)
        assert math.isclose(observed,value,rel_tol=1e-10,abs_tol=1e-9),(observed,saved,error)
        worst = max(worst,error)
    checks += 1

for path in expected['paths']:
    selected = [r for r in rows if int(r['scenario_id']) == path['scenario_id']]
    if path['mode'] == 'prefix_fixture':
        def callback(ctx):
            if not ctx.history:
                return Decision('rebalance',(.2,0,.8))
            return Decision('rebalance',(.4,.2,.4)) if ctx.history[-1].returns[0] > 0 else Decision('keep')
    else:
        callback = POLICIES[path['mode']]
    result = simulate_policy(selected,horizon=6,split='synthetic',callback=callback,fee_rate=number(path['fee_rate']))
    assert result.split == 'synthetic'
    for actual,saved in zip(result.ledger,path['ledger']):
        assert actual.decision.action == saved['action']
        if saved['target'] is None:
            assert actual.decision.target is None
        else:
            for a,b in zip(actual.decision.target,saved['target']): close(a,b)
        for name,value in saved.items():
            if name in ('action','target','period'): continue
            if isinstance(value,list):
                for a,b in zip(getattr(actual,name),value): close(a,b)
            else: close(getattr(actual,name),value)
    for m in path['metrics']:
        h = m['horizon']
        prefix = simulate_policy(selected,horizon=h,split='synthetic',callback=callback,fee_rate=number(path['fee_rate']))
        for name in ('net_real_cagr_pct','annual_real_volatility_pct','max_real_drawdown_pct'):
            close(getattr(prefix.metrics,name),m[name])
        close(prefix.ledger[-1].real_wealth_end,m['terminal_real_wealth'])
        close(sum(e.fee for e in prefix.ledger),m['nominal_fee_sum'])
        close(prefix.trade_share_pct,m['trade_share_pct'])
        close(prefix.trade_share_ex_initial_pct,m['trade_share_ex_initial_pct'])
# Explicit independent hand facts, separate from generator loops.
p = next(p for p in expected['paths'] if p['scenario_id']==123 and p['mode']=='equal_weight_buy_hold' and p['fee_rate']=='1/400')
assert Fraction(p['ledger'][0]['intended_transfer']) == Fraction(200,3)
assert Fraction(p['ledger'][0]['fee']) == Fraction(1,6)
assert Fraction(p['ledger'][0]['wealth_after_fee']) == Fraction(599,6)
assert p['metrics'][-1]['drawdown_trough'] == [1,'post_fee']
assert p['metrics'][-1]['drawdown_peak'] == [0,'initial']
p = next(p for p in expected['paths'] if p['scenario_id']==121 and p['mode']=='bills_keep' and p['fee_rate']=='1/400')
assert Fraction(p['ledger'][0]['real_wealth_end']) == Fraction(5000,51)
assert Fraction(p['ledger'][0]['fee']) == 0
report = dict(schema_version=1,status='passed',scope='generated_reference_preparation_only',
    python=sys.version,competition_inputs_opened=False,final_execution_authorized=False,
    implementation_tested='Existing accepted simulate_policy with split=synthetic only; no final API exists',
    compared_paths=len(expected['paths']), compared_ledger_rows=192,compared_horizon_metrics=96,
    numerical_assertions=checks, max_absolute_error=worst,rel_tol=1e-10,abs_tol=1e-9,
    hand_facts_checked=7,reference_artifacts={n:ref.sha(d) for n,d in ref.build().items()},
    source_sha256={p:ref.sha((root/p).read_bytes().replace(b'\r\n',b'\n')) for p in
        ('audit/chief/final_path_reference.py','specs/FINAL_PATH_ENGINE_HANDOFF.md',
         'src/safeinvest/backtest.py','src/safeinvest/accounting.py','src/safeinvest/metrics.py','src/safeinvest/baselines.py')},
    limits=['No final-capable code accepted','No source/refit authentication','No final data or actual refit',
            'No policy selection or cost-aware outcome conclusion','Rational severe locations do not certify binary64 ties'])
out = root/'audit/chief/final-path-preparation-validation.json'
if args.check:
    saved=json.loads(out.read_bytes())
    assert saved==report, 'reference preparation evidence changed'
else:
    with out.open('x',encoding='utf-8',newline='\n') as handle: json.dump(report,handle,indent=2);handle.write('\n')
print(json.dumps(report,indent=2))
