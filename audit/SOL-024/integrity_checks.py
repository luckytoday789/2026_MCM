"""Exercise only SOL-024's own verifier on ignored scratch copies; preserve every trial.
This is not a scheduler, policy, data-loader or final gate test.
"""
import hashlib
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

def digest_tree(directory):
    return {p.relative_to(directory).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in directory.rglob('*') if p.is_file()}

def main():
    assert sys.version_info[:2] == (3,12)
    target=HERE/'integrity-self-tests.json'
    if target.exists():
        raise FileExistsError('preserve existing self-test report; use a new immutable record')
    original=digest_tree(HERE)
    runtime=ROOT/'.runtime'
    runtime.mkdir(exist_ok=True)
    scratch=Path(tempfile.mkdtemp(prefix='SOL-024-integrity-',dir=runtime))
    outcomes=[]
    def trial(name, mutate=None, expected=1, create=False):
        directory=scratch/name
        shutil.copytree(HERE,directory)
        if mutate:
            mutate(directory)
        before=digest_tree(directory)
        args=[sys.executable,'-B',str(HERE/'verify.py')]
        args += [] if create else ['--check','--evidence-dir',str(directory)]
        proc=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,timeout=45)
        after=digest_tree(directory)
        unchanged=before==after
        record={'name':name,'expected_exit':expected,'exit_code':proc.returncode,
                'stdout':proc.stdout,'stderr':proc.stderr,'all_scratch_bytes_unchanged':unchanged}
        outcomes.append(record)
        assert proc.returncode==expected and unchanged, record
        if create:
            assert 'exclusive creation refuses existing verification' in proc.stderr, record
    def mutate_doc(path, change):
        def mutate(directory):
            file=directory/path
            document=json.loads(file.read_text(encoding='utf-8'))
            change(document)
            file.write_text(json.dumps(document,indent=2)+'\n',encoding='utf-8',newline='\n')
        return mutate
    def set_reference(section,key,value):
        return mutate_doc('verification.json',lambda doc:doc['evidence']['references'][section].__setitem__(key,value))
    trial('valid',expected=0)
    trial('wrong-generic-count',set_reference('generic_counts','annual_ledger_rows',28801))
    trial('wrong-personalized-H30',mutate_doc('verification.json',lambda d:d['evidence']['references']['personalized']['all'].__setitem__('ledger_rows',18000)))
    trial('wrong-personalized-denominator',mutate_doc('verification.json',lambda d:d['evidence']['references']['personalized']['all']['rows'][0].__setitem__('denominator',120)))
    trial('referral-false-screen',mutate_doc('verification.json',lambda d:d['evidence']['references']['personalized']['none']['rows'][0].__setitem__('risk_pass',False)))
    trial('referral-zero-outcome',mutate_doc('verification.json',lambda d:d['evidence']['references']['personalized']['none']['rows'][0].__setitem__('p90_loss',0)))
    trial('wrong-exceedances',set_reference('screens','strict_exceedances',6))
    trial('severe-epsilon-substitution',mutate_doc('verification.json',lambda d:d['evidence']['references']['severe']['earliest'].__setitem__('loss',0.25+1e-15)))
    trial('wrong-freeze-basis',mutate_doc('verification.json',lambda d:d['evidence']['references']['freeze_text_hashes']['base'].__setitem__('runner','0'*64)))
    trial('wrong-source-pin',mutate_doc('task-lock.json',lambda d:d['source_sha256'].__setitem__('scripts/coop.py','0'*64)))
    trial('wrong-task-base',mutate_doc('task-lock.json',lambda d:d.__setitem__('base_commit','0'*40)))
    trial('missing-findings',lambda directory:(directory/'findings.json').unlink())
    trial('changed-review',lambda directory:(directory/'review.md').write_bytes((directory/'review.md').read_bytes()+b'\ncorrupted\n'))
    trial('changed-historical-failure',lambda directory:(directory/'history/failure-001.json').write_bytes(b'{}\n'))
    trial('changed-expected-hash',mutate_doc('verification.json',lambda d:d['evidence']['artifact_sha256'].__setitem__('verify.py','0'*64)))
    trial('ordinary-float-within-tolerance',mutate_doc('verification.json',lambda d:d['evidence']['references']['ordinary'].__setitem__('cagr_pct',d['evidence']['references']['ordinary']['cagr_pct']+5e-10)),expected=0)
    trial('ordinary-float-outside-tolerance',mutate_doc('verification.json',lambda d:d['evidence']['references']['ordinary'].__setitem__('cagr_pct',d['evidence']['references']['ordinary']['cagr_pct']+1e-4)))
    trial('exclusive-create-existing',expected=1,create=True)
    # Prove immutable replay never consults HEAD or mutable remote refs.
    # Only load our own verifier; this imports no production/project helper.
    namespace=runpy.run_path(str(HERE/'verify.py'),run_name='sol024_integrity_reference')
    original_run=subprocess.run
    git_commands=[]
    def pinned_only(command,*args,**kwargs):
        if command[0]=='git':
            assert command[1]=='show' and len(command)==3, command
            commit=command[2].split(':',1)[0]
            assert len(commit)==40 and all(c in '0123456789abcdef' for c in commit), command
            assert 'HEAD' not in command[2] and 'origin/' not in command[2], command
            git_commands.append(command)
        return original_run(command,*args,**kwargs)
    subprocess.run=pinned_only
    try:
        recomputed=namespace['compute'](HERE)
        saved=json.loads((HERE/'verification.json').read_text(encoding='utf-8'))['evidence']
        namespace['compare'](saved,recomputed)
    finally:
        subprocess.run=original_run
    assert len(git_commands)==18, git_commands
    assert original==digest_tree(HERE), 'original audit evidence changed'
    report={'schema_version':1,'task_id':'SOL-024','python':sys.version,
            'trials':outcomes,'trial_count':len(outcomes),
            'corrupt_or_missing_rejections':sum(x['expected_exit']==1 for x in outcomes if x['name']!='exclusive-create-existing'),
            'exclusive_existing_rejected':True,'HEAD_independence':'18 immutable git-show reads only; all mutable refs prohibited',
            'original_audit_files_unchanged':True,'scratch_copies_retained':True,
            'scope':'Own metadata/scalar verifier only; no production inputs/helpers/gates or refs modified.'}
    with target.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(report,stream,indent=2,allow_nan=False)
        stream.write('\n')
    print(json.dumps({'trial_count':len(outcomes),'all_originals_unchanged':True,'all_expected_outcomes':True}))

if __name__=='__main__':
    main()
