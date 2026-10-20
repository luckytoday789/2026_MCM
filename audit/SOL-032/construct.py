"""One-shot synthetic audit construction. Never invoked by --check."""
import base64
import datetime
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import traceback
sys.dont_write_bytecode=True
HOME=Path(__file__).resolve().parent
ROOT=HOME.parents[1]
sys.path.insert(0,str(HOME))
import verify as v

def save(name,obj):
    (HOME/name).write_bytes((json.dumps(obj,sort_keys=True,indent=2,ensure_ascii=True)+'\n').encode())
def load_coop():
    spec=importlib.util.spec_from_file_location('audit_coop',ROOT/'scripts/coop.py')
    c=importlib.util.module_from_spec(spec);sys.modules['audit_coop']=c;spec.loader.exec_module(c);return c

def runtime_fixture():
    parent=ROOT/'.runtime/sol032-local-git';parent.mkdir(parents=True,exist_ok=True)
    top=Path(tempfile.mkdtemp(prefix='trial-',dir=parent));bare=top/'remote.git';worker=top/'worker'
    transcript=[]
    def g(*args,cwd=worker):
        p=subprocess.run(['git',*args],cwd=cwd,capture_output=True)
        transcript.append(dict(argv=['git',*args],cwd=str(cwd),returncode=p.returncode,stdout=p.stdout.decode(errors='replace'),stderr=p.stderr.decode(errors='replace')))
        if p.returncode:raise RuntimeError(transcript[-1])
        return p.stdout
    g('init','--bare',str(bare),cwd=top);g('init','-b','main',str(worker),cwd=top)
    g('config','user.name','Local Synthetic Fixture');g('config','user.email','fixture@localhost')
    g('config','core.autocrlf','false');g('remote','add','origin',str(bare))
    (worker/'ops/tasks').mkdir(parents=True)
    (worker/'.gitignore').write_bytes(b'.runtime/\n')
    (worker/'.gitattributes').write_bytes(b'* text eol=lf\n')
    script="""from pathlib import Path
import json,sys
names=json.loads(Path('names.json').read_text())
out=Path(sys.argv[1]);omit=sys.argv[2]=='omit'
paths=names[:-1] if omit else names
if '--check' in sys.argv:
 assert len(list(out.rglob('*')))>0
 for i,name in enumerate(paths):assert (out/name).read_bytes().replace(b'\\r\\n',b'\\n')==('fixture32 '+str(i)+'\\n').encode()
else:
 assert not out.exists(), 'fixture command executed twice'
 for i,name in enumerate(paths):
  p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(('fixture32 '+str(i)+'\\r\\n').encode())
print('generated files',len(paths),'check', '--check' in sys.argv)
"""
    (worker/'fixture.py').write_bytes(script.encode())
    names=[p[len('R/'):] for p in v.files('R')]
    (worker/'names.json').write_bytes(v.canonical(names))
    (worker/'ops/control.json').write_bytes(v.canonical(dict(state='running',deadline='2099-01-01T00:00:00+00:00')))
    (worker/'ops/queue.json').write_bytes(v.canonical(dict(tasks=[])))
    g('add','.');g('commit','-m','generated local fixture seed')
    base=g('rev-parse','HEAD').decode().strip()
    tasks={}
    for label in ('complete','missing'):
        ident='FIXTURE32-'+label;out='results/generated32/'+label
        tasks[label]=dict(id=ident,attempt=1,owner='hy3',kind='commands',base_commit=base,depends_on=[],
            instructions='Generated local file compatibility fixture only.',allowed_paths=[out],deliverables=v.files(out),
            commands=[['{python}','-B','fixture.py',out,'omit' if label=='missing' else 'all']],
            validation_commands=[['{python}','-B','fixture.py',out,'omit' if label=='missing' else 'all','--check']],
            max_seconds=60,split='synthetic',parameters=dict(synthetic_runtime_only=True))
        (worker/'ops/tasks'/ (ident+'.json')).write_bytes(v.canonical(tasks[label]))
    (worker/'ops/queue.json').write_bytes(v.canonical(dict(tasks=[dict(id=t['id'],state='ready') for t in tasks.values()])))
    g('add','.');g('commit','-m','publish synthetic fixture tasks');g('push','-u','origin','main')
    c=load_coop();oldroot,oldruntime,oldgit=c.ROOT,c.RUNTIME,c.git
    c.ROOT=worker;c.RUNTIME=worker/'.runtime'
    def local_git(*args,**kwargs):
        kwargs.setdefault('cwd',worker);return oldgit(*args,**kwargs)
    c.git=local_git
    result=dict(expected_file_deliverables=44,scratch=str(top),fixture_script_sha256=v.sha(script.encode()),complete=None,missing=None)
    def snapshot(work):return {p.relative_to(work).as_posix():v.sha(p.read_bytes()) for p in (work/'results').rglob('*') if p.is_file()}
    def proof(commit):
        objects={}
        def add(oid):
            if oid in objects:return
            typ=g('cat-file','-t',oid).decode().strip();raw=g('cat-file',typ,oid)
            objects[oid]=dict(type=typ,data=base64.b64encode(raw).decode())
            if typ=='commit':add(raw.splitlines()[0].split()[1].decode())
            if typ=='tree':
                i=0
                while i<len(raw):
                    z=raw.index(b'\0',i);add(raw[z+1:z+21].hex());i=z+21
        add(commit);return dict(objects=objects)
    try:
        require=c.validate_task
        for label,t in tasks.items():
            require(t)
            before_complete=None
            if label=='missing':before_complete=snapshot(complete_work)
            report=c.run_task(t,'commands')
            work=c.RUNTIME/'worktrees'/(t['id']+'-a1')
            if label=='complete':complete_work=work
            before=snapshot(work)
            commit=c.git('rev-parse','HEAD',cwd=work)
            remote='refs/heads/work/hy3/'+t['id']+'-a1'
            remote_commit=g('--git-dir='+str(bare),'rev-parse',remote).decode().strip()
            v.require(remote_commit==commit,'actual local bare delivery')
            e=dict(task=t,receipt=report,result_commit=commit,outputs_before=before,run_task_calls=1)
            e['blobs']={p:base64.b64encode(g('show',commit+':'+p,cwd=work)).decode() for p in report['artifacts_sha256']}
            e['git_proof']=proof(commit)
            e['completed_entry']=json.loads((c.RUNTIME/'hy3-completed.json').read_text())[t['id']+'-a1']
            if label=='complete':
                second=c.run_task(t,'commands');e.update(second_receipt=second,commit_after_second=c.git('rev-parse','HEAD',cwd=work),run_task_calls=2)
            c.fetch()
            # Once complete has been deduplicated, missing is the next ready fixture.
            selected=c.select_task('hy3')
            e['select_after']=selected['id'] if selected else None
            if label=='complete':v.require(e['select_after']==tasks['missing']['id'],'complete dedup selected wrong task')
            if label=='missing':
                e['successful_outputs_before_failed']=before_complete;e['successful_outputs_after_failed']=snapshot(complete_work)
                v.require(e['successful_outputs_before_failed']==e['successful_outputs_after_failed'],'earlier outputs changed')
            e['outputs_after']=snapshot(work)
            result[label]=e
        # Preserve actual selection at each stage; complete is absent after both are done.
        result['complete']['select_after_missing']=result['complete']['select_after']
        result['complete']['select_after']=None
        result['complete']['final_selection']=c.select_task('hy3')
        result['fixture_script']=script
        result['git_commands']=transcript
        save('runtime.json',result)
        return result
    except Exception:
        save('runtime-partial-failure.json',dict(evidence=result,traceback=traceback.format_exc(),git_commands=transcript));raise
    finally:c.ROOT,c.RUNTIME,c.git=oldroot,oldruntime,oldgit

def main():
    v.require(sys.version_info[:2]==(3,12),'Python 3.12')
    save('unchanged-inventory.json',v.inventory())
    save('boundaries.json',v.boundaries())
    runtime=runtime_fixture()
    facts=v.replay_runtime(runtime)
    source=v.source_facts()
    save('verification.json',dict(expected_file_deliverables=44,source_facts=source,runtime_facts=facts,
         verifier_sha256=v.sha((HOME/'verify.py').read_bytes()),evidence_sha256={n:v.sha((HOME/n).read_bytes()) for n in ('task.json','boundaries.json','runtime.json','unchanged-inventory.json')}))
    print(json.dumps(dict(status='constructed',runtime=facts,source=source,modules=v.modules()),sort_keys=True))
if __name__=='__main__':main()
