"""SOL-040 read-only independent review of exact HY3-004 Git objects.
Never starts the producer check. Its sole authorized execution is preserved separately.
Exact failed SOL-036 arithmetic is reused under its historical binding; fresh bindings
and algebraic checks are implemented here. No producer arithmetic imports.
"""
import argparse, collections, copy, hashlib, json, os, pathlib, subprocess, sys, time, types
from decimal import Decimal as D
HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parents[1]
BASE='b75389aefeb06ed750c9b7aa891ecc383af9ce1a'
PUBLICATION='95eb627ce6536662b8c583dfd2e6046c3aaf0ea9'
TASK_SHA='a306b6e9d45d0eddcd2debeeeadac9525030a28b853a267a0e17f2447138d6c7'
HISTORICAL='8a39da30e551f6e4fd54cfef6ec7b070b43d4d8d'
CLEAN_SHA='29134879a3db6f86b47ffa850d590b1568081e4ba500d3502cf4d988848e8dbb'
def sha(b): return hashlib.sha256(b).hexdigest()
def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT,stderr=subprocess.PIPE)
def blob(c,p): return git('show',c+':'+p)
def require(v,msg):
 if not v: raise ValueError(msg)
def pairs(items):
 out={}
 for k,v in items:
  require(k not in out,'duplicate JSON key '+k); out[k]=v
 return out
def loads(b): return json.loads(b,object_pairs_hook=pairs,parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
def inventory(paths):
 out={}
 for p in paths:
  b=(ROOT/p).read_bytes(); out[p]={'sha256':sha(b),'bytes':len(b)}
 return out

def fresh_authentication():
 tb=(HERE/'task-snapshot.json').read_bytes(); require(sha(tb)==TASK_SHA,'SOL-040 task snapshot hash')
 task=loads(tb); published=blob(PUBLICATION,'ops/tasks/SOL-040.json')
 require(published==tb,'SOL-040 exact publication bytes'); require(git('rev-parse',PUBLICATION+'^').decode().strip()==BASE,'SOL-040 publication parent')
 require(task['base_commit']==BASE and task['id']=='SOL-040' and task['owner']=='sol' and task['attempt']==1,'SOL-040 identity')
 require(task['allowed_paths']==['audit/SOL-040'],'SOL-040 allowed paths')
 for p,h in task['parameters']['source_sha256'].items(): require(sha(blob(BASE,p))==h,'new base source pin '+p)
 pred=task['parameters']['failed_predecessor']; require(pred['result_commit']==HISTORICAL,'historical result identity')
 rb=blob(HISTORICAL,'handoff/SOL-036/result.json'); receipt=loads(rb)
 require(sha(rb)==pred['receipt_sha256'] and receipt['status']=='failed','historical failure remains failed')
 require(blob(BASE,'handoff/SOL-036/result.json')==rb,'historical receipt unchanged at new base')
 historical_inventory={}
 for p,h in receipt['artifacts_sha256'].items():
  b=blob(HISTORICAL,p); require(sha(b)==h,'historical artifact pin '+p); historical_inventory[p]={'sha256':h,'bytes':len(b)}
 for local,original in [('historical/verify.py','verify.py'),('historical/task-snapshot.json','task-snapshot.json'),('historical/schemas.json','schemas.json')]:
  require((HERE/local).read_bytes()==blob(HISTORICAL,'audit/SOL-036/'+original),'exact reused arithmetic bytes '+original)
 old_clean=loads(blob(HISTORICAL,'audit/SOL-036/clean-environment-checks.json'))
 require(old_clean['returncode'] is None and old_clean['inventory_before'] is None and old_clean['execution_status']=='interrupted_by_node_tool_timeout_kernel_reset','old interruption must stay disclosed')
 return task,{'task_id':'SOL-040','base_commit':BASE,'publication_commit':PUBLICATION,'task_blob_sha256':TASK_SHA,'task_canonical_sha256':sha(json.dumps(task,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')),'historical_task_id':'SOL-036','historical_result_commit':HISTORICAL,'historical_receipt_sha256':sha(rb),'historical_status':receipt['status'],'historical_artifacts':historical_inventory,'historical_clean_status':old_clean['execution_status'],'historical_clean_exit':old_clean['returncode']}

def clean_evidence(task):
 raw=(HERE/'clean-environment-checks.json').read_bytes(); require(sha(raw)==CLEAN_SHA,'fresh clean-check immutable evidence hash')
 c=loads(raw)
 require(c['task_id']=='SOL-040' and c['producer_commit']==task['parameters']['producer']['result_commit'] and c['checkout_head']==c['producer_commit'],'clean producer binding')
 require(c['execution_status']=='completed' and c['returncode']==0,'fresh producer check failed; no retry authorized')
 require(c['timeout_seconds']==600 and 0<c['elapsed_seconds']<=600,'check timeout/timing')
 require(c['python'].startswith('3.12.') and c['pythonpath_keys']==[] and c['runtime_task_absent'] is True,'check environment')
 require(c['argv'][1:]==['-B','scripts/run_development_policy.py','--config','specs/execution/HY3-004-file44.json','--output','results/development/HY3-004','--check'],'check argv')
 before=(HERE/'producer-before-inventory.json').read_bytes()
 require(sha(before)==c['before_inventory_sha256'] and loads(before)==c['inventory_before'],'durable before inventory')
 require(c['unchanged'] is True and c['inventory_before']==c['inventory_after'] and c['git_status_before']==c['git_status_after']=='','protected checkout changed')
 config=loads(blob(c['producer_commit'],task['parameters']['producer']['config_path']))
 expected=set(config['source_sha256'])|{task['parameters']['producer']['config_path'],task['parameters']['producer']['input']['path']}|{p for p in task['parameters']['producer']['artifacts_sha256'] if p.startswith('results/development/HY3-004/')}
 require(set(c['inventory_before'])==expected,'incomplete protected inventory')
 spellings={}
 for p,meta in c['inventory_before'].items():
  b=blob(c['producer_commit'],p); variants=[('canonical_git_blob',b)]
  if p in config['source_sha256'] or p==task['parameters']['producer']['config_path']: variants.append(('exact_CRLF_spelling',b.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')))
  matched=[name for name,value in variants if meta=={'sha256':sha(value),'bytes':len(value)}]
  require(bool(matched),'checkout bytes outside exact allowed spellings '+p); spellings[p]=matched[0]
 c['verified_checkout_spellings']=spellings
 for p,meta in c['logs'].items():
  b=(HERE/p).read_bytes(); require(meta=={'sha256':sha(b),'bytes':len(b)},'durable log changed '+p)
 require(loads((HERE/'producer-check.stdout.log').read_bytes())=={'status':'passed','read_only':True,'result':'passed'},'unexpected producer check stdout')
 require((HERE/'producer-check.stderr.log').read_bytes()==b'','producer check stderr not empty')
 return c

def all_saved_score_algebra(h,tables,paths,diagnostics):
 count=0; by_mode={}
 for mode in h.NEW:
  nscore=0
  for x in tables[mode,'target_scores']:
   sid,t=int(x['scenario_id']),int(x['period']); row=paths[mode][sid][t-1]; d=diagnostics[mode][sid,t]
   u=[D(row['holdings_before_'+a])/D(row['wealth_before']) for a in h.ASSETS]
   w=h.TARGETS[x['target_name']]; tau=sum(abs(a-b) for a,b in zip(w,u))/2; fee=D('.0025')*tau; ce=D(x['ce_target']); keep=D(d['ce_keep'])
   expected={'tau':tau,'fee_fraction':fee,'pre_cost_benefit':ce-keep,'modeled_fee_impact':fee*ce,'conservative_score':(1-2*fee)*ce,'true_net_ce':(1-fee)*ce}
   for k,v in expected.items(): h.A.near('all_scores.algebra.'+k,v,x[k],D('2e-12'),D('1e-12'))
   count+=1; nscore+=1
  by_mode[mode]=nscore
  for (sid,t),d in diagnostics[mode].items():
   if d['action']=='human_review': continue
   n=min(5,t-1) if mode in ('balanced_context','balanced_adaptive') else 0
   h.A.eq('all_scores.recent_count',n,int(d['recent_count']))
   h.A.near('all_scores.prior_mass',D(15)/(15+n) if n else D(1),d['prior_mass'],D('1e-15'),D('1e-14'))
 h.A.eq('all_scores.exact_count',17823,count)
 return {'rows':count,'by_mode':by_mode,'scope':'Every saved score: target weights, holdings-derived transfer/fee and six scalar algebra fields; empirical CRRA expectations independently rescored on recorded representative states only.'}

def extra_corruptions(h,tables):
 result=[]
 metric=copy.deepcopy(tables['balanced_adaptive','scenario_metrics'][0])
 for case in ('wrong_cpi_derived_growth_rehashed','wrong_trade_denominator','wrong_drawdown_peak_kind','wrong_target_fee_algebra'):
  f=copy.deepcopy(metric)
  if case=='wrong_cpi_derived_growth_rehashed': f['net_real_cagr_pct']=str(D(f['net_real_cagr_pct'])+D('.1'))
  elif case=='wrong_trade_denominator': f['review_count']=str(int(f['review_count'])+1)
  elif case=='wrong_drawdown_peak_kind': f['drawdown_peak_kind']='invented'
  else:
   f=copy.deepcopy(tables['balanced_adaptive','target_scores'][0]); f['fee_fraction']=str(D(f['fee_fraction'])+D('.01'))
  raw=h.canonical(f); before={'sha256':sha(raw),'bytes':len(raw)}
  try:
   if case=='wrong_cpi_derived_growth_rehashed':
    expected=100*((D(f['terminal_real_wealth'])/100)**(D(1)/int(f['horizon']))-1); h.A.near('corrupt.actual.growth',expected,f['net_real_cagr_pct'])
   elif case=='wrong_trade_denominator': h.A.eq('corrupt.actual.denominator',int(f['horizon']),int(f['review_count']))
   elif case=='wrong_drawdown_peak_kind': require(f['drawdown_peak_kind'] in ('initial','post_fee','end'),'invalid drawdown point kind')
   else: h.A.near('corrupt.actual.fee',D('.0025')*D(f['tau']),f['fee_fraction'])
  except ValueError as ex: reason=str(ex)
  else: raise ValueError('accepted actual-row corruption '+case)
  after={'sha256':sha(raw),'bytes':len(raw)}; require(before==after,'corruption fixture changed')
  result.append({'case':case,'fixture':raw.decode(),'inventory_before':before,'inventory_after':after,'rejected':True,'reason':reason})
 return result

def latch_boundary_fixtures(h):
 facts=[]
 for terminal,expected in [('75.0000000001',False),('75',True),('74.9999999999',True)]:
  prefix=[{'period':'1','real_wealth_after_fee':'100','real_wealth_end':terminal}]
  loss=h.dd_path(prefix)[0]; latch=loss>=D(25); h.A.eq('fixture.latch.threshold',expected,latch)
  history=[]
  for obs in (loss,D(0),D(5)):
   history.append(obs>=25 if not history else history[-1] or obs>=25)
  h.A.eq('fixture.latch.persistent',latch,history[-1]); facts.append({'prefix':prefix,'expected_latched_next_review':expected,'observed_drawdown_pct':str(loss),'observed_latched_next_review':latch,'subsequent_drawdowns_pct':['0','5'],'observed_latch_history':history})
 return facts

def keyed_scalar_facts(h,tables,paths,diagnostics):
 metrics=[]; summaries=[]
 def facts(expected,observed):
  out={}
  for key,value in expected.items():
   out[key]={'expected':str(value) if isinstance(value,D) else value,'observed':observed[key]}
   if isinstance(value,D): out[key].update(absolute_tolerance='1e-9',relative_tolerance='1e-10')
  return out
 for mode in (*h.NEW,*h.OLD):
  for H in h.HORIZONS:
   row=next(x for x in tables[mode,'scenario_metrics'] if x['scenario_id']=='1' and int(x['horizon'])==H)
   metrics.append({'mode':mode,'scenario_id':1,'horizon':H,'fields':facts(h.metric_expected(paths[mode][1],diagnostics[mode],H,mode),row)})
   ms=[x for x in tables[mode,'scenario_metrics'] if int(x['horizon'])==H]; row=next(x for x in tables[mode,'summary'] if int(x['horizon'])==H)
   summaries.append({'mode':mode,'horizon':H,'fields':facts(h.summaries(ms,H,mode),row)})
 return {'metrics':metrics,'summaries':summaries}

def decision_reasons(h,diagnostics):
 counts=collections.Counter()
 for mode in h.NEW:
  for (sid,t),d in diagnostics[mode].items():
   action=d['action']
   expected='human_review_latched' if action=='human_review' else 'benefit_gate_failed' if action=='keep' else 'initial_allocation' if d['first_deployment_year'] and int(d['first_deployment_year'])==t else action
   h.A.eq('decision.reason',expected,d['reason']); counts[expected]+=1
 return dict(counts)

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--check',action='store_true',required=True); ap.parse_args(); start=time.perf_counter()
 require(sys.version_info[:2]==(3,12),'Python3.12 required'); require(not any(k.casefold()=='pythonpath' for k in os.environ),'PYTHONPATH must be absent')
 task,binding=fresh_authentication(); clean=clean_evidence(task)
 for deliverable in task['deliverables']:
  fp=ROOT/deliverable; require(fp.is_file() and 0<fp.stat().st_size<=task['parameters']['max_artifact_bytes'],'missing/oversized required review deliverable '+deliverable)
 protected=list(task['parameters']['source_sha256'])+['audit/SOL-040/'+p for p in ('verify.py','task-snapshot.json','historical/verify.py','historical/task-snapshot.json','historical/schemas.json','clean-environment-checks.json','producer-before-inventory.json','producer-check.stdout.log','producer-check.stderr.log')]
 before=inventory(protected)
 h=types.ModuleType('authenticated_sol036_arithmetic'); h.__file__=str(HERE/'historical/verify.py'); exec(compile((HERE/'historical/verify.py').read_bytes(),h.__file__,'exec'),h.__dict__); h.ROOT=ROOT
 t,p,pt,cfg,m,checks,inputb,canonical_inventory,endings=h.authenticate(); require(p==task['parameters']['producer'],'new/historical producer pin divergence')
 binding['historical_arithmetic_binding']={'base_commit':h.BASE,'publication_commit':h.PUBLICATION,'task_snapshot_sha256':h.TASK_HASH,'source_sha256':sha((HERE/'historical/verify.py').read_bytes()),'historical_gate':'Interrupted clean writer remains failed; only exact independent functions replayed here'}
 tables,counts,keyfacts=h.readtables(p,m); h.A.eq('producer.check.counts',counts,checks['counts']); market,gross,supports,priors=h.priors(inputb,p)
 paths,diagnostics,reps,actions=h.ledger_checks(tables,market); reconstructed=h.reconstruct_paths(paths,diagnostics,reps,market); h.metrics_all(tables,paths,diagnostics); bridges=h.imported_bridge(tables,p,cfg)
 algebra=all_saved_score_algebra(h,tables,paths,diagnostics); scores=h.scores_review(tables,paths,diagnostics,reps,supports,gross); future=h.no_lookahead(tables,paths,diagnostics,supports,gross); bad=h.corruptions(tables,p)+extra_corruptions(h,tables); latch_fixtures=latch_boundary_fixtures(h); reason_counts=decision_reasons(h,diagnostics); keyed_facts=keyed_scalar_facts(h,tables,paths,diagnostics)
 after=inventory(protected); require(before==after,'review modified protected inputs/evidence')
 result={'status':'passed_independent_review_checks_not_acceptance','binding':binding,'producer':p,'counts':counts,'canonical_inventory':canonical_inventory,'producer_runtime_seconds':m['elapsed_seconds'],'fresh_check':{'returncode':clean['returncode'],'elapsed_seconds':clean['elapsed_seconds'],'timeout_seconds':600,'unchanged':clean['unchanged'],'protected_files':len(clean['inventory_before']),'evidence_sha256':CLEAN_SHA,'owner_pid':clean['owner_pid'],'checkout_spellings':clean['verified_checkout_spellings'],'logs':clean['logs']},'source_consumed_line_endings':endings,'checked_keys':keyfacts,'training_priors':priors,'complete_paths':reps,'reconstructed_paths':reconstructed,'actions':actions,'decision_reason_counts':reason_counts,'import_bridge':bridges,'all_saved_score_algebra':algebra,'scores':scores,'future_perturbations':future,'latch_boundary_fixtures':latch_fixtures,'corruptions':bad,'comparison_counts':dict(h.A.counts),'max_errors_by_field':h.A.maxima,'scalar_fixtures':h.A.samples,'keyed_scalar_facts':keyed_facts,'read_only':{'inventory_before':before,'inventory_after':after,'unchanged':True},'arithmetic':'Authenticated exact SOL-036 stdlib source; Decimal precision50. CSV/original decimal factors for ledgers; float.hex binary64 reconstruction only where required by training digests and scoring support. All metrics and summaries recomputed; every saved score algebra/link checked, empirical CRRA rescoring sampled.','elapsed_seconds':time.perf_counter()-start,'untested_limits':['No exhaustive independent empirical rescoring of all17823 scores; representative complete paths and observed action boundaries only','Future perturbations replay independent score states with saved past holdings/active state; no mutated producer callback execution','Compact corruptions exercise reduced fixtures and selected real rows, not full mutated production bundles','No doubled group, final inputs, policy selection, customer assignment or generation','Exact locally retained Git objects required; verifier never fetches','Historical SOL-036 failed receipt and interrupted clean-check remain failed; new successful evidence cannot repair that historical attempt','Chief exact-commit review/acceptance remains required']}
 print(json.dumps(result,indent=2,default=str))
if __name__=='__main__':
 try: main()
 except Exception:
  import traceback
  traceback.print_exc(); sys.exit(1)
