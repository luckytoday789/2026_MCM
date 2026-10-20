"""Fresh SOL-041 arithmetic and compact adversarial fixtures; stdlib only."""
from collections import defaultdict,Counter
from decimal import Decimal as D,localcontext
import copy,csv,hashlib,io,json,math
ASSETS=('equity','bond','bill_proxy')
MODES=('conservative_cost','balanced_cost','growth_cost','balanced_context','balanced_adaptive','bills_keep','equal_weight_annual','equal_weight_buy_hold')
TARGETS={'conservative':(.15,.2,.65),'balanced':(1/3,1/3,1/3),'growth':(.6,.3,.1),'defensive':(.2,.25,.55),'growth_tilt':(.45,.3,.25)}
CENTRAL=dict(zip(MODES[:5],('conservative','balanced','growth','balanced','balanced')))
UNITS={'monetary_units':'nominal units; real wealth in CPI_0 purchasing power','return_units':'annual simple decimal','cpi_units':'price index; CPI_0=1','growth_units':'percent/year','volatility_units':'percentage points; annual sample ddof=1','loss_units':'percent of running real peak','trade_share_units':'percent of annual reviews'}
def dec(x):return D.from_float(float(x))
def quantile(xs,q):
 xs=sorted(dec(x) for x in xs);idx=D(len(xs)-1)*D(q);i=int(idx);f=idx-i;return xs[i]*(1-f)+xs[min(i+1,len(xs)-1)]*f

def audit_extra(v,decision_evidence):
 checks=0;maximum=0.;metric_facts=[];summary_facts=[];path_facts=[];score_facts=[];events={};path_ids={}
 def eq(a,b,label):
  nonlocal checks
  checks+=1;v.require(a==b,(label,a,b))
 def near(a,b,label):
  nonlocal checks,maximum
  checks+=1;maximum=max(maximum,abs(float(a)-float(b)));v.near(a,b,label)
 data=v.table('data/development/scenarios_001_120.csv');source={(int(r['scenario_id']),int(r['period'])):r for r in data}
 gross={k:tuple(dec((1+float(r[a+'_return']))/(1+float(r['inflation']))) for a in ASSETS) for k,r in source.items()}
 priors={f:[gross[s,t] for s in range(1,121) if (s-1)%4!=f for t in range(1,31)] for f in range(4)}
 def ce(weights,fold,recent):
  w=tuple(dec(x) for x in weights)
  def moment(row):return sum((x*y for x,y in zip(w,row)),D(0))**-3
  mm=(15*sum((moment(r) for r in priors[fold]),D(0))/2700+sum((moment(r) for r in recent),D(0)))/(15+len(recent))
  return mm**(-D(1)/3)
 with localcontext() as ctx:
  ctx.prec=70
  for mode in MODES:
   base=v.BUNDLE+'cases/'+mode+'/'
   led=v.table(base+'annual_ledgers.csv');metrics=v.table(base+'scenario_metrics.csv');summaries=v.table(base+'summary.csv');ds=v.table(base+'decisions.csv');ss=v.table(base+'target_scores.csv')
   by_s=defaultdict(list);by_d=defaultdict(list);scores=defaultdict(dict)
   for row in led:by_s[int(row['scenario_id'])].append(row)
   for row in ds:by_d[int(row['scenario_id'])].append(row)
   for row in ss:scores[int(row['scenario_id']),int(row['period'])][row['target_name']]=row
   selected={1,2,3,4}|{int(r['severe_scenario_id']) for r in summaries if int(r['horizon'])==30}
   for action in ('keep','rebalance','target_change','human_review'):
    found=next((r for r in ds if r['action']==action),None)
    if found:selected.add(int(found['scenario_id']))
   selected|={int(r['scenario_id']) for r in ds if r['period']=='1' and r['initial_allocation_deferred']=='true'}
   path_ids[mode]=sorted(selected)
   for row in led+metrics+summaries+ds+ss:
    eq(row['split'],'development','split');eq(row['mode'],mode,'mode');eq(float(row['fee_rate']),.005,'fee')
    if 'fold_id' in row:eq(int(row['fold_id']),(int(row['scenario_id'])-1)%4,'fold')
    for k,value in UNITS.items():
     if k in row:eq(row[k],value,'unit '+k)
   for scenario,path in by_s.items():
    for t,row in enumerate(path,1):
     if mode in CENTRAL:
      d=by_d[scenario][t-1];target=TARGETS[d['selected_target']] if d['selected_target'] else None
     else:
      target=None if mode=='bills_keep' or (mode=='equal_weight_buy_hold' and t>1) else TARGETS['balanced']
     eq(row['engine_action'],'rebalance' if target is not None else 'keep','execution target request')
     if target is not None:
      for a,w in zip(ASSETS,target):eq(float(row['target_'+a]),w,'selected actual target')
    if scenario in selected:
     held=(D(0),D(0),D(100));cpi=D(1)
     for t,row in enumerate(path,1):
      W=sum(held);target=tuple(dec(row['target_'+a]) for a in ASSETS) if row['engine_action']=='rebalance' else None
      transfer=sum((abs(W*w-h) for w,h in zip(target,held)),D(0))/2 if target is not None else D(0)
      fee=dec(.005)*transfer;after=tuple((W-fee)*w for w in target) if target is not None else held
      end=tuple(h*(1+dec(source[scenario,t][a+'_return'])) for a,h in zip(ASSETS,after));post=sum(after)/cpi;cpi*=1+dec(source[scenario,t]['inflation']);real=sum(end)/cpi
      expected=[transfer,fee,sum(after),post,cpi,real,*end]
      fields=['intended_transfer','fee','wealth_after_fee','real_wealth_after_fee','cpi_end','real_wealth_end',*['holdings_end_'+a for a in ASSETS]]
      observed=[row[f] for f in fields]
      for field,a,b in zip(fields,observed,expected):near(a,b,'complete path '+field)
      path_facts.append([mode,scenario,t,[float(x) for x in expected],[float(x) for x in observed]])
      held=end
   for m in metrics:
    s,H=int(m['scenario_id']),int(m['horizon']);path=by_s[s][:H];previous=D(100);peak=D(100);loss=D(0);annual=[]
    for row in path:
     real=dec(row['real_wealth_end']);annual.append(real/previous-1);previous=real
     for field in ('real_wealth_after_fee','real_wealth_end'):
      x=dec(row[field]);peak=max(peak,x);loss=max(loss,1-x/peak)
    mean=sum(annual)/H;vol=100*(sum((x-mean)**2 for x in annual)/(H-1)).sqrt()
    expected=[100*((previous/100)**(D(1)/H)-1),vol,100*loss,previous,sum(dec(r['fee']) for r in path)]
    names=['net_real_cagr_pct','annual_real_volatility_pct','max_real_drawdown_pct','terminal_real_wealth','nominal_fee_sum'];observed=[m[k] for k in names]
    for field,a,b in zip(names,observed,expected):near(a,b,'all metric '+field)
    metric_facts.append([mode,s,H,[float(x) for x in expected],[float(x) for x in observed]])
    if mode in CENTRAL:
     prefix=by_d[s][:H];human=sum(r['action']=='human_review' for r in prefix);latch=next((r['period'] for r in prefix if r['human_review_latched']=='true'),'')
     diag={'human_review_count':str(human),'first_latch_year':latch,'target_change_count':str(sum(r['executed_target_change']=='true' for r in prefix)),'first_deployment_year':prefix[-1]['first_deployment_year'],'initial_allocation_deferred':prefix[-1]['initial_allocation_deferred']}
     for key,value in diag.items():eq(m[key],value,'metric '+key)
     near(m['human_review_share_pct'],D(100)*human/H,'human share')
    else:
     for key in ('human_review_count','human_review_share_pct','first_latch_year','target_change_count','first_deployment_year','initial_allocation_deferred'):eq(m[key],'','baseline null '+key)
   for sm in summaries:
    H=int(sm['horizon']);group=[m for m in metrics if int(m['horizon'])==H];facts={}
    for name,field,q in [('median_growth_pct','net_real_cagr_pct','.5'),('p10_growth_pct','net_real_cagr_pct','.1'),('median_loss_pct','max_real_drawdown_pct','.5'),('p90_loss_pct','max_real_drawdown_pct','.9'),('median_volatility_pct','annual_real_volatility_pct','.5'),('median_terminal_real_wealth','terminal_real_wealth','.5'),('median_nominal_fee_sum','nominal_fee_sum','.5')]:
     value=quantile([r[field] for r in group],q);near(sm[name],value,'all summary '+name);facts[name]=[float(value),float(sm[name])]
    for name in ('trade_count','review_count','later_trade_count','later_review_count'):
     value=sum(int(r[name]) for r in group);eq(int(sm['pooled_'+name]),value,'pooled '+name);facts['pooled_'+name]=[value,int(sm['pooled_'+name])]
    for out,num,den in [('pooled_trade_share_pct','trade_count','review_count'),('pooled_trade_share_ex_initial_pct','later_trade_count','later_review_count')]:
     value=D(100)*sum(int(r[num]) for r in group)/sum(int(r[den]) for r in group);near(sm[out],value,out);facts[out]=[float(value),float(sm[out])]
    severe=min(group,key=lambda r:(-dec(r['max_real_drawdown_pct']),int(r['scenario_id'])));eq(int(sm['severe_scenario_id']),int(severe['scenario_id']),'severe tie')
    for field in ('net_real_cagr_pct','max_real_drawdown_pct','terminal_real_wealth','drawdown_peak_year','drawdown_peak_kind','drawdown_trough_year','drawdown_trough_kind','trade_share_pct','trade_share_ex_initial_pct'):eq(sm['severe_'+field],severe[field],'severe '+field)
    if mode in CENTRAL:
     humans=sum(int(r['human_review_count']) for r in group);changes=sum(int(r['target_change_count']) for r in group)
     eq(int(sm['pooled_human_review_count']),humans,'pooled human');eq(int(sm['pooled_target_change_count']),changes,'pooled changes');near(sm['pooled_human_review_share_pct'],D(100)*humans/(120*H),'pooled human share')
    else:
     for key in ('pooled_human_review_count','pooled_human_review_share_pct','pooled_target_change_count'):eq(sm[key],'','summary baseline null')
    summary_facts.append([mode,H,facts,int(severe['scenario_id'])])
   if mode not in CENTRAL:continue
   sample_keys={(s,t) for s in range(1,5) for t in (1,5,6,30)}
   for f in range(4):
    candidates=[d for d in ds if int(d['fold_id'])==f and d['ce_keep']]
    closest=min(candidates,key=lambda d:min(abs(float(x['conservative_score'])-float(d['ce_keep'])-1e-12) for x in scores[int(d['scenario_id']),int(d['period'])].values()))
    sample_keys.add((int(closest['scenario_id']),int(closest['period'])))
   for s in selected:
    for t in (1,6,30):sample_keys.add((s,t))
   for action in ('target_change','keep','human_review'):
    d=next((d for d in ds if d['action']==action),None)
    if d:sample_keys.add((int(d['scenario_id']),int(d['period'])))
   for s,t in sorted(sample_keys):
    d=by_d[s][t-1]
    if not d['ce_keep']:continue
    row=by_s[s][t-1];before=[float(row['holdings_before_'+a]) for a in ASSETS];wealth=math.fsum(before);weights=[x/wealth for x in before];fold=(s-1)%4;n=min(5,t-1) if mode in ('balanced_context','balanced_adaptive') else 0
    recent=[gross[s,i] for i in range(t-n,t)];keep=ce(weights,fold,recent);near(d['ce_keep'],keep,'fresh inverse-cube CE keep')
    for name,score in scores[s,t].items():
     target=TARGETS[name];target_ce=ce(target,fold,recent);tau=sum((abs(dec(a)-dec(b)) for a,b in zip(target,weights)),D(0))/2;fee=dec(.005)*tau;buffer=(1-2*fee)*target_ce;true=(1-fee)*target_ce
     for field,value in [('ce_target',target_ce),('tau',tau),('fee_fraction',fee),('conservative_score',buffer),('true_net_ce',true)]:near(score[field],value,'fresh score '+field)
     score_facts.append({'mode':mode,'scenario_id':s,'period':t,'fold':fold,'target':name,'recent_count':n,'ce_keep':[str(keep),d['ce_keep']],'ce_target':[str(target_ce),score['ce_target']],'score':[str(buffer),score['conservative_score']],'hurdle_margin_expected':str(buffer-keep-D('1e-12')),'action':d['action']})
   events[mode]={'actions':dict(Counter(d['action'] for d in ds)),'initial_deferrals':sum(d['period']=='1' and d['initial_allocation_deferred']=='true' for d in ds),'severe_H30':next(int(x['severe_scenario_id']) for x in summaries if x['horizon']=='30'),'sampled_states':len({(r['scenario_id'],r['period']) for r in score_facts if r['mode']==mode})}
 return {'status':'passed','checks':checks,'max_absolute_difference':maximum,'complete_path_scenarios':path_ids,'ledger_fact_columns':['transfer','fee','wealth_after_fee','real_after_fee','cpi_end','real_end','equity_end','bond_end','bill_end'],'complete_path_facts':path_facts,'metric_columns':['growth','sample_vol','max_drawdown','terminal_real','fees'],'all_metric_expected_observed':metric_facts,'all_summary_expected_observed':summary_facts,'fresh_CRRA_facts':score_facts,'events':events,'method':'Fresh 70-digit Decimal continuous complete paths; every metric and summary; direct gamma4 inverse-cube moments; production functions never imported.','limitations':['Independent CE expectations are representative samples; all 18000 decisions and17585 score identities/state links are checked by authenticated oracle.','Complete Decimal path expectations use saved actions whose choices are separately validated; full28800-row Fraction oracle covers every accounting fact.']}

def history(v,pins):
 p=pins['parameters']['producer'];prior=p['failed_prior'];raw=v.blob('handoff/HY3-005/result.json',prior['result_commit']);v.require(v.digest(raw)==prior['receipt_sha256'],'failed receipt pin');r=v.strict(raw);v.require(r['status']=='failed','failed predecessor preserved')
 matched=[]
 for name,h in r['artifacts_sha256'].items():
  if '/partial-' in name and '/cases/' in name:
   new=v.BUNDLE+'cases/'+name.split('/cases/',1)[1];v.require(v.digest(v.blob(name,prior['result_commit']))==h==v.digest(v.blob(new)),'partial provenance bytes');matched.append(new)
 v.require(len(matched)==15,'15 partial provenance files')
 logs=[]
 for name in v.git('ls-tree','-r','--name-only',prior['result_commit'],'handoff/HY3-005').decode().splitlines():
  b=v.blob(name,prior['result_commit']);logs.append({'path':name,'sha256':v.digest(b),'bytes':len(b)})
 old=v.strict(v.blob('handoff/SOL-036/result.json',v.BASE));v.require(old['status']=='failed','SOL-036 failed receipt')
 old_inventory={'handoff/SOL-036/result.json':v.digest(v.blob('handoff/SOL-036/result.json',v.BASE))}
 for name,h in old['artifacts_sha256'].items():
  # Authenticate exact old evidence where the failed attempt remains in Git;
  # do not execute or reinterpret its prior numerical results.
  try:raw=v.blob(name,v.BASE)
  except Exception:continue
  v.require(v.digest(raw)==h,'historical review artifact');old_inventory[name]=h
 return {'SOL-036_exact_failure':{'status':old['status'],'failure':old['failure'],'command_exits':[x['exit_code'] for x in old['checks']],'artifacts':old_inventory},'HY3-005_status':r['status'],'failure':r['failure'],'receipt_sha256':prior['receipt_sha256'],'partial15_matches':matched,'old_handoff_inventory':logs,'SOL-036':'interrupted/quota-failed; remains failed, no inference of restored quota','SOL-037':'accepted single successful probe only; no remaining-budget guarantee','use':'provenance only; no primary rankings, policy selection or retroactive acceptance','generation_runtime_evidence':'370.672 seconds is writer generation only, within1200; receipt has four exits and no per-command wall times'}


def synthetic(v,fixtures):
 """Execute only generated rows against authenticated kernel bytes, never writer."""
 import dataclasses,sys,types
 package='sol041_generated_only'
 pkg=types.ModuleType(package);pkg.__path__=[];sys.modules[package]=pkg
 for name in ('accounting','metrics','backtest','policy_pilot'):
  mod=types.ModuleType(package+'.'+name);mod.__file__='git:'+v.RESULT+':src/safeinvest/'+name+'.py';sys.modules[mod.__name__]=mod
  exec(compile(v.blob('src/safeinvest/'+name+'.py'),mod.__file__,'exec'),mod.__dict__)
 p=sys.modules[package+'.policy_pilot'];a=sys.modules[package+'.accounting'];results=[]
 for case in fixtures['future']:
  original=case['rows'];changed=case['changed_rows'];prior=p.EmpiricalPrior(tuple(tuple(x) for x in case['prior']))
  _,first=p.simulate_synthetic(original,mode=case['mode'],prior=prior,horizon=len(original),fee_rate=.005)
  _,second=p.simulate_synthetic(changed,mode=case['mode'],prior=prior,horizon=len(changed),fee_rate=.005)
  cut=case['cut_period'];left=[dataclasses.asdict(x) for x in first[:cut]];right=[dataclasses.asdict(x) for x in second[:cut]]
  v.require(left==right,'generated future changed earlier decisions');results.append({'mode':case['mode'],'fold_label':case['fold_label'],'decision_prefix_through':cut,'prefix_sha256':v.digest(v.canonical(left)),'unchanged':True})
 # Test strict hurdle, active priority and global-max anchoring with explicit
 # generated score objects. Expected winner is independent filtering/max order.
 ties=[]
 for case in fixtures['ties']:
  objects=[p.TargetScore(name,(1.,0.,0.),case['ce_keep'],1.,0.,0.,0.,0.,value,1.) for name,value in case['scores']]
  chosen=p.choose_target(objects,case['ce_keep']);observed=chosen.name if chosen else None
  v.require(observed==case['expected'],'synthetic strict/global-max tie');ties.append({'name':case['name'],'expected':case['expected'],'observed':observed})
 # The accounting reporting threshold cannot erase a real fee.
 tiny=fixtures['tiny'];trade=a.rebalance(tuple(tiny['holdings']),tuple(tiny['target']),.005)
 with localcontext() as ctx:
  ctx.prec=70;W=sum(dec(x) for x in tiny['holdings']);T=sum(abs(W*dec(w)-dec(h)) for w,h in zip(tiny['target'],tiny['holdings']))/2
  v.near(trade.intended_transfer,T,'tiny one-way arithmetic',rel=1e-3,abs_=1e-14)
 v.require(0<trade.intended_transfer<1e-10 and trade.fee>0 and trade.fee==.005*trade.intended_transfer,'tiny fee retained')
 severe=fixtures['severe'];prior=p.EmpiricalPrior(tuple(tuple(x) for x in severe['prior']));r,ds=p.simulate_synthetic(severe['rows'],mode='balanced_adaptive',prior=prior,horizon=len(severe['rows']),fee_rate=.005)
 latch=next((i for i,d in enumerate(ds) if d.human_review_latched),None);v.require(latch is not None,'generated severe latch')
 for i in range(latch,len(ds)):
  v.require(ds[i].action=='human_review' and r.ledger[i].fee==0 and r.ledger[i].holdings_after_fee==r.ledger[i].holdings_before,'latch never resets and preserves dollars')
 # Explicit generated initial-deferral coverage, absent in saved competition decisions.
 deferrals=[]
 for mode in MODES[:5]:
  generated=fixtures['deferral_rows'];prior=p.EmpiricalPrior(((1.,1.,1.1),))
  rr,dd=p.simulate_synthetic(generated,mode=mode,prior=prior,horizon=len(generated),fee_rate=.005)
  v.require(dd[0].action=='keep' and dd[0].first_deployment_year is None and rr.ledger[0].fee==0,'initial allocation benefit gate defers')
  v.require(all(d.initial_allocation_deferred for d in dd),'initial deferral flag persists')
  deferrals.append({'mode':mode,'initial_action':dd[0].action,'first_deployment':dd[-1].first_deployment_year,'persistent_deferral':True})
 # Construct a generated valid continuation state to isolate active-target updates
 # below the trade-reporting threshold. The scripted CE is a test double only.
 class ScriptedPrior(p.EmpiricalPrior):
  def certainty_equivalent(self,weights,recent=()):return 1.2 if tuple(weights)==p.TARGETS['defensive'] else 1.0
 b=sys.modules[package+'.backtest'];policy=p.CostAwarePolicy('balanced_adaptive',ScriptedPrior(((1.,1.,1.),)),fee_rate=.005)
 history=tuple(b.Observation(1,t,(0.,0.,0.),0.) for t in range(1,6));holdings=tuple(fixtures['tiny']['holdings'])
 policy.reviews=[None]*5;policy._scenario=1;policy._history=history[:-1];policy._after=holdings
 policy(b.DecisionContext(1,6,holdings,history));last=policy.reviews[-1]
 v.require(last.action=='target_change' and last.active_after=='defensive' and policy.active=='defensive' and last.executed_target_change and not last.is_trade and 0<last.actual_fee<1e-10,'tiny execution updates active state despite reporting flag')
 tiny_state={'action':last.action,'active_before':last.active_before,'active_after':last.active_after,'transfer':last.intended_transfer,'fee':last.actual_fee,'is_trade':last.is_trade,'test_double':'generated explicit CE only; no production arithmetic expectations'}
 return {'initial_deferrals':deferrals,'tiny_active_state':tiny_state,'future':results,'tie_boundaries':ties,'tiny_transfer':trade.intended_transfer,'tiny_fee':trade.fee,'tiny_reported_trade':trade.intended_transfer>1e-10,'severe_first_latch':latch+1,'severe_later_actions':[d.action for d in ds[latch:]],'scope':'generated data only; authenticated exact producer kernel used as system under test, never as expectation generator for competition data'}

def fixture_inputs(v):
 future=[]
 for f in range(4):
  for mode in MODES[:5]:
   rows=[{'scenario_id':f+1,'period':t,'equity_return':.08+.002*f if t%3 else -.06,'bond_return':.025,'bill_proxy_return':.015,'inflation':.02} for t in range(1,9)]
   changed=copy.deepcopy(rows)
   for row in changed[5:]:row.update(equity_return=-.7,bond_return=.17,bill_proxy_return=-.05,inflation=.3)
   future.append({'mode':mode,'fold_label':f,'cut_period':6,'prior':[[1.07+.001*f,1.01,1.0],[.94,1.03,1.01]],'rows':rows,'changed_rows':changed})
 ties=[{'name':'exact keep hurdle','ce_keep':1.,'scores':[['active',1.+1e-12]],'expected':None},
 {'name':'active first inside global tolerance','ce_keep':.9,'scores':[['active',1.],['other',1.+.5e-12]],'expected':'active'},
 {'name':'global maximum avoids chain ties','ce_keep':.9,'scores':[['active',1.],['middle',1.+.75e-12],['last',1.+1.5e-12]],'expected':'middle'},
 {'name':'ineligible preferred cannot be selected','ce_keep':1.,'scores':[['active',1.+.5e-12],['other',1.+1.25e-12]],'expected':'other'}]
 severe=[{'scenario_id':1,'period':t,'equity_return':-.6 if t==3 else .2,'bond_return':-.6 if t==3 else .05,'bill_proxy_return':-.6 if t==3 else .01,'inflation':.02} for t in range(1,9)]
 return {'deferral_rows':[{'scenario_id':1,'period':t,'equity_return':.1,'bond_return':.03,'bill_proxy_return':-.2,'inflation':.01} for t in range(1,9)],'future':future,'ties':ties,'tiny':{'holdings':[20.+1e-11,25.,55.-1e-11],'target':[.2,.25,.55]},'severe':{'rows':severe,'prior':[[1.1,1.03,1.0],[1.05,1.02,1.0]]}}

def compact_base(v):
 mode='balanced_adaptive';base=v.BUNDLE+'cases/'+mode+'/'
 led=v.table(base+'annual_ledgers.csv');metrics=v.table(base+'scenario_metrics.csv');decisions=v.table(base+'decisions.csv');scores=v.table(base+'target_scores.csv')
 path=led[:5];source=v.table('data/development/scenarios_001_120.csv')[:5]
 obj={'task_id':'HY3-006','source_commit':'bc04d428425a9afbea799e036213632dc6568c73','config_sha256':'7c6c97181ff9422637489fc4c9fff37bed6113bfb9011da07cb5790df213d07a','status':'completed','counts':{'ledgers':28800,'metrics':4800,'summaries':40,'decisions':18000,'scores':17585},'files':sorted(v.strict(v.blob(v.BUNDLE+'run_manifest.json'))['artifacts']),'path':path,'source':source,'metric':metrics[0],'decision':decisions[0],'score':scores[0]}
 obj['payload_sha256']=v.digest(v.canonical({k:x for k,x in obj.items() if k not in ('payload_sha256',)}));return obj

def compact_validate(v,x,expected):
 v.require(x['payload_sha256']==v.digest(v.canonical({k:z for k,z in x.items() if k!='payload_sha256'})),'payload hash')
 for key in ('task_id','source_commit','config_sha256','status','counts','files'):v.require(x[key]==expected[key],'compact '+key)
 v.require(len(x['path'])==5 and len({(r['scenario_id'],r['period']) for r in x['path']})==5,'compact duplicate path key')
 # Recalculate five actual Git-bound years with high precision rather than use
 # expected saved metric/hash values. Source and targets remain pinned facts.
 v.require(x['source']==expected['source'],'compact original source')
 with localcontext() as ctx:
  ctx.prec=70;held=(D(0),D(0),D(100));cpi=D(1);peak=D(100);loss=D(0);prev=D(100);annual=[];fees=[]
  for i,row in enumerate(x['path']):
   original=expected['path'][i]
   v.require((row['scenario_id'],row['period'],row['engine_action'])==(original['scenario_id'],original['period'],original['engine_action']),'compact path grid/action')
   target=tuple(dec(row['target_'+a]) for a in ASSETS) if row['engine_action']=='rebalance' else None
   v.require([row['target_'+a] for a in ASSETS]==[original['target_'+a] for a in ASSETS],'compact target')
   W=sum(held);T=sum((abs(W*w-h) for w,h in zip(target,held)),D(0))/2 if target else D(0);fee=dec(.005)*T;after=tuple((W-fee)*w for w in target) if target else held
   v.near(row['intended_transfer'],T,'compact transfer');v.near(row['fee'],fee,'compact one-way fee');v.near(row['real_wealth_after_fee'],sum(after)/cpi,'compact post-fee drawdown point')
   for a,h in zip(ASSETS,after):v.near(row['holdings_after_fee_'+a],h,'compact before returns')
   post=sum(after)/cpi;held=tuple(h*(1+dec(x['source'][i][a+'_return'])) for a,h in zip(ASSETS,after));cpi*=1+dec(x['source'][i]['inflation']);real=sum(held)/cpi
   v.near(row['cpi_end'],cpi,'compact exact CPI');v.near(row['real_wealth_end'],real,'compact annual simple real')
   annual.append(real/prev-1);prev=real;fees.append(fee)
   for value in (post,real):peak=max(peak,value);loss=max(loss,1-value/peak)
  m=x['metric'];mean=sum(annual)/5
  for key,value in [('net_real_cagr_pct',100*((prev/100)**(D(1)/5)-1)),('annual_real_volatility_pct',100*(sum((r-mean)**2 for r in annual)/4).sqrt()),('max_real_drawdown_pct',100*loss),('terminal_real_wealth',prev),('nominal_fee_sum',sum(fees))]:v.near(m[key],value,'compact numerical '+key)
 # All saved state/scalar cells are bound to the exact artifact, separately from
 # the path arithmetic. Rehashed changes must fail semantic checks too.
 d=x['decision'];v.require(d['recent_count']=='0' and d['active_before']=='balanced' and d['active_after']==expected['decision']['active_after'] and d['action']==expected['decision']['action'],'compact decision state')
 sc=x['score'];tau=dec(sc['tau']);cost=dec(.005)*tau;ce=dec(sc['ce_target']);v.near(sc['fee_fraction'],cost,'compact doubled fee');v.near(sc['conservative_score'],(1-2*cost)*ce,'compact doubled buffer');v.near(sc['true_net_ce'],(1-cost)*ce,'compact single modeled fee')
 v.require(sc['ce_target']==expected['score']['ce_target'],'compact CRRA authenticated independent sampled CE')

def fixtures_replay(v,arithmetic,record=False):
 base=compact_base(v);synthetic_fixtures=fixture_inputs(v);corruptions=[]
 def add(name,fn,rehash=True):
  x=copy.deepcopy(base);fn(x)
  if rehash:x['payload_sha256']=v.digest(v.canonical({k:z for k,z in x.items() if k!='payload_sha256'}))
  corruptions.append({'name':name,'rehash':rehash,'payload':x,'expected':'reject'})
 add('missing file',lambda x:x['files'].pop())
 add('wrong source',lambda x:x.update(source_commit='0'*40))
 add('wrong config',lambda x:x.update(config_sha256='0'*64))
 add('wrong task',lambda x:x.update(task_id='HY3-005'))
 add('incomplete status',lambda x:x.update(status='partial'))
 add('false count',lambda x:x['counts'].update(scores=17586))
 add('duplicate typed key',lambda x:x['path'].__setitem__(1,copy.deepcopy(x['path'][0])))
 add('rehash wrong metric',lambda x:x['metric'].update(net_real_cagr_pct=str(float(x['metric']['net_real_cagr_pct'])+1)))
 add('double actual fee',lambda x:x['path'][0].update(fee=str(2*float(x['path'][0]['fee']))))
 add('wrong CPI',lambda x:x['path'][0].update(cpi_end='1.5'))
 add('wrong annual real wealth',lambda x:x['path'][0].update(real_wealth_end='999'))
 add('fee deducted after return',lambda x:x['path'][0].update(holdings_after_fee_equity='33.333333333333336'))
 add('wrong active state',lambda x:x['decision'].update(active_after='defensive'))
 add('context sees current year',lambda x:x['decision'].update(recent_count='1'))
 add('single cost hurdle instead of doubled',lambda x:x['score'].update(conservative_score=x['score']['true_net_ce']))
 add('stale payload hash',lambda x:x['metric'].update(terminal_real_wealth='999'),False)
 fixture={'schema_version':1,'producer':v.RESULT,'base':base,'corruptions':corruptions,'generated':synthetic_fixtures,'duplicate_json':'{"task_id":"HY3-006","task_id":"HY3-005"}'}
 if record:v.save('fixtures.json',fixture)
 else:
  saved=v.strict((v.HERE/'fixtures.json').read_bytes());v.require(saved==fixture,'fixture exact reproducibility');fixture=saved
 fixture_before=v.digest((v.HERE/'fixtures.json').read_bytes());compact_validate(v,fixture['base'],base);results=[]
 for case in fixture['corruptions']:
  before=v.digest(v.canonical(case['payload']))
  try:compact_validate(v,case['payload'],base)
  except (AssertionError,ValueError,KeyError,TypeError) as exc:result={'name':case['name'],'expected':'reject','observed':'rejected','reason':str(exc),'before_sha256':before,'after_sha256':v.digest(v.canonical(case['payload'])),'rehash':case['rehash']}
  else:raise AssertionError('corruption accepted: '+case['name'])
  v.require(result['before_sha256']==result['after_sha256'],'read-only corruption');results.append(result)
 try:v.strict(fixture['duplicate_json'])
 except (ValueError,AssertionError) as exc:results.append({'name':'duplicate JSON key','observed':'rejected','reason':str(exc)})
 else:raise AssertionError('duplicate JSON accepted')
 syn=synthetic(v,fixture['generated']);fixture_after=v.digest((v.HERE/'fixtures.json').read_bytes());v.require(fixture_before==fixture_after,'fixture file unchanged')
 return {'status':'passed','rejected':len(results),'corruptions':results,'fixture_sha256_before':fixture_before,'fixture_sha256_after':fixture_after,'generated_tests':syn,'scope':'compact exact-Git-derived five-year case and typed metadata overlays; independent arithmetic catches rehashed numerical errors; no full bundle duplication or producer --check retry'}
