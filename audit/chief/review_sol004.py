"""Chief independent SOL-004 acceptance, synthetic evidence only. Never rewrites receipts."""
import csv
import io
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import time
from verify_canonical_receipt import ROOT, git, sha, verify

COMMIT = '69ed125b7fde276fe503e1ec5416fbf2e5ec9a7b'
WORK = ROOT / '.runtime/reviews/SOL-004-exact'
OUT = ROOT / 'audit/chief'
ASSETS = ('equity', 'bond', 'bill_proxy')
POLICIES = ('bills_keep', 'equal_weight_annual', 'equal_weight_buy_hold')
HORIZONS = (5, 6, 15, 25, 30)

class Comparisons:
    def __init__(self):
        self.groups = {}
    def close(self, group, actual, expected):
        a, b = float(actual), float(expected)
        residual = abs(a-b)
        g = self.groups.setdefault(group, dict(count=0, max_absolute_residual=0.0, max_scaled_residual=0.0))
        g['count'] += 1
        g['max_absolute_residual'] = max(g['max_absolute_residual'], residual)
        g['max_scaled_residual'] = max(g['max_scaled_residual'], residual/max(abs(a), abs(b), 1e-300))
        assert math.isfinite(a) and math.isclose(a,b,abs_tol=1e-9,rel_tol=1e-10), (group,a,b)


def read_rows(path):
    return list(csv.DictReader(io.StringIO(path.read_text(encoding='utf-8'), newline='')))


def scalar_reference(c):
    """Independent forward scalar holdings from saved synthetic input, no engine imports."""
    audit = WORK / 'audit/SOL-004'
    inputs = read_rows(audit / 'synthetic-input.csv')
    assert len(inputs) == 3600
    bundle = audit / 'synthetic-bundle'
    ledgers = read_rows(bundle / 'annual_ledgers.csv')
    metrics = read_rows(bundle / 'scenario_metrics.csv')
    summaries = read_rows(bundle / 'summary.csv')
    pairs = read_rows(bundle / 'paired_differences.csv')
    assert [len(v) for v in (ledgers,metrics,summaries,pairs)] == [10800,1800,15,1200]
    indexed = {(r['policy'],int(r['scenario_id']),int(r['year'])):r for r in ledgers}
    expected_metrics = {}
    for policy in POLICIES:
        for scenario in range(1,121):
            holdings, cpi, previous_real = [0.,0.,100.],1.,100.
            annual, fees, trades = [], [], []
            peak, loss, peak_at = 100.,0.,(0,'initial')
            reference_peak, reference_loss = 100., 0.
            selected_peak = selected_trough = peak_at
            for year in range(1,31):
                source = inputs[(scenario-1)*30+year-1]
                saved = indexed[policy,scenario,year]
                assert saved['split'] == 'synthetic'
                before = holdings[:]
                wealth = sum(before)
                trading = policy == 'equal_weight_annual' or (policy == 'equal_weight_buy_hold' and year == 1)
                assert saved['action'] == ('rebalance' if trading else 'keep')
                transfer = sum(abs(wealth/3-h) for h in before)/2 if trading else 0.
                fee = transfer/400
                after = [(wealth-fee)/3]*3 if trading else before[:]
                real_before, real_post = wealth/cpi, sum(after)/cpi
                c.close('ledger',saved['cpi_before'],cpi)
                rates = [float(source[a+'_return']) for a in ASSETS]
                inflation = float(source['inflation'])
                holdings = [h*(1+r) for h,r in zip(after,rates)]
                cpi *= 1+inflation
                real_end = sum(holdings)/cpi
                annual.append(real_end/previous_real-1)
                fees.append(fee); trades.append(transfer>1e-10)
                expected = dict(wealth_before=wealth,real_wealth_before=real_before,intended_transfer=transfer,
                    fee=fee,wealth_after_fee=sum(after),real_wealth_after_fee=real_post,
                    inflation=inflation,wealth_end=sum(holdings),cpi_end=cpi,real_wealth_end=real_end,
                    annual_net_real_return=annual[-1])
                for key,value in expected.items(): c.close('ledger',saved[key],value)
                for prefix,values in (('holdings_before',before),('holdings_after_fee',after),('holdings_end',holdings),('return',rates)):
                    for a,value in zip(ASSETS,values): c.close('component_holdings',saved[prefix+'_'+a],value)
                for a in ASSETS:
                    if trading: c.close('target',saved['target_'+a],1/3)
                    else: assert saved['target_'+a] == ''
                for value in (real_post, real_end):
                    reference_peak=max(reference_peak,value)
                    reference_loss=max(reference_loss,1-value/reference_peak)
                # Locations use the contract's exact float comparisons on SAVED observations;
                # economic loss itself is separately checked from independent forward arithmetic.
                for kind,key in (('post_fee','real_wealth_after_fee'),('end','real_wealth_end')):
                    value=float(saved[key])
                    if value>peak: peak,peak_at=value,(year,kind)
                    d=1-value/peak
                    if d>loss: loss,selected_peak,selected_trough=d,peak_at,(year,kind)
                if year in HORIZONS:
                    expected_metrics[policy,scenario,year] = dict(net_real_cagr_pct=100*((real_end/100)**(1/year)-1),
                        annual_real_volatility_pct=100*statistics.stdev(annual), max_real_drawdown_pct=100*reference_loss,
                        terminal_real_wealth=real_end, nominal_fee_sum=sum(fees), trade_count=sum(trades), review_count=year,
                        later_trade_count=sum(trades[1:]),later_review_count=year-1,
                        trade_share_pct=100*sum(trades)/year,trade_share_ex_initial_pct=100*sum(trades[1:])/(year-1),
                        drawdown_peak_year=selected_peak[0],drawdown_peak_kind=selected_peak[1],
                        drawdown_trough_year=selected_trough[0],drawdown_trough_kind=selected_trough[1])
                previous_real=real_end
    saved_metrics = {}
    for row in metrics:
        key=(row['policy'],int(row['scenario_id']),int(row['horizon']))
        saved_metrics[key]=row
        for field,value in expected_metrics[key].items():
            if isinstance(value,str): assert row[field]==value
            else: c.close('scenario_metrics',row[field],value)
    def quantile(rows,field,p):
        ordered=sorted(float(r[field]) for r in rows)
        pos=(len(ordered)-1)*p
        left=math.floor(pos); frac=pos-left
        return ordered[left]+frac*(ordered[min(left+1,len(ordered)-1)]-ordered[left])
    for row in summaries:
        policy,h=row['policy'],int(row['horizon'])
        group=[saved_metrics[policy,s,h] for s in range(1,121)]
        for field,metric,p in [('median_growth_pct','net_real_cagr_pct',.5),('p10_growth_pct','net_real_cagr_pct',.1),
            ('median_loss_pct','max_real_drawdown_pct',.5),('p90_loss_pct','max_real_drawdown_pct',.9),
            ('median_volatility_pct','annual_real_volatility_pct',.5),('median_terminal_real_wealth','terminal_real_wealth',.5),
            ('median_nominal_fee_sum','nominal_fee_sum',.5)]: c.close('summary_quantiles',row[field],quantile(group,metric,p))
        for field in ('trade_count','review_count','later_trade_count','later_review_count'):
            c.close('pooled_counts',row['pooled_'+field],sum(int(r[field]) for r in group))
        c.close('pooled_share',row['pooled_trade_share_pct'],100*sum(int(r['trade_count']) for r in group)/(120*h))
        c.close('pooled_share',row['pooled_trade_share_ex_initial_pct'],100*sum(int(r['later_trade_count']) for r in group)/(120*(h-1)))
        severe=sorted(group,key=lambda r:(-float(r['max_real_drawdown_pct']),int(r['scenario_id'])))[0]
        for field in row:
            if field.startswith('severe_'): assert row[field] == severe[field[7:]], field
    for row in pairs:
        alt,s,h=row['alternative_policy'],int(row['scenario_id']),int(row['horizon'])
        assert row['reference_policy']=='equal_weight_annual' and row['split']=='synthetic'
        for field in ('net_real_cagr_pct','max_real_drawdown_pct','terminal_real_wealth','nominal_fee_sum','trade_share_pct','trade_share_ex_initial_pct'):
            c.close('paired_differences',row[field+'_difference'],float(saved_metrics[alt,s,h][field])-float(saved_metrics['equal_weight_annual',s,h][field]))
    return dict(annual_ledger_rows=len(ledgers),scenario_metric_rows=len(metrics),summary_rows=len(summaries),paired_rows=len(pairs))


def run(command, name, cwd=WORK):
    p=subprocess.run(command,cwd=cwd,capture_output=True,timeout=180)
    log=p.stdout+p.stderr
    (OUT/name).write_bytes(log.replace(b'\r\n',b'\n'))
    assert p.returncode == 0, (command,p.returncode,log[-3000:])
    return dict(argv=[str(x) for x in command],exit_code=p.returncode,log='audit/chief/'+name)


def main():
    assert sys.version_info[:2] == (3,12)
    assert not (OUT/'SOL-004-review.json').exists(), 'Acceptance already recorded; preserve evidence'
    report=verify('SOL-004',COMMIT)
    assert git('rev-parse','HEAD').decode().strip() == git('rev-parse','origin/main').decode().strip()
    before={name:sha((WORK/name).read_bytes()) for name in report['artifacts_sha256']}
    manifest=json.loads((WORK/'audit/SOL-004/synthetic-bundle/run_manifest.json').read_bytes())
    for name,entry in manifest['canonical_git_sources'].items():
        assert sha(git('show',COMMIT+':'+name))==entry['sha256'], ('saved source differs',name)
    report['saved_synthetic_source_matches_delivery']=True
    commands=[]
    commands.append(run([sys.executable,'-B','audit/SOL-004/verify_saved_synthetic.py'],'SOL-004-saved-replay.txt'))
    # Redirect the test suite's new audit output to ignored scratch before executing.
    wrapper="""import pathlib,sys,unittest
suite=unittest.defaultTestLoader.discover('tests')
import test_development_baselines as tests
scratch=pathlib.Path('.runtime/chief-test-replay'); scratch.mkdir(parents=True,exist_ok=True)
tests.AUDIT=scratch
result=unittest.TextTestRunner(verbosity=2).run(suite)
assert result.testsRun==59
sys.exit(0 if result.wasSuccessful() else 1)
"""
    commands.append(run([sys.executable,'-B','-c',wrapper],'SOL-004-tests.txt'))
    c=Comparisons()
    counts=scalar_reference(c)
    after={name:sha((WORK/name).read_bytes()) for name in report['artifacts_sha256']}
    assert before==after, 'saved worker evidence changed during review'
    # Load only exact delivered engine for chief-authored guarded access and fixture checks.
    sys.path.insert(0,str(WORK/'src'))
    from safeinvest import Decision,simulate_policy,rebalance
    from safeinvest.experiments import load_config,load_development,source_snapshot
    from collections.abc import Mapping
    decided=set()
    class Guarded(Mapping):
        def __init__(self,t): self.t=t
        def __len__(self): return 6
        def __iter__(self): return iter(('scenario_id','period','equity_return','bond_return','bill_proxy_return','inflation'))
        def __getitem__(self,key):
            if key=='scenario_id': return 1
            if key=='period': return self.t
            assert self.t in decided, 'outcome precedes decision'
            return .02 if key=='inflation' else .10
    def policy(ctx):
        assert len(ctx.history)==ctx.period-1
        decided.add(ctx.period)
        return Decision('rebalance',(1/3,)*3) if ctx.period==1 else Decision('keep')
    result=simulate_policy([Guarded(i) for i in range(1,31)],horizon=5,split='synthetic',callback=policy)
    assert decided==set(range(1,6))
    c.close('chief_fixture',result.ledger[0].fee,1/6)
    c.close('chief_fixture',result.ledger[-1].real_wealth_end,(599/6)*(55/51)**5)
    assert all(e.fee==0 and e.holdings_before==e.holdings_after_fee for e in result.ledger[1:])
    trade=rebalance((0,0,100),(.2,0,.8))
    c.close('chief_fixture',trade.intended_transfer,20)
    c.close('chief_fixture',trade.fee,1/20)
    c.close('chief_fixture',trade.holdings_after_fee[0],1999/100)
    c.close('chief_fixture',trade.holdings_after_fee[2],1999/25)
    config=load_config(WORK,'specs/development_baselines_v1_1.json')
    snap=source_snapshot(WORK,COMMIT)
    # Production loader only, no strategy run: exact development bytes/schema.
    loaded=load_development(WORK,config)
    assert len(loaded.rows)==3600 and loaded.split=='development'
    report.update(status='accepted',decision='Accept exact driver for fixed development baseline only',
        chief_python=sys.version.split()[0],commands=commands,unit_tests=59,
        independent_method='Forward scalar accounting from synthetic inputs; separate scalar metrics, quantiles, paired differences and exact-float locations; chief guarded current/future access and fee/inflation fixtures',
        numerical_checks=c.groups,numerical_check_count=sum(g['count'] for g in c.groups.values()),output_counts=counts,
        worker_evidence_unchanged=True,production_source_snapshot_matches=True,production_loader_rows=3600,
        actual_competition_performance_computed=False,final_outcomes_computed=False,
        retained_failures=['audit/SOL-004/failure-001.json','audit/SOL-004/failure-002.json','audit/SOL-004/failure-003.json'],
        limitations=['Synthetic implementation acceptance is not investment evidence. HY3 development run and separate remote Sol review remain required.',
          'Growth field labels percentage points per year preserve the fixed schema; manuscript should describe CAGR as percent per year and paired CAGR differences as percentage points per year.'])
    target=OUT/'SOL-004-review.json'
    assert not target.exists(), 'preserve prior review; use a separate replay output'
    target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(status=report['status'],unit_tests=59,numerical_check_count=report['numerical_check_count'],output_counts=counts),indent=2))

if __name__=='__main__':
    try: main()
    except Exception as exc:
        failure=OUT/('SOL-004-chief-failure-'+str(time.time_ns())+'.json')
        failure.write_text(json.dumps(dict(exception=type(exc).__name__,message=str(exc)),indent=2)+'\n',encoding='utf-8')
        raise
