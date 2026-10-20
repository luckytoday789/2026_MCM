import os,sys,subprocess,pathlib,time,json
root=pathlib.Path(sys.argv[1]); out=root/'audit/SOL-036'; env={k:v for k,v in os.environ.items() if k.lower()!='pythonpath'}
argv=[sys.executable,'-B','audit/SOL-036/verify.py','--check']; start=time.perf_counter()
with (out/'verifier-trial-1.stdout.log').open('wb') as stdout,(out/'verifier-trial-1.stderr.log').open('wb') as stderr:
 r=subprocess.run(argv,cwd=root,env=env,stdout=stdout,stderr=stderr)
d={'argv':argv,'returncode':r.returncode,'elapsed_seconds':time.perf_counter()-start,'python':sys.version,'pythonpath_keys':[k for k in env if k.lower()=='pythonpath']}
(out/'verifier-trial-1.json').write_text(json.dumps(d,indent=2)+'\n'); print(json.dumps(d))
