"""SOL-021 independent pinned-blob numeric audit; --check is read-only.
Only extracted unchanged scalar oracles are reused. No historical boundaries run.
"""
from __future__ import annotations
import argparse, ast, hashlib, itertools, json, math, subprocess, sys, types
from dataclasses import asdict, replace
from fractions import Fraction as F
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'audit/SOL-021'
BASE='79a9a63d939c14d4af242d86ceeaa42c044803c4'
PRIOR='90f5c8d3fe9b76861f9e302ce23d2e5cd6f2e839'
TASK_COMMIT='cc080c884d63e6dcf4100c50758042e4120db120'
TASK_HASH='25f12a4b378d9968222eaedb333799fb633b11f24053139df656f1ca7fd15efd'
TASK_CANONICAL='53389f310d3271c476c9be65f6b75ab228ff1ca3e2dfbd4a8466348bf8678669'
def digest(b): return hashlib.sha256(b).hexdigest()
def canonical(b): return b.replace(b'\r\n',b'\n')
def dump(v): return json.dumps(v,indent=2,sort_keys=True,allow_nan=False)+'\n'
def blob(c,p): return subprocess.check_output(['git','show',c+':'+p],cwd=ROOT)
def must(c,msg):
 if not c: raise RuntimeError(msg)
def write_new(p,s):
 with p.open('x',encoding='utf-8',newline='\n') as f:f.write(s)
def scalar(v):
 if isinstance(v,F):return float(v)
 if isinstance(v,(list,tuple)):return [scalar(x) for x in v]
 if isinstance(v,dict):return {k:scalar(x) for k,x in v.items()}
 return v
class Evidence:
 def __init__(self):self.checks=[]
 def check(self,name,expected,observed,*,rel=3e-12,exact=False):
  expected,observed=scalar(expected),scalar(observed)
  def eq(a,b):
   if exact or isinstance(a,(bool,str)) or a is None:return type(a)==type(b) and a==b
   if isinstance(a,(float,int)) and isinstance(b,(float,int)):return math.isclose(a,b,rel_tol=rel,abs_tol=0.)
   if isinstance(a,list) and isinstance(b,list):return len(a)==len(b) and all(eq(x,y) for x,y in zip(a,b))
   return a==b
  self.checks.append(dict(name=name,expected=expected,observed=observed,passed=eq(expected,observed),relative_tolerance=0 if exact else rel,absolute_tolerance=0))
 def rejects(self,name,fn):
  try:fn()
  except (ValueError,OverflowError,TypeError) as exc:
   self.check(name,True,True,exact=True);return type(exc).__name__+': '+str(exc)
  self.check(name,True,False,exact=True);return 'UNEXPECTED ACCEPTANCE'
def extract(s,name):
 n=next(n for n in ast.parse(s).body if getattr(n,'name',None)==name or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets))
 return ast.get_source_segment(s,n)
def boundaries():
 must(sys.version_info[:2]==(3,12),'Python 3.12 required')
 taskraw=blob(TASK_COMMIT,'ops/tasks/SOL-021.json');must(digest(taskraw)==TASK_HASH,'task blob changed')
 task=json.loads(taskraw);must(digest(json.dumps(task,sort_keys=True,separators=(',',':')).encode())==TASK_CANONICAL,'task canonical hash')
 must(task['base_commit']==BASE and task['allowed_paths']==['audit/SOL-021'],'task scope')
 local=ROOT/'.runtime/task.json'
 if local.exists():must(json.loads(local.read_text(encoding='utf-8-sig'))==task,'local task mismatch')
 raw={}
 for path,want in task['parameters']['source_sha256'].items():
  b=blob(BASE,path);must(digest(b)==want,'Pinned source mismatch: '+path);raw[path]=b
 for path,b in raw.items():
  if (ROOT/path).exists():must(canonical((ROOT/path).read_bytes())==b,'Checkout source mismatch: '+path)
 prov=json.loads((OUT/'oracle-provenance.json').read_text())
 oracle_source=canonical((OUT/'oracle.py').read_bytes()).decode()
 must(digest(oracle_source.encode())=='7a47cc2e944d7263166b6e11f9fbd06e6b8be2ac2dafb5913beeda21d2464c19','Independent oracle module checksum mismatch')
 for entry in prov:
  original=blob(entry['commit'],entry['path']);segment=extract(original.decode(),entry['name'])
  must(digest(original)==entry['blob_sha256'] and digest(segment.encode())==entry['segment_sha256'],'Oracle provenance mismatch')
  must(extract(oracle_source,entry['name'])==segment,'Oracle helper changed: '+entry['name'])
 allowed={'decimal_ce','TARGETS','MODES','rat','unit','ce','score','choose','rows','toy_run','oracle_path'}
 names={getattr(n,'name',None) for n in ast.parse(oracle_source).body if isinstance(n,ast.FunctionDef)}
 must(names==allowed-{'TARGETS','MODES'},'Unexpected oracle functions')
 o=types.ModuleType('sol021_independent');exec(compile(oracle_source,str(OUT/'oracle.py'),'exec'),o.__dict__)
 package='_sol021_pinned';pkg=types.ModuleType(package);pkg.__path__=[];sys.modules[package]=pkg
 imports={}
 for name in ('accounting','metrics','backtest','policy_pilot'):
  path='src/safeinvest/'+name+'.py';b=raw[path];filename='git:'+BASE+':'+path
  m=types.ModuleType(package+'.'+name);m.__file__=filename;m.__package__=package;sys.modules[m.__name__]=m
  exec(compile(b,filename,'exec'),m.__dict__);setattr(pkg,name,m)
  imports[path]=dict(sha256=digest(b),git_blob=subprocess.check_output(['git','rev-parse',BASE+':'+path],cwd=ROOT,text=True).strip(),filename=filename)
  for value in m.__dict__.values():
   if isinstance(value,types.FunctionType) and value.__module__==m.__name__:must(value.__code__.co_filename==filename,'Import filename mismatch')
 must(set(n for n in sys.modules if n.startswith(package+'.'))=={package+'.'+x for x in ('accounting','metrics','backtest','policy_pilot')},'Unexpected production import')
 return pkg.policy_pilot,o,imports,raw

def scope_check(raw):
 old=ast.parse(blob(PRIOR,'src/safeinvest/policy_pilot.py'));new=ast.parse(raw['src/safeinvest/policy_pilot.py'])
 oldclass=next(n for n in old.body if isinstance(n,ast.ClassDef) and n.name=='EmpiricalPrior')
 newclass=next(n for n in new.body if isinstance(n,ast.ClassDef) and n.name=='EmpiricalPrior')
 om=next(n for n in oldclass.body if getattr(n,'name',None)=='certainty_equivalent');nm=next(n for n in newclass.body if getattr(n,'name',None)=='certainty_equivalent')
 oi=next(i for i,n in enumerate(om.body) if isinstance(n,ast.Try));ni=next(i for i,n in enumerate(nm.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='log_ce' for t in n.targets))
 must(ast.dump(ast.Module(body=om.body[:oi],type_ignores=[]))==ast.dump(ast.Module(body=nm.body[:ni],type_ignores=[])),'Ordinary log moment changed')
 must(ast.dump(ast.Module(body=om.body[oi+1:],type_ignores=[]))==ast.dump(ast.Module(body=nm.body[ni+2:],type_ignores=[])),'CE postcondition changed')
 newclass.body[newclass.body.index(nm)]=om
 new.body=[n for n in new.body if not (getattr(n,'name',None)=='_small_ce_exact' or isinstance(n,ast.ImportFrom) and n.module=='fractions' or isinstance(n,ast.Import) and n.names[0].name in ('struct','sys'))]
 must(ast.dump(old)==ast.dump(new),'Code outside helper/imports/routing changed')
 return 'AST identical outside helper/imports/CE routing; ordinary log moment and CE postconditions unchanged'

def route_call(p,w,prior,recent=()):
 calls=0;iterations=0
 def trace(frame,event,arg):
  nonlocal calls,iterations
  if frame.f_code.co_name=='_small_ce_exact':
   if event=='call':calls+=1
   if event=='line' and frame.f_lineno==89:iterations+=1
   return trace
  return None
 sys.settrace(trace)
 try:result=p.EmpiricalPrior(prior).certainty_equivalent(w,recent)
 finally:sys.settrace(None)
 return result,calls,iterations

def collect():
 p,o,imports,raw=boundaries();e=Evidence();decimal_ce=o.decimal_ce
 scope=scope_check(raw)
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

 normalized_cases=[]
 for w in ((.1,.2,.7),(.2+5e-13,.3,.5),(.2-5e-13,.3,.5),(math.ulp(0.),.5,.5),(1/3,)*3):
  validated=p.validate_target(w);total=sum(map(F,validated))
  prior=((small,3*small,7*small),(9*small,2*small,small))
  recent=((4*small,5*small,2*small),(2*small,8*small,small),(small,small,12*small),(3*small,7*small,4*small),(11*small,small,2*small))
  for n in range(6):
   expected=decimal_ce(validated,prior,recent[:n]);actual=p.EmpiricalPrior(prior).certainty_equivalent(w,recent[:n])
   e.check('validated rational normalization '+repr(w)+' n='+str(n),expected,actual,exact=True)
  normalized_cases.append(dict(input=list(w),validated=list(validated),exact_validated_sum=str(total),sum_discrepancy=str(total-1)))
 e.check('validated residual sums challenged',True,any(x['sum_discrepancy']!='0' for x in normalized_cases),exact=True)
 for bad in ((.2+2e-12,.3,.5),(.2-2e-12,.3,.5),(-small,.5,.5),(0.,0.,0.),(True,0.,0.)):
  e.rejects('invalid target '+repr(bad),lambda bad=bad:p.EmpiricalPrior(((small,)*3,)).certainty_equivalent(bad))
 boundary=math.log(normal)+1;center=math.exp(boundary);routes=[]
 for label,scale,want in [('below',math.exp(boundary-1e-8),1),('above',math.exp(boundary+1e-8),0),
                          ('nextbelow',math.nextafter(center,0.),None),('center',center,None),('nextabove',math.nextafter(center,math.inf),None)]:
  for n in range(6):
   prior=((scale,)*3,)*2;recent=((scale,)*3,)*n
   actual,calls,steps=route_call(p,(.25,.25,.5),prior,recent)
   e.check('route value '+label+' n='+str(n),decimal_ce((.25,.25,.5),prior,recent),actual,rel=3e-12)
   if want is not None:e.check('route dispatch '+label+' n='+str(n),want,calls,exact=True)
   e.check('bisection upper bound '+label+' n='+str(n),True,steps<=63,exact=True)
   routes.append(dict(label=label,n=n,support_hex=scale.hex(),helper_calls=calls,bisection_comparisons=steps,observed_hex=actual.hex()))
 dup_prior=((small,3*small,7*small),(9*small,2*small,small));dup_recent=((4*small,5*small,2*small),)*5
 for n in range(6):
  e.check('duplicate prior support n='+str(n),decimal_ce((.25,.25,.5),dup_prior,dup_recent[:n]),p.EmpiricalPrior(dup_prior*2).certainty_equivalent((.25,.25,.5),dup_recent[:n]),exact=True)
 for label,w,prior in [('min',(0.,0.,1.),((big,normal,small),)),('max',(.25,.25,.5),((big,)*3,)),('full range',(.2,.3,.5),((small,normal,big),(big,small,normal)))]:
  actual=p.EmpiricalPrior(prior).certainty_equivalent(w)
  e.check('finite positive extrema '+label,True,math.isfinite(actual) and actual>0 and (min(min(r) for r in prior)<=actual or math.isclose(actual,min(min(r) for r in prior),rel_tol=3e-12,abs_tol=0)) and (actual<=max(max(r) for r in prior) or math.isclose(actual,max(max(r) for r in prior),rel_tol=3e-12,abs_tol=0)),exact=True)
 # Direct observed-helper checks cover finite upper sentinel and parity at normal boundary.
 for label,row,w in [('maximum endpoint',(big,big,big),(.25,.25,.5)),
                     ('minimum endpoint',(small,small,small),(.25,.25,.5)),
                     ('normal transition upper',(normal-small,normal,small),(.5,.5,0.)),
                     ('normal transition lower',(normal-2*small,normal-small,small),(.5,.5,0.)),
                     ('normal transition above',(normal,normal+small,small),(.5,.5,0.))]:
  for n in range(6):
   valid=p.validate_target(w);prior=(row,);recent=(row,)*n
   e.check('direct exact helper '+label+' n='+str(n),decimal_ce(valid,prior,recent),p._small_ce_exact(valid,prior,recent),exact=True)
 failed=[c['name'] for c in e.checks if not c['passed']]
 return dict(schema_version=1,task_id='SOL-021',base_commit=BASE,task_commit=TASK_COMMIT,task_blob_sha256=TASK_HASH,
  task_canonical_sha256=TASK_CANONICAL,source_sha256={k:digest(v) for k,v in raw.items()},imported_code=imports,
  independent_oracle_provenance=json.loads((OUT/'oracle-provenance.json').read_text()),
  python_major_minor='3.12',cpu_only=True,competition_outcomes_read=False,code_verdict='changes_required' if failed else 'approve',
  evidence_integrity_verdict='passed',failures=failed,checks=e.checks,check_count=len(e.checks),
  grid_count=2048,grid_failed_count=len(grid_failures),grid_failures=grid_failures,
  initial_exact={k:str(x) for k,x in initial_exact.items()},initial_observed=initial_actual,
  real_tiny_target_change=asdict(v),normalization_cases=normalized_cases,route_cases=routes,scope_check=scope,
  precision='Tiny fixtures and 2048 grid exact equality; ordinary CE 3e-13, other larger values <=3e-12 unless individually declared. All absolute tolerances zero. Historical oracle_path tiny transfer/fee rel=2e-11.',
  limitations=['Synthetic CPU kernel review only; no competition CSV, development or final outcomes.',
   'No production loader/writer/calibration/selector or final-run approval.',
   'Correct rounding proof reviewed for exact near-underflow route; ordinary log path is tolerance checked.',
   'Decimal nonconstant oracle requires independent 160/240-digit agreement; not exhaustive proof for arbitrary binary64 inputs.',
   'Chief provisional tests are provenance only; chief must accept exact delivered commit.',
   'Historical SOL-013 and SOL-017 negative code verdicts remain immutable.'])

def hashes(directory):
 return {str(p.relative_to(directory)).replace('\\','/'):digest(canonical(p.read_bytes())) for p in sorted(directory.rglob('*')) if p.is_file() and p.name!='verification.json' and '__pycache__' not in p.parts}

def finding(f):
 return dict(task_id='SOL-021',code_verdict=f['code_verdict'],evidence_integrity_verdict='passed',
  source_commit=BASE,task_commit=TASK_COMMIT,source_sha256=f['source_sha256'],imported_code=f['imported_code'],
  failures=f['failures'],check_count=f['check_count'],grid_count=2048,grid_failed_count=f['grid_failed_count'],
  closure='K2 midpoint defect closed by independent exact grid and scalar fixtures' if not f['failures'] else 'Numeric discrepancies preserved; code approval withheld',
  unchanged_scope=f['scope_check'],limitations=f['limitations'],
  audit_tool_issues=['history/infrastructure.json','history/diagnosis-001.json','history/diagnosis-002.json'],historical_boundaries='never executed or overridden')

def review(f):
 return f"""# SOL-021 independent K2 review

Code verdict: **{f['code_verdict']}**. Evidence integrity: passed.
{f['check_count']} checks; all 2048 retained rational grid cases; {len(f['failures'])} failed comparisons.

Production base: {BASE}. Immutable task: {TASK_COMMIT}.
Exact SHA256 and imported Git blob IDs are in findings.json and verification.json.
Unchanged named SOL-017 decimal_ce and SOL-013 ordinary helpers are isolated in
oracle.py, with per-function pinned-source provenance. No historical boundary is
invoked, overridden or relabeled. Historical negative verdicts remain unchanged.

The exact route normalizes the fractions of floats returned by validate_target.
Positive unit-sum weights make each q a convex combination of finite positive
support. Their inverse-cube mean is bounded by inverse cubes of support extrema,
so its inverse cube root lies within those extrema. The 15:n mixture preserves
these bounds.

Positive finite binary64 encodings increase with value. Starting at zero and
maximum finite, x^3*M<=1 is monotone and halves an integer interval below 2^63,
requiring at most 63 comparisons. Adjacent endpoints bracket the root; if it
equals maximum finite, the upper endpoint still returns correctly. Comparing
the rational midpoint cubed times M with one selects the nearest endpoint.
Encoding parity equals significand parity, including subnormal/normal transitions;
the equality branch therefore implements ties-to-even.

The exact 5u/2 midpoint returns 2u; the opposite 7u/2 midpoint returns 4u.
All n=0..5, heterogeneous prior/recent support, duplicates, zero/tiny weights,
residual validated unit sums, minimum positive through maximum finite, invalid
support and both sides of log(minimum normal)+1 are checked. Adjacent boundary
probes record the actual route: preliminary log roundoff may map neighboring
values to the same route, within the one-log-unit margin and ordinary tolerance.

Ordinary 15:n mixtures, strict hurdle/ties and real tiny positive transfer state
transitions use unchanged independent oracles. Initial rational fixtures:
T=200/3, fee=1/6, each post-fee holding=599/18, buffered score=3887/3750,
true net CE=7787/7500, terminal wealth=7787/75. The twice-fee decision buffer
remains separate from actual one-fee accounting. The tiny selected change executes,
charges its positive fee and updates active state below the trade-count epsilon.

AST comparison confirms code outside helper/imports/CE routing is unchanged.
The ordinary log moment is unchanged. No clipping, input bound, strategy threshold,
fee, target or parameter tuning is introduced; the routing margin is numeric only.
Tiny comparisons are exact; larger tolerances are declared with zero absolute
tolerance. Correct rounding is reviewed for the exact route, not the ordinary route.

Read-only --check recomputes observations, verifies pinned imports, oracle
provenance and artifact hashes, and does not require HEAD equality. Scratch tests
challenge numeric observations, source/import hashes, artifacts and exclusive
creation, preserving deliberate corruptions without repair.

Infrastructure issues are in history/infrastructure.json. The first audit trial
wrongly required exact ordinary maximum-support bounds; diagnosis-001.json records
the correction to the declared relative tolerance, and the failed trial and source
are preserved. Two malformed tool-call constructions ran no code. The first
advanced-HEAD scratch view omitted a refs directory; diagnosis-002.json records
the fix and preserves the failed creation. No verification existed at that point.
The shell helper could not start; Node execFile ran Python 3.12 without a shell.
A missing NumPy probe affected no check: reviewed modules use the standard library.
A task-path probe was corrected to the pinned dispatch commit.
No real CSV reads, installs, source/spec/task edits, workers, commits, pushes,
publication or production/final runs occurred. Production loader, writer,
calibration and final evaluation remain outside this kernel review.
"""

def check_saved(evidence,artifact_dir):
 saved=json.loads(evidence.read_text(encoding='utf-8'))
 must(hashes(artifact_dir)==hashes(OUT),'Artifacts differ from audited implementation directory')
 must(saved['artifact_sha256']==hashes(artifact_dir),'Artifact hash mismatch')
 facts=collect()
 must(saved['facts']==facts,'Recomputed evidence mismatch')
 must(json.loads((artifact_dir/'findings.json').read_text())==finding(facts),'Findings mismatch')
 must(canonical((artifact_dir/'review.md').read_bytes()).decode()==review(facts),'Review mismatch')
 return facts


def integrity_self_tests(f):
 import copy, os, shutil
 scratch=ROOT/'.runtime/SOL-021-scratch/integrity-002'
 must(not scratch.exists(),'Integrity scratch already exists; preserve and diagnose, do not repair')
 scratch.mkdir()
 must(subprocess.run(['git','check-ignore','-q',str(scratch)],cwd=ROOT).returncode==0,'Scratch must be ignored')
 baseline=dict(schema_version=1,facts=f,artifact_sha256=hashes(OUT));results=[]
 def trial(name,saved,want,artifact_dir=OUT,env=None,create=False):
  evidence=scratch/(name+'.json');write_new(evidence,dump(saved))
  before=digest(evidence.read_bytes());before_art=hashes(artifact_dir);before_out=hashes(OUT)
  args=[sys.executable,'-B',str(OUT/'verify.py')]
  args+=['--create'] if create else ['--check','--evidence',str(evidence),'--artifact-dir',str(artifact_dir)]
  proc=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,env=env)
  item=dict(name=name,expected_exit=want,observed_exit=proc.returncode,stdout=proc.stdout,stderr=proc.stderr,
    read_only=before==digest(evidence.read_bytes()) and before_art==hashes(artifact_dir) and before_out==hashes(OUT),
    scratch_evidence=str(evidence.relative_to(ROOT)).replace('\\','/'))
  results.append(item)
  write_new(scratch/(name+'-result.json'),dump(item))
 trial('clean',baseline,0)
 bad=copy.deepcopy(baseline)
 c=next(c for c in bad['facts']['checks'] if c['name']=='K2 exact midpoint n=0');c['observed']+=math.ulp(0.)
 trial('corrupt-exact-midpoint',bad,1)
 bad=copy.deepcopy(baseline);c=next(c for c in bad['facts']['checks'] if c['name']=='REAL tiny independent fee');c['observed']=0.
 trial('corrupt-tiny-fee',bad,1)
 bad=copy.deepcopy(baseline);bad['facts']['imported_code']['src/safeinvest/policy_pilot.py']['sha256']='0'*64
 trial('corrupt-pinned-import-hash',bad,1)
 bad=copy.deepcopy(baseline);bad['facts']['source_sha256']['specs/POLICY_NUMERIC_K2.md']='0'*64
 trial('corrupt-source-hash',bad,1)
 copied=scratch/'corrupted-artifacts';shutil.copytree(OUT,copied)
 with (copied/'review.md').open('a',encoding='utf-8') as file:file.write('\nDELIBERATE CORRUPTION\n')
 trial('corrupt-artifact',baseline,1,copied)
 trial('exclusive-create-refuses-overwrite',baseline,1,create=True)
 # Read-only alternate Git view with HEAD at the existing descendant dispatch
 # commit. No commits, refs or branches in the actual repository are changed.
 gitdir=scratch/'advanced-head-view';(gitdir/'objects/info').mkdir(parents=True)
 (gitdir/'refs').mkdir()
 common=Path(subprocess.check_output(['git','rev-parse','--path-format=absolute','--git-common-dir'],cwd=ROOT,text=True).strip())
 write_new(gitdir/'config','[core]\n repositoryformatversion = 0\n bare = true\n')
 write_new(gitdir/'HEAD',TASK_COMMIT+'\n')
 write_new(gitdir/'objects/info/alternates',str(common/'objects').replace('\\','/')+'\n')
 env=dict(os.environ,GIT_DIR=str(gitdir),GIT_WORK_TREE=str(ROOT))
 advanced=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,env=env,text=True).strip()
 must(advanced==TASK_COMMIT and advanced!=BASE,'Advanced HEAD fixture invalid')
 trial('advanced-head-same-pinned-inputs',baseline,0,env=env)
 write_new(OUT/'integrity-self-tests.json',dump(dict(tests=results,advanced_head=advanced,production_git_unchanged=True)))
 must(all(t['observed_exit']==t['expected_exit'] and t['read_only'] for t in results),'Integrity self-test failure preserved')
 return results

def main():
 ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True)
 g.add_argument('--create',action='store_true');g.add_argument('--check',action='store_true');g.add_argument('--probe',action='store_true')
 ap.add_argument('--evidence',type=Path,default=OUT/'verification.json')
 ap.add_argument('--artifact-dir',type=Path,default=OUT)
 a=ap.parse_args()
 if a.check:
  f=check_saved(a.evidence,a.artifact_dir);print(json.dumps(dict(read_only=True,code_verdict=f['code_verdict'],checks=f['check_count'],integrity='passed')))
 elif a.probe:
  print(dump(collect()))
 else:
  for name in ('findings.json','review.md','verification.json'):must(not (OUT/name).exists(),'Refusing overwrite: '+name)
  f=collect();write_new(OUT/'findings.json',dump(finding(f)));write_new(OUT/'review.md',review(f))
  integrity_self_tests(f)
  write_new(OUT/'verification.json',dump(dict(schema_version=1,facts=f,artifact_sha256=hashes(OUT))))
  print(json.dumps(dict(created=True,code_verdict=f['code_verdict'],checks=f['check_count'],failures=f['failures'])))
if __name__=='__main__':
 try:main()
 except Exception as exc:print(type(exc).__name__+': '+str(exc),file=sys.stderr);sys.exit(1)
