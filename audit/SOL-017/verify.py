"""SOL-017 bounded independent K1 review; Python 3.12, synthetic, CPU only.

The exact historical SOL-013 module is loaded unchanged for named scalar helper
reuse. Its bind_sources/collect/create/check functions are NEVER called or patched.
This review has its own task and new-source boundary. --check writes nothing.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict, replace
from decimal import Decimal, localcontext
from fractions import Fraction as F
import hashlib
import itertools
import json
import math
from pathlib import Path
import subprocess
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'audit/SOL-017'
BASE = '315b7072e98f4d6aafd8573507074fc023477918'
TASK_COMMIT = '27c6c26effb14dd9148476d129248640df715947'
PRIOR_COMMIT = '1908813ef2627ca6e15591278ec15ccf2f9e9cff'
TASK_HASH = '323fb71bf92c8786dd9659e8021fdecc7f3b17fbac17208e8a7c77c49cea6019'
SOURCES = {
 'specs/PROBLEM_LOCK.md':'566c93ad1b5f79c9ec10a42725ab023953c9a02aeb1c91a459e740caf68c0e46',
 'specs/ACCOUNTING.md':'a9c3ab8dbba3ad752336642061ead272e2c196de83f73eb410e39bd5b559f71e',
 'specs/DEVELOPMENT_POLICY_PILOT_V2.md':'ada0257f813091a01526e497e28ca3871bf9b13afa98487708be17ae8249bcb1',
 'specs/development_policy_pilot_v2.json':'d7b20f38196831befc80dfdcc69c6653d1ae8352d1c87c79e19bcc09d5c84df3',
 'specs/POLICY_NUMERIC_K1.md':'72c056dff68ce6028cb1258cb8a23502eec1e9343696f52798fdbe9b875497ac',
 'src/safeinvest/policy_pilot.py':'9026abd22818fb420ce75dcf100b461c1833eab8be03526366dd3faadaa77bba',
 'tests/test_policy_pilot.py':'09cbe72579f46be55f8f2ecf8187127260ff414fd88834ed52bb6225212bdc95',
 'src/safeinvest/accounting.py':'0c73b143ed9755924be16d9c4fe9d9e8d8888931cb5c8a8c303434e2280389e5',
 'src/safeinvest/backtest.py':'bbe2e602124adf068da424df0a28c9f40f970f81c126bed393f61ebb25b244b6',
 'src/safeinvest/metrics.py':'efb7dad73e71515b9f164a95935231479ebca14b46c5b086a14de4bf5d38df9e',
 'audit/SOL-013/verify.py':'4ca6fb8069234543e165fde9b4a19c2bcd9480f0d07b87fdf446fad5be0a94bf',
 'audit/SOL-013/findings.json':'b2c82f41ed0abd7c62cf350ed5b554c967085d5cbbee70a3e62d4f6feb64c6bd',
 'audit/chief/SOL-013-review.json':'20923f671dd26e40be6e383f21398931eceac036d74c73c06fb8e48b9caaa462',
 'audit/chief/policy-k1-validation.json':'4f84abd57d5e08bbca544c70972db08b9056c87bcab9af65373e1cb6897dd00f',
}
REUSED = ['ce (80-digit Decimal; ordinary factors only)', 'score', 'choose',
          'oracle_path (tiny-transfer path only)', 'rows', 'toy_run', 'TARGETS']
LIMITATIONS = [
 'Synthetic kernel review only; no competition CSVs or outcomes read.',
 'No production loader, writer, calibration, selector or final-run certification.',
 'SOL-013 design approval is inherited, not a new parameter or performance review.',
 'Finite fixtures cannot prove correctly rounded CE for every binary64 input; numerical tolerances are explicit.',
 'Injected scores exercise strict hurdle/tie mechanics; the tiny transfer uses the actual CE gate.',
 'Chief tests are provisional provenance, not independent acceptance; chief accepts exact delivered evidence.',
]

def digest(raw): return hashlib.sha256(raw).hexdigest()
def canonical(raw): return raw.replace(b'\r\n', b'\n')
def dump(value): return json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n'
def blob(commit, path): return subprocess.check_output(['git','show',commit+':'+path], cwd=ROOT)
def task_digest(task): return digest(json.dumps(task,sort_keys=True,separators=(',',':')).encode())

def boundaries():
 if sys.version_info[:2] != (3,12): raise RuntimeError('Python 3.12 required')
 task=json.loads(blob(TASK_COMMIT,'ops/tasks/SOL-017.json'))
 if task_digest(task)!=TASK_HASH or task['id']!='SOL-017' or task['owner']!='sol' or task['attempt']!=1:
  raise RuntimeError('Immutable SOL-017 task mismatch')
 if task['base_commit']!=BASE or task['allowed_paths']!=['audit/SOL-017'] or task['parameters']['source_sha256']!=SOURCES:
  raise RuntimeError('Immutable base, scope or source map mismatch')
 local=ROOT/'.runtime/task.json'
 if local.exists():
  current=json.loads(local.read_text(encoding='utf-8-sig'))
  if current.get('id')=='SOL-017' and current!=task: raise RuntimeError('Local task mismatch')
 raw={name:blob(BASE,name) for name in SOURCES}
 for name,want in SOURCES.items():
  if digest(raw[name])!=want: raise RuntimeError('Pinned source mismatch: '+name)
 for name in ('audit/SOL-013/verify.py','audit/SOL-013/findings.json'):
  if blob(PRIOR_COMMIT,name)!=raw[name]: raise RuntimeError('Historical oracle provenance mismatch')
 old=json.loads(raw['audit/SOL-013/findings.json']);chief=json.loads(raw['audit/chief/SOL-013-review.json'])
 if (old['code_verdict'],old['corrected_design_verdict'],chief['decision'])!=('changes_required','approve','accept_review_evidence_only'):
  raise RuntimeError('Prior negative-evidence provenance mismatch')
 oracle=types.ModuleType('sol013_scalar_oracle');oracle.__file__=str(ROOT/'audit/SOL-013/verify.py')
 sys.modules[oracle.__name__]=oracle
 exec(compile(raw['audit/SOL-013/verify.py'],oracle.__file__,'exec'),oracle.__dict__)
 # Keep all old task/hash constraints unchanged; do not invoke its collector.
 if oracle.BASE!='7c804ffb960be6b9fadfc840e246ff060668a96d': raise RuntimeError('Old constraints changed')
 pkg=types.ModuleType('safeinvest');pkg.__path__=[];sys.modules['safeinvest']=pkg
 imported={}
 for short in ('accounting','metrics','backtest','policy_pilot'):
  path='src/safeinvest/'+short+'.py';code=raw[path]
  if digest(code)!=SOURCES[path]: raise RuntimeError('Imported code hash mismatch: '+path)
  mod=types.ModuleType('safeinvest.'+short);mod.__file__=BASE+':'+path;mod.__package__='safeinvest'
  sys.modules[mod.__name__]=mod;exec(compile(code,mod.__file__,'exec'),mod.__dict__)
  setattr(pkg,short,mod);imported[path]=digest(code)
 # Mathematical source outside log_power is byte-for-byte unchanged.
 prior=blob(PRIOR_COMMIT,'src/safeinvest/policy_pilot.py')
 def strip_log_power(b):
  start=b.index(b'        def log_power(row):');end=b.index(b'        prior_log_moment',start)
  return b[:start]+b[end:]
 if strip_log_power(prior)!=strip_log_power(raw['src/safeinvest/policy_pilot.py']):
  raise RuntimeError('Unexpected source change outside log_power')
 return pkg.policy_pilot,oracle,imported,raw

class Evidence:
 def __init__(self): self.checks=[]
 def check(self,name,expected,observed,rel=3e-12,exact=False):
  if exact: passed=type(expected)==type(observed) and expected==observed
  else: passed=isinstance(observed,(float,int)) and math.isfinite(observed) and math.isclose(float(expected),observed,rel_tol=rel,abs_tol=0.)
  self.checks.append(dict(name=name,expected=expected,observed=observed,passed=passed,
                          relative_tolerance=0. if exact else rel,absolute_tolerance=0.))
 def rejects(self,name,fn):
  try: fn()
  except (ValueError,OverflowError,TypeError) as exc: actual=type(exc).__name__+': '+str(exc)
  else: actual='UNEXPECTED ACCEPTANCE'
  self.check(name,True,actual!='UNEXPECTED ACCEPTANCE',exact=True)
  return actual

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

def collect():
 p,o,imports,raw=boundaries(); e=Evidence()
 config=json.loads(raw['specs/development_policy_pilot_v2.json'])
 constants={'gamma':4,'fee_buffer_multiplier':2,'decision_epsilon':1e-12,'trade_amount_epsilon':1e-10,
  'prior_equivalent_years':15,'history_window':5,'adaptive_min_completed_years':5,'review_drawdown_pct':25}
 e.check('unchanged config constants',constants,{k:config[k] for k in constants},exact=True)
 e.check('unchanged executable constants',[4.,1e-12,1e-10,15,5],[p.GAMMA,p.EPSILON,p.TRANSFER_EPSILON,p.PRIOR_STRENGTH,p.WINDOW],exact=True)
 e.check('unchanged fee rates',[.0025,.005],config['fee_rates'],exact=True)
 for name,w in o.TARGETS.items():
  for i,(want,got) in enumerate(zip(w,p.TARGETS[name])): e.check('unchanged target '+name+str(i),float(want),got,rel=2e-16)
 small=math.ulp(0.);normal=sys.float_info.min;big=sys.float_info.max
 weights=[(.2,.3,.5),(0.,0.,1.),(1/3,)*3,(.25,.25,.5),(small,.5,.5),(1e-300,.5,.5),(small,0.,1.)]
 scales=[small,2*small,16*small,1024*small,normal,math.nextafter(normal,0.),1e-300,1e-100,1.,1e100,1e300,big]
 for wi,w in enumerate(weights):
  for scale in scales:
   prior=((scale,)*3,)*3
   for n in range(6):
    recent=((scale,)*3,)*n;expected=decimal_ce(w,prior,recent)
    try: actual=p.EmpiricalPrior(prior).certainty_equivalent(w,recent)
    except (ValueError,OverflowError) as exc: actual=type(exc).__name__+': '+str(exc)
    e.check(f'constant w={wi} scale={scale.hex()} n={n}',expected,actual,exact=scale<=1024*small)
 # Heterogeneous rational dot products, mixed scales and tiny held weights.
 cases=[
  ('rational subnormal',(.25,.25,.5),((small,3*small,6*small),),((2*small,4*small,8*small),)*5),
  ('varying subnormal',(.2,.3,.5),((small,2*small,7*small),(9*small,4*small,2*small)),((3*small,5*small,11*small),)*5),
  ('zero weight enormous',(0.,.5,.5),((big,small,small),),((big,2*small,4*small),)*5),
  ('tiny weight dominant',(small,0.,1.),((big,normal,small),),((big/2,normal,2*small),)*5),
  ('tiny positive weight',(1e-300,.5,.5),((big,normal,small),(big/2,1e-300,normal)),((big/4,normal,small),)*5),
  ('full range',(.2,.3,.5),((small,normal,big),(big,small,normal),(normal,big,small)),((small,big,normal),(big,normal,small),(normal,small,big),(big/2,big/3,big/4),(small,small,small))),
  ('near maximum',(.25,.25,.5),((big,big/2,big/4),(big/2,big,big)),((big,big,big),)*5),
  ('K2 exact midpoint',(.25,.25,.5),((small,small,4*small),),((small,small,4*small),)*5),
  ('K2 exact midpoint downward',(.25,.25,.5),((small,3*small,5*small),),((small,3*small,5*small),)*5),
 ]
 for label,w,prior,recent in cases:
  for n in range(6):
   expected=decimal_ce(w,prior,recent[:n])
   try: actual=p.EmpiricalPrior(prior).certainty_equivalent(w,recent[:n])
   except (ValueError,OverflowError) as exc: actual=type(exc).__name__+': '+str(exc)
   e.check(label+' n='+str(n),expected,actual,exact=expected<=1024*small)
 # Bounded K1-specific challenge: exact heterogeneous subnormal dot products.
 # No production CE/log helper is used to obtain these Fraction expectations.
 grid_failures=[]
 for wi,w in enumerate(((.25,.25,.5),(0.,.5,.5),(.5,.5,0.),(.2,.3,.5))):
  fw=tuple(map(F,w));fw=tuple(x/sum(fw) for x in fw)
  for units in itertools.product(range(1,9),repeat=3):
   row=tuple(k*small for k in units)
   expected=float(sum(a*F(b) for a,b in zip(fw,row)))
   actual=p.EmpiricalPrior((row,)).certainty_equivalent(w)
   label=f'K2 subnormal grid w={wi} units={units}'
   e.check(label,expected,actual,exact=True)
   if expected!=actual: grid_failures.append(dict(weights=w,support_units=units,expected_hex=expected.hex(),observed_hex=actual.hex()))
 # Ordinary scalar fixture reuse, not a replay of old production bytes.
 multi=((.78,1.04,1.01),(1.37,.96,1.03),(1.02,1.12,.99))
 recent=((.9,1.03,.98),(1.15,.95,1.04),(1.01,1.1,1.02),(.88,1.08,1.05),(1.22,1.03,1.))
 for n in range(6):
  for name,w in o.TARGETS.items():
   prior=p.EmpiricalPrior(multi);fw=tuple(map(float,w))
   e.check('ordinary inverse cube '+name+' n='+str(n),o.ce(w,multi,recent[:n]),prior.certainty_equivalent(fw,recent[:n]),rel=3e-13)
   for fee in (0.,.0025,.005):
    expected=o.score(w,(.1,.2,.7),multi,recent[:n],fee)
    actual=p.score_target(name,fw,(.1,.2,.7),prior,recent[:n],fee)
    for key,want in expected.items(): e.check(f'ordinary score {name} n={n} k={fee} {key}',want,getattr(actual,key))
 result,reviews=o.toy_run(p,o.rows(1,(.1,.02,0.)))
 initial_exact={'transfer':F(200,3),'fee':F(1,6),'each_post_fee':F(599,18),'buffered':F(3887,3750),'wealth_end':F(7787,75),'true_net_ce':F(7787,7500)}
 entry=result.ledger[0];score=reviews[0].scores[0]
 initial_actual=dict(transfer=entry.intended_transfer,fee=entry.fee,each_post_fee=entry.holdings_after_fee[0],buffered=score.conservative_score,wealth_end=entry.wealth_end,true_net_ce=score.true_net_ce)
 for key,want in initial_exact.items(): e.check('rational initial '+key,float(want),initial_actual[key],rel=5e-15)
 e.check('buffer separate from actual fee',True,score.conservative_score<score.true_net_ce and entry.fee==.0025*entry.intended_transfer,exact=True)
 seed=score
 cases=[('ineligible active',[('balanced',1+.75e-12),('defensive',1+1.5e-12)],'defensive'),
  ('nontransitive chain',[('balanced',1.02),('defensive',1.02+.75e-12),('growth_tilt',1.02+1.5e-12)],'defensive'),
  ('active priority',[('growth_tilt',1.02),('defensive',1.02+.5e-12),('balanced',1.02+.7e-12)],'growth_tilt'),
  ('defensive priority',[('defensive',1.02),('balanced',1.02+.2e-12),('growth_tilt',1.02+.3e-12)],'defensive'),
  ('central priority',[('balanced',1.02),('growth_tilt',1.02+.2e-12)],'balanced')]
 hurdle=1.+1e-12
 for label,v,want in [('below',math.nextafter(hurdle,-math.inf),None),('equal',hurdle,None),('above',math.nextafter(hurdle,math.inf),'balanced')]:
  cases.append(('strict hurdle '+label,[('balanced',v)],want))
 for label,pairs,want in cases:
  chosen=p.choose_target(tuple(replace(seed,name=name,conservative_score=s) for name,s in pairs),1.)
  got=None if chosen is None else chosen.name
  e.check('threshold '+label,want,got,exact=True);e.check('independent threshold '+label,want,o.choose(pairs,1.),exact=True)
 # Also test the inclusive tie limit against adjacent representable values.
 top=1.02;lower=top-1e-12
 for candidate in (math.nextafter(lower,-math.inf),lower,math.nextafter(lower,math.inf)):
  pairs=[('balanced',candidate),('growth_tilt',top)]
  chosen=p.choose_target(tuple(replace(seed,name=name,conservative_score=s) for name,s in pairs),1.)
  e.check('tie nextafter '+candidate.hex(),o.choose(pairs,1.),chosen.name,exact=True)
 tiny=o.rows(8)
 for key in ('equity_return','bond_return','bill_proxy_return','inflation'): tiny[0][key]=-1+1e-13
 tr,tv=o.toy_run(p,tiny,'balanced_adaptive',prior=((1.3,1.02,1.),))
 v=tv[5];entry=tr.ledger[5];expected_l,_=o.oracle_path(tiny,'balanced_adaptive',((1.3,1.02,1.),),.0025,25)
 e.check('REAL tiny action/state',['target_change','balanced','growth_tilt',True,False],[v.action,v.active_before,v.active_after,v.executed_target_change,v.is_trade],exact=True)
 e.check('REAL tiny positive exact fee',True,0<entry.intended_transfer<1e-10 and entry.fee>0 and entry.fee==.0025*entry.intended_transfer,exact=True)
 e.check('REAL tiny actual strict gate',True,next(s for s in v.scores if s.name==v.selected_target).conservative_score>v.ce_keep+1e-12,exact=True)
 e.check('REAL tiny changed holdings and next active',True,entry.holdings_after_fee!=entry.holdings_before and tv[6].active_before=='growth_tilt' and v.first_deployment_year==1,exact=True)
 e.check('REAL tiny independent transfer',float(expected_l[5]['intended_transfer']),entry.intended_transfer,rel=2e-11)
 e.check('REAL tiny independent fee',float(expected_l[5]['fee']),entry.fee,rel=2e-11)
 failures={}
 for value in (0.,-1.,float('nan'),float('inf'),-float('inf')):
  for pos in range(3):
   row=[1.,1.,1.];row[pos]=value;row=tuple(row)
   for n in range(6):
    failures[f'invalid prior {value} pos={pos} n={n}']=e.rejects(f'invalid prior {value} pos={pos} n={n}',lambda row=row,n=n:p.EmpiricalPrior((row,)).certainty_equivalent((0.,0.,1.),((1.,)*3,)*n))
    if n: failures[f'invalid recent {value} pos={pos} n={n}']=e.rejects(f'invalid recent {value} pos={pos} n={n}',lambda row=row,n=n:p.EmpiricalPrior(((1.,)*3,)).certainty_equivalent((0.,0.,1.),(row,)*n))
 failures['empty prior']=e.rejects('empty prior',lambda:p.EmpiricalPrior(()))
 failures['n greater than five']=e.rejects('n greater than five',lambda:p.EmpiricalPrior(((1.,)*3,)).certainty_equivalent((.2,.3,.5),((1.,)*3,)*6))
 for key,bad in [('equity_return',-1.),('bond_return',float('nan')),('bill_proxy_return',float('inf')),('inflation',-1.)]:
  for suspended in (False,True):
   data=o.rows(3 if suspended else 2)
   if suspended: data[0]['inflation']=.5
   data[-1][key]=bad;name=f'invalid final {key} suspended={suspended}'
   failures[name]=e.rejects(name,lambda data=data:o.toy_run(p,data))
 bad=[c['name'] for c in e.checks if not c['passed']]
 return dict(schema_version=1,task_id='SOL-017',base_commit=BASE,immutable_task_commit=TASK_COMMIT,immutable_task_sha256=TASK_HASH,
  source_sha256=SOURCES,imported_code_sha256=imports,python_major_minor='3.12',cpu_only=True,competition_outcomes_read=False,
  corrected_design_verdict='approve',code_verdict='changes_required' if bad else 'approve',blockers=bad,
  checks=e.checks,check_count=len(e.checks),prior_review_commit=PRIOR_COMMIT,reused_unchanged_helpers=REUSED,
  reuse_method='Execute exact old module without mutation; call named scalar helpers only. Own new task/source boundary. Old bind_sources, collect and evidence are untouched and unused.',
  normative_parameters=dict(constants,fee_rates=[.0025,.005],targets={n:list(map(float,w)) for n,w in o.TARGETS.items()}),
  code_findings=[dict(id='K2',severity='material_relative_error_at_subnormal_rounding_boundary',
   expected='For u=2^-1074, weights (1/4,1/4,1/2), support (u,u,4u), exact CE=5u/2, correctly rounded binary64 CE=2u.',
   observed='Pinned new code returns 3u at n=0; check records retain all n=0..5 and grid observations.',
   cause='Logarithm/exponential roundoff moves exact rational subnormal midpoints across rounding boundaries; no correctly-rounded final rescaling is provided.',
   effect='Original all-products-zero rejection is fixed, but heterogeneous finite positive support still has a material relative numeric error. No competition outcome exposure.',
   requested_action='Chief must resolve this separate numeric blocker under a new task or explicit numerical contract; no source or parameter edits are authorized here.') ] if grid_failures else [],
  numerical_facts=dict(minimum_subnormal_hex=small.hex(),subnormal_grid_count=2048,subnormal_grid_failed_count=len(grid_failures),subnormal_grid_failures=grid_failures,initial_exact={k:str(v) for k,v in initial_exact.items()},initial_observed=initial_actual,
   real_tiny_target_change=asdict(v),invalid_observation_diagnoses=failures),
  precision='New extreme oracle: exact Fraction moments; Decimal 160/240-digit rounded-float agreement. Ordinary reused oracle: 80 digits. All absolute tolerances zero; CE up to 1024 minimum-subnormal units compared exactly. Larger subnormals use relative tolerance 3e-12.',
  limitations=LIMITATIONS)

def findings(facts):
 return {key:facts[key] for key in ('schema_version','task_id','base_commit','immutable_task_commit','immutable_task_sha256','source_sha256','imported_code_sha256','corrected_design_verdict','code_verdict','code_findings','blockers','check_count','prior_review_commit','reused_unchanged_helpers','reuse_method','normative_parameters','numerical_facts','precision','limitations')}

def review_text(facts):
 tiny=facts['numerical_facts']['real_tiny_target_change']
 return f'''# SOL-017 independent K1 closure

code_verdict: **{facts['code_verdict']}**. Corrected design remains **approve** under accepted SOL-013.
Evidence integrity is separate from the mathematical code verdict.

The original constant minimum-subnormal underflow rejection is closed. A new
heterogeneous subnormal rounding blocker K2 remains: let u=2^-1074, with weights
(1/4,1/4,1/2) and support (u,u,4u). The exact single-support CE is 5u/2.
Binary64 ties-to-even rounds it to 2u (0x0.0000000000002p-1022); the reviewed
code returns 3u (0x0.0000000000003p-1022), a 50% error against the rounded oracle.
The exact gross has 20% relative error. Log/exp roundoff crosses the rounding
midpoint. A bounded 2048-case rational subnormal grid finds
{facts['numerical_facts']['subnormal_grid_failed_count']} mismatches. Exact fixture
observations for every n=0..5 remain in verification.json. This is a true new
blocker under the requested tiny-value comparisons; no production fix, clipping,
new support bound or parameter adjustment was attempted.

Reviewed exact base {BASE}, policy SHA256 {SOURCES['src/safeinvest/policy_pilot.py']}.
The only mathematical source diff is log_power. For positive weights,
log(sum(w*g)) = logsumexp(log(w)+log(g)); zero weights contribute no terms.
This avoids underflow of individual products before the inverse-cube moment.
CE = [(15*mean_prior(gross^-3)+sum_recent(gross^-3))/(15+n)]^(-1/3).
There is no clipping or imputation. Source outside log_power is byte-identical
to accepted SOL-013. New test bytes are pinned but chief tests do not count as
independent acceptance.

{facts['check_count']} focused checks; {len(facts['blockers'])} failed comparisons
are retained by exact name and expected/observed values in verification.json.
Minimum-subnormal support (0x0.0000000000001p-1022) is checked with exact positive
equality, including zero and minimum-positive weights, duplicate supports and
every n=0..5. Minimum normal through maximum finite factors, heterogeneous
subnormal rational products, mixed extremes and tiny-weight dominant products
use independent exact Fraction moments and 160/240-digit Decimal agreement.
CE up to 1024 minimum-subnormal units is compared exactly; all numeric absolute tolerances
are zero (relative tolerance at most 3e-12, except tiny path 2e-11).
For identical portfolio support the extreme oracle returns the exact Fraction
CE directly, avoiding any Decimal-root approximation at exact midpoints.

Unchanged SOL-013 helpers reused: {', '.join(REUSED)}. The old exact verifier
blob is executed unchanged in its own module; its old task, BASE and hash
constraints are neither overwritten nor invoked. Only named scalar functions
are reused with the independently imported NEW production bytes. No historical
saved evidence is replayed as new acceptance or edited. No broad scheduler,
accounting, screening, or calibration suite was rerun.

The ordinary fixture (prior gross 1.10/1.02/1, one annual return .10/.02/0,
zero inflation, initial 100 bills, thirds target, k=.0025) independently gives
T=200/3, actual fee=1/6, each post-fee holding=599/18, buffered score=3887/3750,
actual net CE=7787/7500 and terminal wealth=7787/75. The twice-fee buffer is a
decision score; actual wealth pays one fee. Ordinary 15:n mixtures and scores
cover all five targets, n=0..5 and k=0/.0025/.005.

Strict keep hurdle, maximum-anchored epsilon ties, active/defensive/central
priority, adjacent floating-point threshold values, actual tiny-transfer state
and invalid final observations (also suspended) were checked. The real tiny
fixture has T={tiny['intended_transfer']:.17g}, positive fee={tiny['actual_fee']:.17g},
action={tiny['action']}, active_after={tiny['active_after']},
is_trade={tiny['is_trade']}, executed_target_change={tiny['executed_target_change']}.
Reporting epsilon does not cancel execution or active-state transition.

Normative gamma=4, prior strength=15, window=5, first alternatives at n=5,
buffer=2, epsilon=1e-12, transfer-reporting epsilon=1e-10, review threshold=25%,
targets and fee rates .0025/.005 remain unchanged. No parameter review or tuning.

verify.py --create uses exclusive creation. --check recomputes read-only,
binds exact task/source/import hashes and artifacts, permits HEAD to advance,
and never repairs evidence. Integrity self-tests and preserved trial records
are separate artifacts. Historical SOL-013 remains changes_required.
Trial 001 required exact equality even at the largest subnormal; its 42 failures
were within 8.6e-14 relative error and did not establish a source defect. That
overstrict audit trial is preserved under history/ with its diagnosis. The
subsequent K2 midpoint failures persist at the appropriate comparisons.

Limitations: {' '.join(LIMITATIONS)}
'''

def hashes(directory):
 return {f.relative_to(directory).as_posix():digest(canonical(f.read_bytes())) for f in sorted(directory.rglob('*')) if f.is_file() and f.name!='verification.json'}

def write_exclusive(path,value):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('x',encoding='utf-8',newline='\n') as handle: handle.write(value)

def check_saved(evidence,artifact_dir):
 saved=json.loads(evidence.read_text(encoding='utf-8'));actual=json.loads(dump(collect()))
 # Artifact bytes bind saved facts exactly. Recomputed floats permit only a
 # small relative difference across libm implementations, never absolute slack.
 def equal(a,b):
  if isinstance(a,bool) or isinstance(b,bool): return type(a)==type(b) and a==b
  if isinstance(a,float) and isinstance(b,(int,float)):
   if abs(a)<sys.float_info.min or abs(b)<sys.float_info.min: return a==b
   return math.isclose(a,b,rel_tol=3e-13,abs_tol=0.)
  if isinstance(a,dict) and isinstance(b,dict): return a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
  if isinstance(a,list) and isinstance(b,list): return len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
  return type(a)==type(b) and a==b
 if not equal(saved['facts'],actual): raise RuntimeError('Saved numerical/source mismatch; read-only evidence preserved')
 if saved['artifact_sha256']!=hashes(artifact_dir): raise RuntimeError('Artifact hash mismatch; read-only evidence preserved')
 if json.loads((artifact_dir/'findings.json').read_text(encoding='utf-8'))!=findings(saved['facts']): raise RuntimeError('Findings mismatch')
 if canonical((artifact_dir/'review.md').read_bytes())!=review_text(saved['facts']).encode(): raise RuntimeError('Review mismatch')
 return actual

def main():
 parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group(required=True)
 group.add_argument('--create',action='store_true');group.add_argument('--check',action='store_true')
 parser.add_argument('--evidence',type=Path,default=OUT/'verification.json');parser.add_argument('--artifact-dir',type=Path,default=OUT)
 args=parser.parse_args()
 if args.create:
  facts=collect();write_exclusive(OUT/'findings.json',dump(findings(facts)));write_exclusive(OUT/'review.md',review_text(facts))
  write_exclusive(OUT/'verification.json',dump(dict(facts=facts,artifact_sha256=hashes(OUT))))
 else: facts=check_saved(args.evidence,args.artifact_dir)
 print(json.dumps(dict(evidence_integrity_verdict='passed',code_verdict=facts['code_verdict'],check_count=facts['check_count'],read_only=args.check)))

if __name__=='__main__': main()
