"""Read-only exact HY3-004 review. Stdlib only; no producer imports or baseline execution.
Uses immutable Git blobs, independent Decimal arithmetic, and compact rejection fixtures.
"""
import argparse, collections, csv, hashlib, io, json, math, os, pathlib, subprocess, sys, time
from decimal import Decimal as D, getcontext
getcontext().prec=50
HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parents[1]
BASE='2694cf053586e71488781b192efb54518f77c62f'
PUBLICATION='c21af611288936474a866c550894dbca9fe14d75'
TASK_HASH='c35c70135c296104326ddfad1cfdaba1ee16a21130b0a97856097f7ebf3ce70e'
SCHEMA_HASH='95c86210121afd493b7d5f50409b05e20cabcd745f104f0a21eaa221cd9d9b65'
PREFIX='results/development/HY3-004/'
ASSETS=('equity','bond','bill_proxy')
HORIZONS=(5,6,15,25,30)
NEW=('conservative_cost','balanced_cost','growth_cost','balanced_context','balanced_adaptive')
OLD=('bills_keep','equal_weight_annual','equal_weight_buy_hold')
TARGETS={'conservative':(D('.15'),D('.2'),D('.65')),'balanced':(D(1)/3,)*3,'growth':(D('.6'),D('.3'),D('.1')),'defensive':(D('.2'),D('.25'),D('.55')),'growth_tilt':(D('.45'),D('.3'),D('.25'))}
UNITS={'monetary_units':'nominal units; real wealth in CPI_0 purchasing power','return_units':'annual simple decimal','cpi_units':'price index; CPI_0=1','growth_units':'percent/year','volatility_units':'percentage points; annual sample ddof=1','loss_units':'percent of running real peak','trade_share_units':'percent of annual reviews'}
CACHE={}
def sha(b): return hashlib.sha256(b).hexdigest()
def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')
def pairs(items):
 d={}
 for k,v in items:
  if k in d: raise ValueError('duplicate JSON key '+k)
  d[k]=v
 return d
def loads(b): return json.loads(b,object_pairs_hook=pairs,parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
def git(*a): return subprocess.check_output(['git',*a],cwd=ROOT,stderr=subprocess.PIPE)
def blob(c,p):
 key=(c,p)
 if key not in CACHE: CACHE[key]=git('show',c+':'+p)
 return CACHE[key]
def require(v,msg):
 if not v: raise ValueError(msg)
def dec(x): return D(str(x))
def bdec(x): return D.from_float(float(x))
def boolean(x):
 require(x in ('true','false'),'invalid bool'); return x=='true'
class Audit:
 def __init__(self): self.counts=collections.Counter(); self.maxima={}; self.samples=[]
 def eq(self,k,e,o):
  self.counts[k]+=1
  require(e==o,f'{k}: expected {e!r}, observed {o!r}')
 def near(self,k,e,o,atol=D('1e-9'),rtol=D('1e-10'),sample=False):
  e=dec(e); o=dec(o); err=abs(e-o); lim=atol+rtol*abs(e)
  self.counts[k]+=1
  if k not in self.maxima or err>D(self.maxima[k]['absolute_error']): self.maxima[k]={'expected':str(e),'observed':str(o),'absolute_error':str(err),'allowed_error':str(lim)}
  if sample or self.counts[k]==1: self.samples.append({'key':k,'expected':str(e),'observed':str(o),'absolute_tolerance':str(atol),'relative_tolerance':str(rtol)})
  require(err<=lim,f'{k}: expected {e}, observed {o}, error {err} > {lim}')
A=Audit()
def csvrows(b):
 r=csv.DictReader(io.StringIO(b.decode('utf8'),newline=''))
 require(r.fieldnames and len(set(r.fieldnames))==len(r.fieldnames),'duplicate CSV columns')
 out=list(r); require(all(None not in row and None not in row.values() for row in out),'ragged CSV')
 return out

def authenticate():
 tbytes=(HERE/'task-snapshot.json').read_bytes(); require(sha(tbytes)==TASK_HASH,'review task snapshot pin')
 t=loads(tbytes); p=t['parameters']['producer']; r=p['result_commit']; e=p['base_commit']; pub=p['publication_commit']; c=p['source_commit']
 # Exact review publication is independent of current HEAD and runtime task presence.
 A.eq('review.publication.parent',BASE,git('rev-parse',PUBLICATION+'^').decode().strip())
 A.eq('review.published.task',loads(tbytes),loads(blob(PUBLICATION,'ops/tasks/SOL-036.json')))
 A.eq('review.base',BASE,t['base_commit']); A.eq('review.allowed_paths',['audit/SOL-036'],t['allowed_paths'])
 for path,h in t['parameters']['source_sha256'].items(): A.eq('review.base.source.'+path,h,sha(blob(BASE,path)))
 A.eq('producer.result.parent',e,git('rev-parse',r+'^').decode().strip())
 require(subprocess.run(['git','merge-base','--is-ancestor',c,e],cwd=ROOT).returncode==0,'C not ancestor E')
 require(subprocess.run(['git','merge-base','--is-ancestor',e,pub],cwd=ROOT).returncode==0,'E not ancestor P')
 A.eq('producer.publication.parent',e,git('rev-parse',pub+'^').decode().strip())
 tb=blob(pub,'ops/tasks/HY3-004.json'); pt=loads(tb)
 A.eq('producer.task.blob',p['task_blob_sha256'],sha(tb)); A.eq('producer.task.canonical',p['task_sha256'],sha(canonical(pt)))
 A.eq('producer.task.base',e,pt['base_commit']); A.eq('producer.task.owner','hy3',pt['owner']); A.eq('producer.task.attempt',1,pt['attempt'])
 cfgb=blob(e,p['config_path']); cfg=loads(cfgb); A.eq('config.sha',p['config_sha256'],sha(cfgb)); A.eq('config.result.unchanged',cfgb,blob(r,p['config_path']))
 A.eq('config.source',c,cfg['source_commit']); A.eq('config.group','primary',cfg['group'])
 receiptb=blob(r,'handoff/HY3-004/result.json'); receipt=loads(receiptb)
 A.eq('receipt.sha',p['receipt_sha256'],sha(receiptb)); A.eq('receipt.status','completed',receipt['status']); A.eq('receipt.failure',None,receipt['failure'])
 for key,expect in [('task_id','HY3-004'),('attempt',1),('role','hy3'),('base_commit',e),('task_sha256',p['task_sha256']),('artifact_hash_basis','canonical_git_blob')]: A.eq('receipt.'+key,expect,receipt[key])
 A.eq('receipt.artifacts',p['artifacts_sha256'],receipt['artifacts_sha256']); A.eq('receipt.parameters',pt['parameters'],receipt['task_parameters'])
 require(receipt['python'].startswith('3.12.'),'receipt Python not 3.12')
 commands=pt['commands']+pt['validation_commands']; A.eq('receipt.command.count',4,len(receipt['checks']))
 for i,(expected,record) in enumerate(zip(commands,receipt['checks'])):
  A.eq('receipt.command.argv.'+str(i),expected[1:],record['argv'][1:]); A.eq('receipt.command.exit.'+str(i),0,record['exit_code'])
  text=blob(r,f'handoff/HY3-004/check-{i}.txt').decode(); require(text.strip(),'empty producer log')
 changed=git('diff-tree','--no-commit-id','--name-only','-r',r).decode().splitlines()
 expected=set(pt['deliverables'])|set(p['artifacts_sha256'])|{'handoff/HY3-004/result.json'}
 A.eq('result.changed.paths',expected,set(changed)); A.eq('result.required.files',44,len(pt['deliverables']))
 inventory={}
 for path in sorted(expected):
  line=git('ls-tree',r,'--',path).decode(); require(line.startswith('100644 blob '),'not regular file '+path)
  b=blob(r,path); require(len(b)<=10485760,'artifact too large'); inventory[path]={'sha256':sha(b),'bytes':len(b)}
  if path in p['artifacts_sha256']: A.eq('artifact.hash.'+path,p['artifacts_sha256'][path],sha(b))
 for path,h in cfg['source_sha256'].items():
  for commit in (c,e,r): A.eq('source.pin.'+path,h,sha(blob(commit,path)))
 inputb=blob(r,p['input']['path']); A.eq('input.sha',p['input']['sha256'],sha(inputb)); A.eq('input.base',inputb,blob(e,p['input']['path']))
 m=loads(blob(r,PREFIX+'run_manifest.json')); checks=loads(blob(r,PREFIX+'checks.json'))
 A.eq('manifest.status','completed',m['status']); A.eq('manifest.config',cfg,m['configuration']); A.eq('manifest.input',p['input']['sha256'],m['input_sha256']); A.eq('manifest.fee',.0025,m['fee_rate'])
 A.eq('manifest.P',pub,m['provenance']['binding']['publication_commit']); A.eq('manifest.task',pt,m['provenance']['binding']['task'])
 A.eq('manifest.E',e,m['provenance']['binding']['base_commit']); A.eq('manifest.C',c,m['provenance']['binding']['source_commit']); A.eq('manifest.digest',p['task_sha256'],m['provenance']['binding']['task_digest'])
 require(0<m['elapsed_seconds']<=1200,'producer runtime exceeds limit'); require(m['python'].startswith('3.12.'),'manifest Python')
 for path,key in [('calibrations.json','calibrations_sha256'),('checks.json','checks_sha256'),('reference_imports.json','references_sha256')]: A.eq('manifest.sidehash.'+path,sha(blob(r,PREFIX+path)),m[key])
 # Historical CRLF consumption is evidence, never rehashed into a new receipt.
 endings={}
 for path,h in m['provenance']['sources']['consumed'].items():
  b=blob(c,path); variants={sha(b):'canonical',sha(b.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')):'CRLF'}
  require(h in variants,'unexplained consumed bytes '+path); endings[path]=variants[h]
 ref=cfg['references'][0]; refb=blob(ref['reviewed_commit'],'handoff/HY3-003/result.json'); A.eq('HY3-003.receipt',ref['receipt_sha256'],sha(refb))
 for path,h in ref['artifacts_sha256'].items(): A.eq('HY3-003.artifact.'+path,h,sha(blob(ref['reviewed_commit'],path)))
 return t,p,pt,cfg,m,checks,inputb,inventory,endings

def readtables(p,m):
 sb=(HERE/'schemas.json').read_bytes(); require(sha(sb)==SCHEMA_HASH,'schema snapshot pin'); schemas=loads(sb)
 A.eq('manifest.schemas',schemas,m['artifacts'])
 tables={}; totals=collections.Counter(); keys_digests={}
 for path,meta in schemas.items():
  b=blob(p['result_commit'],PREFIX+path); A.eq('table.bytes.'+path,meta['bytes'],len(b)); A.eq('table.hash.'+path,meta['sha256'],sha(b))
  rows=csvrows(b); names=[x[0] for x in meta['schema']]; A.eq('table.columns.'+path,names,next(csv.reader(io.StringIO(b.decode()))))
  A.eq('table.rows.'+path,meta['rows'],len(rows)); keys=[]
  for row in rows:
   for name,typ,nullable in meta['schema']:
    x=row[name]
    if x=='': require(nullable,'forbidden null '+name); continue
    if typ=='int': require(str(int(x))==x,'noncanonical int '+name)
    elif typ=='float': require(math.isfinite(float(x)),'nonfinite '+name)
    elif typ=='bool': boolean(x)
    else: require(typ=='str','unknown schema type')
   key=tuple(int(row[k]) if k!='target_name' else row[k] for k in meta['keys']); keys.append(key)
   A.eq('table.split','development',row['split']); A.near('table.fee',D('.0025'),row['fee_rate'],D(0),D(0))
   if 'scenario_id' in row: A.eq('table.fold',(int(row['scenario_id'])-1)%4,int(row['fold_id']))
   for k,v in UNITS.items():
    if k in row: A.eq('table.unit.'+k,v,row[k])
  require(len(keys)==len(set(keys)),'duplicate table key '+path)
  mode,filename=path.split('/')[1:]; kind=filename[:-4]
  if kind=='annual_ledgers' or kind=='decisions' and mode in NEW: expected=[(s,t) for s in range(1,121) for t in range(1,31)]; A.eq('keys.'+path,expected,keys)
  elif kind=='scenario_metrics': A.eq('keys.'+path,[(s,h) for s in range(1,121) for h in HORIZONS],keys)
  elif kind=='summary': A.eq('keys.'+path,[(h,) for h in HORIZONS],keys)
  if mode in OLD and kind in ('decisions','target_scores'): A.eq('reference.empty.'+path,[],rows); A.eq('reference.inapplicable.'+path,False,meta['applicable'])
  totals[kind]+=len(rows); keys_digests[path]={'count':len(keys),'keys_sha256':sha(canonical(keys))}
  tables[(mode,kind)]=rows
 A.eq('counts.ledgers',28800,totals['annual_ledgers']); A.eq('counts.metrics',4800,totals['scenario_metrics']); A.eq('counts.summary',40,totals['summary']); A.eq('counts.decisions',18000,totals['decisions']); require(totals['target_scores']<=24000,'score limit')
 return tables,dict(totals),keys_digests

def priors(inputb,p):
 market=csvrows(inputb); fields=['scenario_id','period','equity_return','bond_return','bill_proxy_return','inflation']; require(list(market[0])==fields,'market schema'); A.eq('market.rows',3600,len(market))
 original={}; floats={}; gross={}
 for i,row in enumerate(market):
  sid,t=divmod(i,30); A.eq('market.key',(sid+1,t+1),(int(row['scenario_id']),int(row['period'])))
  nums=[float(row[k]) for k in fields[2:]]; require(all(math.isfinite(x) and x>-1 for x in nums),'market gross')
  original[sid+1,t+1]=tuple(D(row[k]) for k in fields[2:]); floats[sid+1,t+1]=nums
  gross[sid+1,t+1]=tuple((1+x)/(1+nums[3]) for x in nums[:3])
 cal=loads(blob(p['result_commit'],PREFIX+'calibrations.json')); facts=[]; supports={}
 for f in range(4):
  train=[s for s in range(1,121) if (s-1)%4!=f]; ev=[s for s in range(1,121) if (s-1)%4==f]; keys=[(s,t) for s in train for t in range(1,31)]
  rp={'schema':'training-annual-simple-v1','fields':fields,'rows':[[s,t,*(x.hex() for x in floats[s,t])] for s,t in keys]}
  gp={'schema':'training-real-gross-v1','asset_order':fields[2:5],'rows':[[s,t,*(x.hex() for x in gross[s,t])] for s,t in keys]}
  expect={'fold_id':f,'training_scenario_ids':train,'evaluation_scenario_ids':ev,'training_row_keys':[list(k) for k in keys],'training_row_count':2700,'training_rows_sha256':sha(canonical(rp)),'real_gross_sha256':sha(canonical(gp)),'annual_weight':'1 / training_row_count','asset_order':fields[2:5]}
  A.eq('calibration.fold.'+str(f),expect,cal['arithmetic_manifest']['folds'][f]); A.eq('calibration.attestation.'+str(f),expect,cal['attestation']['folds'][f])
  supports[f]=[tuple(D.from_float(x) for x in gross[k]) for k in keys]
  facts.append({k:v for k,v in expect.items() if k not in ('training_row_keys','training_scenario_ids','evaluation_scenario_ids')})
 return original,gross,supports,facts

def dd_path(rows):
 peak=D(100); loc=(0,'initial'); best=D(0); pl=tl=loc
 for row in rows:
  for kind,col in [('post_fee','real_wealth_after_fee'),('end','real_wealth_end')]:
   value=D(row[col]); point=(int(row['period']),kind)
   if value>peak: peak=value; loc=point
   loss=100*(1-value/peak)
   if loss>best: best=loss; pl=loc; tl=point
 return best,pl,tl

def ledger_checks(tables,market):
 paths={}; action_counts={}; reps={}; diagnostics={}
 for mode in (*NEW,*OLD):
  rows=tables[mode,'annual_ledgers']; grouped=collections.defaultdict(list)
  for row in rows: grouped[int(row['scenario_id'])].append(row)
  paths[mode]=grouped
  ds={(int(d['scenario_id']),int(d['period'])):d for d in tables[mode,'decisions']}; diagnostics[mode]=ds
  counts=collections.Counter(); examples={}; selected={1,2,3,4}
  selected.add(int(next(x for x in tables[mode,'summary'] if x['horizon']=='30')['severe_scenario_id']))
  for sid,rs in grouped.items():
   cpi=D(1); prev=[D(0),D(0),D(100)]; active='conservative' if mode=='conservative_cost' else 'growth' if mode=='growth_cost' else 'balanced'; deployed=None; deferred=False; latch=False
   for row in rs:
    t=int(row['period']); returns=market[sid,t]; before=[D(row['holdings_before_'+a]) for a in ASSETS]; after=[D(row['holdings_after_fee_'+a]) for a in ASSETS]; end=[D(row['holdings_end_'+a]) for a in ASSETS]; W=sum(before)
    for i,a in enumerate(ASSETS): A.near('ledger.continuity.'+a,prev[i],before[i]); require(before[i]>=0 and after[i]>=0 and end[i]>=0,'short holding')
    for i,a in enumerate(ASSETS): A.near('ledger.original.return.'+a,returns[i],row['return_'+a],D('1e-16'),D('1e-14'))
    A.near('ledger.original.inflation',returns[3],row['inflation'],D('1e-16'),D('1e-14'))
    A.near('ledger.cpi.before',cpi,row['cpi_before']); A.near('ledger.wealth.before',W,row['wealth_before']); A.near('ledger.real.before',W/cpi,row['real_wealth_before'])
    if row['engine_action']=='keep':
     transfer=D(0); fee=D(0); A.eq('ledger.keep.exact.dollars',before,after)
     require(all(row['target_'+a]=='' for a in ASSETS),'keep target must null')
    else:
     A.eq('ledger.engine.action','rebalance',row['engine_action']); target=[D(row['target_'+a]) for a in ASSETS]; A.near('ledger.target.sum',1,sum(target)); require(min(target)>=0,'short target')
     transfer=sum(abs(W*w-h) for w,h in zip(target,before))/2; fee=transfer*D('.0025')
     for i,a in enumerate(ASSETS): A.near('ledger.after_fee.'+a,(W-fee)*target[i],after[i])
    A.near('ledger.transfer',transfer,row['intended_transfer']); A.near('ledger.fee',fee,row['fee']); A.near('ledger.after_fee.W',W-fee,row['wealth_after_fee']); A.near('ledger.after_fee.real',(W-fee)/cpi,row['real_wealth_after_fee'])
    for i,a in enumerate(ASSETS): A.near('ledger.end.'+a,after[i]*(1+returns[i]),end[i])
    old_real=W/cpi; cpi*=1+returns[3]; real=sum(end)/cpi
    A.near('ledger.cpi.end',cpi,row['cpi_end']); A.near('ledger.wealth.end',sum(end),row['wealth_end']); A.near('ledger.real.end',real,row['real_wealth_end']); A.near('ledger.annual.net',real/old_real-1,row['annual_net_real_return'])
    prev=end
    if mode in OLD: continue
    d=ds[sid,t]; action=d['action']; counts[action]+=1; examples.setdefault(action,(sid,t)); obs=dd_path(rs[:t-1])[0]
    A.near('decision.observed.dd',obs,d['observed_max_drawdown_pct']); latch=latch or obs>=25
    A.eq('decision.latch',latch,boolean(d['human_review_latched'])); A.eq('decision.human.action',latch,action=='human_review')
    A.eq('decision.active.before',active,d['active_before']); selected_name=d['selected_target']
    executed=action in ('rebalance','target_change'); A.eq('decision.engine.link',executed,row['engine_action']=='rebalance'); A.eq('decision.selected.link',executed,bool(selected_name))
    change=executed and selected_name!=active; A.eq('decision.target.change',change,boolean(d['executed_target_change'])); A.eq('decision.action.target_change',change,action=='target_change')
    if executed:
     require(selected_name in TARGETS,'unknown selected target')
     for i,a in enumerate(ASSETS): A.near('decision.target.weights',TARGETS[selected_name][i],row['target_'+a],D('1e-15'),D('1e-14'))
     active=selected_name
     if deployed is None and transfer>0: deployed=t
    if t==1: deferred=deployed is None
    A.eq('decision.active.after',active,d['active_after']); A.eq('decision.deployment',deployed,int(d['first_deployment_year']) if d['first_deployment_year'] else None); A.eq('decision.deferral',deferred,boolean(d['initial_allocation_deferred']))
    A.near('decision.transfer.link',row['intended_transfer'],d['intended_transfer'],D(0),D(0)); A.near('decision.fee.link',row['fee'],d['actual_fee'],D(0),D(0)); A.eq('decision.trade',D(row['intended_transfer'])>D('1e-10'),boolean(d['is_trade']))
    if latch: require(transfer==fee==0,'latched fee/transfer'); A.eq('decision.latch.keep',before,after)
    if deferred: examples.setdefault('initial_deferral',(sid,t))
   # selected complete paths will also receive independent score reconstruction
  for key in ('initial_deferral','target_change','human_review'):
   if key in examples: selected.add(examples[key][0])
  reps[mode]=sorted(selected); action_counts[mode]={'counts':dict(counts),'first_examples':examples,'absent':[x for x in ('initial_deferral','target_change','human_review') if x not in examples]}
 return paths,diagnostics,reps,action_counts

def reconstruct_paths(paths,diagnostics,reps,market):
 facts=[]
 for mode in NEW:
  for sid in reps[mode]:
   holding=[D(0),D(0),D(100)]; cpi=D(1); fee_sum=D(0)
   for row in paths[mode][sid]:
    t=int(row['period']); d=diagnostics[mode][sid,t]; W=sum(holding)
    for i,a in enumerate(ASSETS): A.near('path.reconstructed.before.'+a,holding[i],row['holdings_before_'+a])
    if d['selected_target']:
     target=TARGETS[d['selected_target']]; transfer=sum(abs(W*w-h) for w,h in zip(target,holding))/2; fee=transfer*D('.0025'); after=[(W-fee)*w for w in target]
    else: transfer=fee=D(0); after=list(holding)
    A.near('path.reconstructed.transfer',transfer,row['intended_transfer']); A.near('path.reconstructed.fee',fee,row['fee']); fee_sum+=fee
    for i,a in enumerate(ASSETS): A.near('path.reconstructed.after.'+a,after[i],row['holdings_after_fee_'+a])
    returns=market[sid,t]; holding=[h*(1+r) for h,r in zip(after,returns[:3])]; cpi*=1+returns[3]
    for i,a in enumerate(ASSETS): A.near('path.reconstructed.end.'+a,holding[i],row['holdings_end_'+a])
    A.near('path.reconstructed.real',sum(holding)/cpi,row['real_wealth_end'])
   facts.append({'mode':mode,'scenario_id':sid,'periods':30,'expected_terminal_real':str(sum(holding)/cpi),'observed_terminal_real':row['real_wealth_end'],'expected_fee_sum':str(fee_sum),'all_values_propagated_independently_from_initial_bills':True})
 return facts

def metric_expected(rs,ds,H,mode):
 prefix=rs[:H]; terminal=D(prefix[-1]['real_wealth_end']); returns=[D(x['annual_net_real_return']) for x in prefix]; avg=sum(returns)/H
 loss,peak,trough=dd_path(prefix); trade=sum(D(x['intended_transfer'])>D('1e-10') for x in prefix); later=sum(D(x['intended_transfer'])>D('1e-10') for x in prefix[1:])
 out={'net_real_cagr_pct':100*((terminal/100)**(D(1)/H)-1),'annual_real_volatility_pct':100*(sum((v-avg)**2 for v in returns)/(H-1)).sqrt(),'max_real_drawdown_pct':loss,'terminal_real_wealth':terminal,'nominal_fee_sum':sum(D(x['fee']) for x in prefix),'trade_count':trade,'review_count':H,'later_trade_count':later,'later_review_count':H-1,'trade_share_pct':D(100)*trade/H,'trade_share_ex_initial_pct':D(100)*later/(H-1),'drawdown_peak_year':peak[0],'drawdown_peak_kind':peak[1],'drawdown_trough_year':trough[0],'drawdown_trough_kind':trough[1]}
 if mode in NEW:
  decisions=[ds[int(x['scenario_id']),int(x['period'])] for x in prefix]; hr=[int(d['period']) for d in decisions if d['action']=='human_review']; deploy=[int(d['period']) for d in decisions if d['selected_target'] and D(d['intended_transfer'])>0]
  out.update(human_review_count=len(hr),human_review_share_pct=D(100)*len(hr)/H,first_latch_year=min(hr) if hr else None,target_change_count=sum(d['action']=='target_change' for d in decisions),first_deployment_year=min(deploy) if deploy else None,initial_allocation_deferred=boolean(decisions[0]['initial_allocation_deferred']))
 else:
  out.update({k:None for k in ('human_review_count','human_review_share_pct','first_latch_year','target_change_count','first_deployment_year','initial_allocation_deferred')})
 return out

def compare_record(label,e,row,sample=False):
 for k,v in e.items():
  obs=row[k]
  if v is None: A.eq(label+'.'+k,'',obs)
  elif isinstance(v,bool): A.eq(label+'.'+k,v,boolean(obs))
  elif isinstance(v,str): A.eq(label+'.'+k,v,obs)
  elif isinstance(v,int): A.eq(label+'.'+k,v,int(obs))
  else: A.near(label+'.'+k,v,obs,sample=sample)

def quantile(v,q):
 v=sorted(v); pos=(len(v)-1)*q; low=int(pos); f=pos-low; return v[low]+f*(v[min(low+1,len(v)-1)]-v[low])
def summaries(ms,H,mode):
 col=lambda k:[D(x[k]) for x in ms]
 out={'scenario_count':120}
 for target,k,q in [('median_growth_pct','net_real_cagr_pct','.5'),('p10_growth_pct','net_real_cagr_pct','.1'),('median_loss_pct','max_real_drawdown_pct','.5'),('p90_loss_pct','max_real_drawdown_pct','.9'),('median_volatility_pct','annual_real_volatility_pct','.5'),('median_terminal_real_wealth','terminal_real_wealth','.5'),('median_nominal_fee_sum','nominal_fee_sum','.5')]: out[target]=quantile(col(k),D(q))
 for src in ('trade_count','review_count','later_trade_count','later_review_count'): out['pooled_'+src]=sum(int(x[src]) for x in ms)
 out['pooled_trade_share_pct']=D(100)*out['pooled_trade_count']/out['pooled_review_count']; out['pooled_trade_share_ex_initial_pct']=D(100)*out['pooled_later_trade_count']/out['pooled_later_review_count']
 # Exact binary64 ordering is the locked saved-metric severe rule, no epsilon tie.
 severe=min(ms,key=lambda x:(-float(x['max_real_drawdown_pct']),int(x['scenario_id'])))
 out['severe_scenario_id']=int(severe['scenario_id'])
 for k in ('net_real_cagr_pct','max_real_drawdown_pct','terminal_real_wealth','drawdown_peak_year','drawdown_peak_kind','drawdown_trough_year','drawdown_trough_kind','trade_share_pct','trade_share_ex_initial_pct'):
  out['severe_'+k]=severe[k] if k.endswith('kind') else int(severe[k]) if k.endswith('year') else D(severe[k])
 if mode in NEW:
  count=sum(int(x['human_review_count']) for x in ms); out.update(pooled_human_review_count=count,pooled_human_review_share_pct=D(100)*count/(120*H),pooled_target_change_count=sum(int(x['target_change_count']) for x in ms))
 else: out.update(pooled_human_review_count=None,pooled_human_review_share_pct=None,pooled_target_change_count=None)
 return out

def metrics_all(tables,paths,ds):
 for mode in (*NEW,*OLD):
  for row in tables[mode,'scenario_metrics']:
   s,H=int(row['scenario_id']),int(row['horizon']); expected=metric_expected(paths[mode][s],ds[mode],H,mode); compare_record('metric',expected,row,sample=s==1 and H==30)
  for row in tables[mode,'summary']:
   H=int(row['horizon']); ms=[x for x in tables[mode,'scenario_metrics'] if int(x['horizon'])==H]; expected=summaries(ms,H,mode); compare_record('summary',expected,row,sample=H==30)

def imported_bridge(tables,p,cfg):
 ref=cfg['references'][0]; counts={}
 for kind in ('annual_ledgers','scenario_metrics','summary'):
  original=csvrows(blob(ref['reviewed_commit'],'results/development/HY3-003/'+kind+'.csv')); indexed={}
  for mode in OLD:
   new=tables[mode,kind]; old=[x for x in original if x['policy']==mode]; A.eq('bridge.rowcount.'+kind,len(old),len(new)); n=0
   for x,y in zip(old,new):
    for k,v in x.items():
     dest={'policy':'mode','year':'period','action':'engine_action'}.get(k,k)
     if k=='growth_units': A.eq('bridge.unit.old','percentage points per year',v); v='percent/year'
     A.eq('bridge.value.'+kind+'.'+dest,v,y[dest]); n+=1
   counts[mode+'/'+kind]={'rows':len(old),'unchanged_cells_including_explicit_renames':n}
 return counts

MOMENTS={}
def ce(weights,support,recent,fold,cache_name=None):
 weights=tuple(x/sum(weights) for x in weights)
 def moment(rows): return sum(sum(w*g for w,g in zip(weights,row))**-3 for row in rows)/len(rows)
 if cache_name is not None:
  key=(fold,cache_name)
  if key not in MOMENTS: MOMENTS[key]=moment(support)
  prior=MOMENTS[key]
 else: prior=moment(support)
 n=len(recent); m=(15*prior+sum(sum(w*g for w,g in zip(weights,row))**-3 for row in recent))/(15+n)
 return m**(-D(1)/3)
def preferred(scores,active):
 top=max(scores.values()); allowed={k for k,v in scores.items() if top-v<=D('1e-12')}
 return next(k for k in dict.fromkeys((active,'defensive','balanced','growth_tilt',*scores)) if k in allowed)
def score_one(row,d,mode,sid,t,supports,gross,history_override=None):
 holding=[D(row['holdings_before_'+a]) for a in ASSETS]; W=sum(holding); u=[h/W for h in holding]; fold=(sid-1)%4
 n=min(5,t-1) if mode in ('balanced_context','balanced_adaptive') else 0
 recent=[tuple(D.from_float(x) for x in gross[sid,j]) for j in range(t-n,t)] if history_override is None else history_override[-n:] if n else []
 keep=ce(u,supports[fold],recent,fold); active=d['active_before']; names=[active] if mode!='balanced_adaptive' or t<6 else ['defensive','balanced','growth_tilt']
 scores={}; details={}
 for name in names:
  w=TARGETS[name]; target=ce(w,supports[fold],recent,fold,name); tau=sum(abs(wi-ui) for wi,ui in zip(w,u))/2; fee=D('.0025')*tau
  detail={'ce_target':target,'tau':tau,'fee_fraction':fee,'pre_cost_benefit':target-keep,'modeled_fee_impact':fee*target,'conservative_score':(1-2*fee)*target,'true_net_ce':(1-fee)*target}
  details[name]=detail; scores[name]=detail['conservative_score']
 eligible={k:v for k,v in scores.items() if v>keep+D('1e-12')}; selected=preferred(eligible,active) if eligible else ''
 return keep,details,preferred(scores,active),selected,n

def scores_review(tables,paths,diagnostics,reps,supports,gross):
 records=[]; checked=[]
 for mode in NEW:
  score_index=collections.defaultdict(list)
  for x in tables[mode,'target_scores']: score_index[int(x['scenario_id']),int(x['period'])].append(x)
  for sid,rs in paths[mode].items():
   for row in rs:
    t=int(row['period']); d=diagnostics[mode][sid,t]; linked=score_index[sid,t]
    if d['action']=='human_review': A.eq('scores.latch.empty',[],linked); A.eq('scores.latch.ce.null','',d['ce_keep']); continue
    active=d['active_before']; expected_names=[active] if mode!='balanced_adaptive' or t<6 else ['defensive','balanced','growth_tilt']
    A.eq('scores.evaluated.names',set(expected_names),{x['target_name'] for x in linked})
    # Every saved target/decision link and strict hurdle, even outside sampled paths.
    scores={x['target_name']:D(x['conservative_score']) for x in linked}; eligible={k:v for k,v in scores.items() if v>D(d['ce_keep'])+D('1e-12')}
    A.eq('scores.saved.proposed',preferred(scores,active),d['proposed_target']); A.eq('scores.saved.selected',preferred(eligible,active) if eligible else '',d['selected_target'])
    for x in linked:
     require(x['target_name'] in TARGETS,'unknown scored target');
     for i,a in enumerate(ASSETS): A.near('scores.weights',TARGETS[x['target_name']][i],x['target_'+a],D('1e-15'),D('1e-14'))
    if sid not in reps[mode]: continue
    keep,details,proposed,selected,n=score_one(row,d,mode,sid,t,supports,gross)
    A.near('score.independent.keep',keep,d['ce_keep'],D('2e-12'),D('1e-12'),sample=t in (1,5,6,30) and sid==1)
    A.eq('score.independent.recent',n,int(d['recent_count'])); A.near('score.independent.prior_mass',D(15)/(15+n) if mode in ('balanced_context','balanced_adaptive') else D(1),d['prior_mass'],D('1e-15'),D('1e-14'))
    A.eq('score.independent.proposed',proposed,d['proposed_target']); A.eq('score.independent.selected',selected,d['selected_target'])
    for x in linked:
     for k,v in details[x['target_name']].items(): A.near('score.independent.'+k,v,x[k],D('2e-12'),D('1e-12'),sample=sid==1 and t in (1,5,6))
    checked.append((mode,sid,t))
    if t in (1,5,6) and sid<=4: records.append({'mode':mode,'scenario_id':sid,'period':t,'expected_ce_keep':str(keep),'observed_ce_keep':d['ce_keep'],'expected_selected':selected,'observed_selected':d['selected_target'],'n':n,'fold':(sid-1)%4})
 return {'checked_states':len(checked),'checked_keys':checked,'scalar_boundaries':records}

def no_lookahead(tables,paths,diagnostics,supports,gross):
 # Isolated in-memory copied fixtures: evaluation future rows are never inserted in training.
 facts=[]
 for mode in ('balanced_context','balanced_adaptive'):
  for sid in range(1,5):
   for boundary in (5,6):
    row=paths[mode][sid][boundary-1]; d=diagnostics[mode][sid,boundary]
    if d['action']=='human_review': continue
    changed=dict(gross)
    for t in range(boundary,31): changed[sid,t]=(9.0,.1,1.7)
    a=score_one(row,d,mode,sid,boundary,supports,gross); b=score_one(row,d,mode,sid,boundary,supports,changed)
    A.eq('future.perturbation',a,b); facts.append({'mode':mode,'sid':sid,'decision_period':boundary,'changed_periods':[boundary,30],'expected_selected':a[3],'observed_selected':b[3],'unchanged':True})
 return facts

def fixture_validate(f):
 require(set(f['files'])=={'metric','decision'},'missing required file')
 require(f['task']=='HY3-004' and f['base']=='93a232a926dc3d1bfb18e2866ef0ddb0aaf9bc0f' and f['source']=='bc04d428425a9afbea799e036213632dc6568c73','wrong binding')
 require(f['config']=='5d09fe13400b04b14a26fbfa03810a56c5b1b0a7f0ddd13e855918afbeb60eee','wrong config')
 require(f['input']=='9c4ad83f5dda86251a754e126528a71dd930ae88ed7cdb8a0663a327b6bfb7c7','wrong input')
 require(f['count']==1 and f['status']=='completed','wrong count/status')
 require(f['metric_hash']==sha(canonical(f['files']['metric'])),'metric hash')
 row=f['files']['metric']; expected=100*((D(row['terminal_real_wealth'])/100)**(D(1)/int(row['H']))-1)
 require(abs(expected-D(row['growth']))<D('1e-10'),'independent numerical metric mismatch')
 d=f['files']['decision']; require(d['action']=='human_review' and d['engine_action']=='keep' and D(d['fee'])==0 and D(d['transfer'])==0,'bad observed action link')

def corruptions(tables,p):
 import copy
 base={'task':'HY3-004','base':'93a232a926dc3d1bfb18e2866ef0ddb0aaf9bc0f','source':'bc04d428425a9afbea799e036213632dc6568c73','config':'5d09fe13400b04b14a26fbfa03810a56c5b1b0a7f0ddd13e855918afbeb60eee','input':'9c4ad83f5dda86251a754e126528a71dd930ae88ed7cdb8a0663a327b6bfb7c7','count':1,'status':'completed','files':{'metric':{'terminal_real_wealth':'121','H':2,'growth':'10'},'decision':{'action':'human_review','engine_action':'keep','fee':'0','transfer':'0'}}}; actual=tables['balanced_adaptive','scenario_metrics'][0]
 base['files']['metric']={'terminal_real_wealth':actual['terminal_real_wealth'],'H':int(actual['horizon']),'growth':actual['net_real_cagr_pct']}
 observed=next(d for d in tables['balanced_adaptive','decisions'] if d['action']=='human_review')
 base['files']['decision']={'action':observed['action'],'engine_action':'keep','fee':observed['actual_fee'],'transfer':observed['intended_transfer']}
 base['canonical_bindings']={'metric':{'path':PREFIX+'cases/balanced_adaptive/scenario_metrics.csv','sha256':p['artifacts_sha256'][PREFIX+'cases/balanced_adaptive/scenario_metrics.csv'],'key':[int(actual['scenario_id']),int(actual['horizon'])]},'decision':{'path':PREFIX+'cases/balanced_adaptive/decisions.csv','sha256':p['artifacts_sha256'][PREFIX+'cases/balanced_adaptive/decisions.csv'],'key':[int(observed['scenario_id']),int(observed['period'])]}}
 base['metric_hash']=sha(canonical(base['files']['metric'])); fixture_validate(base)
 result=[]
 for case in ('missing_file','duplicate_key','wrong_task','wrong_base','wrong_source','wrong_config','wrong_input','false_count','incomplete_status','changed_metric','rehashed_wrong_metric','bad_observed_action_link'):
  f=copy.deepcopy(base)
  if case=='missing_file': del f['files']['decision']
  elif case.startswith('wrong_'): f[case[6:]]='wrong'
  elif case=='false_count': f['count']=2
  elif case=='incomplete_status': f['status']='failed'
  elif case in ('changed_metric','rehashed_wrong_metric'):
   f['files']['metric']['growth']=str(D(f['files']['metric']['growth'])+1)
   if case=='rehashed_wrong_metric': f['metric_hash']=sha(canonical(f['files']['metric']))
  elif case=='bad_observed_action_link': f['files']['decision']['fee']='.01'
  raw=canonical(f)
  if case=='duplicate_key': raw=raw[:-1]+b',"status":"completed"}'
  before={'sha256':sha(raw),'bytes':len(raw)}
  try: fixture_validate(loads(raw))
  except (ValueError,KeyError) as ex: reason=str(ex)
  else: raise ValueError('corruption accepted '+case)
  after={'sha256':sha(raw),'bytes':len(raw)}; A.eq('corruption.unchanged',before,after)
  result.append({'case':case,'fixture':raw.decode(),'inventory_before':before,'inventory_after':after,'rejected':True,'reason':reason})
 return result

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--check',action='store_true',required=True); args=ap.parse_args(); started=time.perf_counter()
 require(sys.version_info[:2]==(3,12),'Python3.12 required'); require(not any(k.lower()=='pythonpath' for k in os.environ),'PYTHONPATH must be absent')
 t,p,pt,cfg,m,checks,inputb,inventory,endings=authenticate(); tables,counts,keyfacts=readtables(p,m)
 A.eq('producer.check.counts',counts,checks['counts']); market,gross,supports,priorfacts=priors(inputb,p)
 paths,diagnostics,reps,actions=ledger_checks(tables,market); reconstructed=reconstruct_paths(paths,diagnostics,reps,market); metrics_all(tables,paths,diagnostics); bridges=imported_bridge(tables,p,cfg)
 scorefacts=scores_review(tables,paths,diagnostics,reps,supports,gross); future=no_lookahead(tables,paths,diagnostics,supports,gross); bad=corruptions(tables,p)
 clean=loads((HERE/'clean-environment-checks.json').read_bytes()); require(clean['runtime_task_absent'] and clean['pythonpath_keys']==[],'clean environment binding'); clean_pass=clean['returncode']==0 and clean.get('unchanged') is True and clean.get('inventory_before')==clean.get('inventory_after')
 # An interrupted actual execution remains blocking even when independent arithmetic passes.
 result={'status':'passed_independent_arithmetic_clean_writer_blocked' if not clean_pass else 'passed_independent_review_checks_not_acceptance','review_base':BASE,'review_publication':PUBLICATION,'producer':p,'counts':counts,'canonical_inventory':inventory,'producer_runtime_seconds':m['elapsed_seconds'],'clean_writer_runtime_seconds':clean['elapsed_seconds'],'source_consumed_line_endings':endings,'checked_keys':keyfacts,'training_priors':priorfacts,'complete_paths':reps,'reconstructed_paths':reconstructed,'actions':actions,'import_bridge':bridges,'scores':scorefacts,'future_perturbations':future,'corruptions':bad,'comparison_counts':dict(A.counts),'max_errors_by_field':A.maxima,'scalar_fixtures':A.samples,'arithmetic':'Decimal precision50; decimal CSV ledger arithmetic and original decimal market factors; binary64 hex reconstructed only for specified training digest; Decimal inverse-cube moments over binary64 support without producer functions','elapsed_seconds':time.perf_counter()-started,'untested_limits':['No doubled-fee outcomes or behavior reviewed','No full independent rescoring of every unsampled score state; all saved score/decision links and gates checked','No producer kernel extreme-subnormal repeat; accepted earlier reviews unchanged','No final inputs, policy selection, customer assignment or production generation','Portable verifier requires exact Git objects retained locally; does not fetch network objects','Future perturbations replay independent predecision states and same saved past holdings; no mutated production callback execution']}
 print(json.dumps(result,indent=2,default=str))
 if not clean_pass: sys.exit(2)
if __name__=='__main__':
 try: main()
 except Exception as ex:
  import traceback
  traceback.print_exc(); sys.exit(1)
