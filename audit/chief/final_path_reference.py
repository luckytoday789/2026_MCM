"""Generated final-shaped accounting references; reads no competition inputs.

Standard library and exact rational arithmetic only. This is a fixed-action
oracle, not a candidate policy, refit, final implementation or final result.
"""
import argparse
import csv
from decimal import Decimal, localcontext
from fractions import Fraction as Q
import hashlib
import io
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'audit/chief/final-path-reference'
FIELDS = ('scenario_id', 'period', 'equity_return', 'bond_return', 'bill_proxy_return', 'inflation')
PATTERNS = (
    (('0','0','0','0.02'),) + (('0','0','0','0'),) * 5,
    (('0.2','0.04','0.01','0.05'), ('-0.15','-0.02','0.01','-0.02'),
     ('0.1','0.03','0.02','0.01'), ('-0.05','0.01','0','0.03'),
     ('0.12','0.02','0.01','0'), ('0','-0.01','0.01','0.02')),
    (('0','0','0','0'),) * 6,
    (('0.1','0.04','0.02','0.03'), ('-0.4','-0.1','0.01','0.02'),
     ('0.3','0.1','0.02','0.01'), ('0.05','-0.02','0.01','-0.01'),
     ('-0.2','0.03','0.01','0.02'), ('0.1','0.02','0','0')),
)
MODES = ('bills_keep', 'equal_weight_annual', 'equal_weight_buy_hold', 'prefix_fixture')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


def fixture_rows(scenarios=4, periods=6):
    return tuple(dict(zip(FIELDS, (str(121+s), str(t+1), *PATTERNS[s % 4][t % 6])))
                 for s in range(scenarios) for t in range(periods))


def csv_bytes(rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def qtext(value):
    return f'{value.numerator}/{value.denominator}'


def decimal(value):
    return Decimal(value.numerator) / Decimal(value.denominator)


def target_for(mode, history):
    if mode == 'bills_keep':
        return None
    if mode == 'equal_weight_annual' or mode == 'equal_weight_buy_hold' and not history:
        return (Q(1, 3),) * 3
    if mode == 'equal_weight_buy_hold':
        return None
    # A diagnostic callback only: initial 20% equity; subsequent decisions see
    # the previous year's equity return, never the current year's outcomes.
    if not history:
        return Q(1, 5), Q(0), Q(4, 5)
    return (Q(2, 5), Q(1, 5), Q(2, 5)) if history[-1][0] > 0 else None


def rational_path(rows, mode, fee):
    holdings, cpi, history, ledger = (Q(0), Q(0), Q(100)), Q(1), [], []
    for t, source in enumerate(rows, 1):
        target = target_for(mode, history)  # First construct the decision.
        wealth = sum(holdings)
        transfer = wealth / 2 * sum(abs(w - h / wealth) for w, h in zip(target, holdings)) if target else Q(0)
        cost = fee * transfer
        after = tuple((wealth - cost) * w for w in target) if target else holdings
        returns = tuple(Q(source[name]) for name in FIELDS[2:5])
        inflation = Q(source['inflation'])
        end = tuple(h * (1 + r) for h, r in zip(after, returns))
        end_cpi = cpi * (1 + inflation)
        ledger.append(dict(period=t, action='rebalance' if target else 'keep', target=target,
            holdings_before=holdings, wealth_before=wealth, cpi_before=cpi,
            real_wealth_before=wealth/cpi, intended_transfer=transfer, fee=cost,
            holdings_after_fee=after, wealth_after_fee=sum(after), real_wealth_after_fee=sum(after)/cpi,
            holdings_end=end, wealth_end=sum(end), cpi_end=end_cpi, real_wealth_end=sum(end)/end_cpi,
            annual_net_real_return=(sum(end)/end_cpi)/(wealth/cpi)-1))
        holdings, cpi = end, end_cpi
        history.append((*returns, inflation))
    return ledger


def metrics(ledger):
    peak, loss, peak_at = Q(100), Q(0), (0, 'initial')
    selected_peak = selected_trough = peak_at
    for row in ledger:
        for kind, wealth in (('post_fee', row['real_wealth_after_fee']), ('end', row['real_wealth_end'])):
            if wealth > peak:
                peak, peak_at = wealth, (row['period'], kind)
            if 1 - wealth / peak > loss:
                loss, selected_peak, selected_trough = 1-wealth/peak, peak_at, (row['period'], kind)
    count = sum(r['intended_transfer'] > Q(1, 10**10) for r in ledger)
    later = sum(r['intended_transfer'] > Q(1, 10**10) for r in ledger[1:])
    h = len(ledger)
    with localcontext() as ctx:
        ctx.prec = 80
        ratio = ledger[-1]['real_wealth_end'] / 100
        growth = ((decimal(ratio).ln()/h).exp()-1)*100
        annual = [r['annual_net_real_return'] for r in ledger]
        mean = sum(annual)/h
        variance = sum((r-mean)**2 for r in annual)/(h-1) if h > 1 else None
        return dict(horizon=h, net_real_cagr_pct=str(+growth),
            annual_real_volatility_pct=str(decimal(variance).sqrt()*100) if variance is not None else None,
            max_real_drawdown_pct=qtext(100*loss), terminal_real_wealth=qtext(ledger[-1]['real_wealth_end']),
            nominal_fee_sum=qtext(sum(r['fee'] for r in ledger)), trade_count=count,
            trade_share_pct=qtext(Q(100*count,h)),
            trade_share_ex_initial_pct=qtext(Q(100*later,h-1)) if h > 1 else None,
            drawdown_peak=list(selected_peak), drawdown_trough=list(selected_trough))


def packed(row):
    return {k: [qtext(v) for v in value] if isinstance(value, tuple)
            else qtext(value) if isinstance(value, Q) else value for k, value in row.items()}


def build():
    rows = fixture_rows()
    paths = []
    for scenario in range(121, 125):
        selected = rows[(scenario-121)*6:(scenario-120)*6]
        for mode in MODES:
            for fee in (Q(1, 400), Q(1, 200)):
                ledger = rational_path(selected, mode, fee)
                paths.append(dict(scenario_id=scenario, mode=mode, fee_rate=qtext(fee),
                    ledger=[packed(r) for r in ledger], metrics=[metrics(ledger[:h]) for h in (1,3,6)]))
    # A direct independent prefix witness, including the period of perturbation.
    original = rows[6:12]
    changed = [dict(r) for r in original]
    changed[3].update(equity_return='0.9', bond_return='-0.6', inflation='0.4')
    a = rational_path(original, 'prefix_fixture', Q(1,400))
    b = rational_path(changed, 'prefix_fixture', Q(1,400))
    assert [r['target'] for r in a[:4]] == [r['target'] for r in b[:4]]
    assert a[3]['real_wealth_end'] != b[3]['real_wealth_end']
    assert a[4]['target'] != b[4]['target']
    full = csv_bytes(fixture_rows(60,30))
    tie = [{'scenario_id':122,'loss':0.25}, {'scenario_id':121,'loss':0.25}]
    near = tie + [{'scenario_id':123,'loss':math.nextafter(0.25,1.0)}]
    assert min(tie,key=lambda r:(-r['loss'],r['scenario_id']))['scenario_id'] == 121
    assert min(near,key=lambda r:(-r['loss'],r['scenario_id']))['scenario_id'] == 123
    expected = dict(schema_version=1, origin='program_generated_fixed_action_references',
        competition_inputs_opened=False, final_execution_authorized=False,
        semantics='Exact rational accounting; decimal80 CAGR/volatility. Not binary64 severe-tie authority.',
        fixture_sha256=sha(csv_bytes(rows)), fixture_rows=len(rows), path_count=len(paths),
        ledger_count=sum(len(p['ledger']) for p in paths), metric_count=sum(len(p['metrics']) for p in paths),
        full_generated_shape=dict(scenarios=60,periods=30,rows=1800,ids=[121,180],csv_sha256=sha(full)),
        prefix_witness=dict(perturbed_period=4,unchanged_decisions_through=4,next_decision_changes=True),
        exact_float_severe_witness=dict(tie_selects=121,one_ulp_larger_selects=123,
            greater_loss_hex=math.nextafter(0.25,1.0).hex(),epsilon_used=False), paths=paths)
    return {'fixture.csv':csv_bytes(rows),'expected.json':encode(expected)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    args = parser.parse_args()
    outputs = build()
    if args.check:
        for name, data in outputs.items():
            assert (OUT/name).read_bytes() == data, name
    else:
        OUT.mkdir(parents=True,exist_ok=True)
        for name, data in outputs.items():
            with (OUT/name).open('xb') as handle:
                handle.write(data)
    print(json.dumps({'status':'passed','mode':'check' if args.check else 'create',
                      'files':{n:sha(d) for n,d in outputs.items()}},sort_keys=True))


if __name__ == '__main__':
    main()
