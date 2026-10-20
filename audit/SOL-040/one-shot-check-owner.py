"""One-shot SOL-040 authorized producer read-only check; no retry."""
import os,sys,pathlib,subprocess,time,json,hashlib,datetime
root=pathlib.Path(sys.argv[1]).resolve(); out=root/'audit/SOL-040'; checkout=root/'.runtime/SOL-040-producer-isolated'
commit='6aa2ccdce80834c8beb52a827993f1f587d1d8a6'
def save(p,x):
 with p.open('w',encoding='utf8',newline='\n') as f: json.dump(x,f,indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
def sha(b): return hashlib.sha256(b).hexdigest()
def git(*args,cwd=root): return subprocess.check_output(['git',*args],cwd=cwd,stderr=subprocess.PIPE)
def inventory():
 result={}
 for rel in git('ls-files',cwd=checkout).decode().splitlines():
  p=checkout/rel
  if p.is_file():
   b=p.read_bytes(); result[rel]={'sha256':sha(b),'bytes':len(b)}
 return result
record={'task_id':'SOL-040','producer_commit':commit,'timeout_seconds':600,'execution_status':'preparing','python':sys.version,'owner_pid':os.getpid(),'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
try:
 assert sys.version_info[:2]==(3,12)
 with (out/'single-launch.guard').open('x') as f: f.write(record['started_at'])
 assert not checkout.exists()
 subprocess.run(['git','clone','--quiet','--shared','--no-checkout',str(root),str(checkout)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 cfg=json.loads(git('show',commit+':specs/execution/HY3-004-file44.json'))
 selected=set(cfg['source_sha256'])|{'scripts/run_development_policy.py','specs/execution/HY3-004-file44.json','data/development/scenarios_001_120.csv','results/development/HY3-004/'}
 subprocess.run(['git','sparse-checkout','set','--no-cone',*('/'+x for x in sorted(selected))],cwd=checkout,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 subprocess.run(['git','-c','core.autocrlf=false','checkout','--quiet','--detach',commit],cwd=checkout,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 env={k:v for k,v in os.environ.items() if k.casefold()!='pythonpath'}
 record.update(argv=[sys.executable,'-B','scripts/run_development_policy.py','--config','specs/execution/HY3-004-file44.json','--output','results/development/HY3-004','--check'],cwd=str(checkout),pythonpath_keys=[k for k in env if k.casefold()=='pythonpath'],removed_pythonpath_keys=[k for k in os.environ if k.casefold()=='pythonpath'],runtime_task_absent=not (checkout/'.runtime/task.json').exists(),checkout_head=git('rev-parse','HEAD',cwd=checkout).decode().strip(),git_status_before=git('status','--porcelain',cwd=checkout).decode(),inventory_before=inventory())
 assert record['runtime_task_absent'] and record['checkout_head']==commit and not record['git_status_before']
 save(out/'producer-before-inventory.json',record['inventory_before'])
 record['before_inventory_sha256']=sha((out/'producer-before-inventory.json').read_bytes()); record['execution_status']='running'; save(out/'clean-environment-checks.json',record)
 start=time.perf_counter(); record['launched_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
 with (out/'producer-check.stdout.log').open('xb') as stdout,(out/'producer-check.stderr.log').open('xb') as stderr:
  try:
   result=subprocess.run(record['argv'],cwd=checkout,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,timeout=600)
   record.update(returncode=result.returncode,execution_status='completed')
  except subprocess.TimeoutExpired:
   record.update(returncode=None,execution_status='timeout_600s')
  stdout.flush(); os.fsync(stdout.fileno()); stderr.flush(); os.fsync(stderr.fileno())
 record.update(elapsed_seconds=time.perf_counter()-start,finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),inventory_after=inventory(),git_status_after=git('status','--porcelain',cwd=checkout).decode())
 record['unchanged']=record['inventory_before']==record['inventory_after'] and record['git_status_before']==record['git_status_after']
 record['logs']={name:{'sha256':sha((out/name).read_bytes()),'bytes':(out/name).stat().st_size} for name in ('producer-check.stdout.log','producer-check.stderr.log')}
except Exception as ex:
 import traceback
 record.update(execution_status='infrastructure_failed',error=str(ex),traceback=traceback.format_exc())
save(out/'clean-environment-checks.json',record)
