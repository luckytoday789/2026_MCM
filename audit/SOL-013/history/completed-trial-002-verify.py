"""Independent SOL-013 synthetic audit. Python 3.12 standard library only.

--create exclusively creates evidence; --check never writes, imports pinned Git
blobs in memory and compares evidence with explicit numeric tolerances. A supported
negative policy verdict is evidence, not a failing evidence-integrity check.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict, replace
from decimal import Decimal, localcontext
from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'audit' / 'SOL-013'
BASE = '7c804ffb960be6b9fadfc840e246ff060668a96d'
TASK_COMMIT = '5d709e0a8e39cea2e8fa891928bb53bc6d93005f'
TASK_HASH = 'fd1cd04500fb04b91041e835678dee787ff16c00cb21578e368fda313cb9d4e7'
SOURCES = {
  "specs/DEVELOPMENT_POLICY_PILOT_V2.md": "ada0257f813091a01526e497e28ca3871bf9b13afa98487708be17ae8249bcb1",
  "specs/development_policy_pilot_v2.json": "d7b20f38196831befc80dfdcc69c6653d1ae8352d1c87c79e19bcc09d5c84df3",
  "specs/POLICY_CORRECTION_V2.md": "b7c5779ee553e9a364b69e20a8de43cee086cc480d1fd825228e11f454a85383",
  "src/safeinvest/policy_pilot.py": "1f439cff5627279219867497b891549f3702434966b3194c11f8e18894ffba90",
  "tests/test_policy_pilot.py": "0a8d605c38e75aef00a7185978a8925989b413aa1eb44c0bd534085125bdb11f",
  "src/safeinvest/accounting.py": "0c73b143ed9755924be16d9c4fe9d9e8d8888931cb5c8a8c303434e2280389e5",
  "src/safeinvest/backtest.py": "bbe2e602124adf068da424df0a28c9f40f970f81c126bed393f61ebb25b244b6",
  "specs/ACCOUNTING.md": "a9c3ab8dbba3ad752336642061ead272e2c196de83f73eb410e39bd5b559f71e",
  "specs/PROBLEM_LOCK.md": "566c93ad1b5f79c9ec10a42725ab023953c9a02aeb1c91a459e740caf68c0e46",
  "audit/SOL-009/findings.json": "1b425c6b0ab0399c2c94614768ab362975e676cfd474e964aa3a1ee4d60c6e83",
  "audit/chief/SOL-009-review.json": "6f1a480162704fa67a2f70358cc9413584c44d6a455d662e7369f7c7ea4a8964"
}
# The engine imports metrics; bind this supporting dependency without asserting
# this narrow review certifies the general metric implementation.
METRICS_HASH = 'efb7dad73e71515b9f164a95935231479ebca14b46c5b086a14de4bf5d38df9e'
REL = 2e-11
ABS = 2e-10
TARGETS = {
 'conservative': (F(15,100), F(20,100), F(65,100)),
 'balanced': (F(1,3),)*3,
 'growth': (F(60,100),F(30,100),F(10,100)),
 'defensive': (F(20,100),F(25,100),F(55,100)),
 'growth_tilt': (F(45,100),F(30,100),F(25,100)),
}
MODES = {'conservative_cost':'conservative','balanced_cost':'balanced',
 'growth_cost':'growth','balanced_context':'balanced','balanced_adaptive':'balanced'}

def digest(b): return hashlib.sha256(b).hexdigest()
def canonical(b): return b.replace(b'\r\n', b'\n')
def blob(commit, name):
 return subprocess.check_output(['git','show',commit+':'+name],cwd=ROOT)
def dump(v): return json.dumps(v,indent=2,sort_keys=True,allow_nan=False)+'\n'
def normalized(v):
 if isinstance(v,F): return float(v)
 if isinstance(v,tuple): return [normalized(x) for x in v]
 if isinstance(v,list): return [normalized(x) for x in v]
 if isinstance(v,dict): return {k:normalized(x) for k,x in v.items()}
 return v

def equal(a,b,rel=REL,abs_tol=ABS):
 if isinstance(a,bool) or isinstance(b,bool): return type(a)==type(b) and a==b
 if isinstance(a,(int,float)) and isinstance(b,(int,float)):
  return math.isclose(a,b,rel_tol=rel,abs_tol=abs_tol)
 if isinstance(a,dict) and isinstance(b,dict):
  return a.keys()==b.keys() and all(equal(a[k],b[k],rel,abs_tol) for k in a)
 if isinstance(a,(tuple,list)) and isinstance(b,(tuple,list)):
  return len(a)==len(b) and all(equal(x,y,rel,abs_tol) for x,y in zip(a,b))
 return a==b

class Evidence:
 def __init__(self): self.checks=[]
 def check(self,name,expected,observed,*,scope='kernel',rel=REL,abs_tol=ABS,exact=False):
  expected,observed=normalized(expected),normalized(observed)
  passed=(expected==observed) if exact else equal(expected,observed,rel,abs_tol)
  self.checks.append(dict(name=name,scope=scope,expected=expected,observed=observed,
                         passed=passed,relative_tolerance=0 if exact else rel,
                         absolute_tolerance=0 if exact else abs_tol))
 def rejects(self,name,fn):
  try: fn()
  except (ValueError,OverflowError,TypeError,AttributeError) as exc:
   self.check(name,True,True,exact=True)
   return type(exc).__name__+': '+str(exc)
  self.check(name,True,False,exact=True)
  return 'UNEXPECTED COMPLETED RUN'

# Oracle uses rational moments and an 80-digit Decimal cube root; no production
# CE, score, accounting or expected-value helper is used for expected values.
def rat(x): return x if isinstance(x,F) else F(x) if isinstance(x,float) else F(str(x))
def unit(w):
 w=tuple(map(rat,w)); return tuple(x/sum(w) for x in w)
def ce(weights,prior,recent=()):
 w=unit(weights)
 moment=lambda row: sum(a*rat(b) for a,b in zip(w,row))**-3
 m=(15*sum(map(moment,prior))/len(prior)+sum(map(moment,recent)))/(15+len(recent))
 with localcontext() as c:
  c.prec=80
  return float((Decimal(m.numerator)/Decimal(m.denominator)) ** (Decimal(-1)/Decimal(3)))
def score(w,u,prior,recent,k):
 cw,cu=ce(w,prior,recent),ce(u,prior,recent)
 tau=sum(abs(a-b) for a,b in zip(unit(w),unit(u)))/2
 fee=rat(k)*tau
 return dict(ce_keep=cu,ce_target=cw,tau=float(tau),fee_fraction=float(fee),
  pre_cost_benefit=cw-cu,modeled_fee_impact=float(fee)*cw,
  conservative_score=(1-2*float(fee))*cw,true_net_ce=(1-float(fee))*cw)
def choose(pairs,keep):
 eligible=[(name,s) for name,s in pairs if s>keep+1e-12]
 if not eligible:return None
 top=max(s for _,s in eligible)
 return next(name for name,s in eligible if top-s<=1e-12)
def quantile(values,q):
 v=sorted(map(rat,values)); p=(len(v)-1)*rat(q); i=p.numerator//p.denominator
 return v[i] if i==len(v)-1 else v[i]+(p-i)*(v[i+1]-v[i])
def median(values):return quantile(values,F(1,2))
def gates(ga,gb,la,lb):
 d=[rat(a)-rat(b) for a,b in zip(ga,gb)]
 facts=dict(gain=median(d),tail_growth_difference=quantile(ga,F(1,10))-quantile(gb,F(1,10)),
  tail_loss_difference=quantile(la,F(9,10))-quantile(lb,F(9,10)),
  positive_fold_count=sum(median(d[j::4])>0 for j in range(4)))
 return facts, facts['gain']>=F(1,10) and facts['tail_growth_difference']>=-F(1,10) and facts['tail_loss_difference']<=1 and facts['positive_fold_count']>=3

def bind_sources():
 if sys.version_info[:2]!=(3,12):raise RuntimeError('Python 3.12 is required')
 found={}
 for name,want in SOURCES.items():
  b=blob(BASE,name)
  if digest(b)!=want:raise RuntimeError('Pinned source hash mismatch: '+name)
  found[name]=digest(b)
 raw=blob(TASK_COMMIT,'ops/tasks/SOL-013.json'); task=json.loads(raw)
 taskhash=digest(json.dumps(task,sort_keys=True,separators=(',',':')).encode())
 if taskhash!=TASK_HASH or task['base_commit']!=BASE or task['parameters']['source_sha256']!=SOURCES:
  raise RuntimeError('Immutable task mismatch')
 if task['owner']!='sol' or task['allowed_paths']!=['audit/SOL-013']:
  raise RuntimeError('Immutable scope mismatch')
 # Do not require HEAD to remain the base or a worker delivery commit.
 if (ROOT/'.runtime/task.json').exists():
  local=json.loads((ROOT/'.runtime/task.json').read_text(encoding='utf-8'))
  if local.get('id')=='SOL-013' and local!=task: raise RuntimeError('Local immutable task differs')
 pkg=types.ModuleType('safeinvest'); pkg.__path__=[];sys.modules['safeinvest']=pkg
 imported={}
 for short in ('accounting','metrics','backtest','policy_pilot'):
  name='src/safeinvest/'+short+'.py'; raw=blob(BASE,name)
  want=METRICS_HASH if short=='metrics' else SOURCES[name]
  if digest(raw)!=want:raise RuntimeError('Imported bytes differ: '+name)
  mod=types.ModuleType('safeinvest.'+short);mod.__file__=str(ROOT/name)
  mod.__package__='safeinvest';sys.modules[mod.__name__]=mod
  exec(compile(raw,mod.__file__,'exec'),mod.__dict__)
  setattr(pkg,short,mod); imported[name]=digest(raw)
 return sys.modules['safeinvest.policy_pilot'],sys.modules['safeinvest.backtest'],found,imported

def rows(n=30,rates=(0.,0.,0.),inflation=0.,scenario=9001):
 return [dict(scenario_id=scenario,period=t,equity_return=rates[0],bond_return=rates[1],
              bill_proxy_return=rates[2],inflation=inflation) for t in range(1,n+1)]
def toy_run(p,data,mode='balanced_cost',prior=((1.1,1.02,1.),),fee=.0025,threshold=25,h=None):
 return p.simulate_synthetic(data,mode=mode,prior=p.EmpiricalPrior(prior),horizon=h or len(data),
                             fee_rate=fee,review_drawdown_pct=threshold)
def oracle_path(data,mode,prior,fee,threshold):
 h=(F(0),F(0),F(100));cpi=F(1);peak=F(100);loss=F(0);latched=False
 active=MODES[mode];deferred=False;first=None;history=[];ledger=[];reviews=[]
 for t,row in enumerate(data,1):
  observed=float(loss);latched=latched or observed>=threshold;before=active
  recent=history[-5:] if mode in ('balanced_context','balanced_adaptive') else []
  names=[active]
  if mode=='balanced_adaptive' and len(recent)==5:
   names += [n for n in ('defensive','balanced','growth_tilt') if n!=active]
  scores={} if latched else {n:score(TARGETS[n],unit(h),prior,recent,fee) for n in names}
  chosen=None if latched else choose([(n,s['conservative_score']) for n,s in scores.items()],ce(unit(h),prior,recent))
  proposal=None
  if scores:
   top=max(s['conservative_score'] for s in scores.values())
   proposal=next(n for n,s in scores.items() if top-s['conservative_score']<=1e-12)
  if latched:action='human_review'
  elif chosen is None:action='keep'
  else:action='rebalance' if chosen==active else 'target_change'
  W=sum(h);T=F(0);cost=F(0);after=h
  if chosen is not None:
   w=TARGETS[chosen];T=W*sum(abs(a-b) for a,b in zip(w,unit(h)))/2
   cost=rat(fee)*T;after=tuple((W-cost)*a for a in w);active=chosen
   if first is None and T>0:first=t
  if t==1:deferred=first is None
  real_after=sum(after)/cpi
  peak=max(peak,real_after);loss=max(loss,100*(1-real_after/peak))
  r=tuple(rat(row[k]) for k in ('equity_return','bond_return','bill_proxy_return'));inf=rat(row['inflation'])
  end=tuple(x*(1+y) for x,y in zip(after,r));newcpi=cpi*(1+inf);real_end=sum(end)/newcpi
  ledger.append(dict(holdings_before=h,intended_transfer=T,fee=cost,holdings_after_fee=after,
    holdings_end=end,cpi_before=cpi,cpi_end=newcpi,real_wealth_after_fee=real_after,
    real_wealth_end=real_end))
  reviews.append(dict(action=action,active_before=before,active_after=active,selected_target=chosen,
   proposed_target=proposal,initial_allocation_deferred=deferred,first_deployment_year=first,
   reason='human_review_latched' if latched else 'benefit_gate_failed' if chosen is None else 'initial_allocation' if first==t else action,
   executed_target_change=action=='target_change',is_trade=T>F(1,10**10),recent_count=len(recent),
   prior_mass=15/(15+len(recent)),observed_max_drawdown_pct=observed,scores=scores))
  peak=max(peak,real_end);loss=max(loss,100*(1-real_end/peak))
  history.append(tuple((1+x)/(1+inf) for x in r));h,cpi=end,newcpi
 return ledger,reviews

def design_checks(e,p,config,doc):
 e.check('normative targets',TARGETS,{n:tuple(map(F,map(str,p.TARGETS[n]))) for n in TARGETS},scope='design',abs_tol=1e-15)
 constants={'gamma':4,'fee_buffer_multiplier':2,'decision_epsilon':1e-12,'trade_amount_epsilon':1e-10,
 'prior_equivalent_years':15,'history_window':5,'adaptive_min_completed_years':5,'review_drawdown_pct':25}
 e.check('unchanged normative constants',constants,{k:config[k] for k in constants},scope='design',exact=True)
 e.check('full eligibility sets',{'A':['conservative'],'B':['conservative','balanced'],
  'C':['conservative','balanced','growth'],'D':['conservative','balanced'],'E':['conservative']},
  config['suitability']['eligible_classes_before_outcome_screens'],scope='design',exact=True)
 elig={}
 for name,profile in config['profiles'].items():
  cap=1 if profile['horizon']<=6 else 2 if profile['horizon']<20 else 3
  reserve=config['suitability']['minimum_target_bill'][profile['liquidity']]
  elig[name]=[n for n in ('conservative','balanced','growth')[:cap] if TARGETS[n][2]>=F(str(reserve))]
 e.check('independently intersect horizon and liquidity',config['suitability']['eligible_classes_before_outcome_screens'],elig,scope='design',exact=True)
 e.check('own horizons and tolerances',[[5,10],[15,25],[30,40],[25,15],[6,35]],
  [[x['horizon'],x['loss_tolerance_pct']] for x in config['profiles'].values()],scope='design',exact=True)
 e.check('personalized risk AND purchasing-power rescreen, referral no fallback',
  'refer_to_human_no_reselection; rescreen_risk_and_purchasing_power_at_own_horizon',config['suitability']['personalized_failure'],scope='design',exact=True)
 e.check('personalized rescreen required',True,config['suitability']['personalized_review_overlay_required_before_freeze'],scope='design',exact=True)
 sel=config['selection']
 e.check('fixed adaptive comparators',['balanced_context','balanced_cost'],sel['adaptive_comparators'],scope='design',exact=True)
 e.check('context comparator',['balanced_cost'],sel['context_comparators'],scope='design',exact=True)
 e.check('adaptive can qualify if context fails',True,sel['adaptive_eligible_when_context_fails'],scope='design',exact=True)
 e.check('primary separate from sensitivity',[.0025,'robustness_only_no_primary_retuning'],[sel['primary_selection_fee'],sel['doubled_fee_role']],scope='design',exact=True)
 a=[0,2,10];b=[1,0,11]
 stats=dict(median_paired=median([x-y for x,y in zip(a,b)]),difference_of_medians=median(a)-median(b),
  marginal_p10_difference=quantile(a,F(1,10))-quantile(b,F(1,10)),paired_p10=quantile([x-y for x,y in zip(a,b)],F(1,10)),
  marginal_p90_difference=quantile(a,F(9,10))-quantile(b,F(9,10)),paired_p90=quantile([x-y for x,y in zip(a,b)],F(9,10)))
 e.check('D2 synthetic paired versus marginal facts',dict(median_paired=-1,difference_of_medians=1,
  marginal_p10_difference=.2,paired_p10=-1,marginal_p90_difference=-.6,paired_p90=1.4),stats,scope='oracle_fixture')
 # Exact rational boundary facts: zero fold median does not count.
 direct=dict(gain=F(1,10),tail_growth_difference=-F(1,10),tail_loss_difference=F(1),positive_fold_count=3)
 passes=lambda z:z['gain']>=F(1,10) and z['tail_growth_difference']>=-F(1,10) and z['tail_loss_difference']<=1 and z['positive_fold_count']>=3
 e.check('inclusive promotion boundaries',True,passes(direct),scope='design',exact=True)
 e.check('fold zero excluded',3,sum(x>0 for x in (F(1,10),F(1,10),F(1,10),F(0))),scope='design',exact=True)
 choose_policy=lambda ctx,ac,af:'balanced_adaptive' if ac and af else 'balanced_context' if ctx else 'balanced_cost'
 e.check('context failure does not disqualify dual-pass adaptive','balanced_adaptive',choose_policy(False,True,True),scope='design',exact=True)
 e.check('both direct controls mandatory',['balanced_cost','balanced_cost'],[choose_policy(False,True,False),choose_policy(False,False,True)],scope='design',exact=True)
 # Text is reviewed as a contract. These clauses bind future implementations;
 # these oracle fixtures do not claim a production selector already exists.
 for name,phrase in [('marginal tails','marginal linear quantiles'),('strict fold','strictly positive median_s'),
  ('complete screens','Show all candidates, exclusions and reason codes'),('no fallback','no automatic reselection'),
  ('sampling limitations','not significance tests'),('unchanged baselines','Preserve the three existing pilot baselines unchanged')]:
  e.check('v2 clause '+name,True,phrase in doc,scope='design',exact=True)
 return normalized(stats)

def collect():
 p,b,source,imports=bind_sources(); e=Evidence();config=json.loads(blob(BASE,'specs/development_policy_pilot_v2.json'))
 doc=blob(BASE,'specs/DEVELOPMENT_POLICY_PILOT_V2.md').decode();stats=design_checks(e,p,config,doc)
 e.check('module constants',[4,1e-12,1e-10,15,5],[p.GAMMA,p.EPSILON,p.TRANSFER_EPSILON,p.PRIOR_STRENGTH,p.WINDOW],exact=True)
 baseprior=((1.10,1.02,1.),)
 prior=p.EmpiricalPrior(baseprior)
 result,reviews=toy_run(p,rows(1,(.1,.02,0)))
 expected_score=score(TARGETS['balanced'],(0,0,1),baseprior,(),.0025)
 e.check('rational initial score',expected_score,{k:getattr(reviews[0].scores[0],k) for k in expected_score},abs_tol=1e-13)
 exact=dict(transfer=F(200,3),fee=F(1,6),each_post_fee=F(599,18),wealth_end=F(7787,75),buffered=F(3887,3750),actual_ce=F(7787,7500))
 observed=dict(transfer=result.ledger[0].intended_transfer,fee=result.ledger[0].fee,
  each_post_fee=result.ledger[0].holdings_after_fee[0],wealth_end=result.ledger[0].wealth_end,
  buffered=reviews[0].scores[0].conservative_score,actual_ce=reviews[0].scores[0].true_net_ce)
 e.check('rational initial actual versus buffer',exact,observed,abs_tol=1e-12)
 e.check('exact inflation factors',[F(55,51),F(1),F(50,51)],p.real_gross((.1,.02,0),.02),abs_tol=1e-15)
 multi=((.78,1.04,1.01),(1.37,.96,1.03),(1.02,1.12,.99))
 recent=((.9,1.03,.98),(1.15,.95,1.04),(1.01,1.1,1.02),(.88,1.08,1.05),(1.22,1.03,1.))
 for n in range(6):
  for name,w in TARGETS.items():
   expected=ce(w,multi,recent[:n]);observed_ce=p.EmpiricalPrior(multi).certainty_equivalent(tuple(map(float,w)),recent[:n])
   e.check('inverse cube 15:n n='+str(n)+' '+name,expected,observed_ce,rel=3e-13,abs_tol=1e-14)
   for fee in (0.,.0025,.005):
    actual=p.score_target(name,tuple(map(float,w)),(.1,.2,.7),p.EmpiricalPrior(multi),recent[:n],fee)
    ex=score(w,(.1,.2,.7),multi,recent[:n],fee)
    e.check('all-target score n='+str(n)+' '+name+' fee='+str(fee),ex,{k:getattr(actual,k) for k in ex},rel=3e-12,abs_tol=2e-14)
 for scale in (5e-324,1e-300,1e-100,1.,1e100,1e300,1.7976931348623157e308):
  try:actual=p.EmpiricalPrior(((scale,scale,scale),)).certainty_equivalent((.2,.3,.5))
  except (ValueError,OverflowError) as exc:actual=type(exc).__name__+': '+str(exc)
  e.check('finite extreme constant '+str(scale),scale,actual,rel=3e-12,abs_tol=0)
 mix=((1e-300,1e300,1.),(1e300,1e-300,1.))
 e.check('finite extreme heterogeneous support',ce((.2,.3,.5),mix),p.EmpiricalPrior(mix).certainty_equivalent((.2,.3,.5)),rel=3e-12,abs_tol=0)
 failures={}
 for name,fn in [
  ('empty prior',lambda:p.EmpiricalPrior(())),('zero gross',lambda:p.EmpiricalPrior(((1.,0.,1.),))),
  ('nan prior',lambda:p.EmpiricalPrior(((1.,float('nan'),1.),))),('infinite prior',lambda:p.EmpiricalPrior(((1.,float('inf'),1.),))),
  ('negative gross',lambda:p.EmpiricalPrior(((-1.,1.,1.),))),('too much history',lambda:prior.certainty_equivalent((.2,.3,.5),((1,1,1),)*6)),
  ('nonfinite score inputs',lambda:p.score_target('x',(.2,.3,.5),(0,0,1),prior,(),float('inf'))),
  ('invalid final overflow real factor',lambda:p.real_gross((1e308,1,1),-1+2**-52))]:
  failures[name]=e.rejects(name,fn)
 # Selection fixtures only inject scores; production choose_target is exercised.
 seed=p.score_target('balanced',p.TARGETS['balanced'],(0,0,1),prior,(),.0025)
 cases=[('ineligible active',[('balanced',1+.75e-12),('defensive',1+1.5e-12)],1.,'defensive'),
 ('nontransitive chain',[('balanced',1.02),('defensive',1.02+.75e-12),('growth_tilt',1.02+1.5e-12)],1.,'defensive'),
 ('active wins max anchored tie',[('growth_tilt',1.02),('defensive',1.02+.5e-12),('balanced',1.02+.7e-12)],1.,'growth_tilt'),
 ('defensive priority',[('defensive',1.02),('balanced',1.02+.2e-12),('growth_tilt',1.02+.3e-12)],1.,'defensive'),
 ('central priority',[('balanced',1.02),('growth_tilt',1.02+.2e-12)],1.,'balanced')]
 hurdle=1+1e-12
 for tag,value,want in [('below',math.nextafter(hurdle,-math.inf),None),('equal',hurdle,None),('above',math.nextafter(hurdle,math.inf),'balanced')]:
  cases.append(('strict boundary '+tag,[('balanced',value)],1.,want))
 for tag,pairs,keep,want in cases:
  s=tuple(replace(seed,name=n,conservative_score=v) for n,v in pairs);chosen=p.choose_target(s,keep)
  actual=None if chosen is None else chosen.name
  e.check('D1 injected-score fixture '+tag,want,actual,exact=True)
  e.check('D1 independent filter/max oracle '+tag,want,choose(pairs,keep),scope='oracle_fixture',exact=True)
  e.check('D1 final chosen strict hurdle '+tag,True,chosen is None or chosen.conservative_score>keep+1e-12,exact=True)
 data=rows(30)
 for j,row in enumerate(data):
  row.update(equity_return=(.14,-.12,.06,.20,-.04)[j%5],bond_return=(.03,.01,-.02)[j%3],
   bill_proxy_return=.012,inflation=(.02,.035,.01)[j%3])
 # Full rational scalar paths are independent of production decisions.
 for mode in MODES:
  for fee in (0.,.0025,.005):
   full,rev=toy_run(p,data,mode,fee=fee,prior=multi)
   expected_l,expected_r=oracle_path(data,mode,multi,fee,25)
   for t,(el,er,al,ar) in enumerate(zip(expected_l,expected_r,full.ledger,rev),1):
    tag=mode+' fee='+str(fee)+' t='+str(t)
    e.check('independent CPI/holdings/fee '+tag,el,{k:getattr(al,k) for k in el},abs_tol=1e-9,rel=1e-10)
    statekeys=[k for k in er if k not in ('scores','observed_max_drawdown_pct','prior_mass')]
    e.check('independent state/action '+tag,{k:er[k] for k in statekeys},{k:getattr(ar,k) for k in statekeys},exact=True)
    e.check('independent prior/DD '+tag,{k:er[k] for k in ('observed_max_drawdown_pct','prior_mass')},
     {k:getattr(ar,k) for k in ('observed_max_drawdown_pct','prior_mass')},abs_tol=1e-10)
    e.check('independent scores '+tag,er['scores'],{s.name:{k:getattr(s,k) for k in er['scores'][s.name]} for s in ar.scores},abs_tol=1e-12)
    e.check('observer engine fee agreement '+tag,[al.intended_transfer,al.fee],[ar.intended_transfer,ar.actual_fee],exact=True)
   for h in range(1,31):
    short,sr=toy_run(p,data[:h],mode,fee=fee,prior=multi)
    e.check('all horizon prefix '+mode+' fee='+str(fee)+' H='+str(h),True,short.ledger==full.ledger[:h] and sr==rev[:h],exact=True)
   changed=[dict(x) for x in data]
   for row in changed[5:]:row.update(equity_return=-.55,bond_return=.3,bill_proxy_return=-.1,inflation=.4)
   pert,pr=toy_run(p,changed,mode,fee=fee,prior=multi)
   e.check('current/future perturbation boundary '+mode+' '+str(fee),True,rev[:6]==pr[:6] and full.ledger[:5]==pert.ledger[:5] and full.ledger[5].decision==pert.ledger[5].decision,exact=True)
   again,ag=toy_run(p,data,mode,fee=fee,prior=multi)
   e.check('fresh repeat state '+mode+' '+str(fee),True,again==full and ag==rev,exact=True)
 # Adaptive opening, no gate bypass, deferred allocation retry diagnostics.
 _,ar=toy_run(p,rows(8),'balanced_adaptive',prior=((1.3,1.02,1.),))
 e.check('adaptive year-6 alternatives',[1,1,1,1,1,3,3,3],[len(v.scores) for v in ar],exact=True)
 e.check('adaptive first change at year 6','target_change',ar[5].action,exact=True)
 e.check('adaptive active-first deduplicated next review',['growth_tilt','defensive','balanced'],[s.name for s in ar[6].scores],exact=True)
 for mode in MODES:
  for fee in (0.,.0025,.005):
   result,rv=toy_run(p,rows(8,(.02,.02,.02)),mode,prior=((1.02,1.02,1.02),),fee=fee)
   e.check('flat support no deployment '+mode+' '+str(fee),True,all(v.action=='keep' and v.first_deployment_year is None and v.initial_allocation_deferred and not v.executed_target_change for v in rv),exact=True)
   e.check('flat support exact keep '+mode+' '+str(fee),True,all(x.holdings_after_fee==x.holdings_before and x.fee==0 for x in result.ledger),exact=True)
 delayed=rows(4);delayed[0]['equity_return']=1.
 dr,dv=toy_run(p,delayed,'balanced_context',prior=((1.,1.,1.),))
 e.check('deferred first deployment separate persistent flag',[None,2,2,2],[x.first_deployment_year for x in dv],exact=True)
 e.check('deferred flag historical',[True]*4,[x.initial_allocation_deferred for x in dv],exact=True)
 e.check('late first deployment reason','initial_allocation',dv[1].reason,exact=True)
 e.check('postdeployment reason not initial again',True,all(x.reason in ('rebalance','benefit_gate_failed','target_change') for x in dv[2:]),exact=True)
 # Real score-gate tiny target change: nominal contraction exactly matched by
 # deflation preserves real information. No injected scores/decisions here.
 tiny=rows(8)
 for key in ('equity_return','bond_return','bill_proxy_return','inflation'):tiny[0][key]=-1+1e-13
 tr,tv=toy_run(p,tiny,'balanced_adaptive',prior=((1.3,1.02,1.),))
 v=tv[5];entry=tr.ledger[5];tinyfacts=asdict(v)
 e.check('REAL tiny target change action/state',['target_change','balanced','growth_tilt',True,False],
  [v.action,v.active_before,v.active_after,v.executed_target_change,v.is_trade],exact=True)
 e.check('REAL tiny target change strictly passing score',True,next(s for s in v.scores if s.name==v.selected_target).conservative_score>v.ce_keep+1e-12,exact=True)
 e.check('REAL tiny positive exact fee',True,0<entry.intended_transfer<1e-10 and entry.fee==.0025*entry.intended_transfer and entry.fee>0,exact=True)
 e.check('REAL tiny executed holdings differ',True,entry.holdings_after_fee!=entry.holdings_before,exact=True)
 e.check('REAL tiny first deployment remains year 1',1,v.first_deployment_year,exact=True)
 e.check('REAL tiny next review active state','growth_tilt',tv[6].active_before,exact=True)
 tl,to=oracle_path(tiny,'balanced_adaptive',((1.3,1.02,1.),),.0025,25)
 e.check('REAL tiny independent transfer/fee',dict(T=tl[5]['intended_transfer'],fee=tl[5]['fee']),dict(T=entry.intended_transfer,fee=entry.fee),rel=2e-11,abs_tol=1e-26)
 # Post-fee observation must survive recovery within the same year.
 rr,rv=toy_run(p,rows(5,(.5,.5,.5)),threshold=.1)
 e.check('fee loss then same-year recovery',[F(1,6),True,'human_review'],[rv[1].observed_max_drawdown_pct,rr.ledger[0].real_wealth_end>100,rv[1].action],abs_tol=1e-11)
 e.check('fee-loss latch persistence',True,all(x.action=='human_review' for x in rv[1:]),exact=True)
 infdata=rows(5);infdata[0]['inflation']=.5;infdata[1].update(equity_return=2.,bond_return=2.,bill_proxy_return=2.)
 for fee in (0.,.0025,.005):
  ir,iv=toy_run(p,infdata,fee=fee)
  e.check('pure inflation latch next year '+str(fee),['rebalance','human_review','human_review','human_review','human_review'],[v.action for v in iv],exact=True)
  el,er=oracle_path(infdata,'balanced_cost',baseprior,fee,25)
  e.check('pure inflation independent max loss '+str(fee),[x['observed_max_drawdown_pct'] for x in er],[x.observed_max_drawdown_pct for x in iv],abs_tol=1e-10)
  e.check('pending exact component dollars and zero fees '+str(fee),True,all(x.holdings_after_fee==x.holdings_before and x.fee==0 and x.intended_transfer==0 for x in ir.ledger[1:]),exact=True)
  e.check('pending retains return exposure '+str(fee),True,ir.ledger[1].holdings_end!=ir.ledger[1].holdings_after_fee,exact=True)
 # No current observations: only metadata can be inspected before callback.
 flags={}
 class Guard(dict):
  def __getitem__(self,k):
   if k in ('equity_return','bond_return','bill_proxy_return','inflation') and not flags.get(self['period']):
    raise RuntimeError('current observation read before decision')
   return super().__getitem__(k)
 cb=p.CostAwarePolicy('balanced_adaptive',prior)
 def guarded(ctx):
  e.check('context contains exact t-1 history '+str(ctx.period),ctx.period-1,len(ctx.history),exact=True)
  e.check('context has no current outcome fields '+str(ctx.period),['history','holdings','period','scenario_id'],sorted(vars(ctx)),exact=True)
  decision=cb(ctx);flags[ctx.period]=True;return decision
 b.simulate_policy([Guard(x) for x in rows(8)],horizon=8,split='synthetic',callback=guarded)
 # State reuse, wrong scenario/history, wrong fee and immutable prefix.
 def callback():return p.CostAwarePolicy('balanced_context',prior)
 fresh=b.DecisionContext(9001,1,(0.,0.,100.),())
 q=callback();q(fresh)
 failures['state reuse']=e.rejects('same state reused at period 1',lambda:q(fresh))
 failures['skip review']=e.rejects('skipped review',lambda:q(b.DecisionContext(9001,3,q._after,())))
 failures['wrong scenario']=e.rejects('wrong scenario',lambda:q(b.DecisionContext(9002,2,q._after,(b.Observation(9002,1,(0.,0.,0.),0.),))))
 failures['wrong period']=e.rejects('wrong history ordering',lambda:q(b.DecisionContext(9001,2,q._after,(b.Observation(9001,2,(0.,0.,0.),0.),))))
 failures['wrong holdings']=e.rejects('holdings disagree with prior fee',lambda:q(b.DecisionContext(9001,2,(0.,0.,100.),(b.Observation(9001,1,(0.,0.,0.),0.),))))
 obs=b.Observation(9001,1,(0.,0.,0.),0.)
 q(b.DecisionContext(9001,2,q._after,(obs,)))
 altered=b.Observation(9001,1,(.1,0.,0.),0.)
 failures['mutated prefix']=e.rejects('completed history mutation',lambda:q(b.DecisionContext(9001,3,q._after,(altered,b.Observation(9001,2,(0.,0.,0.),0.)))))
 q=callback()
 failures['engine fee mismatch']=e.rejects('observer versus engine fee mismatch',lambda:b.simulate_policy(rows(3),horizon=3,split='synthetic',callback=q,fee_rate=.005))
 original=[1.,1.02,1.03];ep=p.EmpiricalPrior([original]);original[0]=99.
 e.check('prior copies mutable inputs',1.,ep.gross[0][0],exact=True)
 mutable=[0.,0.,0.];captured=[]
 b.decide_from_history(lambda ctx:(captured.append(ctx) or b.Decision('keep')),scenario_id=9001,period=2,
  holdings=[0.,0.,100.],history=[b.Observation(9001,1,mutable,0.)]);mutable[0]=1.
 e.check('engine copies nested history returns',0.,captured[0].history[0].returns[0],exact=True)
 for key,bad in [('equity_return',-1.),('bond_return',float('nan')),('bill_proxy_return',float('inf')),('inflation',-1.)]:
  badrows=rows(2);badrows[-1][key]=bad
  failures['invalid final '+key]=e.rejects('invalid final observation '+key,lambda data=badrows:toy_run(p,data))
  suspended=rows(3);suspended[0]['inflation']=.5;suspended[-1][key]=bad
  failures['invalid suspended final '+key]=e.rejects('invalid final during suspension '+key,lambda data=suspended:toy_run(p,data))
 # Preserve genuine policy failures separately from audit integrity failures.
 design_bad=[c['name'] for c in e.checks if not c['passed'] and c['scope']=='design']
 code_bad=[c['name'] for c in e.checks if not c['passed'] and c['scope']=='kernel']
 oracle_bad=[c['name'] for c in e.checks if not c['passed'] and c['scope']=='oracle_fixture']
 if oracle_bad:raise RuntimeError('Independent fixture arithmetic error: '+', '.join(oracle_bad))
 return dict(schema_version=1,task_id='SOL-013',base_commit=BASE,immutable_task_commit=TASK_COMMIT,
  immutable_task_sha256=TASK_HASH,source_sha256=source,imported_code_sha256=imports,
  hash_basis='Exact pinned Git blobs compiled in memory; artifact text SHA256 after CRLF-to-LF only; HEAD is unconstrained.',
  python_major_minor='3.12',corrected_design_verdict='changes_required' if design_bad else 'approve',
  code_verdict='changes_required' if code_bad else 'approve',design_failures=design_bad,code_failures=code_bad,
  checks=e.checks,numerical_highlights=dict(initial=normalized(exact),actual_initial=observed,
  D2_statistics=stats,real_tiny_target_change=tinyfacts),invalid_failed_run_diagnoses=failures,
  limitations=['No production loader, writer, selector, calibration provenance or final API is certified.',
   'No competition outcomes read; no HY3-003 rerun or actual strategy outcomes.',
   'Injected score fixtures test tie/threshold mechanics only; tiny target-change fixture uses the REAL score gate.',
   'Normative assumptions and personalized own-horizon follow-up remain to be evaluated; design closure is not performance approval.'])

def write_exclusive(path,text):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('x',encoding='utf-8',newline='\n') as f:f.write(text)
def hashes(directory):
 return {p.relative_to(directory).as_posix():digest(canonical(p.read_bytes())) for p in sorted(directory.rglob('*')) if p.is_file() and p.name!='verification.json'}
def check_saved(file,artifact_dir):
 saved=json.loads(file.read_text(encoding='utf-8'));actual=collect()
 if not equal(saved['facts'],actual,rel=3e-12,abs_tol=1e-13):raise RuntimeError('Saved numerical/source evidence mismatch; read-only evidence preserved')
 if saved['artifact_sha256']!=hashes(artifact_dir):raise RuntimeError('Saved artifact hash mismatch; read-only evidence preserved')
 return actual

def findings(facts):
 return dict(schema_version=1,task_id='SOL-013',base_commit=BASE,source_sha256=SOURCES,
  corrected_design_verdict=facts['corrected_design_verdict'],code_verdict=facts['code_verdict'],
  blockers=facts['design_failures']+facts['code_failures'],
  exact_fixes=[] if not facts['code_failures'] else ['See failed expected/observed checks in verification.json; coordinator must fix source in a separate task.'],
  design_closure={
   'D1':'Eligible-first filtering, maximum-anchored epsilon ties, active/defensive/central/growth priority and final strict hurdle close both concrete ambiguities.',
   'D2':'Paired median and fold medians; marginal Q10/Q90 differences; fixed adaptive controls [balanced_context, balanced_cost], both required even if context promotion fails; primary and sensitivity separate.',
   'L1':'Gamma, targets and buffer remain normative; pooled marginal/myopic CE and exchangeability/dependence caveats explicit.',
   'L2':'Own horizons and intersected horizon/liquidity eligibility A/E=C; B/D=C,B; C=C,B,G explicit.',
   'L3':'Inclusive risk, p10 growth and indifference screens; all exclusions, denominator, severe loss and reasons required; no guarantee.',
   'L4':'Own-tolerance suspension rerun AND risk/purchasing-power rescreen at own horizon, failed class referred without reselection/fallback.',
   'L5':'Fold-exclusion/immutable calibration requirements retained; kernel timing independently tested, calibration implementation outside scope.',
   'L6':'All sixteen mode/fee cases, direct comparisons and failed trials retained; doubled fee cannot retune primary.',
   'L7':'Tiny requests execute with exact positive fee and active-state change independent of reporting epsilon; first deployment/year-1 deferred flag separated.',
   'L8':'Sequential observer matches independent rational CPI, holdings, fees and post-fee/year-end peaks; production adapters remain separate.'},
  numerical_highlights=facts['numerical_highlights'],invalid_failed_run_diagnoses=facts['invalid_failed_run_diagnoses'],
  limitations=facts['limitations'],negative_verdict_is_evidence_failure=False)

def review_text(facts):
 tiny=facts['numerical_highlights']['real_tiny_target_change']
 return f'''# SOL-013 independent corrected-design and kernel review

Corrected design: **{facts['corrected_design_verdict']}**. Kernel: **{facts['code_verdict']}**.
Reviewed base: {BASE}; exact eleven requested source SHA256 values are in findings.json
and verification.json. The immutable successor task is pinned at {TASK_COMMIT}.
SOL-009 remains accepted negative evidence; cancelled SOL-011 was not executed.
Current v2 prevails over historical prototype prose. This review grants no production
execution, customer recommendation or final-data authorization.

D1 is closed: discard targets failing S > keep + 1e-12, anchor ties to the eligible
maximum and use active, defensive, central, growth priority. Ineligible-active,
nontransitive-chain, nextafter boundary and near-tie fixtures independently challenge
choose_target. The final strict hurdle is checked on every chosen fixture.
D2 is closed: gain and folds use paired differences, tails use differences of marginal
quantiles. Synthetic permutations produce different statistics; full signed facts are
recorded. Adaptive must directly pass both balanced_context and balanced_cost, including
when context fails promotion. Inclusive numerical gates and strictly positive folds
are explicit. Primary selection at .0025 and doubled-fee robustness remain separate.
These are design/oracle checks; a production selector does not yet exist.

L1-L8 are resolved for this narrow contract. Targets, gamma=4, buffer=2, 15: n mixture,
five-year history, four folds, 25% generic latch and promotion thresholds are unchanged.
Own-horizon eligibility is A/E={{Conservative}}, B/D={{Conservative,Balanced}},
C={{Conservative,Balanced,Growth}}. A provisional customer rule requires its own loss-
tolerance overlay AND risk/purchasing-power rescreen at its own horizon. Failure means
referral without reselection or fallback. Complete exclusions and tail facts remain
required. These are normative service assumptions, not guarantees or optimized targets.
Calibration provenance, personalized outcomes and output integration are separate work.

The independent oracle uses Fraction inverse-cube moments and an 80-digit Decimal cube
root. It never calls production CE/score/accounting helpers for expected values.
For all-bills to thirds at k=.0025 and prior (1.10,1.02,1), T=200/3, fee=1/6,
post-fee holdings each 599/18, CE_target=26/25, buffered score=3887/3750,
true net CE=7787/7500 and actual year-end wealth=7787/75. Only the actual fee is charged.
All targets, n=0..5 and zero/primary/doubled fees are compared independently.
Finite subnormal through maximum-float constant gross factors and heterogeneous
extreme factors are probed; invalid/nonfinite observations fail, including the final
observation of a suspended path. Rejected inputs produce diagnoses, never completed
imputed outcomes. Valid suspended paths continue earning returns with exact dollar keep.

All five modes and three fees have independently reconstructed 30-year synthetic
holdings, CPI, fees, actions, scores and maximum real losses. All H=1..30 prefixes,
current/future perturbations, fresh-state repeats, sequential reuse, changed history,
wrong scenarios/holdings/fees, input copies and guarded no-current-observation access
are checked. Adaptive alternatives first appear in year 6. Fee-induced loss followed
by same-year recovery still latches next year; pure-inflation loss and later recovery
preserve the latch. Pending reviews preserve component dollars and charge zero fees,
including at zero fee. Initial deferred allocation is a persistent year-1 flag;
first deployment is independently null or its accepted positive-transfer year.
A late first deployment has reason initial_allocation, later requests use their action.

The real tiny-transfer case uses a year-1 nominal contraction matched by deflation,
so real factors remain valid. At year 6 the actual score gate selects growth_tilt:
T={tiny['intended_transfer']:.17g}, fee={tiny['actual_fee']:.17g},
is_trade={tiny['is_trade']}, executed_target_change={tiny['executed_target_change']}.
State advances to growth_tilt and the exact positive fee is charged. No injected decision
is used for this corner. Separate injected-score fixtures are labelled and only prove
selection mechanics. Reporting epsilon never cancels an accepted request.

Evidence is generated exclusively and refuses overwrite. --check recompiles the exact
pinned Git blobs in memory, verifies imported byte hashes, recomputes all facts, checks
artifact hashes and numerical tolerances, and writes nothing. Artifact text hashes
normalize CRLF to LF only for cross-checkout portability; source hashes use exact blobs.
HEAD need not remain a worker commit. Deliberate scratch numerical/source/artifact
corruption is rejected; a harmless rounding variant is accepted. Failures and diagnoses
are preserved under history/. A supported negative verdict is not an integrity failure.

No original/development/final CSV outcomes were opened, no HY3 experiment rerun, no
installs, source edits, task changes, watchers, commits or pushes were performed.
The chief's seventeen provisional tests are read as source, not used as independent evidence.
'''

def create():
 for name in ('review.md','findings.json','verification.json'):
  if (OUT/name).exists():raise RuntimeError('Refusing overwrite: '+name)
 facts=collect()
 write_exclusive(OUT/'findings.json',dump(findings(facts)))
 write_exclusive(OUT/'review.md',review_text(facts))
 preliminary=dict(schema_version=1,facts=facts,artifact_sha256=hashes(OUT))
 selftests=[]
 with tempfile.TemporaryDirectory(prefix='SOL-013-integrity-') as td:
  scratch=Path(td);candidate=scratch/'candidate.json';candidate.write_text(dump(preliminary),encoding='utf-8')
  variants=[('clean',None,0),('corrupt numerical fact','number',1),('corrupt source hash','source',1),('rounding within tolerance','round',0)]
  for name,mutation,want in variants:
   v=json.loads(dump(preliminary))
   change=None
   if mutation in ('number','round'):
    check=next(c for c in v['facts']['checks'] if c['name']=='rational initial actual versus buffer')
    old=check['observed']['fee'];check['observed']['fee']+=.01 if mutation=='number' else 1e-15
    change=dict(path='facts.checks[rational initial actual versus buffer].observed.fee',before=old,after=check['observed']['fee'])
   elif mutation=='source':
    key=next(iter(v['facts']['source_sha256']));old=v['facts']['source_sha256'][key];v['facts']['source_sha256'][key]='0'*64
    change=dict(path='facts.source_sha256.'+key,before=old,after='0'*64)
   candidate.write_text(dump(v),encoding='utf-8');before=digest(candidate.read_bytes());artifact_before=hashes(OUT)
   proc=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--check','--evidence',str(candidate)],cwd=ROOT,capture_output=True,text=True)
   selftests.append(dict(name=name,expected_exit=want,observed_exit=proc.returncode,mutation=change,
    stdout=proc.stdout,stderr=proc.stderr,read_only=before==digest(candidate.read_bytes()) and artifact_before==hashes(OUT)))
  copied=scratch/'artifacts';shutil.copytree(OUT,copied)
  target=copied/'review.md';target.write_text(target.read_text(encoding='utf-8')+'\nCORRUPTED\n',encoding='utf-8')
  candidate.write_text(dump(preliminary),encoding='utf-8');artifact_before=hashes(copied)
  proc=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--check','--evidence',str(candidate),'--artifact-dir',str(copied)],cwd=ROOT,capture_output=True,text=True)
  selftests.append(dict(name='corrupt artifact',expected_exit=1,observed_exit=proc.returncode,
   mutation='append CORRUPTED to scratch review.md',stdout=proc.stdout,stderr=proc.stderr,read_only=artifact_before==hashes(copied)))
 write_exclusive(OUT/'history/integrity-self-tests.json',dump(selftests))
 if any(t['observed_exit']!=t['expected_exit'] or not t['read_only'] for t in selftests):
  raise RuntimeError('Self-test failure preserved; final verification not created')
 write_exclusive(OUT/'verification.json',dump(dict(schema_version=1,facts=facts,artifact_sha256=hashes(OUT))))
 print(json.dumps(dict(created=True,check_count=len(facts['checks']),corrected_design_verdict=facts['corrected_design_verdict'],code_verdict=facts['code_verdict'],integrity_self_tests=len(selftests))))

def main():
 ap=argparse.ArgumentParser();group=ap.add_mutually_exclusive_group(required=True)
 group.add_argument('--create',action='store_true');group.add_argument('--check',action='store_true')
 ap.add_argument('--evidence',type=Path,default=OUT/'verification.json')
 ap.add_argument('--artifact-dir',type=Path,default=OUT)
 args=ap.parse_args()
 if args.create:create()
 else:
  facts=check_saved(args.evidence,args.artifact_dir)
  print(json.dumps(dict(evidence_integrity_verdict='passed',corrected_design_verdict=facts['corrected_design_verdict'],code_verdict=facts['code_verdict'],check_count=len(facts['checks']),read_only=True)))
if __name__=='__main__':
 try:main()
 except Exception as exc:
  print(type(exc).__name__+': '+str(exc),file=sys.stderr);sys.exit(1)
