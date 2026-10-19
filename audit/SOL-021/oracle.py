"""Unchanged named independent helpers extracted from pinned historical Git blobs.
No historical boundary or verification entry point is present. See oracle-provenance.json.
"""
from decimal import Decimal, localcontext
from fractions import Fraction as F

def decimal_ce(weights,prior,recent=()):
 """Exact rational weighted gross and inverse-cube moment; independent roots.

 No production arithmetic/logs/helpers. 160/240 significant-digit convergence
 must produce the identical rounded binary64 expected value.
 """
 w=tuple(F(x) for x in weights);total=sum(w);w=tuple(x/total for x in w)
 gross=lambda row: sum(a*F(b) for a,b in zip(w,row))
 # Constant portfolio support has an exact rational CE. Avoid approximating
 # the -1/3 power at binary64 rounding midpoints such as 2.5 minimum units.
 support=[gross(row) for row in (*prior,*recent)]
 if all(x==support[0] for x in support): return float(support[0])
 moment=(15*sum(gross(row)**-3 for row in prior)/len(prior)+sum(gross(row)**-3 for row in recent))/(15+len(recent))
 results=[]
 for precision in (160,240):
  with localcontext() as ctx:
   ctx.prec=precision
   value=(Decimal(moment.numerator)/Decimal(moment.denominator))**(-Decimal(1)/Decimal(3))
   results.append(float(value))
 if results[0]!=results[1]: raise RuntimeError('Oracle precision did not converge')
 return results[1]

TARGETS = {
 'conservative': (F(15,100), F(20,100), F(65,100)),
 'balanced': (F(1,3),)*3,
 'growth': (F(60,100),F(30,100),F(10,100)),
 'defensive': (F(20,100),F(25,100),F(55,100)),
 'growth_tilt': (F(45,100),F(30,100),F(25,100)),
}

MODES = {'conservative_cost':'conservative','balanced_cost':'balanced',
 'growth_cost':'growth','balanced_context':'balanced','balanced_adaptive':'balanced'}

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
