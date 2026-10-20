"""One authorized writer check; this file is never called by portable verification."""
import hashlib,json,os,platform,subprocess,sys,time,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE/'.isolated'
PINS=json.loads((HERE/'task-pins.json').read_text())
p=PINS['parameters']['producer']
paths=set(PINS['parameters']['source_sha256'])|set(p['artifacts_sha256'])|{p['input']['path'],p['config_path'],'handoff/HY3-006/result.json','ops/tasks/HY3-006.json'}
# Some review-only source pins postdate the producer checkout. Protect all present pins.
paths=sorted(x for x in paths if (ROOT/x).is_file())
def digest(b):return hashlib.sha256(b).hexdigest()
def inventory():
 return {'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'runtime_task_exists':(ROOT/'.runtime/task.json').exists(),'files':{x:{'bytes':(ROOT/x).stat().st_size,'sha256':digest((ROOT/x).read_bytes())} for x in paths},'git_status':subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)}
def save(name,obj):
 with (HERE/name).open('w',encoding='utf-8',newline='\n') as f:json.dump(obj,f,indent=2);f.write('\n')
before=inventory();save('protected-before.json',before)
assert before['head']==p['result_commit'] and not before['runtime_task_exists'] and not before['git_status']
env={k:v for k,v in os.environ.items() if k.upper()!='PYTHONPATH'}
argv=[sys.executable,'-B','scripts/run_development_policy.py','--config',p['config_path'],'--output','results/development/HY3-006','--check']
start=time.time();mono=time.monotonic()
record={'schema_version':1,'argv':argv,'python':platform.python_version(),'cwd_kind':'new isolated actual Git checkout','producer_commit':p['result_commit'],'timeout_seconds':600,'removed_environment_keys':[k for k in os.environ if k.upper()=='PYTHONPATH'],'started_at_unix':start,'launch_count':1,'retry_allowed':False,'stdout':'writer.stdout.log','stderr':'writer.stderr.log','before_inventory':'protected-before.json','owner_pid':os.getpid()}
with (HERE/'writer.stdout.log').open('wb') as stdout,(HERE/'writer.stderr.log').open('wb') as stderr:
 save('writer-launch.json',record)
 try:
  child=subprocess.Popen(argv,cwd=ROOT,env=env,stdout=stdout,stderr=stderr)
  record['child_pid']=child.pid
  try:record['exit_code']=child.wait(timeout=600);record['timed_out']=False
  except subprocess.TimeoutExpired:
   child.kill();child.wait();record.update(exit_code=child.returncode,timed_out=True)
 except Exception as exc:record.update(exit_code=None,launch_failure=repr(exc));traceback.print_exc(file=stderr)
record['duration_seconds']=time.monotonic()-mono;record['finished_at_unix']=time.time()
after=inventory();save('protected-after.json',after)
record.update(unchanged=before==after,after_inventory='protected-after.json',stdout_sha256=digest((HERE/'writer.stdout.log').read_bytes()),stderr_sha256=digest((HERE/'writer.stderr.log').read_bytes()))
record['status']='passed' if record.get('exit_code')==0 and record['unchanged'] and not record.get('timed_out') else 'failed'
save('clean-environment-checks.json',record)
