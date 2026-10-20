import os,sys,subprocess,pathlib,time,json,hashlib
project=pathlib.Path(sys.argv[1]); target=pathlib.Path(sys.argv[2]); label=sys.argv[3]; out=project/'audit/SOL-036'; env={k:v for k,v in os.environ.items() if k.lower()!='pythonpath'}
watch=['verify.py','task-snapshot.json','schemas.json','clean-environment-checks.json','.gitattributes']
def inventory():
 d={}
 for name in watch:
  b=(target/'audit/SOL-036'/name).read_bytes(); d['audit/SOL-036/'+name]={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
 producer=project/'.runtime/SOL-036-producer'
 clean=json.loads((out/'clean-environment-checks.json').read_text())
 for name in clean['inventory_after']:
  b=(producer/name).read_bytes(); d['isolated-producer/'+name]={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
 return d
argv=[sys.executable,'-B','audit/SOL-036/verify.py','--check']; before=inventory(); start=time.perf_counter()
with (out/(label+'.stdout.log')).open('wb') as stdout,(out/(label+'.stderr.log')).open('wb') as stderr:
 r=subprocess.run(argv,cwd=target,env=env,stdout=stdout,stderr=stderr)
after=inventory(); d={'argv':argv,'cwd':str(target),'returncode':r.returncode,'elapsed_seconds':time.perf_counter()-start,'python':sys.version,'pythonpath_keys':[k for k in env if k.lower()=='pythonpath'],'HEAD':subprocess.check_output(['git','rev-parse','HEAD'],cwd=target).decode().strip(),'runtime_task_absent':not (target/'.runtime/task.json').exists(),'inventory_before':before,'inventory_after':after,'unchanged':before==after}
(out/(label+'.json')).write_bytes((json.dumps(d,indent=2)+'\n').encode()); print(json.dumps({k:d[k] for k in ('returncode','elapsed_seconds','HEAD','runtime_task_absent','unchanged')}))
