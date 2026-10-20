"""Durable launcher for reviewer-only checks. Never invokes producer writer."""
import sys,os,pathlib,subprocess,time,json,hashlib,datetime
root=pathlib.Path(sys.argv[1]).resolve(); label=sys.argv[2]; out=root/'audit/SOL-040'; cwd=pathlib.Path(sys.argv[3]).resolve() if len(sys.argv)>3 else root
assert all(c.isalnum() or c in '-_' for c in label)
env={k:v for k,v in os.environ.items() if k.casefold()!='pythonpath'}
argv=[sys.executable,'-B','audit/SOL-040/verify.py','--check']; start=time.perf_counter()
record={'argv':argv,'cwd':str(cwd),'python':sys.version,'pythonpath_keys':[k for k in env if k.casefold()=='pythonpath'],'runtime_task_absent':not(cwd/'.runtime/task.json').exists(),'HEAD':subprocess.check_output(['git','rev-parse','HEAD'],cwd=cwd).decode().strip(),'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
with (out/(label+'.stdout.log')).open('xb') as stdout,(out/(label+'.stderr.log')).open('xb') as stderr:
 try:
  result=subprocess.run(argv,cwd=cwd,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,timeout=300)
  record.update(returncode=result.returncode,execution_status='completed')
 except subprocess.TimeoutExpired: record.update(returncode=None,execution_status='timeout_300s')
 stdout.flush(); os.fsync(stdout.fileno()); stderr.flush(); os.fsync(stderr.fileno())
record.update(elapsed_seconds=time.perf_counter()-start,finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
record['logs']={name:{'sha256':hashlib.sha256((out/name).read_bytes()).hexdigest(),'bytes':(out/name).stat().st_size} for name in (label+'.stdout.log',label+'.stderr.log')}
with (out/(label+'.json')).open('x',encoding='utf8',newline='\n') as f: json.dump(record,f,indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
