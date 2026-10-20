"""SOL-043 read-only recovery replay; uses local exact Git objects, never a writer.

--check creates disposable ignored clones only. It does not record or rewrite any
source, expected evidence, task, original log, or prior audit. No remote refs used.
"""
import argparse, copy, hashlib, json, os, platform, subprocess, sys, tempfile, time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
BASE='e23fc9aa76407be9d7efe8702825c90d616d507a'
PUBLICATION='452c8ad7dad856eb271d4cfb266c45eb7904f362'
TASK_DIGEST='9d7ae651d4cb8264213197f2d00ed7c0cf8b8b1170996191f5e5fd20b37632ab'
OLD='1f7f328313a5976aa9ff60375432d61457f7d811'

def need(ok,msg):
 if not ok: raise AssertionError(msg)
def sha(b): return hashlib.sha256(b).hexdigest()
def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
def pairs(xs):
 d={}
 for k,v in xs:
  need(k not in d,'duplicate JSON key');d[k]=v
 return d
def strict(b): return json.loads(b,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite JSON')))
def git(*args,cwd=ROOT): return subprocess.check_output(['git',*args],cwd=cwd,stderr=subprocess.PIPE)
def blob(c,p): return git('show',c+':'+p)
def pinned(raw,h,label): need(sha(raw)==h,'pinned bytes: '+label)
def task_bound(t,h,label): need(sha(canonical(t))==h,'immutable task: '+label)
def entry(raw): return {'bytes':len(raw),'sha256':sha(raw)}
def ancestor(a,b): need(subprocess.run(['git','merge-base','--is-ancestor',a,b],cwd=ROOT,capture_output=True).returncode==0,'ancestry')

def authenticate():
 t=strict((HERE/'task-pins.json').read_bytes());task_bound(t,TASK_DIGEST,'SOL-043')
 need(strict(blob(PUBLICATION,'ops/tasks/SOL-043.json'))==t,'exact new task publication')
 q=next(x for x in strict(blob(PUBLICATION,'ops/queue.json'))['tasks'] if x['id']=='SOL-043')
 need(q['task_sha256']==TASK_DIGEST and q['state']=='ready' and q['branch']=='work/sol/SOL-043-a1','immutable publication queue')
 ancestor(BASE,PUBLICATION)
 need((t['id'],t['attempt'],t['owner'],t['base_commit'],t['allowed_paths'])==('SOL-043',1,'sol',BASE,['audit/SOL-043']),'new task scope/base')
 for p,h in t['parameters']['source_sha256'].items(): pinned(blob(BASE,p),h,'SOL-043 base '+p)
 p=t['parameters']['unaccepted_predecessor'];need(p['result_commit']==OLD,'old result identity')
 need(git('rev-parse',OLD+'^').decode().strip()==p['base_commit'],'old exact parent')
 raw=blob(OLD,'audit/SOL-041/task-pins.json');ot=strict(raw);task_bound(ot,p['task_sha256'],'SOL-041')
 need(raw==blob(BASE,'ops/tasks/SOL-041.json'),'old task canonical Git blob')
 need((ot['id'],ot['owner'],ot['attempt'],ot['base_commit'])==('SOL-041','sol',1,p['base_commit']),'old task identity')
 need(ot['allowed_paths']==['audit/SOL-041'],'old task scope')
 for name,h in ot['parameters']['source_sha256'].items(): pinned(blob(ot['base_commit'],name),h,'SOL-041 source '+name)
 raw=blob(OLD,'handoff/SOL-041/result.json');pinned(raw,p['receipt_sha256'],'old receipt');r=strict(raw)
 need((r['task_id'],r['role'],r['attempt'],r['base_commit'],r['task_sha256'])==('SOL-041','sol',1,p['base_commit'],p['task_sha256']),'old receipt identity')
 need(r['status']=='completed' and r['failure'] is None and r['artifact_hash_basis']=='canonical_git_blob' and r['started_from_pinned_source'] is True,'old completed receipt is preserved')
 need(r['task_parameters']==ot['parameters'] and r['python'].startswith('3.12.'),'old receipt full parameters/Python')
 need(r['input_manifest']==strict(blob(p['base_commit'],'data/manifest.json')),'old receipt metadata')
 commands=ot['commands']+ot['validation_commands'];checks=r['checks'][1:]
 need(len(checks)==len(commands) and all(x['exit_code']==0 for x in r['checks']),'old command exits')
 for a,b in zip(commands,checks): need(a[1:]==b['argv'][1:],'old command argv')
 need(r['artifacts_sha256']==p['artifacts_sha256'],'old full artifact map')
 names=set(git('diff','--name-only',p['base_commit'],OLD).decode().splitlines())
 need(names==set(p['artifacts_sha256'])|{'handoff/SOL-041/result.json'},'old exact changed paths')
 need(set(ot['deliverables'])<=names,'old required deliverables')
 inventory={}
 for name,h in p['artifacts_sha256'].items():
  raw=blob(OLD,name);pinned(raw,h,'old artifact '+name)
  need(git('ls-tree',OLD,'--',name).split()[0] in (b'100644',b'100755'),'regular Git artifact')
  need(name.startswith(('audit/SOL-041/','handoff/SOL-041/')),'old allowed paths');inventory[name]=entry(raw)
 for name in p['missing_logs_sha256']: need(not git('ls-tree',OLD,'--',name).strip(),'original delivery failure must remain')
 rejection=strict(blob(BASE,'audit/chief/SOL-041-delivery-rejection.json'))
 need(rejection['reviewed_commit']==OLD and rejection['exit_code']==1 and rejection['missing_logs']==p['missing_logs_sha256'] and rejection['producer_accepted'] is False,'chief rejection preserved')
 records={}
 for record_name,prefix in [('clean-environment-checks.json','writer'),('portability.json','portable')]:
  rec=strict(blob(OLD,'audit/SOL-041/'+record_name));need(rec['status']=='passed' and rec['exit_code']==0 and rec['unchanged'],'old local record')
  need(rec['python'].startswith('3.12.'),'old recorded Python')
  for key in ('stdout','stderr'):
   path='audit/SOL-041/'+rec[key];need(path=='audit/SOL-041/'+prefix+'.'+key+'.log','original named log')
   need(rec[key+'_sha256']==p['missing_logs_sha256'][path],'original log record binding')
  if prefix=='writer':
   need(rec['launch_count']==1 and rec['timeout_seconds']==600 and not rec.get('timed_out') and rec['duration_seconds']<=601,'old single writer record')
   a=strict(blob(OLD,'audit/SOL-041/'+rec['before_inventory']));b=strict(blob(OLD,'audit/SOL-041/'+rec['after_inventory']))
   need(a==b and a['head']==t['parameters']['producer']['result_commit'] and not a['runtime_task_exists'] and not a['git_status'],'old writer protected inventories')
  else:
   need(rec['runtime_task_exists'] is False and rec['timeout_seconds']==300,'old portable record')
   need(blob(OLD,'audit/SOL-041/portable-before.json')==blob(OLD,'audit/SOL-041/portable-after.json'),'old portable inventory equality')
  records[prefix]=rec
 return t,ot,{'new_task_digest':TASK_DIGEST,'new_base':BASE,'new_publication':PUBLICATION,'old_task_digest':p['task_sha256'],'old_base':p['base_commit'],'old_result':OLD,'receipt_sha256':p['receipt_sha256'],'artifact_inventory':inventory,'source_pins':ot['parameters']['source_sha256'],'changed_paths':sorted(names),'chief_rejection':rejection,'original_records':records}

def recovered(t,meta,files):
 expected=t['parameters']['unaccepted_predecessor']['missing_logs_sha256'];need(set(meta['files'])==set(expected),'four log metadata keys')
 need(meta['predecessor']==OLD and meta['source_kind']=='preserved original SOL-041 worktree','original local recovery origin')
 out={}
 for path,h in expected.items():
  m=meta['files'][path];dest='recovered-'+path.rsplit('/',1)[1].replace('.log','.txt')
  need(m['deliverable']==dest and m['sha256']==h,'immutable original log metadata '+path)
  need(dest in files,'missing recovered log '+dest);raw=files[dest];pinned(raw,h,'original recovered log '+path)
  need(m['bytes']==len(raw) and m['source_git_tracked'] is False,'log byte count/original untracked status')
  out[path]=entry(raw)
 return out

def negative_tests(t,ot,meta,files):
 results=[]
 def reject(name,fn,payload):
  before=sha(canonical(payload))
  try: fn()
  except (AssertionError,KeyError,ValueError,TypeError) as e: reason=str(e)
  else: raise AssertionError('corruption accepted: '+name)
  need(before==sha(canonical(payload)),'read-only negative overlay')
  results.append({'name':name,'observed':'rejected','reason':reason,'overlay_sha256_before':before,'overlay_sha256_after':sha(canonical(payload))})
 for path,m in meta['files'].items():
  name=m['deliverable'];f=dict(files);del f[name]
  reject('missing '+name,lambda:recovered(t,meta,f),{k:entry(v) for k,v in f.items()})
  f=dict(files);f[name]=files[name]+b'false log\n'
  reject('changed '+name,lambda:recovered(t,meta,f),{k:entry(v) for k,v in f.items()})
  mm=copy.deepcopy(meta);mm['files'][path].update(entry(f[name]))
  reject('rehashed false metadata '+name,lambda:recovered(t,mm,f),mm)
 for label,obj,h in [('new task',t,TASK_DIGEST),('original task',ot,t['parameters']['unaccepted_predecessor']['task_sha256'])]:
  wrong=copy.deepcopy(obj);wrong['base_commit']='0'*40
  reject('wrong '+label,lambda:task_bound(wrong,h,label),wrong)
 for label,c,path,h in [('original source',ot['base_commit'],'src/safeinvest/accounting.py',ot['parameters']['source_sha256']['src/safeinvest/accounting.py']),('original numeric evidence',OLD,'audit/SOL-041/verification.json',t['parameters']['unaccepted_predecessor']['artifacts_sha256']['audit/SOL-041/verification.json'])]:
  raw=blob(c,path)+b'\nfalse\n'
  reject('changed '+label,lambda:pinned(raw,h,label),entry(raw))
 return results

def protected_inventory(clone,paths):
 inv={p:entry((clone/p).read_bytes()) for p in sorted(paths)}
 logpaths=sorted('audit/SOL-041/'+n for n in ('writer.stdout.log','writer.stderr.log','portable.stdout.log','portable.stderr.log'))
 need(not git('ls-files','--',*logpaths,cwd=clone).strip(),'recovered logs remain untracked in reconstruction')
 return {'head':git('rev-parse','HEAD',cwd=clone).decode().strip(),'runtime_task_exists':(clone/'.runtime/task.json').exists(),'git_status':git('status','--porcelain','--untracked-files=all',cwd=clone).decode(),'protected_files':inv,'recovered_untracked_logs':{p:entry((clone/p).read_bytes()) for p in logpaths},'ignored_logs':git('ls-files','--others','--ignored','--exclude-standard','--','audit/SOL-041/*.log',cwd=clone).decode().splitlines()}

def replay(t,ot,files):
 scratch=ROOT/'.runtime';scratch.mkdir(exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='sol043-check-',dir=scratch) as tmp:
  clone=Path(tmp)/'old-exact'
  started=time.monotonic();git('clone','--shared','--no-checkout',str(ROOT),str(clone))
  git('config','core.autocrlf','false',cwd=clone);git('config','core.eol','lf',cwd=clone);git('checkout','--detach',OLD,cwd=clone)
  need((clone/'.git').is_dir(),'actual Git clone')
  for path in t['parameters']['unaccepted_predecessor']['missing_logs_sha256']:
   name='recovered-'+path.rsplit('/',1)[1].replace('.log','.txt');(clone/path).write_bytes(files[name])
  producer=ot['parameters']['producer'];paths=set(t['parameters']['unaccepted_predecessor']['artifacts_sha256'])|set(ot['parameters']['source_sha256'])|set(producer['artifacts_sha256'])|{'handoff/SOL-041/result.json','handoff/HY3-006/result.json'}
  object_only={p:entry(blob(producer['result_commit'],p)) for p in sorted(paths) if not (clone/p).is_file()}
  paths={p for p in paths if (clone/p).is_file()}
  before=protected_inventory(clone,paths)
  need(before['head']==OLD and not before['runtime_task_exists'] and not before['git_status'],'exact clean reconstruction')
  for p in t['parameters']['unaccepted_predecessor']['artifacts_sha256']: need((clone/p).read_bytes()==blob(OLD,p),'unchanged old canonical audit '+p)
  env={k:v for k,v in os.environ.items() if k.upper()!='PYTHONPATH'}
  removed=[k for k in os.environ if k.upper()=='PYTHONPATH']
  argv=[sys.executable,'-B','audit/SOL-041/verify.py','--check'];out=Path(tmp)/'replay.stdout.txt';err=Path(tmp)/'replay.stderr.txt'
  wall=time.monotonic();start_unix=time.time();exit_code=None;timed_out=False
  with out.open('wb') as so,err.open('wb') as se:
   try: exit_code=subprocess.run(argv,cwd=clone,env=env,stdout=so,stderr=se,timeout=300).returncode
   except subprocess.TimeoutExpired: timed_out=True
  duration=time.monotonic()-wall;after=protected_inventory(clone,paths);stdout=out.read_bytes();stderr=err.read_bytes()
  r={'argv':argv,'python':platform.python_version(),'cwd_kind':'new ignored actual local Git clone at exact original result','clone_method':'git clone --shared --no-checkout; local objects only','head':OLD,'started_at_unix':start_unix,'duration_seconds':duration,'total_with_setup_seconds':time.monotonic()-started,'timeout_seconds':300,'exit_code':exit_code,'timed_out':timed_out,'removed_environment_keys':removed,'pythonpath_keys_in_child':[k for k in env if k.upper()=='PYTHONPATH'],'stdout_utf8':stdout.decode('utf8'),'stderr_utf8':stderr.decode('utf8'),'stdout_sha256':sha(stdout),'stderr_sha256':sha(stderr),'before_inventory':before,'after_inventory':after,'unchanged':before==after}
  need(exit_code==0 and not timed_out,'unchanged original verifier failed: '+stderr.decode('utf8',errors='replace'))
  need(before==after,'original audit/source/evidence changed')
  result=strict(stdout);need((result['accounting_checks'],result['decision_checks'],result['own_checks'],result['corruptions'],result['read_only'])==(735115,472295,624595,17,True),'full original arithmetic counts')
  need(result['status']=='passed' and result['producer']==t['parameters']['producer']['result_commit'],'original numerical replay identity')
  saved=strict(blob(OLD,'audit/SOL-041/verification.json'));future=saved['fixtures']['generated_tests']['future']
  need(len(future)==20 and all(x['unchanged'] for x in future),'original 20 future perturbations')
  r['arithmetic']=result;r['future_perturbations_replayed']=len(future);r['producer_evidence_in_exact_git_objects_only']=object_only
  return r

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true',required=True);ap.parse_args()
 need(sys.version_info[:2]==(3,12),'Python 3.12 required')
 start=time.monotonic();t,ot,auth=authenticate();meta=strict((HERE/'recovery-provenance.json').read_bytes())
 files={m['deliverable']:(HERE/m['deliverable']).read_bytes() for m in meta['files'].values()}
 logs=recovered(t,meta,files);negative=negative_tests(t,ot,meta,files);r=replay(t,ot,files)
 report={'schema_version':1,'status':'passed','task_id':'SOL-043','task_sha256':TASK_DIGEST,'base_commit':BASE,'authentication':auth,'recovered_logs':logs,'negative_tests':negative,'original_replay':r,'writer_launches':0,'producer_accepted':False,'chief_exact_successor_review_required':True,'read_only':True,'duration_seconds':time.monotonic()-start}
 print(json.dumps(report,sort_keys=True,allow_nan=False))
if __name__=='__main__': main()
