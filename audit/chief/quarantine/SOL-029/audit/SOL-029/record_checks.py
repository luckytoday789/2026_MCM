"""Create one exclusive evidence trial, then record actual clean subprocess checks.

No production inputs/configs. No Git commits, fetches or branch changes.
"""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'audit/SOL-029'))
import verify as v
from verify import w
import json
import os
import subprocess
import time
import uuid
import shutil

AUDIT=ROOT/'audit/SOL-029'


def inventory(root):
    return {p.relative_to(root).as_posix():dict(bytes=p.stat().st_size,sha256=w.sha(p.read_bytes()))
            for p in root.rglob('*') if p.is_file()}


def protected():
    task=w.strict_json(w.blob(ROOT,v.PUBLICATION,'ops/tasks/SOL-029.json'))
    paths=set(task['parameters']['source_sha256'])|set(v.DELIVERED)
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


def portable():
    # New ignored scratch repository view, sharing existing immutable objects only.
    home=ROOT/'.runtime'/('SOL-029-portable-'+uuid.uuid4().hex);home.mkdir(parents=True)
    common=Path(w.git(ROOT,'rev-parse','--git-common-dir').decode().strip())
    if not common.is_absolute():common=(ROOT/common).resolve()
    g=home/'.git';(g/'objects/info').mkdir(parents=True);(g/'refs/remotes/origin').mkdir(parents=True)
    later=v.PUBLICATION
    (g/'HEAD').write_text(later+'\n',encoding='ascii')
    (g/'config').write_text('[core]\nrepositoryformatversion = 0\nbare = false\n',encoding='ascii')
    (g/'objects/info/alternates').write_bytes(((common/'objects').as_posix()+'\n').encode('utf8'))
    (g/'refs/remotes/origin/main').write_text(later+'\n',encoding='ascii')
    task=w.strict_json(w.blob(ROOT,v.PUBLICATION,'ops/tasks/SOL-029.json'))
    paths=set(task['parameters']['source_sha256'])|set(w.CLOSURE)|set(v.DELIVERED)
    paths|={p.relative_to(ROOT).as_posix() for p in AUDIT.rglob('*') if p.is_file()}
    for name in paths:
        target=home/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    w.require(not (home/'.runtime/task.json').exists(),'portable runtime task unexpectedly exists')
    original_head=w.git(ROOT,'rev-parse','HEAD').decode().strip()
    actual_head=w.git(home,'rev-parse','HEAD').decode().strip()
    w.require(actual_head==later and actual_head!=original_head,'portable later HEAD')
    w.ancestor(ROOT,original_head,actual_head)
    before={n:w.sha((home/n).read_bytes()) for n in paths}
    result=command([sys.executable,'-B','audit/SOL-029/verify.py','--check'],home)
    after={n:w.sha((home/n).read_bytes()) for n in paths}
    return dict(original_head=original_head,later_head=actual_head,live_runtime_task=False,
        original_repository_changed=False,scratch_path=str(home),command=result,
        source_reference_audit_unchanged=before==after,original_inventory=before,
        method='real separate detached HEAD view and existing Git object alternates; no new commits')


def main():
    w.require(sys.version_info[:2]==(3,12),'Python 3.12 required')
    w.require(not (AUDIT/'clean-environment-checks.json').exists(),'command evidence already exists')
    creation=command([sys.executable,'-B','audit/SOL-029/verify.py'])
    w._write(AUDIT/('creation-command-'+uuid.uuid4().hex+'.json'),w._json_bytes(creation))
    w.require(creation['returncode']==0,'exclusive creation failed; preserve trial and diagnose before a new trial')
    before=protected()
    commands=[command([sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_policy_writer.py','-v']),
              command([sys.executable,'-B','audit/SOL-029/verify.py','--check'])]
    after=protected()
    portable_result=portable()
    evidence=w.strict_json((AUDIT/'verification.json').read_bytes())
    passed=all(r['returncode']==0 and not r['pythonpath_keys'] and r['imported_module_paths'] for r in commands)
    passed=passed and before==after and portable_result['command']['returncode']==0 and portable_result['source_reference_audit_unchanged']
    envelope=dict(schema_version=1,task_id='SOL-029',status='passed' if passed else 'failed',
        python=sys.version,python_executable=sys.executable,creation_command=creation,commands=commands,
        portable_replay=portable_result,protected_before=before,protected_after=after,
        source_reference_audit_unchanged=before==after,identity=evidence['identity'],
        core_evidence_sha256={p:w.sha((AUDIT/p).read_bytes()) for p in ('verification.json','integrity-self-tests.json')},
        note='Outer command envelope created after actual subprocess completion; no self or future log hash.')
    w._write(AUDIT/'clean-environment-checks.json',w._json_bytes(envelope))
    w.require(passed,'prescribed or portable checks failed; original trial preserved')
    print(json.dumps(dict(status='passed',commands=[r['returncode'] for r in commands],
        portable_returncode=portable_result['command']['returncode'],unchanged=before==after)))


if __name__=='__main__':main()
