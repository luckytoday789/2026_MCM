"""Chief acceptance of exact SOL-016, using independently prepared scalar fixtures."""
from copy import deepcopy
from datetime import datetime, timezone
from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from verify_canonical_receipt import verify
from analysis_reference import calculate, quantile

ROOT = Path(__file__).resolve().parents[2]
COMMIT = 'ceec2b6d1107a4137ee3d24d689ba7ba614703c2'
WORK = ROOT / '.runtime/review-SOL-016'
MODES = ('bills_keep','equal_weight_annual','equal_weight_buy_hold','conservative_cost','balanced_cost','growth_cost','balanced_context','balanced_adaptive')
FEES = (.0025,.005)
HS = (5,6,15,25,30)
UNITS = dict(monetary_units='nominal units; real wealth in CPI_0 purchasing power',return_units='annual simple decimal',cpi_units='price index; CPI_0=1',growth_units='percentage points per year',volatility_units='percentage points; annual sample ddof=1',loss_units='percent of running real peak',trade_share_units='percent of annual reviews')


def snapshot(folder):
    return {str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file()}


def grid(n=4):
    rows=[]
    for mode in MODES:
        for fee in FEES:
            for h in HS:
                for sid in range(1,n+1):
                    policy=mode not in MODES[:3]
                    rows.append(dict(mode=mode,fee_rate=fee,horizon=h,scenario_id=sid,fold_id=(sid-1)%4,split='synthetic',
                        net_real_cagr_pct=0.,annual_real_volatility_pct=0.,max_real_drawdown_pct=0.,terminal_real_wealth=100.,nominal_fee_sum=0.,
                        trade_count=0,review_count=h,later_trade_count=0,later_review_count=h-1,trade_share_pct=0.,trade_share_ex_initial_pct=0.,
                        drawdown_peak_year=0,drawdown_peak_kind='initial',drawdown_trough_year=0,drawdown_trough_kind='initial',
                        human_review_count=0 if policy else None,human_review_share_pct=0. if policy else None,first_latch_year=None,
                        target_change_count=0 if policy else None,first_deployment_year=None,initial_allocation_deferred=True if policy else None,**UNITS))
    return rows


def set_values(rows, mode, field, values, fee=None):
    for row in rows:
        if row['mode']==mode and (fee is None or row['fee_rate']==fee):
            row[field]=values[row['scenario_id']-1] if isinstance(values,list) else values


def close(actual, expected):
    assert math.isclose(actual,float(expected),rel_tol=1e-12,abs_tol=1e-12),(actual,expected)


def main():
    assert sys.version_info[:2]==(3,12)
    info=verify('SOL-016',COMMIT)
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=WORK).decode().strip()==COMMIT
    for name,digest in info['source_hashes_checked'].items():
        assert hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==digest,name
    refs=calculate()
    assert refs==json.loads((ROOT/'audit/chief/analysis-reference.json').read_bytes())
    out=WORK/'audit/SOL-016';before=snapshot(out)
    scratch=ROOT/'.runtime/review-SOL-016-chief-corrupt';scratch.mkdir(exist_ok=False)
    saved=json.loads((out/'verification.json').read_bytes())
    replay=[]
    for name in ['valid','wrong-number','wrong-hash','threshold-neighbor']:
        file=out/'verification.json'
        altered=deepcopy(saved)
        expected=0
        if name!='valid':
            expected=1
            if name=='wrong-number':
                altered['generated_tables']['paired_differences'][0]['terminal_real_wealth_difference']+=1
            elif name=='wrong-hash':
                altered['binding']['delivered_sha256_lf']['src/safeinvest/policy_analysis.py']='0'*64
            else:
                row=altered['generated_tables']['comparison_gates'][0]
                row['median_paired_growth_gain_pp']=math.nextafter(row['median_paired_growth_gain_pp'],math.inf)
            file=scratch/(name+'.json');file.write_text(json.dumps(altered),encoding='utf-8')
        raw=file.read_bytes()
        run=subprocess.run([sys.executable,'-B',str(out/'verify.py'),'--check','--evidence',str(file)],cwd=WORK,capture_output=True,text=True,timeout=120)
        replay.append(dict(case=name,expected_exit=expected,exit_code=run.returncode,stdout=run.stdout.strip(),stderr=run.stderr.strip()))
        assert run.returncode==expected,replay[-1]
        if expected:
            needle={'wrong-number':'evidence number mismatch','wrong-hash':'evidence exact mismatch','threshold-neighbor':'evidence number mismatch'}[name]
            assert needle in run.stderr,replay[-1]
        assert file.read_bytes()==raw
    assert before==snapshot(out)
    sys.path.insert(0,str(WORK/'src'))
    from safeinvest.policy_analysis import build_analysis_tables
    import safeinvest.policy_analysis as module
    assert Path(module.__file__).resolve()==(WORK/'src/safeinvest/policy_analysis.py').resolve()
    config=json.loads((ROOT/'specs/development_policy_pilot_v2.json').read_bytes())
    def build(rows): return build_analysis_tables(rows,config=config,split='synthetic')
    def gate(t): return next(r for r in t.comparison_gates if (r['candidate_mode'],r['reference_mode'],r['fee_rate'],r['horizon'])==('balanced_context','balanced_cost',.0025,30))
    facts={}
    rows=grid()
    r=refs['facts']['paired_vs_marginal']
    set_values(rows,'balanced_cost','net_real_cagr_pct',list(map(float,r['reference'])))
    set_values(rows,'balanced_context','net_real_cagr_pct',list(map(float,r['candidate'])))
    g=gate(build(rows))
    close(g['median_paired_growth_gain_pp'],F(r['median_paired']))
    close(g['marginal_p10_growth_difference_pp'],F(r['marginal_p10_difference']))
    assert g['positive_fold_count']==3 and not g['passed']
    facts['paired_vs_marginal']={k:g[k] for k in ('median_paired_growth_gain_pp','marginal_p10_growth_difference_pp','positive_fold_count','passed')}
    rows=grid(8);r=refs['facts']['zero_fold_excluded']
    set_values(rows,'balanced_context','net_real_cagr_pct',[float(F(v)) for v in r['gains']])
    g=gate(build(rows));assert [x['positive'] for x in g['folds']]==[False,True,True,True]
    close(g['median_paired_growth_gain_pp'],F(1,10));assert g['positive_fold_count']==3
    facts['zero_fold_excluded']=g['positive_fold_count']
    boundaries=[]
    for field,center,flag in [('net_real_cagr_pct',.1,'gain_at_least_0_10'),('net_real_cagr_pct',-.1,'tail_growth_at_least_minus_0_10'),('max_real_drawdown_pct',1.,'tail_loss_at_most_1_00')]:
        for v in [math.nextafter(center,-math.inf),center,math.nextafter(center,math.inf)]:
            rows=grid();set_values(rows,'balanced_context',field,v);g=gate(build(rows))
            expected=v<=center if field=='max_real_drawdown_pct' else v>=center
            assert g['flags'][flag] is expected,(v,g)
            boundaries.append(dict(field=field,stored_value=v,flag=flag,passed=expected))
    facts['inclusive_binary64_boundaries']=boundaries
    cases=[]
    for context,adaptive,expected in [(.2,.25,'balanced_context'),(-.2,.05,'balanced_cost'),(.05,.25,'balanced_adaptive')]:
        rows=grid();set_values(rows,'balanced_context','net_real_cagr_pct',context);set_values(rows,'balanced_adaptive','net_real_cagr_pct',adaptive)
        selection=build(rows).selection
        assert selection['selected_mode']==expected
        assert selection['adaptive']['required_comparators']==['balanced_context','balanced_cost']
        cases.append(dict(context=context,adaptive=adaptive,selected_mode=expected))
    rows=grid();set_values(rows,'balanced_context','net_real_cagr_pct',.25);set_values(rows,'balanced_adaptive','net_real_cagr_pct',.5)
    set_values(rows,'balanced_adaptive','net_real_cagr_pct',.125,.005)
    selection=build(rows).selection
    assert selection['selected_mode']=='balanced_adaptive' and selection['doubled_fee_support']['supported'] is False
    assert selection['sensitivity_may_reselect'] is False
    facts['fixed_control_selection']=cases;facts['sensitivity_does_not_reselect']=True
    rows=grid(120)
    set_values(rows,'conservative_cost','max_real_drawdown_pct',[10.]*110+[20.]*10)
    original=deepcopy(rows);t=build(rows);assert rows==original
    assert [len(x) for x in (t.paired_differences,t.comparison_gates,t.profile_screen,t.profile_recommendations)]==[12000,100,30,10]
    a=next(p for p in t.profile_screen if p['profile']=='A' and p['candidate_class']=='conservative' and p['fee_rate']==.0025)
    assert a['p90_loss_pct']==10 and a['flags']['risk_pass'] and a['exceedance_count']==10 and a['severe_scenario_id']==111
    close(a['exceedance_fraction'],F(1,12))
    for p in t.profile_screen:
        ref=refs['facts']['own_horizon_and_eligibility'][p['profile']]
        assert p['horizon']==ref['horizon'] and p['loss_tolerance_pct']==ref['tolerance']
        assert p['flags']['willingness_eligible']==(p['candidate_class'] in ref['eligible_classes'])
        assert p['status']=='provisional' and p['personalized_overlay_pending'] is True
    facts['own_horizon_profiles_and_p90_exceedances']=dict(table_counts=[12000,100,30,10],p90=10,exceedance_count=10,denominator=120,severe_scenario_id=111)
    indifference=[]
    for name in ['exact','neighbor']:
        rows=grid();r=refs['facts']['inclusive_indifference']
        for cls,value in r[name+'_medians'].items():set_values(rows,cls+'_cost','net_real_cagr_pct',value)
        t=build(rows)
        selected=next(p for p in t.profile_recommendations if p['profile']=='C' and p['fee_rate']==.0025)
        assert selected['selected_class']==r[name+'_choice'] and selected['indifference_classes']==r[name+'_candidates']
        indifference.append(dict(case=name,selected=selected['selected_class']))
    facts['indifference']=indifference
    rows=grid()
    for mode in MODES[3:6]:set_values(rows,mode,'net_real_cagr_pct',-.25)
    assert all(p['selected_class'] is None and p['action']=='human_review' for p in build(rows).profile_recommendations)
    facts['all_referral']=True
    rejections=[]
    for kind in ['missing','duplicate','bool','nonfinite','wrong-fold','wrong-fee','wrong-horizon','extra-field','final']:
        rows=grid();split='synthetic'
        if kind=='missing':rows.pop()
        elif kind=='duplicate':rows.append(deepcopy(rows[0]))
        elif kind=='bool':rows[0]['net_real_cagr_pct']=True
        elif kind=='nonfinite':rows[0]['max_real_drawdown_pct']=float('nan')
        elif kind=='wrong-fold':rows[0]['fold_id']=1
        elif kind=='wrong-fee':rows[0]['fee_rate']=.01
        elif kind=='wrong-horizon':rows[0]['horizon']=7
        elif kind=='extra-field':rows[0]['surplus']=1
        else:split='final'
        try:build_analysis_tables(rows,config=config,split=split)
        except ValueError as error:rejections.append(dict(case=kind,error=str(error)))
        else:raise AssertionError('accepted malformed input '+kind)
    facts['rejections']=rejections
    info.update(schema_version=1,checked_at=datetime.now(timezone.utc).isoformat(),decision='accept_pure_analysis_implementation',code_verdict='approve',
        chief_independent_checks=facts,prepared_reference_groups=refs['reference_groups'],worker_replay_checks=replay,
        worker_scalar_rational_comparisons=saved['checks']['scalar_rational_comparisons'],worker_tests_replayed=saved['checks']['unittest_tests_run'],audit_files_unchanged=True,
        preserved_history='All worker failed initialization and corruption-fixture trials retained without rewriting.',
        integration_notes=['Canonical metric inputs retain existing metric_row COMMON_UNITS literals; growth levels numerically are percent/year. Writer must explicitly bridge any corrected level label from case tables and label final report levels percent/year, differences pp/year; do not rescale values.','Pure module enforces shape only. Production input authenticity, path-ledger consistency and personalized overlay remain independent writer/run/review gates.','Retain all direct controls and negative gates. No policy performance or final selection is established by synthetic evidence.'],
        competition_outcomes_read=False,final_data_open=False)
    with (ROOT/'audit/chief/SOL-016-review.json').open('x',encoding='utf-8',newline='\n') as file:
        json.dump(info,file,indent=2,allow_nan=False);file.write('\n')
    print(json.dumps(dict(reviewed_commit=COMMIT,code_verdict='approve',worker_checks=info['worker_scalar_rational_comparisons'],worker_tests=info['worker_tests_replayed'],chief_groups=len(facts),corruptions_rejected=3,final_data_open=False)))


if __name__=='__main__':main()