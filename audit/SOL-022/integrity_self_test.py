#!/usr/bin/env python3
"""Exercise SOL-022 evidence integrity on ignored scratch copies only."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
AUDIT=ROOT/'audit'/'SOL-022'
OUT=AUDIT/'integrity-self-tests.json'
ARTIFACTS=('verify.py','task-lock.json','findings.json','review.md','verification.json')


def sha(b):
    return hashlib.sha256(b).hexdigest()


def snapshot(path):
    return {str(p.relative_to(path)): {'sha256_raw':sha(p.read_bytes()),'mtime_ns':p.stat().st_mtime_ns}
            for p in sorted(path.rglob('*')) if p.is_file()}


def main():
    if OUT.exists():
        raise FileExistsError('Refuse overwrite: '+str(OUT))
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    scratch=ROOT/'.runtime'/('SOL-022-integrity-'+stamp)
    ignored=subprocess.run(['git','check-ignore',str(scratch.relative_to(ROOT))],
                           cwd=ROOT,capture_output=True)
    if ignored.returncode!=0:
        raise RuntimeError('Scratch must be ignored')
    scratch.mkdir()
    before=snapshot(AUDIT)
    records=[]
    def copy_case(name):
        target=scratch/name
        target.mkdir()
        for filename in ARTIFACTS:
            (target/filename).write_bytes((AUDIT/filename).read_bytes())
        return target
    def execute(name, target, expected, create=False):
        command=[sys.executable,'-B',str(AUDIT/'verify.py')]
        if not create:
            command+=['--check']
        command+=['--evidence',str(target/'verification.json'),'--artifact-dir',str(target)]
        old=snapshot(target)
        result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=90)
        new=snapshot(target)
        records.append({'case':name,'expected_exit':expected,'exit_code':result.returncode,
            'command_portable':['python','-B','audit/SOL-022/verify.py',*(['--check'] if not create else []),
                '--evidence',str((target/'verification.json').relative_to(ROOT)),
                '--artifact-dir',str(target.relative_to(ROOT))],
            'stdout':result.stdout.decode('utf-8'),'stderr':result.stderr.decode('utf-8'),
            'stdout_sha256_raw':sha(result.stdout),'stderr_sha256_raw':sha(result.stderr),
            'subprocess_hash_basis':'exact captured UTF-8 bytes, including Windows CRLF if emitted',
            'all_scratch_bytes_and_mtimes_unchanged':old==new})
        if result.returncode!=expected or old!=new:
            raise RuntimeError('Integrity self-test failed: '+name)
    valid=copy_case('valid')
    execute('valid_read_only_replay',valid,0)
    execute('initializer_refuses_existing',valid,1,create=True)
    for name,mutation in (
        ('corrupt_input_hash',lambda f:f['facts']['fixtures'][0].__setitem__('input_sha256','0'*64)),
        ('corrupt_training_key',lambda f:f['facts']['fixtures'][1]['folds'][0]['manifest']['training_row_keys'][0].__setitem__(0,999)),
    ):
        target=copy_case(name)
        saved=json.loads((target/'verification.json').read_bytes())
        mutation(saved)
        (target/'verification.json').write_text(json.dumps(saved,indent=2)+'\n',encoding='utf-8',newline='\n')
        execute(name,target,1)
    damaged=copy_case('corrupt_findings')
    with (damaged/'findings.json').open('ab') as stream:
        stream.write(b' ')
    execute('corrupt_findings_artifact_hash',damaged,1)

    # Checker-only unit: an internally consistent supported negative result
    # must be accepted as evidence. This is NOT a negative source-code verdict.
    negative=copy_case('negative_verdict_checker_unit')
    module=runpy.run_path(str(AUDIT/'verify.py'))
    saved=json.loads((negative/'verification.json').read_bytes())
    negative_facts=deepcopy(saved['facts'])
    negative_facts['code_verdict']='changes_required'
    negative_facts['failures']=[{'group':'checker_unit_simulated_defect','detail':'not a calibration finding'}]
    saved['facts']=negative_facts
    report=json.loads((negative/'findings.json').read_bytes())
    report['code_verdict']='changes_required'
    (negative/'findings.json').write_text(json.dumps(report)+'\n',encoding='utf-8',newline='\n')
    saved['artifact_sha256_lf']=module['artifact_hashes'](negative)
    (negative/'verification.json').write_text(json.dumps(saved)+'\n',encoding='utf-8',newline='\n')
    readonly_before=snapshot(negative)
    checker=module['check_saved']
    original=checker.__globals__['recompute']
    checker.__globals__['recompute']=lambda:deepcopy(negative_facts)
    try:
        observed=checker(negative/'verification.json',negative)
    finally:
        checker.__globals__['recompute']=original
    if observed['code_verdict']!='changes_required' or snapshot(negative)!=readonly_before:
        raise RuntimeError('Negative verdict was treated as evidence failure')
    records.append({'case':'supported_negative_verdict_checker_unit','passed':True,
        'scope':'Simulated checker result only, not executed source verdict or source acceptance',
        'code_verdict':'changes_required','all_scratch_bytes_and_mtimes_unchanged':True})

    after=snapshot(AUDIT)
    if before!=after:
        raise RuntimeError('Original audit bytes or mtimes changed')
    result={'schema_version':1,'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'python':sys.version,'scratch_relative_path':str(scratch.relative_to(ROOT)),
        'scratch_is_git_ignored':True,'tests':records,'all_passed':True,
        'original_audit_bytes_and_mtimes_unchanged':True,'original_snapshot':before,
        'scope':'Original primary evidence preserved; all intentional corruption confined to ignored scratch.'}
    with OUT.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(result,stream,indent=2,sort_keys=True)
        stream.write('\n')
    print(json.dumps({'integrity_self_tests':len(records),'all_passed':True,
        'original_evidence_unchanged':True}))


if __name__=='__main__':
    main()
