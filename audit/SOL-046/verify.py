"""SOL-046 focused supplemental audit. --check is strictly read-only.

No original input access, final policy run, refit run, or result acceptance.
The five fixtures below were derived for this review, rather than copied tests.
"""
import argparse
import csv
import hashlib
import io
import json
import math
from fractions import Fraction as F
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'audit/SOL-046'
PUBLICATION = '3dc37e6aad87a9fca7afa0c2773992f38746bd98'
BASE = '96b9ac2632695264f97ea08f0cce9b1009517cb0'
PRESULT = 'b334b27a2f9fb8df99a6dee611e298bd0dc867d3'
PREFIX = 'results/development/CHIEF-PERSONALIZED-RUN-002/'
COMMANDS = []
HASHES = {}

def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def sha(x):
    return hashlib.sha256(x).hexdigest()

def git(*args):
    assert args[0] in ('show', 'rev-parse', 'merge-base', 'status', 'diff')
    if args[0] == 'show':
        path = args[-1].split(':', 1)[-1].replace('\\', '/')
        assert not path.startswith(('data/raw/', 'data/development/', 'data/final_holdout/', 'problem/', 'results/final/'))
    r = subprocess.run(['git', *args], cwd=ROOT, capture_output=True)
    COMMANDS.append({'argv': ['git', *args], 'exit_code': r.returncode})
    assert r.returncode == 0, r.stderr.decode(errors='replace')
    return r.stdout

def blob(commit, path):
    raw = git('show', commit + ':' + path)
    HASHES[commit + ':' + path] = sha(raw)
    return raw

def js(commit, path):
    return json.loads(blob(commit, path))

def ancestor(a, b):
    git('merge-base', '--is-ancestor', a, b)

def close(a, b):
    assert math.isclose(float(a), float(b), abs_tol=1e-9, rel_tol=1e-10), (a, b)

def expect_error(fn):
    try:
        fn()
    except (ValueError, AssertionError):
        return True
    raise AssertionError('expected rejection')

def row(s, t, returns=(0, 0, 0), inflation=0):
    return dict(zip(('scenario_id','period','equity_return','bond_return','bill_proxy_return','inflation'),
                    (s,t,*returns,inflation)))

def fixtures():
    sys.path.insert(0, str(ROOT / 'src'))
    from safeinvest.accounting import rebalance
    from safeinvest.backtest import Decision, simulate_policy
    from safeinvest.metrics import compute_metrics
    from safeinvest.experiments import drawdown_locations, summary_row
    from safeinvest.policy_pilot import CostAwarePolicy, EmpiricalPrior, simulate_synthetic
    from safeinvest.final_refit import build_generated_refit
    from safeinvest.policy_personalized import build_personalized_case_tables, _outcome_screen
    result = {}
    # 1. Fractions fixed directly by moving 100/5, 200/3, or 100 out of bills.
    initial = []
    for target, transfer, fee, after in [
        ((F(1,5),0,F(4,5)),F(20),F(1,20),(F(1999,100),0,F(1999,25))),
        ((F(1,3),)*3,F(200,3),F(1,6),(F(599,18),)*3),
        ((1,0,0),F(100),F(1,4),(F(399,4),0,0))]:
        actual = rebalance((0,0,100), target, .0025)
        close(actual.intended_transfer,transfer);close(actual.fee,fee)
        for a,b in zip(actual.holdings_after_fee,after):close(a,b)
        initial.append({'target':[str(x) for x in target], 'transfer':str(transfer),
                        'fee':str(fee),'holdings_after_fee':[str(x) for x in after]})
    result['initial_transfer'] = initial
    # 2. First fee=50/400; equity then rises 20%, bills unchanged. Rebalance
    # next year sells exactly half of the equity-minus-bill dollar difference.
    p1=F(799,16); e1=p1*F(6,5); b1=p1
    w1=e1+b1; transfer2=(e1-b1)/2; fee2=transfer2/400
    p2=(w1-fee2)/2; w2=p2*(F(9,10)+F(51,50))
    cpi1=F(11,10); cpi2=F(209,200)
    expected=[{'transfer':F(50),'fee':F(1,8),'post':2*p1,'end':w1,'cpi':cpi1,
               'real_post':2*p1,'real_end':w1/cpi1},
              {'transfer':transfer2,'fee':fee2,'post':2*p2,'end':w2,'cpi':cpi2,
               'real_post':2*p2/cpi1,'real_end':w2/cpi2}]
    rows=[row(1,1,(.2,0,0),.1),row(1,2,(-.1,0,.02),-.05)]
    sim=simulate_policy(rows,horizon=2,split='synthetic',callback=lambda c:Decision('rebalance',(.5,0,.5)))
    for entry,x in zip(sim.ledger,expected):
        for name,key in [('intended_transfer','transfer'),('fee','fee'),('wealth_after_fee','post'),
                         ('wealth_end','end'),('cpi_end','cpi'),('real_wealth_after_fee','real_post'),('real_wealth_end','real_end')]:
            close(getattr(entry,name),x[key])
    result['exact_cpi_fee_timing']=[{k:str(v) for k,v in x.items()} for x in expected]
    # 3. A fee trough recovers at each year end. Ignoring post-fee wealth
    # gives zero loss, whereas the rational path loses exactly 1/10.
    ledger=[SimpleNamespace(period=t,real_wealth_after_fee=90.,real_wealth_end=100.) for t in (1,2)]
    loc=drawdown_locations(ledger)
    assert loc==dict(drawdown_peak_year=0,drawdown_peak_kind='initial',drawdown_trough_year=1,drawdown_trough_kind='post_fee')
    m=compute_metrics([100,100],[90,90],split='synthetic');close(m.max_real_drawdown_pct,10)
    def metric(s,loss):
        return dict(scenario_id=s,split='synthetic',net_real_cagr_pct=0.,max_real_drawdown_pct=loss,
                    terminal_real_wealth=100.,annual_real_volatility_pct=0.,nominal_fee_sum=0.,
                    trade_count=0,review_count=2,later_trade_count=0,later_review_count=1,
                    trade_share_pct=0.,trade_share_ex_initial_pct=0.,**loc)
    tie=summary_row('toy',2,[metric(8,10.),metric(3,10.)])
    near=summary_row('toy',2,[metric(3,10.),metric(9,math.nextafter(10.,math.inf))])
    assert tie['severe_scenario_id']==3 and near['severe_scenario_id']==9
    result['real_drawdown_severe_tie']={'loss_pct':10,'locations':loc,'exact_tie_id':3,'one_ulp_greater_id':9}
    # 4. Four explicit training rows, disjoint from synthetic evaluation.
    # Real gross vectors are independent rational divisions, equally weighted.
    raw=b'scenario_id,period,equity_return,bond_return,bill_proxy_return,inflation\n1,1,0.2,0.1,0,0.1\n1,2,0,0.2,0.1,0\n2,1,0.1,0,0.2,-0.1\n2,2,0.3,0.1,0,0.05\n'
    refit=build_generated_refit(raw,scenario_count=2,periods=2)
    rational=((F(12,11),F(1),F(10,11)),(F(1),F(6,5),F(11,10)),
              (F(11,9),F(10,9),F(4,3)),(F(26,21),F(22,21),F(20,21)))
    assert refit.training_keys==((1,1),(1,2),(2,1),(2,2))
    for a,b in zip(refit.prior.gross,rational):
        for x,y in zip(a,b):close(x,y)
    prior=EmpiricalPrior(((1.2,1.1,1.),)); before=prior.gross
    rows=[row(7,t,(.01,.02,.003),.005) for t in (1,2,3)]
    events=[]
    class Trace(dict):
        def __getitem__(self,key):
            if key not in ('scenario_id','period'):events.append(['outcome',dict.__getitem__(self,'period'),key])
            return super().__getitem__(key)
    policy=CostAwarePolicy('balanced_context',prior)
    def decide(c):
        events.append(['decision',c.period,len(c.history)])
        assert len(c.history)==c.period-1 and all(o.scenario_id==7 for o in c.history)
        return policy(c)
    a=simulate_policy([Trace(x) for x in rows],horizon=3,split='synthetic',callback=decide)
    for t in (1,2,3):
        assert events.index(['decision',t,t-1])<next(i for i,e in enumerate(events) if e[0]=='outcome' and e[1]==t)
    changed=[dict(x) for x in rows];changed[1]['equity_return']=-.9;changed[2]['inflation']=.9
    b,br=simulate_synthetic(changed,mode='balanced_context',prior=prior,horizon=3)
    assert policy.reviews[:2]==list(br[:2])
    assert policy.prior is prior and prior.gross is before
    close(policy.reviews[1].prior_mass,F(15,16))
    other,_=simulate_synthetic([row(8,t,(-.2,0,0)) for t in (1,2,3)],mode='balanced_context',prior=prior,horizon=3)
    again,_=simulate_synthetic(rows,mode='balanced_context',prior=prior,horizon=3)
    assert again==a and prior.gross is before
    boundary=[expect_error(lambda:simulate_policy([row(121,1)],horizon=1,split='development',callback=lambda c:Decision('keep'))),
              expect_error(lambda:simulate_policy([row(1,1)],horizon=1,split='final',callback=lambda c:Decision('keep')))]
    meta=refit.manifest();assert meta['source_verified'] is False and meta['production_execution_authorized'] is False
    result['prior_separation_t_minus_one']={'training_gross_rationals':[[str(v) for v in r] for r in rational],
        'training_keys':[list(k) for k in refit.training_keys],'events':events,'year2_prior_mass':'15/16',
        'same_first_two_decisions_after_year2_and_future_perturbation':True,'fresh_path_isolation':True,
        'development_and_final_boundary_rejected':boundary,'generated_origin_verified':False}
    # 5. Uniform 30% loss in year 1 breaches B25 but not C40. The decision
    # in year 1 precedes it; only year 2 can suspend. Exact H15/H30 prefixes.
    rows=[row(9,t,(-.3,-.3,-.3) if t==1 else (0,0,0)) for t in range(1,31)]
    thresholds=[]
    for profile,h,threshold in [('B',15,25),('C',30,40)]:
        path,reviews=simulate_synthetic(rows,mode='conservative_cost',prior=prior,horizon=h,review_drawdown_pct=threshold)
        assert len(path.ledger)==h and reviews[0].action!='human_review'
        assert (reviews[1].action=='human_review')==(profile=='B')
        if profile=='B':assert all(r.action=='human_review' and e.fee==0 for r,e in zip(reviews[1:],path.ledger[1:]))
        thresholds.append({'profile':profile,'horizon':h,'threshold_pct':threshold,'year2_action':reviews[1].action})
    # 11 outcomes: p90 is sorted index 9, so one strict exceedance may pass.
    boundary_screen=_outcome_screen([0.]*11,[25.]*10+[26.],25)
    assert boundary_screen['risk_pass'] and boundary_screen['purchasing_power_pass'] and boundary_screen['exceedance_count']==1
    fail=_outcome_screen([-.01]*11,[25.]*10+[26.],25)
    assert not fail['purchasing_power_pass']
    referrals=[]
    for profile in ('A','D','E'):
        for fee in (.0025,.005):
            case=build_personalized_case_tables(None,calibrations=None,profile_id=profile,proposed_class=None,
                fee_rate=fee,split='synthetic',upstream_reasons=['no_qualifying_class'])
            assert case.case is None and case.rescreen['recommended_class'] is None and case.rescreen['scenario_count']==0
            referrals.append([profile,fee,case.rescreen['horizon'],case.rescreen['review_threshold_pct']])
    result['own_horizons_thresholds_referral']={'threshold_paths':thresholds,'boundary_screen':boundary_screen,
        'negative_p10_rejected':True,'six_zero_simulation_referrals':referrals}
    return result

def reference(ref, base):
    assert set(ref)=={'commit','path','sha256'}
    ancestor(ref['commit'],base)
    raw=blob(ref['commit'],ref['path']);assert sha(raw)==ref['sha256']
    return json.loads(raw)

def references(live=False):
    published=js(PUBLICATION,'ops/tasks/SOL-046.json');task=published
    if live:
        runtime=json.loads((ROOT/'.runtime/task.json').read_bytes());assert canonical(runtime)==canonical(published)
    assert task['allowed_paths']==['audit/SOL-046'] and task['owner']=='sol' and task['base_commit']==BASE
    ancestor(BASE,git('rev-parse','HEAD').decode().strip())
    if live:assert git('rev-parse','--abbrev-ref','HEAD').decode().strip()=='work/sol/SOL-046-a1'
    queue=js(PUBLICATION,'ops/queue.json')['tasks'];q={r['id']:r for r in queue}
    for dep in task['depends_on']:assert q[dep]['state']=='accepted'
    assert q['SOL-046']['task_sha256']==sha(canonical(task))
    availability=js(PUBLICATION,'audit/chief/SOL-045-review.json')
    assert availability['status']=='accepted' and availability['reviewed_commit']==q['SOL-045']['reviewed_commit']
    assert availability['probe']['usable'] is True and availability['probe']['exit_code']==0
    for path,digest in task['parameters']['source_sha256'].items():
        data=blob(BASE,path);assert sha(data)==digest, path
        assert (ROOT/path).read_bytes() in (data,data.replace(b'\n',b'\r\n')), 'checkout differs: '+path
    freeze=js(task['parameters']['freeze_commit'],'ops/freeze.json')
    config=js(BASE,'specs/execution/HY3-010.json')
    effective={k:v for k,v in config.items() if k not in ('freeze','freeze_attestation')}
    assert sha(canonical(effective))==freeze['effective_configuration_sha256']
    assert config['source_commit']==freeze['source_commit']==task['parameters']['source_commit']
    for path,digest in freeze['source_sha256'].items():assert sha(blob(config['source_commit'],path))==digest
    assert freeze['source_sha256']==config['source_sha256']
    assert freeze['profile_choices']==config['profile_choices'] and freeze['primary_mode']==config['primary_mode']=='balanced_cost'
    for name in ('source_review','development_review','refit'):assert freeze[name]==config[name]
    source=reference(config['source_review'],BASE)
    assert source['status']=='accepted' and source['source_sha256']==config['source_sha256']
    development=reference(config['development_review'],BASE)
    assert development['status']=='accepted' and development['all_ten_rescreens_accepted'] is True
    assert development['profile_choices']==config['profile_choices']
    for ref in development['evidence']:reference(ref,BASE)
    refit=reference(config['refit'],BASE);r=refit['refit']
    assert refit['status']=='completed_refit' and refit['configuration']['source_commit']==config['source_commit']
    assert refit['configuration']['source_sha256']==config['source_sha256']
    assert refit['configuration']['profile_choices']==config['profile_choices']
    assert r['training_row_keys']==[[s,t] for s in range(1,121) for t in range(1,31)]
    assert r['training_row_count']==len(r['gross'])==3600 and r['training_scenario_ids']==list(range(1,121))
    assert all(len(v)==3 and all(isinstance(x,float) and math.isfinite(x) and x>0 for x in v) for v in r['gross'])
    fields=['equity_return','bond_return','bill_proxy_return']
    support={'schema':'all-development-prior-support-v1','asset_order':fields,'rows':[[x.hex() for x in v] for v in r['gross']]}
    assert sha(canonical(support))==r['prior_support_sha256']
    gross={'schema':'training-real-gross-v1','asset_order':fields,'rows':[[*key,*(x.hex() for x in v)] for key,v in zip(r['training_row_keys'],r['gross'])]}
    assert sha(canonical(gross))==r['real_gross_sha256'] and r['annual_weight']=='1 / 3600'
    manifest=js(config['source_commit'],'data/manifest.json');inputs={e['path']:e['sha256'] for e in manifest['files']}
    assert inputs==freeze['input_files_sha256'] and r['input_sha256']==inputs['data/development/scenarios_001_120.csv']
    acceptance=reference(freeze['refit_acceptance'],BASE)
    assert acceptance['status']=='accepted' and acceptance['refit']==config['refit']
    attestation=reference(config['freeze_attestation'],BASE)
    fr=blob(config['freeze']['commit'],config['freeze']['path'])
    assert sha(fr)==attestation['freeze_blob_sha256'] and sha(fr.decode().strip().encode())==attestation['freeze_runner_sha256']
    assert attestation['refit']==config['refit'] and attestation['refit_acceptance']==freeze['refit_acceptance']
    assert attestation['final_data_open_at_review'] is False and 'no remote Sol' in attestation['reviewer']
    assert 'no remote Sol' in freeze['review_scope']
    failures=[]
    for path in attestation['previous_failures']:
        failure=js(BASE,path);assert failure['exit_code']==1
        failures.append({'path':path,'exit_code':failure['exit_code'],'last_error':failure['stderr'].strip().splitlines()[-1]})
    success=js(BASE,attestation['audit_execution']);assert success['exit_code']==0
    gate=js(BASE,'audit/chief/FINAL-GATE-20261020.json')
    final_task=js(BASE,'ops/tasks/HY3-010.json')
    assert gate['freeze']==config['freeze'] and gate['freeze_attestation']==config['freeze_attestation']
    assert gate['refit']==config['refit'] and gate['refit_acceptance']==freeze['refit_acceptance']
    assert gate['configuration_sha256']==sha(canonical(config))==final_task['parameters']['config_sha256']
    assert final_task['freeze_sha256']==attestation['freeze_runner_sha256']
    assert final_task['commands']==freeze['planned_execution']['commands']
    assert final_task['split']=='final' and final_task['owner']=='hy3'
    assert final_task['parameters']['output_path']==freeze['planned_execution']['output']
    assert freeze['policy_parameters']==js(config['source_commit'],'specs/development_policy_pilot_v2.json')
    assert freeze['evaluation_contract']==js(config['source_commit'],'specs/final_evaluation_contract_v1.json')
    original_refit=js(q['CHIEF-REFIT-001']['reviewed_commit'],config['refit']['path'])
    assert original_refit==refit
    diagnosis=js(BASE,'audit/chief/final-freeze-audit/source-line-ending-diagnosis.json')
    assert diagnosis['final_data_accessed'] is False and diagnosis['freeze_changed'] is False
    assert all(change['semantic_change'] is False for change in diagnosis['changes'])
    historical=js(BASE,'audit/chief/final-freeze-history/7e2ecf3-pre-gate-unaccepted.json')
    for name in ('source_commit','source_sha256','primary_mode','profile_choices','policy_parameters','evaluation_contract','counts'):
        assert historical[name]==freeze[name],name
    assert historical['refit']['sha256']==freeze['refit']['sha256']
    assert freeze['status']=='frozen_before_final_access' and freeze['no_final_tuning'] is True
    assert attestation['accepted_at']<json.loads((ROOT/'ops/control.json').read_bytes())['final_gate_opened_at']
    for path in ('src/safeinvest/policy_personalized.py','src/safeinvest/personalized_writer.py','src/safeinvest/policy_analysis.py',
                 'audit/chief/check_frozen_execution.py','audit/chief/check_personalized_result.py','audit/chief/check_actual_refit.py'):
        data=blob(BASE,path);assert (ROOT/path).read_bytes() in (data,data.replace(b'\n',b'\r\n'))
    return {'task_digest':sha(canonical(task)),'publication_commit':PUBLICATION,'source_commit':config['source_commit'],
            'freeze_commit':config['freeze']['commit'],'freeze_blob_sha256':sha(fr),
            'freeze_runner_sha256':sha(fr.decode().strip().encode()),'effective_configuration_sha256':sha(canonical(effective)),
            'refit':config['refit'],'refit_support_sha256':r['prior_support_sha256'],
            'takeover_authorship':'chief; supplemental SOL-046 review does not backdate or relabel approval',
            'preserved_pre_gate_failures':failures,'production_final_execution_not_performed':True}

def quantile(values,p):
    a=sorted(values);n=(len(a)-1)*p;i=int(n);f=n-i
    return a[i] if i+1==len(a) else a[i]+f*(a[i+1]-a[i])

def personal():
    accepted=js(BASE,'audit/chief/CHIEF-PERSONALIZED-RUN-002-review.json')
    assert accepted['status']=='accepted' and accepted['reviewed_commit']==PRESULT
    for path,digest in accepted['artifacts_sha256'].items():assert sha(blob(PRESULT,path))==digest
    data=js(PRESULT,PREFIX+'personalized_results.json')
    frozen=js(BASE,'ops/freeze.json')['profile_choices']
    summary=list(csv.DictReader(io.StringIO(blob(PRESULT,PREFIX+'personalized_summary.csv').decode())))
    assert len(data)==len(summary)==10
    inspected=[];referrals=[]
    for entry,s in zip(data,summary):
        p=entry['component_payload'];profile=p['profile_id'];fee=p['fee_rate'];h=p['horizon'];tol=p['loss_tolerance_pct']
        assert p['source_verified'] is False and entry['bridge_authentication']['verified'] is True
        assert s['component_source_verified']=='false' and s['bridge_provenance_verified']=='true'
        assert p['review_threshold_pct']==tol and h=={'A':5,'B':15,'C':30,'D':25,'E':6}[profile]
        assert p['recommended_class']==(None if profile in 'ADE' else 'conservative')
        choice=next(c for c in frozen if c['profile_id']==profile and c['fee_rate']==fee)
        assert choice['eligible']==(profile in 'BC') and choice['proposed_class']==p['recommended_class']
        if profile in 'ADE':
            assert entry['source_case_path'] is None and p['scenario_count']==p['denominator']==0
            assert p['status']=='upstream_referral' and p['exceedance_count'] is None and p['p10_growth_pct'] is None
            assert all(not c['qualified'] for c in entry['candidate_screens'])
            referrals.append({'profile':profile,'fee_rate':fee,'horizon':h,'reason':p['reasons']})
            continue
        case=PREFIX+entry['source_case_path']+'/'
        metrics=list(csv.DictReader(io.StringIO(blob(PRESULT,case+'scenario_metrics.csv').decode())))
        decisions=list(csv.DictReader(io.StringIO(blob(PRESULT,case+'decisions.csv').decode())))
        ledgers=list(csv.DictReader(io.StringIO(blob(PRESULT,case+'annual_ledgers.csv').decode())))
        assert len(metrics)==120 and len(decisions)==len(ledgers)==120*h
        assert {int(m['scenario_id']) for m in metrics}==set(range(1,121))
        assert all(int(m['horizon'])==h and float(m['review_threshold_pct'])==tol for m in metrics)
        assert all(float(d['review_threshold_pct'])==tol for d in decisions)
        growth=[float(m['net_real_cagr_pct']) for m in metrics];loss=[float(m['max_real_drawdown_pct']) for m in metrics]
        values={'median_growth_pct':quantile(growth,.5),'p10_growth_pct':quantile(growth,.1),
                'median_loss_pct':quantile(loss,.5),'p90_loss_pct':quantile(loss,.9),
                'exceedance_count':sum(x>tol for x in loss)}
        for key,value in values.items():close(p[key],value);close(s[key],value)
        assert values['exceedance_count']==5 and values['p90_loss_pct']<=tol and values['p10_growth_pct']>=0
        close(p['exceedance_fraction'],F(5,120))
        for field,count,denom in [('pooled_trade_share_pct','trade_count',120*h),('pooled_trade_share_ex_initial_pct','later_trade_count',120*(h-1))]:
            close(p[field],100*sum(int(m[count]) for m in metrics)/denom)
        severe=min(metrics,key=lambda m:(-float(m['max_real_drawdown_pct']),int(m['scenario_id'])))
        assert int(severe['scenario_id'])==p['severe_scenario_id']
        latch_ids=[int(d['scenario_id']) for d in decisions if d['action']=='human_review']
        selected=sorted({1,int(severe['scenario_id']),*(latch_ids[:1])})
        by_decision={(int(d['scenario_id']),int(d['period'])):d for d in decisions}
        for scenario in selected:
            path=[e for e in ledgers if int(e['scenario_id'])==scenario]
            obs=[(0,'initial',100.)];previous=100.;cpi=1.;latched=False
            for e in path:
                d=by_decision[scenario,int(e['period'])]
                observed=100*max(1-b[2]/a[2] for i,a in enumerate(obs) for b in obs[i:])
                close(d['observed_max_drawdown_pct'],observed)
                latched=latched or observed>=tol
                assert (d['human_review_latched']=='true')==latched
                assert (d['action']=='human_review')==latched
                if latched:assert e['engine_action']=='keep' and float(e['fee'])==0
                holdings=[float(e['holdings_before_'+a]) for a in ('equity','bond','bill_proxy')]
                W=math.fsum(holdings);close(W,previous)
                if e['engine_action']=='keep':transfer=0.
                else:
                    target=[float(e['target_'+a]) for a in ('equity','bond','bill_proxy')]
                    transfer=sum(max(0.,W*t-v) for t,v in zip(target,holdings))
                close(e['intended_transfer'],transfer);close(e['fee'],fee*transfer)
                close(e['wealth_after_fee'],W-fee*transfer)
                close(e['real_wealth_after_fee'],(W-fee*transfer)/cpi)
                after=[float(e['holdings_after_fee_'+a]) for a in ('equity','bond','bill_proxy')]
                expected_after=holdings if e['engine_action']=='keep' else [(W-fee*transfer)*t for t in target]
                for a,b in zip(after,expected_after):close(a,b)
                expected_end=[a*(1+float(e['return_'+asset])) for a,asset in zip(after,('equity','bond','bill_proxy'))]
                close(e['wealth_end'],math.fsum(expected_end));cpi*=1+float(e['inflation']);close(e['cpi_end'],cpi)
                previous=float(e['wealth_end']);close(e['real_wealth_end'],previous/cpi)
                obs.extend([(int(e['period']),'post_fee',float(e['real_wealth_after_fee'])),(int(e['period']),'end',previous/cpi)])
            # Pair enumeration is independent of the producer's running-peak scan.
            worst=max(1-b[2]/a[2] for i,a in enumerate(obs) for b in obs[i:])
            m=next(m for m in metrics if int(m['scenario_id'])==scenario)
            close(m['max_real_drawdown_pct'],100*worst)
            close(m['net_real_cagr_pct'],100*((obs[-1][2]/100)**(1/h)-1))
        inspected.append({'profile':profile,'fee_rate':fee,'horizon':h,'threshold_pct':tol,**values,
            'severe_scenario_id':int(severe['scenario_id']),'independently_reconciled_saved_paths':selected,
            'decision_rows_inspected':len(decisions),'ledger_rows_shape_checked':len(ledgers)})
    assert len(inspected)==4 and len(referrals)==6
    manuscript=blob(BASE,'report/submission-draft.md').decode()
    for phrase in ['support Conservative for B and C at both fees','A, D and E have no qualifying class at either fee',
                   'zero personalized simulations','five losses beyond tolerance','not guarantees or unconditional investment instructions',
                   'PENDING FINAL_EVALUATION']:
        assert phrase in manuscript,phrase
    builder=blob(BASE,'report/build_submission.py').decode()
    assert 'PERSONALIZED_TABLE' in builder
    return {'executed_cases':inspected,'referrals':referrals,'manuscript_personalized_wording':'accurate and conditional',
            'manuscript_final_slots':'pending; complete final manuscript not reviewed',
            'sampling':'aggregate all 480 saved metrics; arithmetic on selected saved paths only; no policy replay'}

def compute(live=False):
    fixture=fixtures();refs=references(live);p=personal()
    return fixture,{'bindings':refs,'personalized':p,'reviewed_hashes':dict(sorted(HASHES.items()))}

def main():
    parser=argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument('--derive',action='store_true')
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--fixtures',type=Path,default=OUT/'fixtures.json')
    args=parser.parse_args();assert args.derive != args.check
    assert sys.version_info[:2]==(3,12)
    control=json.loads((ROOT/'ops/control.json').read_bytes())
    assert control['state']=='running' and not (ROOT/'.runtime/STOP').exists() and not (ROOT/'STOP').exists()
    from datetime import datetime
    assert datetime.now().astimezone()<datetime.fromisoformat(control['deadline'])
    def access_guard(event,arguments):
        if event=='open':
            path,mode,flags=arguments
            if isinstance(path,(str,bytes)):
                normalized=str(path).replace('\\','/').lower()
                assert not any(x in normalized for x in ('/data/raw/','/data/development/','/data/final_holdout/','/problem/','/results/final/')), 'original/final access forbidden'
            if args.check:
                assert not (isinstance(mode,str) and any(x in mode for x in 'wax+')), 'read-only check'
                assert not (isinstance(flags,int) and flags & (1|2|64|512|1024)), 'read-only flags'
        if args.check and event in ('os.remove','os.rename','os.mkdir','os.rmdir','os.chmod','os.utime'):raise AssertionError('read-only check')
    sys.addaudithook(access_guard)
    fixture,refs=compute(args.derive)
    if args.derive:
        (OUT/'fixtures.json').write_text(json.dumps(fixture,indent=2)+'\n',encoding='utf8')
        (OUT/'reference_findings.json').write_text(json.dumps(refs,indent=2)+'\n',encoding='utf8')
    else:
        assert json.loads(args.fixtures.read_bytes())==fixture,'saved independent fixture mismatch'
        assert json.loads((OUT/'reference_findings.json').read_bytes())==refs,'saved reference findings mismatch'
        findings=json.loads((OUT/'findings.json').read_bytes())
        assert findings['verdict']=='approve' and findings['reviewed_hashes']==refs['reviewed_hashes']
        assert findings['independent_scope'] and findings['limitations'] and findings['final_result_acceptance'] is False
        verification=json.loads((OUT/'verification.json').read_bytes())
        for name,digest in verification['artifact_sha256'].items():assert sha((OUT/name).read_bytes())==digest,'saved artifact mismatch: '+name
        logs=json.loads((OUT/'execution_log.json').read_bytes())
        assert any(r.get('exit')==0 and 'unittest' in r.get('command',[]) for r in logs['executions'])
        assert any(r.get('exit')==1 and '--fixtures' in r.get('command',[]) for r in logs['executions']),'corruption execution not recorded'
    print(json.dumps({'status':'passed','mode':'derive' if args.derive else 'check','read_only':args.check,
        'fixture_groups':len(fixture),'reviewed_blobs':len(HASHES),'personalized_cases':4,'referrals':6,
        'no_original_or_final_inputs':True,'final_result_acceptance':False,'git_commands':COMMANDS},sort_keys=True))

if __name__=='__main__':
    main()
