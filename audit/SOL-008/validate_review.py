"""SOL-008 CLI integrity checks. Uses existing evidence; no experiment reruns."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NAMES = ('verification.json','scheduler-review.json','findings.json')

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def snapshot():
    paths = set()
    for folder in ('audit/SOL-008','scripts','src','tests','specs','ops'):
        paths.update(p for p in (ROOT/folder).rglob('*') if p.is_file())
    paths.add(ROOT/'data/development/scenarios_001_120.csv')
    return {p.relative_to(ROOT).as_posix():digest(p.read_bytes()) for p in sorted(paths)}

def encoded(value):
    return (json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False)+'\n').encode()

def main():
    if sys.version_info[:2] != (3,12):
        raise AssertionError('Python 3.12 required')
    if (HERE/'validation.json').exists():
        raise AssertionError('validation exists; preserve it')
    history=HERE/'history'/'cli-corruptions'
    history.mkdir(exist_ok=False)
    cases=[]
    for name,target,mutation in [
        ('valid-read-only',None,None),
        ('corrupt-verification','verification.json',lambda x:x.update(task='SOL-006')),
        ('corrupt-scheduler','scheduler-review.json',lambda x:x['current_probes']['arrival_during_turn']['checkpoint_after_each_tick'][0].update(fingerprint='swallowed')),
        ('corrupt-findings','findings.json',lambda x:x['numerical'].update(verdict='unreviewed')),
        ('missing-findings','findings.json',None),
        ('initializer-refuses-existing',None,None),
    ]:
        argv=[sys.executable,'-B','audit/SOL-008/verify.py']
        portable=['{python}','-B','audit/SOL-008/verify.py']
        if name != 'initializer-refuses-existing':
            argv.append('--check'); portable.append('--check')
        if target:
            scratch=history/name
            scratch.mkdir()
            for file in NAMES:
                (scratch/file).write_bytes((HERE/file).read_bytes())
            if mutation:
                value=json.loads((scratch/target).read_text())
                mutation(value)
                (scratch/target).write_bytes(encoded(value))
            else:
                (scratch/target).unlink()
            rel=scratch.relative_to(ROOT).as_posix()
            argv.extend(['--evidence-dir',rel])
            portable.extend(['--evidence-dir',rel])
        before=snapshot()
        result=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True)
        after=snapshot()
        changes=[p for p in sorted(set(before)|set(after)) if before.get(p)!=after.get(p)]
        expected_success=name=='valid-read-only'
        observation={'name':name,'command':portable,'exit_code':result.returncode,
            'expected_exit':'zero' if expected_success else 'nonzero',
            'stdout':result.stdout.strip(),'stderr':result.stderr.strip(),
            'files_unchanged':not changes,'changed_paths':changes,
            'files_checked':len(before),
            'before_tree_sha256':digest(encoded(before)),
            'after_tree_sha256':digest(encoded(after))}
        (history/(name+'-execution.json')).write_bytes(encoded(observation))
        cases.append(observation)
        print(json.dumps({'name':name,'exit':result.returncode,'unchanged':not changes}),flush=True)
        if (result.returncode==0)!=expected_success or changes:
            (history/(name+'-unexpected-failure.json')).write_bytes(encoded(observation))
            raise AssertionError('CLI validation failed: '+name)
    report={'schema_version':1,'task':'SOL-008','python':'.'.join(map(str,sys.version_info[:3])),
        'cases':cases,'all_expected_outcomes':True,
        'original_reviewed_results_modified':False,
        'production_run_or_historical_suite_rerun':False}
    with (HERE/'validation.json').open('xb') as stream:
        stream.write(encoded(report))

if __name__=='__main__':
    main()
