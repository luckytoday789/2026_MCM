"""Independent read-only arithmetic on exact Git-published development case CSVs.

No SafeInvest imports, policy execution, checkout input reads, raw or final inputs.
This is a persistence/accounting audit, not policy or production acceptance.
"""
from collections import defaultdict
from decimal import Decimal as D, localcontext
from fractions import Fraction as F
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ('equity', 'bond', 'bill_proxy')
MODES = ('conservative_cost', 'balanced_cost', 'growth_cost', 'balanced_context',
         'balanced_adaptive', 'bills_keep', 'equal_weight_annual', 'equal_weight_buy_hold')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def rational(text):
    value = float(text)
    assert math.isfinite(value), ('nonfinite', text)
    return F(value)


def decimal(value):
    return D(value.numerator) / D(value.denominator)


def audit_group(task_id, commit, overrides=None):
    assert re.fullmatch('[0-9a-f]{40}', commit)
    assert task_id in ('HY3-004', 'HY3-005', 'HY3-006')
    output_root = 'results/development/' + task_id
    expected_group, expected_fee = ('primary', .0025) if task_id == 'HY3-004' else ('doubled', .005)
    originals = {}
    checks = 0
    max_abs_error = 0.0

    def read(relative):
        if relative == 'generated.csv':
            path = 'data/development/scenarios_001_120.csv'
        else:
            assert relative.startswith(expected_group + '/')
            path = output_root + '/' + relative[len(expected_group) + 1:]
        raw = subprocess.check_output(['git', 'show', commit + ':' + path], cwd=ROOT)
        originals[path] = digest(raw)
        return (overrides or {}).get(relative, raw)

    def table(relative):
        reader = csv.DictReader(io.StringIO(read(relative).decode(), newline=''))
        assert len(reader.fieldnames) == len(set(reader.fieldnames))
        rows = list(reader)
        assert all(None not in row for row in rows)
        return rows

    def equal(actual, expected, label):
        nonlocal checks
        checks += 1
        assert actual == expected, (label, actual, expected)

    def near(actual, expected, label):
        nonlocal checks, max_abs_error
        actual, expected = float(actual), float(expected)
        checks += 1
        max_abs_error = max(max_abs_error, abs(actual - expected))
        assert math.isfinite(actual) and math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-9), (label, actual, expected)

    data = table('generated.csv')
    inputs = {(int(r['scenario_id']), int(r['period'])): r for r in data}
    equal(len(data), len(inputs), 'unique input keys')
    counts = {}
    for group, fee in ((expected_group, expected_fee),):
        manifest = json.loads(read(group + '/run_manifest.json'))
        equal(manifest['split'], 'development', 'development only')
        equal(manifest['group'], group, 'group')
        equal(manifest['fee_rate'], fee, 'fixed fee')
        equal(manifest['input_sha256'], originals['data/development/scenarios_001_120.csv'], 'fixed development input hash')
        n, t = manifest['scenario_count'], manifest['periods']
        hs = manifest['horizons']
        equal((n, t, hs), (120, 30, [5, 6, 15, 25, 30]), 'locked development shape')
        equal(set(inputs), {(s, p) for s in range(1, n+1) for p in range(1, t+1)}, 'input grid')
        for mode in MODES:
            base = group + '/cases/' + mode + '/'
            ledgers, metrics, summaries = (table(base + name + '.csv') for name in ('annual_ledgers', 'scenario_metrics', 'summary'))
            equal([(int(r['scenario_id']), int(r['period'])) for r in ledgers], sorted(inputs), 'ledger grid')
            equal([(int(r['scenario_id']), int(r['horizon'])) for r in metrics], [(s,h) for s in range(1,n+1) for h in hs], 'metric grid')
            equal([int(r['horizon']) for r in summaries], hs, 'summary grid')
            by_scenario = defaultdict(list)
            for row in ledgers:
                by_scenario[int(row['scenario_id'])].append(row)
            recomputed = {}
            for scenario, ledger in by_scenario.items():
                previous = [F(0), F(0), F(100)]
                cpi, previous_real, peak, loss = F(1), F(100), F(100), F(0)
                returns, fees, transfers = [], [], []
                peak_at = selected_peak = selected_trough = (0, 'initial')
                for period, row in enumerate(ledger, 1):
                    equal((row['split'], row['mode'], float(row['fee_rate'])), ('development',mode,fee), 'row identity')
                    source = inputs[scenario, period]
                    before = [rational(row['holdings_before_' + a]) for a in ASSETS]
                    after = [rational(row['holdings_after_fee_' + a]) for a in ASSETS]
                    end = [rational(row['holdings_end_' + a]) for a in ASSETS]
                    equal(before, previous, 'exact saved holdings continuity')
                    assert min(before+after+end) >= 0
                    wealth = sum(before)
                    transfer, charge = rational(row['intended_transfer']), rational(row['fee'])
                    if row['engine_action'] == 'keep':
                        equal(after, before, 'keep preserves dollars')
                        equal((transfer,charge), (F(0),F(0)), 'keep free')
                        equal([row['target_'+a] for a in ASSETS], ['', '', ''], 'keep null targets')
                    else:
                        equal(row['engine_action'], 'rebalance', 'engine action')
                        target = [rational(row['target_'+a]) for a in ASSETS]
                        near(sum(target), 1, 'fully invested target')
                        near(transfer, sum(abs(wealth*w-h) for w,h in zip(target,before))/2, 'rational one-way transfer')
                        equal(float(row['fee']).hex(), (fee*float(row['intended_transfer'])).hex(), 'exact binary64 fee')
                        for actual, weight in zip(after,target):
                            near(actual,(wealth-charge)*weight,'rational post-fee allocation')
                    near(row['wealth_before'],wealth,'wealth before')
                    near(row['wealth_after_fee'],sum(after),'wealth after')
                    near(sum(after)+charge,wealth,'self financing')
                    equal(rational(row['inflation']), rational(source['inflation']), 'saved inflation')
                    near(row['cpi_before'],cpi,'rational CPI before')
                    real_after=sum(after)/cpi
                    near(row['real_wealth_before'],wealth/cpi,'real before')
                    near(row['real_wealth_after_fee'],real_after,'real after fee')
                    for asset, actual, held in zip(ASSETS,end,after):
                        rate=rational(source[asset+'_return'])
                        equal(rational(row['return_'+asset]),rate,'saved return')
                        near(actual,held*(1+rate),'return after fee')
                    cpi*=1+rational(source['inflation'])
                    real=sum(end)/cpi
                    near(row['wealth_end'],sum(end),'nominal end')
                    near(row['cpi_end'],cpi,'compounded exact CPI')
                    near(row['real_wealth_end'],real,'exact deflation')
                    annual=real/previous_real-1
                    near(row['annual_net_real_return'],annual,'annual net return')
                    returns.append(annual);fees.append(charge);transfers.append(transfer)
                    for kind,value in (('post_fee',real_after),('end',real)):
                        if value>peak:peak=value;peak_at=(period,kind)
                        drawdown=1-value/peak
                        if drawdown>loss:loss=drawdown;selected_peak=peak_at;selected_trough=(period,kind)
                    if period in hs:
                        with localcontext() as ctx:
                            ctx.prec=70
                            growth=100*((decimal(real)/100)**(D(1)/period)-1)
                            mean=sum(returns)/period
                            variance=sum((r-mean)**2 for r in returns)/(period-1) if period>1 else None
                            vol=100*decimal(variance).sqrt() if variance is not None else None
                        recomputed[scenario,period]=dict(terminal_real_wealth=real,net_real_cagr_pct=growth,
                            max_real_drawdown_pct=100*loss,annual_real_volatility_pct=vol,nominal_fee_sum=sum(fees),
                            trade_count=sum(x>F(1e-10) for x in transfers),review_count=period,
                            later_trade_count=sum(x>F(1e-10) for x in transfers[1:]),later_review_count=period-1,
                            drawdown_peak_year=selected_peak[0],drawdown_peak_kind=selected_peak[1],
                            drawdown_trough_year=selected_trough[0],drawdown_trough_kind=selected_trough[1])
                    previous=end;previous_real=real
            for row in metrics:
                key=int(row['scenario_id']),int(row['horizon'])
                expected=recomputed[key]
                for name,value in expected.items():
                    if value is None:equal(row[name],'','undefined metric')
                    elif isinstance(value,str):equal(row[name],value,name)
                    elif type(value) is int:equal(int(row[name]),value,name)
                    else:near(row[name],value,name)
                h=key[1]
                near(row['trade_share_pct'],100*F(expected['trade_count'],h),'trade share')
                if h>1:near(row['trade_share_ex_initial_pct'],100*F(expected['later_trade_count'],h-1),'later trade share')
                else:equal(row['trade_share_ex_initial_pct'],'','later share null')
                equal(row['growth_units'],'percent/year','growth label')
            for summary in summaries:
                h=int(summary['horizon']); subset=[r for r in metrics if int(r['horizon'])==h]
                equal(int(summary['scenario_count']),n,'summary scenario count')
                for name,field,q in [('median_growth_pct','net_real_cagr_pct',F(1,2)),('p10_growth_pct','net_real_cagr_pct',F(1,10)),
                    ('median_loss_pct','max_real_drawdown_pct',F(1,2)),('p90_loss_pct','max_real_drawdown_pct',F(9,10)),
                    ('median_volatility_pct','annual_real_volatility_pct',F(1,2)),('median_terminal_real_wealth','terminal_real_wealth',F(1,2)),
                    ('median_nominal_fee_sum','nominal_fee_sum',F(1,2))]:
                    if field=='annual_real_volatility_pct' and h==1:
                        equal(summary[name],'','volatility summary null');continue
                    values=sorted(rational(r[field]) for r in subset)
                    index=(n-1)*q;left=index.numerator//index.denominator;fraction=index-left
                    expected=(1-fraction)*values[left]+fraction*values[min(left+1,n-1)]
                    near(summary[name],expected,'rational quantile '+name)
                severe=min(subset,key=lambda r:(-float(r['max_real_drawdown_pct']),int(r['scenario_id'])))
                equal(int(summary['severe_scenario_id']),int(severe['scenario_id']),'severe tie rule')
                for name in ('trade_count','review_count','later_trade_count','later_review_count'):
                    equal(int(summary['pooled_'+name]),sum(int(r[name]) for r in subset),'pooled '+name)
            counts[group+'/'+mode]=dict(ledgers=len(ledgers),metrics=len(metrics),summaries=len(summaries))
    return dict(schema_version=1,reviewed_result_commit=commit,output_root=output_root,status='passed',
        independent_numeric_checks=checks,case_counts=counts,max_absolute_difference=max_abs_error,
        method='stdlib Fraction binary64-input arithmetic and 70-digit Decimal CAGR/sample deviation; no SafeInvest imports',
        tolerances=dict(ordinary_ledger_relative=1e-10,ordinary_ledger_absolute=1e-9,fee_multiplication='exact binary64'),
        original_git_blob_sha256=originals,competition_input_read=True,input_scope='fixed development Git blob only',production_acceptance=False,
        limitations=['Does not independently rederive the policy choice; existing kernel/case reviews remain required.',
                     'Does not accept writer provenance or source binding; exact task and writer evidence review remains required.'])


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('task_id', choices=('HY3-004','HY3-005','HY3-006'));parser.add_argument('commit')
    parser.add_argument('--output', required=True)
    args=parser.parse_args()
    from datetime import datetime, timezone
    from verify_canonical_receipt import verify
    output = Path(args.output).resolve()
    assert output.is_relative_to(ROOT / 'audit/chief') and not output.exists()
    record = dict(checked_at=datetime.now(timezone.utc).isoformat(), task_id=args.task_id, reviewed_commit=args.commit, status='started', decision='manual_review_required')
    try:
        record['structural'] = verify(args.task_id, args.commit)
        record['arithmetic'] = audit_group(args.task_id, args.commit)
        record['status'] = 'passed'
    except Exception as exc:
        record['status'] = 'failed'
        record['failure'] = dict(type=type(exc).__name__, message=str(exc))
        raise
    finally:
        with output.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(record, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps(dict(status=record['status'], task_id=args.task_id, checks=record['arithmetic']['independent_numeric_checks'], decision='manual_review_required')))


if __name__=='__main__':main()
