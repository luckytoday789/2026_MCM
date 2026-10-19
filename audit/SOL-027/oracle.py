"""SOL-027 independent generated-only scalar/rational review. No production I/O."""
from fractions import Fraction as F
from dataclasses import replace, asdict
from copy import deepcopy
from pathlib import Path
import math, json, sys, hashlib
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from safeinvest.policy_personalized import build_personalized_case_tables as build, _outcome_screen
from safeinvest.policy_cases import build_case_tables
from safeinvest.policy_calibration import FoldCalibration, CalibrationBundle
from safeinvest.policy_pilot import EmpiricalPrior

FIELDS=('scenario_id','period','equity_return','bond_return','bill_proxy_return','inflation')
PROFILES={'A':(5,10,'high'), 'B':(15,25,'medium'), 'C':(30,40,'low'), 'D':(25,15,'medium'), 'E':(6,35,'high')}
ELIGIBLE={'A':('conservative',),'B':('conservative','balanced'),'C':('conservative','balanced','growth'),'D':('conservative','balanced'),'E':('conservative',)}
W={'conservative':(F(3,20),F(1,5),F(13,20)),'balanced':(F(1,3),)*3,'growth':(F(3,5),F(3,10),F(1,10))}
FEES=(.0025,.005)

def sha(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def rows(n=4,p=30,fn=None):
    return [dict(zip(FIELDS,(s,t,*(fn(s,t) if fn else (0.,0.,0.,0.))))) for s in range(1,n+1) for t in range(1,p+1)]
def priors(n=4,p=30,neutral=False):
    ids=range(1,n+1); out=[]
    for f in range(4):
        train=tuple(s for s in ids if (s-1)%4!=f); ev=tuple(s for s in ids if (s-1)%4==f)
        keys=tuple((s,t) for s in train for t in range(1,p+1))
        support=(1.,1.,1.) if neutral else (2.+f/8,1.125,1.)
        out.append(FoldCalibration(f,train,ev,keys,'0'*64,'1'*64,EmpiricalPrior((support,)*len(keys))))
    return tuple(out)
def run(rr,pp,profile='A',cls='conservative',fee=.0025,split='synthetic',reasons=()):
    return build(rr,calibrations=pp,profile_id=profile,proposed_class=cls,fee_rate=fee,split=split,upstream_reasons=reasons)

def scalar(path,prior,cls,fee,h,tolerance):
    # Expected arithmetic uses no production helper or chief expected value.
    w=W[cls]; k=F(str(fee)); hold=(F(0),F(0),F(100)); cpi=F(1); peak=F(100); loss=F(0)
    latched=False; first=None; deferred=None; annual=[]; decisions=[]; returns=[]; peak_at=(0,'initial'); dp=dt=(0,'initial')
    def observe(value,t,kind):
        nonlocal peak,loss,peak_at,dp,dt
        if value>peak: peak=value; peak_at=(t,kind)
        new=1-value/peak
        if new>loss: loss=new; dp=peak_at; dt=(t,kind)
    def ce(weights):
        # Direct inverse-cube expectation, independently derived gamma=4 CE.
        return (sum(float(sum(a*F(g) for a,g in zip(weights,row)))**-3 for row in prior)/len(prior))**(-1/3)
    for t,r in enumerate(path[:h],1):
        before=hold; wealth=sum(hold); real_before=wealth/cpi; observed=100*float(loss)
        latched=latched or observed>=tolerance
        transfer=F(0); charge=F(0); u=tuple(a/wealth for a in hold); cu=cw=tau=ff=None
        if latched: action='human_review'; selected=None; proposal=None
        else:
            cu,cw=ce(u),ce(w); tau=float(sum(abs(a-b) for a,b in zip(w,u))/2); ff=fee*tau
            selected=cls if (1-2*ff)*cw>cu+1e-12 else None; proposal=cls
            action='rebalance' if selected else 'keep'
            if selected:
                transfer=wealth*sum(abs(a-b) for a,b in zip(w,u))/2; charge=k*transfer; hold=tuple((wealth-charge)*a for a in w)
                if first is None and transfer>0: first=t
        if t==1: deferred=first is None
        post=hold; real_post=sum(post)/cpi; observe(real_post,t,'post_fee')
        rr=tuple(F(str(r[x])) for x in FIELDS[2:5]); infl=F(str(r['inflation']))
        hold=tuple(a*(1+b) for a,b in zip(post,rr)); end_cpi=cpi*(1+infl); real_end=sum(hold)/end_cpi
        ar=real_end/real_before-1; returns.append(float(ar)); observe(real_end,t,'end')
        annual.append(dict(wealth_before=float(wealth),cpi_before=float(cpi),real_wealth_before=float(real_before),intended_transfer=float(transfer),fee=float(charge),wealth_after_fee=float(sum(post)),real_wealth_after_fee=float(real_post),wealth_end=float(sum(hold)),cpi_end=float(end_cpi),real_wealth_end=float(real_end),annual_net_real_return=float(ar),holdings_before=before,holdings_after_fee=post,holdings_end=hold))
        decisions.append(dict(action=action,active_before=cls,active_after=cls,proposed_target=proposal,selected_target=selected,ce_keep=cu,prior_mass=1.,recent_count=0,observed_max_drawdown_pct=observed,human_review_latched=latched,initial_allocation_deferred=deferred,intended_transfer=float(transfer),actual_fee=float(charge),is_trade=transfer>F(1,10**10),executed_target_change=False,reason='human_review_latched' if latched else 'benefit_gate_failed' if selected is None else 'initial_allocation' if first==t else 'rebalance',first_deployment_year=first,score=None if latched else dict(ce_target=cw,tau=tau,fee_fraction=ff,pre_cost_benefit=cw-cu,modeled_fee_impact=ff*cw,conservative_score=(1-2*ff)*cw,true_net_ce=(1-ff)*cw)))
        cpi=end_cpi
    trades=[a['intended_transfer']>1e-10 for a in annual]; human=sum(d['action']=='human_review' for d in decisions)
    avg=sum(returns)/h
    metrics=dict(net_real_cagr_pct=100*((annual[-1]['real_wealth_end']/100)**(1/h)-1),annual_real_volatility_pct=100*math.sqrt(sum((r-avg)**2 for r in returns)/(h-1)),max_real_drawdown_pct=100*float(loss),terminal_real_wealth=annual[-1]['real_wealth_end'],nominal_fee_sum=sum(a['fee'] for a in annual),trade_count=sum(trades),review_count=h,later_trade_count=sum(trades[1:]),later_review_count=h-1,trade_share_pct=100*sum(trades)/h,trade_share_ex_initial_pct=100*sum(trades[1:])/(h-1),drawdown_peak_year=dp[0],drawdown_peak_kind=dp[1],drawdown_trough_year=dt[0],drawdown_trough_kind=dt[1],human_review_count=human,human_review_share_pct=100*human/h,first_latch_year=next((i+1 for i,d in enumerate(decisions) if d['human_review_latched']),None),target_change_count=0,first_deployment_year=first,initial_allocation_deferred=deferred)
    return annual,decisions,metrics

def exercise():
    checks=0; groups={}; facts=[]; expected_errors=[]; max_abs=0.
    def eq(a,b,name):
        nonlocal checks
        checks+=1; groups[name]=groups.get(name,0)+1
        assert type(a)==type(b) and a==b,(name,a,b)
    def close(a,b,name):
        nonlocal checks,max_abs
        checks+=1; groups[name]=groups.get(name,0)+1
        max_abs=max(max_abs,abs(a-float(b)))
        assert math.isfinite(a) and math.isclose(a,float(b),abs_tol=1e-9,rel_tol=1e-10),(name,a,b)
    def value(a,b,name):
        if b is None or isinstance(b,(bool,str,int)): eq(a,b,name)
        else: close(a,b,name)
    def error(label,fn):
        try: fn()
        except (ValueError,TypeError,OverflowError) as e: expected_errors.append({'case':label,'type':type(e).__name__,'message':str(e)})
        else: raise AssertionError('invalid input accepted: '+label)
    def audit(rr,pp,p,c,k,label):
        before=deepcopy(rr); prior_before=repr(pp); out=run(rr,pp,p,c,k); h,tol,liq=PROFILES[p]; case=out.case
        eq(rr,before,'input_immutability'); eq(repr(pp),prior_before,'prior_immutability')
        eq(out.rescreen['source_verified'],False,'unverified'); eq(case.metadata['source_verified'],False,'unverified')
        eq(out.rescreen['horizon'],h,'profile');eq(out.rescreen['loss_tolerance_pct'],tol,'profile');eq(out.rescreen['liquidity'],liq,'profile')
        n=len(rr)//30
        independent_metrics=[]
        counts={'annual_ledgers':n*h,'decisions':n*h,'scenario_metrics':n,'summary':1,'target_scores':sum(d['action']!='human_review' for d in case.decisions)}
        eq(case.counts,counts,'counts'); eq(out.rescreen['denominator'],n,'counts')
        for name in counts:
            rec=getattr(case,name);keys=[(r.get('profile_id'),r.get('fee_rate'),r.get('scenario_id',0),r.get('period',r.get('horizon',0))) for r in rec]
            eq(keys,sorted(keys),'ordered_keys');eq(len(keys),len(set(keys)),'unique_keys')
        for s in range(1,n+1):
            aa,dd,mm=scalar(rr[(s-1)*30:s*30],pp[(s-1)%4].prior.gross,c,k,h,tol)
            actual_a=[r for r in case.annual_ledgers if r['scenario_id']==s];actual_d=[r for r in case.decisions if r['scenario_id']==s]
            for a,b in zip(actual_a,aa):
                for key,v in b.items():
                    if key.startswith('holdings_'):
                        for asset,x in zip(('equity','bond','bill_proxy'),v):close(a[key+'_'+asset],x,'rational_dollars')
                    else: close(a[key],v,'rational_annual')
            for a,b in zip(actual_d,dd):
                for key,v in b.items():
                    if key!='score':value(a[key],v,'scalar_decision')
                score=[r for r in case.target_scores if r['scenario_id']==s and r['period']==a['period']]
                eq(len(score),int(b['score'] is not None),'score_count')
                if score:
                    for key,v in b['score'].items():close(score[0][key],v,'scalar_score')
            for key,v in mm.items():value(case.scenario_metrics[s-1][key],v,'scalar_metrics')
            independent_metrics.append(mm|{'scenario_id':s})
        def quantile(values,numerator,denominator):
            ordered=sorted(values); ix=F((len(ordered)-1)*numerator,denominator); lo=ix.numerator//ix.denominator; fraction=ix-lo
            hi=min(lo+1,len(ordered)-1)
            return float((1-fraction)*F(ordered[lo])+fraction*F(ordered[hi]))
        summary={}
        for name,key,num,den in [('median_growth_pct','net_real_cagr_pct',1,2),('p10_growth_pct','net_real_cagr_pct',1,10),('median_loss_pct','max_real_drawdown_pct',1,2),('p90_loss_pct','max_real_drawdown_pct',9,10),('median_volatility_pct','annual_real_volatility_pct',1,2),('median_terminal_real_wealth','terminal_real_wealth',1,2),('median_nominal_fee_sum','nominal_fee_sum',1,2)]:
            summary[name]=quantile([m[key] for m in independent_metrics],num,den)
        for key in ('trade_count','review_count','later_trade_count','later_review_count','human_review_count','target_change_count'):summary['pooled_'+key]=sum(m[key] for m in independent_metrics)
        summary['pooled_trade_share_pct']=100*summary['pooled_trade_count']/summary['pooled_review_count']
        summary['pooled_trade_share_ex_initial_pct']=100*summary['pooled_later_trade_count']/summary['pooled_later_review_count']
        summary['pooled_human_review_share_pct']=100*summary['pooled_human_review_count']/(n*h)
        severe=min(independent_metrics,key=lambda m:(-m['max_real_drawdown_pct'],m['scenario_id']))
        for key in ('scenario_id','net_real_cagr_pct','max_real_drawdown_pct','terminal_real_wealth','drawdown_peak_year','drawdown_peak_kind','drawdown_trough_year','drawdown_trough_kind','trade_share_pct','trade_share_ex_initial_pct'):summary['severe_'+key]=severe[key]
        for key,v in summary.items():
            value(case.summary[0][key],v,'independent_summary');value(out.rescreen[key],v,'independent_rescreen_statistics')
        risk=summary['p90_loss_pct']<=tol; power=summary['p10_growth_pct']>=0
        exceeded=sum(m['max_real_drawdown_pct']>tol for m in independent_metrics)
        expected_screen={'risk_pass':risk,'purchasing_power_pass':power,'exceedance_count':exceeded,'exceedance_fraction':exceeded/n,'reasons':([] if risk else ['p90_loss_exceeds_tolerance'])+([] if power else ['p10_growth_negative']),'recommended_class':c if risk and power else None,'proposed_class':c,'mode':c+'_cost','status':'eligible_after_personalized_development_rescreen' if risk and power else 'human_review_after_rescreen','simulation_status':'completed','horizon_pass':True,'reserve_pass':True}
        for key,v in expected_screen.items():eq(out.rescreen[key],v,'integrated_screens_no_fallback')
        facts.append({'label':label,'profile':p,'class':c,'fee':k,'counts':counts,'record_sha256':sha(asdict(out)),'first_metric':case.scenario_metrics[0],'rescreen':out.rescreen})
        return out
    pp=priors(); rr=rows(fn=lambda s,t: ((.125,-.0625,.03125,.015625) if t%3==1 else (-.125,.0625,0.,.03125) if t%3==2 else (.0625,.03125,.015625,0.)))
    # Every eligible class, every profile, both independent fee cases.
    for p in PROFILES:
        for c in ELIGIBLE[p]:
            for k in FEES:audit(rr,pp,p,c,k,'varied_path')
    # Integrated failures retain proposed class and every reason, with no alternate policy.
    for label,fn,flags in [('risk_only_integrated',lambda s,t:(-.125,-.125,-.125,0.) if t==1 else (.125,.125,.125,0.),(False,True)),('power_only_integrated',lambda s,t:(-.0625,-.0625,-.0625,0.) if t==5 else (0.,0.,0.,0.),(True,False)),('both_integrated',lambda s,t:(-.25,-.25,-.25,0.) if t==5 else (0.,0.,0.,0.),(False,False))]:
        for k in FEES:
            out=audit(rows(fn=fn),priors(neutral=True),'A','conservative',k,label)
            eq((out.rescreen['risk_pass'],out.rescreen['purchasing_power_pass']),flags,'integrated_failure_kind')
            eq(out.rescreen['proposed_class'],'conservative','integrated_failure_kind');eq(out.rescreen['recommended_class'],None,'integrated_failure_kind')
    isolation=run(rows(fn=lambda s,t:(-.5,-.5,-.5,0.) if s==1 and t==1 else (0.,0.,0.,0.)),priors(neutral=True))
    eq([r['first_latch_year'] for r in isolation.case.scenario_metrics],[2,None,None,None],'scenario_state_isolation')
    eq(asdict(run(rr,pp)),asdict(run(rr,pp)),'repeat_after_other_profiles_and_fees')
    # Exact equality is deliberately binary-exact and never tolerance-relaxed.
    for k in FEES:
        rr_eq=rows(fn=lambda s,t: ((-.25,)*3+(0.,)) if t==1 else ((.125,)*3+(0.,)))
        out=audit(rr_eq,priors(neutral=True),'B','conservative',k,'exact_equality')
        eq(out.case.decisions[1]['observed_max_drawdown_pct'],25.,'exact_equality');eq(out.case.scenario_metrics[0]['first_latch_year'],2,'exact_equality')
        eq(out.rescreen['exceedance_count'],0,'strict_count')
        # Initial deployment, then heterogeneous negative returns; pending assets keep dollars and earn returns.
        rr_pending=rows(fn=lambda s,t: (-.75,-.5,-.25,0.) if t==1 else (.25,.125,.0625,.03125))
        out=audit(rr_pending,pp,'A','conservative',k,'pending_component_dollars')
        eq(out.case.decisions[1]['action'],'human_review','pending');eq(out.case.annual_ledgers[1]['fee'],0.,'pending')
        # Year-2 rebalance fee alone crosses A's threshold; year-2 recovery must not erase it.
        post=F(100)-35*F(str(k)); endpoint=F(90001,1000)
        other=(endpoint-post*F(3,20)*F(1,2))/(post*F(17,20))
        crossing=rows(fn=lambda s,t:(-.5,float(other-1),float(other-1),0.) if t==1 else (.25,.25,.25,0.) if t==2 else (.0625,.125,.03125,0.))
        out=audit(crossing,pp,'A','conservative',k,'post_fee_crossing_recovery')
        eq(out.case.decisions[1]['action'],'rebalance','post_fee_lag');eq(out.case.decisions[2]['action'],'human_review','post_fee_lag')
        assert out.case.annual_ledgers[1]['real_wealth_after_fee']<90<100<out.case.annual_ledgers[1]['real_wealth_end']
    # Pure-inflation rational paths across all thresholds with neutral keep prior.
    for p in PROFILES:
        out=audit(rows(fn=lambda s,t:(.0625,.0625,.0625,.25)),priors(neutral=True),p,'conservative',.0025,'inflation_17_over_20')
        close(out.case.scenario_metrics[0]['terminal_real_wealth'],100*F(17,20)**PROFILES[p][0],'rational_closed_form')
    # No final-year H+1 latch and suffix outcomes irrelevant for fixed full-length priors.
    finalrows=rows(fn=lambda s,t:(0.,0.,0.,1.) if t==5 else (0.,0.,0.,0.)); neutral=priors(neutral=True)
    final=run(finalrows,neutral);eq(final.case.scenario_metrics[0]['first_latch_year'],None,'final_year');eq(final.case.scenario_metrics[0]['max_real_drawdown_pct'],50.,'final_year')
    suffix=deepcopy(finalrows)
    for r in suffix:
        if r['period']>5:r['equity_return']=3.;r['inflation']=2.
    eq(asdict(final),asdict(run(suffix,neutral)),'suffix_independence')
    changed=deepcopy(rr)
    for r in changed:
        if r['period']==3:r['inflation']=1.
    a=run(rr,pp).case;b=run(changed,pp).case
    eq([d for d in a.decisions if d['period']<=3],[d for d in b.decisions if d['period']<=3],'t_minus_one')
    assert [d for d in a.decisions if d['period']==4]!=[d for d in b.decisions if d['period']==4]
    # B's complete inherited numeric and diagnostic records, exact equality, no tolerance.
    prefix_facts=[]
    for c in ELIGIBLE['B']:
        for k in FEES:
            own=run(rr,pp,'B',c,k).case;generic=build_case_tables(rr,calibrations=pp,mode=c+'_cost',fee_rate=k,split='synthetic',horizons=(15,30))
            for name in ('annual_ledgers','decisions','target_scores','scenario_metrics','summary'):
                actual=[{k:v for k,v in r.items() if k not in ('profile_id','review_threshold_pct')} for r in getattr(own,name)]
                expected=[r for r in getattr(generic,name) if r.get('period',0)<=15 and r.get('horizon',15)==15]
                eq(actual,expected,'B_exact_full_prefix')
            prefix_facts.append({'class':c,'fee':k,'record_sha256':sha(asdict(own))})
    # Full support is the other three folds x 30, including when H=5.
    seen=[]
    import safeinvest.policy_personalized as adapter
    original_policy=adapter.CostAwarePolicy
    class Spy(original_policy):
        def __init__(self,mode,prior,**kw):
            seen.append((id(self),len(prior.gross),prior.gross[0]));super().__init__(mode,prior,**kw)
    adapter.CostAwarePolicy=Spy
    try:run(rr,pp)
    finally:adapter.CostAwarePolicy=original_policy
    eq([x[1] for x in seen],[90]*4,'full_training_support');eq([x[2] for x in seen],[p.prior.gross[0] for p in pp],'fold_selection')
    # Referral no compute, all known statistical fields and screen flags null, independent reasons containers.
    reasons=['original upstream reason','liquidity and risk screen']
    oldsim=adapter.simulate_policy
    adapter.simulate_policy=lambda *a,**k: (_ for _ in ()).throw(AssertionError('referral simulated'))
    referral=[]
    try:
        for p in PROFILES:
            for k in FEES:
                out=run(None,None,p,None,k,reasons=reasons);res=out.rescreen
                eq(out.case,None,'referral');eq(res['denominator'],0,'referral');eq(res['scenario_count'],0,'referral');eq(res['reasons'],reasons,'referral')
                nulls=(*adapter._STATISTICS,'recommended_class','proposed_class','mode','risk_pass','purchasing_power_pass','horizon_pass','reserve_pass','exceedance_count','exceedance_fraction')
                for name in nulls:eq(res[name],None,'referral_null')
                eq(res['pending_holdings_initial'],'retain original bills','referral');eq(res['pending_holdings_existing'],'keep current component dollars','referral')
                referral.append({'profile':p,'fee':k,'rescreen_sha256':sha(res)})
    finally:adapter.simulate_policy=oldsim
    out=run(None,None,reasons=reasons,cls=None);out.rescreen['upstream_reasons'].append('output change');eq(reasons,['original upstream reason','liquidity and risk screen'],'no_alias')
    out.rescreen['reasons'].append('other');eq(reasons,['original upstream reason','liquidity and risk screen'],'no_alias')
    normal=run(rr,pp);saved=deepcopy(rr);normal.case.annual_ledgers[0]['wealth_end']=999.;normal.rescreen['upstream_reasons'].append('x');eq(rr,saved,'no_alias');eq(run(rr,pp).case.annual_ledgers[0]['wealth_end']!=999.,True,'fresh_returns')
    # Direct outcome tests include strict float neighbors with no tolerance.
    screen_facts=[]
    for label,g,l,flags,count in [('equality',0.,10.,(True,True),0),('risk_only',0.,11.,(False,True),120),('power_only',-.125,10.,(True,False),0),('both',-.125,11.,(False,False),120),('above_loss',0.,math.nextafter(10.,math.inf),(False,True),120),('below_loss',0.,math.nextafter(10.,-math.inf),(True,True),0),('negative_growth',math.nextafter(0.,-math.inf),10.,(True,False),0),('positive_growth',math.nextafter(0.,math.inf),10.,(True,True),0)]:
        actual=_outcome_screen([g]*120,[l]*120,10.)
        expected={'risk_pass':flags[0],'purchasing_power_pass':flags[1],'exceedance_count':count,'exceedance_fraction':count/120,'reasons':([] if flags[0] else ['p90_loss_exceeds_tolerance'])+([] if flags[1] else ['p10_growth_negative'])}
        eq(actual,expected,'strict_outcome_screen');screen_facts.append({'case':label,'growth_hex':g.hex(),'loss_hex':l.hex(),'expected':expected,'actual':actual})
    tail=_outcome_screen([0.]*120,[10.]*119+[11.],10.);eq(tail['risk_pass'],True,'p90_not_guarantee');eq(tail['exceedance_count'],1,'p90_not_guarantee');eq(tail['exceedance_fraction'],1/120,'p90_not_guarantee')
    # API errors must not produce a referral; coverage includes metadata and actual support.
    for p in PROFILES:
        for c in W:
            if c not in ELIGIBLE[p]:error('ineligible_'+p+'_'+c,lambda p=p,c=c:run(rr,pp,p,c))
    badcases=[('final',{'split':'final'}),('profile',{'profile_id':'Z'}),('adaptive',{'proposed_class':'balanced_adaptive'}),('fee_zero',{'fee_rate':0.}),('fee_bool',{'fee_rate':True}),('fee_str',{'fee_rate':'.0025'}),('fee_adjacent',{'fee_rate':math.nextafter(.0025,math.inf)}),('fee_nan',{'fee_rate':float('nan')}),('reason_str',{'upstream_reasons':'x'}),('reason_empty',{'upstream_reasons':['']}),('referral_with_rows',{'proposed_class':None}),('development_bad_shape',{'split':'development'})]
    for label,kwargs in badcases:
        base=dict(calibrations=pp,profile_id='A',proposed_class='conservative',fee_rate=.0025,split='synthetic');base.update(kwargs);error(label,lambda base=base:build(rr,**base))
    error('referral_without_reason',lambda:run(None,None,cls=None))
    for label,bad in [('reordered_columns',[dict(reversed(list(r.items()))) for r in rr]),('missing_row',rr[:-1]),('duplicate',rr[:1]+rr[:-1]),('reordered_rows',list(reversed(rr))),('nan',[r|({'inflation':float('nan')} if i==0 else {}) for i,r in enumerate(rr)]),('boolean',[r|({'equity_return':True} if i==0 else {}) for i,r in enumerate(rr)]),('invalid_future',[r|({'inflation':-1.} if r['period']==30 else {}) for r in rr])]:error(label,lambda bad=bad:run(bad,pp))
    for label,bad in [('reverse_folds',pp[::-1]),('training_includes_eval',(replace(pp[0],training_ids=(1,2,3)),*pp[1:])),('wrong_evaluation',(replace(pp[0],evaluation_ids=(2,)),*pp[1:])),('truncated_keys',(replace(pp[0],training_keys=pp[0].training_keys[:15]),*pp[1:])),('short_prior',(replace(pp[0],prior=EmpiricalPrior(((2.,1.,1.),))),*pp[1:])),('bad_hash',(replace(pp[0],training_rows_sha256='x'),*pp[1:])),('bool_ids',(replace(pp[0],evaluation_ids=(True,)),*pp[1:]))]:error(label,lambda bad=bad:run(rr,bad))
    error('bundle_shape',lambda:run(rr,CalibrationBundle('0'*64,1,8,30,pp)))
    for label,g,l,t in [('empty',[],[],10),('mismatch',[0.],[],10),('bool',[True],[10.],10),('nan',[0.],[float('nan')],10),('negative_loss',[0.],[-1.],10),('tol_bool',[0.],[10.],True)]:error('outcome_'+label,lambda g=g,l=l,t=t:_outcome_screen(g,l,t))
    # Generated 120x30 shape only. Neutral priors avoid any production fitting or inputs.
    devrows=rows(n=120);devpriors=priors(n=120,neutral=True);dev=run(devrows,devpriors,split='development')
    eq(dev.case.counts,{'annual_ledgers':600,'decisions':600,'scenario_metrics':120,'summary':1,'target_scores':600},'generated_development_shape')
    eq([len(p.training_keys) for p in devpriors],[2700]*4,'generated_development_shape')
    eq(dev.rescreen['source_verified'],False,'generated_development_shape')
    return {'split':'synthetic','competition_inputs_read':False,'production_execution_authorized':False,'checks':checks,'groups':groups,'maximum_absolute_arithmetic_residual':max_abs,'tolerance':{'abs':1e-9,'rel':1e-10,'boundaries_counts_hashes':'exact'},'cases':facts,'B_prefix':prefix_facts,'outcome_screens':screen_facts,'tail_exceedance':tail,'referrals':referral,'invalid_inputs':expected_errors,'generated_120x30':{'origin':'generated zero-return synthetic rows; development label tests shape only','counts':dev.case.counts,'training_rows_per_fold':[2700]*4,'record_sha256':sha(asdict(dev))},'imported_modules':{name:str(Path(m.__file__).resolve()) for name,m in sorted(sys.modules.items()) if name=='safeinvest' or name.startswith('safeinvest.')}}

if __name__=='__main__':
    print(json.dumps(exercise(),sort_keys=True,allow_nan=False))
