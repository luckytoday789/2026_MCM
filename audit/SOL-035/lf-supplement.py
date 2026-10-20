import json,pathlib,subprocess,sys,os,time,importlib.util
R=pathlib.Path(__file__).resolve().parents[2]; H=R/'audit/SOL-035'; s=importlib.util.spec_from_file_location('v',H/'verify.py'); v=importlib.util.module_from_spec(s); s.loader.exec_module(v)
env={k:x for k,x in os.environ.items() if k.upper()!='PYTHONPATH'}; env['PYTHONDONTWRITEBYTECODE']='1'; records=[]
def save(): (H/'lf-supplement.json').write_text(json.dumps(records,indent=2,sort_keys=True)+'\n',encoding='utf8',newline='\n')
def snap(root): return {p.relative_to(root).as_posix():v.sha(p.read_bytes()) for d in v.PROTECTED for p in (root/d).rglob('*') if p.is_file()}
def run(args,cwd,check=False,expect=0,label=None):
 before=snap(cwd) if check else None; t=time.time(); r=subprocess.run(args,cwd=cwd,env=env,capture_output=True); after=snap(cwd) if check else None
 x=dict(argv=[str(a) for a in args],cwd=str(cwd),exit_code=r.returncode,runtime_seconds=time.time()-t,stdout=r.stdout.decode(errors='replace'),stderr=r.stderr.decode(errors='replace'),PYTHONPATH_keys=[k for k in env if k.upper()=='PYTHONPATH'])
 if check: x.update(before=before,after=after,unchanged=before==after,label=label)
 records.append(x); save()
 if r.returncode!=expect or (check and before!=after): raise AssertionError('unexpected command result')
 return r
D=R/'.runtime/sol035-fixtures/explicit-lf'
run(['git','clone','--shared','--no-checkout','--local',str(R),str(D)],R)
run(['git','config','core.autocrlf','false'],D); run(['git','config','core.eol','lf'],D)
run(['git','sparse-checkout','init','--cone'],D); run(['git','sparse-checkout','set',*v.PROTECTED,'ops'],D)
run(['git','checkout','--detach',v.BASE],D)
T=D/'audit/SOL-035'; T.mkdir(parents=True)
copied={}
for n in ('.gitattributes','task.json','task-runtime.json','verify.py','canonical-inventory.json','verification.json'):
 b=(H/n).read_bytes(); (T/n).write_bytes(b); copied[n]=v.sha(b)
assert not (D/'.runtime/task.json').exists()
raw=(D/'specs/PROBLEM_LOCK.md').read_bytes(); cr=(R/'.runtime/sol035-fixtures/autocrlf-true/specs/PROBLEM_LOCK.md').read_bytes(); canonical=v.blob(v.OLDPUB,'specs/PROBLEM_LOCK.md')
assert raw==canonical and cr==canonical.replace(b'\n',b'\r\n') and raw!=cr
records.append(dict(actual_LF=True,actual_CRLF=True,LF_sha256=v.sha(raw),CRLF_sha256=v.sha(cr),LF_bytes=len(raw),CRLF_bytes=len(cr),runtime_task_absent=True,copied_sha256=copied)); save()
run([sys.executable,'-B','audit/SOL-035/verify.py','--check'],D,True,label='explicit-lf-later-main')
extra=D/'audit/SOL-002/sol035-extra.txt'; extra.write_bytes(b'extra\n')
try: run([sys.executable,'-B','audit/SOL-035/verify.py','--check'],D,True,1,'actual_extra_path_rejection')
finally: extra.unlink()
