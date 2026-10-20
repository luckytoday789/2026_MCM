"""Single audit replay at later HEAD; never invokes producer writer."""
import hashlib,json,os,platform,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE/'.portable'
CHECK=ROOT/'audit/SOL-041'
def sha(b):return hashlib.sha256(b).hexdigest()
def inventory():
 files={}
 for p in CHECK.iterdir():
  if p.is_file():files[p.name]={'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())}
 return {'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'runtime_task_exists':(ROOT/'.runtime/task.json').exists(),'audit_files':files,'git_status':subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)}
def save(name,obj):
 with (HERE/name).open('w',encoding='utf8',newline='\n') as f:json.dump(obj,f,indent=2);f.write('\n')
before=inventory();save('portable-before.json',before)
assert not before['runtime_task_exists']
env={k:v for k,v in os.environ.items() if k.upper()!='PYTHONPATH'}
argv=[sys.executable,'-B','audit/SOL-041/verify.py','--check'];started=time.monotonic();record={'argv':argv,'head':before['head'],'python':platform.python_version(),'runtime_task_exists':False,'removed_environment_keys':[k for k in os.environ if k.upper()=='PYTHONPATH'],'timeout_seconds':300,'stdout':'portable.stdout.log','stderr':'portable.stderr.log'}
with (HERE/record['stdout']).open('wb') as out,(HERE/record['stderr']).open('wb') as err:
 try:record['exit_code']=subprocess.run(argv,cwd=ROOT,env=env,stdout=out,stderr=err,timeout=300).returncode
 except subprocess.TimeoutExpired:record.update(exit_code=None,timed_out=True)
record['duration_seconds']=time.monotonic()-started;after=inventory();save('portable-after.json',after);record['unchanged']=before==after
for key in ('stdout','stderr'):record[key+'_sha256']=sha((HERE/record[key]).read_bytes())
record['status']='passed' if record.get('exit_code')==0 and record['unchanged'] else 'failed';save('portability.json',record)
