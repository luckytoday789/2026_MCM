"""Record actual fresh commands; creation only, never used by --check."""
import os,subprocess,sys,time,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def main():
    label=sys.argv[1]
    commands=[[sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_policy_analysis_writer.py','-v']]
    if label.endswith('verify-only'):commands=[]
    if not label.endswith('tests-only'):commands.append([sys.executable,'-B','audit/SOL-038/verify.py','--check'])
    env={k:v for k,v in os.environ.items() if k.upper()!='PYTHONPATH'}
    def inventory():
        paths=list(json.loads((ROOT/'audit/SOL-038/task.json').read_text())['parameters']['source_sha256'])
        paths+=['src/safeinvest/policy_analysis_writer.py','scripts/run_development_analysis.py','tests/test_policy_analysis_writer.py']
        paths+=[p.relative_to(ROOT).as_posix() for p in (ROOT/'audit/SOL-038/fixture').rglob('*') if p.is_file()]
        return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    records=[]
    for i,argv in enumerate(commands):
        before=inventory();start=time.monotonic()
        with (ROOT/'audit/SOL-038'/(label+'-'+str(i)+'.stdout.txt')).open('xb') as out, (ROOT/'audit/SOL-038'/(label+'-'+str(i)+'.stderr.txt')).open('xb') as err:
            r=subprocess.run(argv,cwd=ROOT,env=env,stdout=out,stderr=err,timeout=300)
        def desc(name):
            p=ROOT/'audit/SOL-038'/name;raw=p.read_bytes()
            return dict(path=p.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
        record=dict(argv=argv,exit_code=r.returncode,elapsed_seconds=time.monotonic()-start,
            python=sys.version,executable=sys.executable,before=before,after=inventory(),inventories_unchanged=before==inventory(),
            pythonpath_absent=not any(k.upper()=='PYTHONPATH' for k in env),
            stdout=desc(label+'-'+str(i)+'.stdout.txt'),stderr=desc(label+'-'+str(i)+'.stderr.txt'))
        records.append(record)
        (ROOT/'audit/SOL-038'/(label+'.json')).write_text(json.dumps(records,indent=2)+'\n',encoding='utf8')
    print(json.dumps([dict(argv=r['argv'],exit_code=r['exit_code'],elapsed_seconds=r['elapsed_seconds'],inventories_unchanged=r['inventories_unchanged']) for r in records]))
    sys.exit(0 if all(r['exit_code']==0 for r in records) else 1)

if __name__=='__main__':main()
