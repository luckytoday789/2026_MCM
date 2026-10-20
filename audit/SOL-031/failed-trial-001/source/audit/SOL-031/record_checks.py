"""Create one exclusive evidence trial, then record actual clean subprocess checks.

No production inputs/configs. No Git commits, fetches or branch changes.
"""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'audit/SOL-031'))
import verify as v
from verify import w
import json
import os
import subprocess
import time
import uuid
import shutil

AUDIT=ROOT/'audit/SOL-031'


def inventory(root):
    return {p.relative_to(root).as_posix():dict(bytes=p.stat().st_size,sha256=w.sha(p.read_bytes()))
            for p in root.rglob('*') if p.is_file()}


def protected():
    task=w.strict_json(w.blob(ROOT,v.PUBLICATION,'ops/tasks/SOL-031.json'))
    paths=set(task['parameters']['source_sha256'])|set(v.DELIVERED)|{'.gitattributes','.gitignore'}
    paths|={p.relative_to(ROOT).as_posix() for p in AUDIT.rglob('*') if p.is_file()}
    return {name:dict(bytes=(ROOT/name).stat().st_size,sha256=w.sha((ROOT/name).read_bytes())) for name in sorted(paths)}


def command(argv,cwd=ROOT):
    env={k:x for k,x in os.environ.items() if k.upper()!='PYTHONPATH'}
    start=time.monotonic();result=subprocess.run(argv,cwd=cwd,env=env,capture_output=True,text=True)
    modules={}
    marker='IMPORTED_MODULE_PATHS='
    for line in result.stderr.splitlines():
        if line.startswith(marker):modules=json.loads(line[len(marker):])
    if result.stdout.strip():
        try:modules=json.loads(result.stdout)['imported_module_paths']
        except (ValueError,KeyError,TypeError):pass
    return dict(argv=argv,cwd=str(cwd),returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,
        elapsed_seconds=time.monotonic()-start,pythonpath_keys=[k for k in env if k.upper()=='PYTHONPATH'],
        imported_module_paths=modules)


def git_roundtrips():
    """Actual clean/index/tree/checkout transport; all mutations in ignored scratch."""
    home=ROOT/'.runtime'/('SOL-031-roundtrip-'+uuid.uuid4().hex);home.mkdir(parents=True)
    common=Path(w.git(ROOT,'rev-parse','--git-common-dir').decode().strip())
    if not common.is_absolute():common=(ROOT/common).resolve()
    task=w.strict_json(w.blob(ROOT,v.PUBLICATION,'ops/tasks/SOL-031.json'))
    paths=set(task['parameters']['source_sha256'])|set(w.CLOSURE)|set(v.DELIVERED)|{'.gitattributes','.gitignore'}
    paths|={p.relative_to(ROOT).as_posix() for p in AUDIT.rglob('*') if p.is_file()}
    paths=sorted(paths)
    original_head=w.git(ROOT,'rev-parse','HEAD').decode().strip()
    later=w.git(ROOT,'rev-parse','origin/main').decode().strip()
    w.require(later!=original_head,'later HEAD fixture must advance')
    w.ancestor(ROOT,original_head,later)
    records=[]
    for mode in ('true','false'):
        repo=home/('autocrlf-'+mode);repo.mkdir()
        export=home/('export-'+mode);export.mkdir()
        rec=dict(core_autocrlf=mode,scratch_repository=str(repo),exported_view=str(export),commands=[])
        records.append(rec)
        def git(*args,input=None,binary=False,cwd=repo):
            argv=['git',*args];start=time.monotonic()
            env={k:x for k,x in os.environ.items() if k.upper()!='PYTHONPATH'}
            r=subprocess.run(argv,cwd=cwd,env=env,input=input,capture_output=True)
            log=dict(argv=argv,cwd=str(cwd),returncode=r.returncode,elapsed_seconds=time.monotonic()-start,
                stdout=(dict(bytes=len(r.stdout),sha256=w.sha(r.stdout)) if binary else r.stdout.decode('utf8','strict')),
                stderr=r.stderr.decode('utf8','replace'),input_bytes=None if input is None else len(input),
                input_sha256=None if input is None else w.sha(input))
            rec['commands'].append(log)
            (home/'partial-roundtrip-log.json').write_bytes(w._json_bytes(records))
            w.require(r.returncode==0,'Git roundtrip command failed: '+repr(argv))
            return r.stdout
        git('init','--quiet')
        git('config','--local','core.autocrlf',mode)
        (repo/'.git/objects/info/alternates').write_bytes(((common/'objects').as_posix()+'\n').encode('utf8'))
        for name in paths:
            p=repo/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
        original={n:dict(bytes=(repo/n).stat().st_size,sha256=w.sha((repo/n).read_bytes())) for n in paths}
        rec['original_inventory']=original
        git('add','--force','--pathspec-from-file=-','--pathspec-file-nul',
            input=b''.join(n.encode('utf8')+b'\0' for n in paths))
        rec['tree']=git('write-tree').decode().strip()
        staged=git('ls-files','--stage','-z')
        entries={}
        for entry in staged.split(b'\0'):
            if not entry:continue
            meta,name=entry.split(b'\t');perms,oid,stage=meta.split()
            w.require(stage==b'0','nonzero index stage')
            entries[name.decode()]=oid.decode()
        w.require(set(entries)==set(paths),'incomplete roundtrip index')
        raw=git('cat-file','--batch',input=''.join(oid+'\n' for oid in entries.values()).encode(),binary=True)
        pos=0;canonical={}
        for name,oid in entries.items():
            end=raw.index(b'\n',pos);got,kind,size=raw[pos:end].split();size=int(size)
            w.require(got.decode()==oid and kind==b'blob','bad canonical blob')
            data=raw[end+1:end+1+size];pos=end+2+size
            canonical[name]=dict(bytes=len(data),sha256=w.sha(data),git_blob=oid)
        w.require(pos==len(raw),'trailing batch bytes')
        rec['canonical_inventory']=canonical
        attrs=git('check-attr','--cached','text','eol','--',*paths).decode()
        rec['attribute_decisions']=attrs
        git('checkout-index','--all','--force','--prefix='+export.as_posix()+'/')
        checkout={n:dict(bytes=(export/n).stat().st_size,sha256=w.sha((export/n).read_bytes())) for n in paths}
        rec['checkout_inventory']=checkout
        audit_paths=[n for n in paths if n.startswith('audit/SOL-031/')]
        rec['strict_audit_paths']=audit_paths
        rec['all_audit_bytes_equal']=all(original[n]==checkout[n] and
            original[n]=={k:canonical[n][k] for k in ('bytes','sha256')} for n in audit_paths)
        failures=[n for n in audit_paths if '/failed-' in n]
        rec['preserved_failure_paths']=failures
        w.require(len([n for n in failures if n.endswith('/failure.json')])==3 and
                  len([n for n in failures if n.endswith('/partial.txt')])==1,'failure fixture omission')
        w.require(rec['all_audit_bytes_equal'],'Git altered new audit bytes')
        # Exported view shares immutable objects. Its detached HEAD deliberately
        # advances, but the working files came through checkout-index, not copy.
        git('init','--quiet',cwd=export)
        git('config','--local','core.autocrlf',mode,cwd=export)
        (export/'.git/objects/info/alternates').write_bytes(
            ((repo/'.git/objects').as_posix()+'\n'+(common/'objects').as_posix()+'\n').encode('utf8'))
        (export/'.git/HEAD').write_bytes((later+'\n').encode('ascii'))
        (export/'.git/refs/remotes/origin').mkdir(parents=True)
        (export/'.git/refs/remotes/origin/main').write_bytes((later+'\n').encode('ascii'))
        rec['original_head']=original_head
        rec['later_head']=git('rev-parse','HEAD',cwd=export).decode().strip()
        rec['live_runtime_task']=(export/'.runtime/task.json').exists()
        w.require(rec['later_head']==later and not rec['live_runtime_task'],'export identity')
        rec['prescribed_commands']=[
            command([sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_policy_writer.py','-v'],export),
            command([sys.executable,'-B','audit/SOL-031/verify.py','--check'],export)]
        after={n:dict(bytes=(export/n).stat().st_size,sha256=w.sha((export/n).read_bytes())) for n in paths}
        rec['after_commands_inventory']=after
        rec['source_reference_audit_unchanged']=after==checkout
        rec['status']='passed' if all(r['returncode']==0 and not r['pythonpath_keys'] and r['imported_module_paths']
            for r in rec['prescribed_commands']) and after==checkout else 'failed'
    return dict(schema_version=1,task_id='SOL-031',method='git init/config/add/write-tree/cat-file/checkout-index; real filters',
        root_attributes_blob_sha256=w.sha(w.blob(ROOT,v.BASE,'.gitattributes')),
        scoped_attributes_sha256=w.sha((AUDIT/'.gitattributes').read_bytes()),
        paths=paths,roundtrips=records,status='passed' if all(r['status']=='passed' for r in records) else 'failed',
        scratch_outcomes_preserved=True,assigned_repository_mutations=False)

def repository_state():
    """Read only assigned metadata; scratch Git never uses these paths."""
    gd=Path(w.git(ROOT,'rev-parse','--git-dir').decode().strip())
    common=Path(w.git(ROOT,'rev-parse','--git-common-dir').decode().strip())
    if not gd.is_absolute():gd=(ROOT/gd).resolve()
    if not common.is_absolute():common=(ROOT/common).resolve()
    files={str(p):None if not p.exists() else dict(bytes=p.stat().st_size,sha256=w.sha(p.read_bytes()))
           for p in (ROOT/'.git',gd/'HEAD',gd/'index',gd/'config',common/'config',ROOT/'.gitattributes')}
    return dict(files=files,head=w.git(ROOT,'rev-parse','HEAD').decode().strip(),
                refs_sha256=w.sha(w.git(ROOT,'show-ref')))


def main():
    w.require(sys.version_info[:2]==(3,12),'Python 3.12 required')
    w.require(not (AUDIT/'clean-environment-checks.json').exists(),'command evidence already exists')
    repo_before=repository_state()
    creation=command([sys.executable,'-B','audit/SOL-031/verify.py'])
    w._write(AUDIT/('creation-command-'+uuid.uuid4().hex+'.json'),w._json_bytes(creation))
    w.require(creation['returncode']==0,'exclusive creation failed; preserve trial and diagnose before a new trial')
    before=protected()
    commands=[command([sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_policy_writer.py','-v']),
              command([sys.executable,'-B','audit/SOL-031/verify.py','--check'])]
    after=protected()
    portable_result=git_roundtrips()
    w._write(AUDIT/'git-roundtrip-checks.json',w._json_bytes(portable_result))
    evidence=w.strict_json((AUDIT/'verification.json').read_bytes())
    passed=all(r['returncode']==0 and not r['pythonpath_keys'] and r['imported_module_paths'] for r in commands)
    repo_after=repository_state()
    passed=passed and before==after and portable_result['status']=='passed' and repo_before==repo_after
    envelope=dict(schema_version=1,task_id='SOL-031',status='passed' if passed else 'failed',
        python=sys.version,python_executable=sys.executable,creation_command=creation,commands=commands,
        git_roundtrip_evidence=dict(path='audit/SOL-031/git-roundtrip-checks.json',
            sha256=w.sha((AUDIT/'git-roundtrip-checks.json').read_bytes()),status=portable_result['status']),
        assigned_repository_before=repo_before,assigned_repository_after=repo_after,
        assigned_repository_unchanged=repo_before==repo_after,protected_before=before,protected_after=after,
        source_reference_audit_unchanged=before==after,identity=evidence['identity'],
        core_evidence_sha256={p:w.sha((AUDIT/p).read_bytes()) for p in ('verification.json','integrity-self-tests.json')},
        note='Outer command envelope created after actual subprocess completion; no self or future log hash.')
    w._write(AUDIT/'clean-environment-checks.json',w._json_bytes(envelope))
    w.require(passed,'prescribed or portable checks failed; original trial preserved')
    print(json.dumps(dict(status='passed',commands=[r['returncode'] for r in commands],
        git_roundtrip_status=portable_result['status'],unchanged=before==after)))


if __name__=='__main__':main()
