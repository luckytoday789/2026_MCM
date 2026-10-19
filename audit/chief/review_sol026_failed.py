"""Chief preserves and diagnoses exact failed SOL-026; no acceptance or outcomes."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[2]
COMMIT='e8733bbc9f1234e04a5e382046d3c89fc12cae7d'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    task=json.loads((ROOT/'ops/tasks/SOL-026.json').read_bytes())
    queue=json.loads((ROOT/'ops/queue.json').read_bytes())
    q=next(x for x in queue['tasks'] if x['id']=='SOL-026')
    r=json.loads(git('show',COMMIT+':handoff/SOL-026/result.json'))
    assert git('rev-parse','origin/work/sol/SOL-026-a1').decode().strip()==COMMIT
    assert git('rev-parse',COMMIT+'^').decode().strip()==task['base_commit']
    subprocess.run(['git','merge-base','--is-ancestor',task['base_commit'],'origin/main'],cwd=ROOT,check=True)
    digest=sha(json.dumps(task,sort_keys=True,separators=(',',':')).encode())
    assert r['task_sha256']==q['task_sha256']==digest
    assert (r['task_id'],r['attempt'],r['role'],r['base_commit'])==('SOL-026',1,'sol',task['base_commit'])
    assert r['task_parameters']==task['parameters'] and r['started_from_pinned_source'] is True
    assert r['status']=='failed' and r['artifact_hash_basis']=='canonical_git_blob'
    assert r['python'].startswith('3.12.') and len(r['checks'])==1 and r['checks'][0]['exit_code']==1
    assert r['input_manifest']==json.loads(git('show',task['base_commit']+':data/manifest.json'))
    names=git('diff','--name-only',task['base_commit'],COMMIT).decode().splitlines()
    allowed=task['allowed_paths']+['handoff/SOL-026']
    assert all(any(p==a or p.startswith(a+'/') for a in allowed) for p in names)
    assert set(names)==set(r['artifacts_sha256'])|{'handoff/SOL-026/result.json'}
    sizes={}
    for p,h in r['artifacts_sha256'].items():
        raw=git('show',COMMIT+':'+p);assert sha(raw)==h,p;sizes[p]=len(raw)
        assert git('ls-tree',COMMIT,'--',p).decode().split()[0] in ('100644','100755')
    for p,h in task['parameters']['source_sha256'].items():assert sha(git('show',task['base_commit']+':'+p))==h,p
    log=git('show',COMMIT+':handoff/SOL-026/check-0.txt').decode()
    assert 'hit your usage limit' in log and '6:02 AM' in log
    missing=sorted(set(task['deliverables'])-set(names))
    work=ROOT/'.runtime/review-SOL-026'
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=work).decode().strip()==COMMIT
    snapshot=lambda:{p:sha((work/p).read_bytes()) for p in names}
    before=snapshot();checks=[]
    env={k:v for k,v in os.environ.items() if k.upper()!='PYTHONPATH'}
    for command in task['validation_commands']:
        argv=[sys.executable if x=='{python}' else x for x in command]
        start=time.monotonic();proc=subprocess.run(argv,cwd=work,env=env,capture_output=True,text=True,timeout=180)
        checks.append(dict(argv=command,exit_code=proc.returncode,seconds=time.monotonic()-start,stdout=proc.stdout,stderr=proc.stderr))
    assert snapshot()==before
    assert checks[0]['exit_code']==0 and 'Ran 13 tests' in checks[0]['stderr']
    assert checks[1]['exit_code']!=0 and 'verification.json' in checks[1]['stderr']
    copied={}
    for p in ('src/safeinvest/policy_writer.py','scripts/run_development_policy.py','tests/test_policy_writer.py',
              'audit/SOL-026/verify.py','audit/SOL-026/findings.json','audit/SOL-026/implementation.md'):
        dest=ROOT/'audit/chief/quarantine/SOL-026'/p;dest.parent.mkdir(parents=True,exist_ok=True)
        raw=git('show',COMMIT+':'+p)
        with dest.open('xb') as f:f.write(raw)
        copied[dest.relative_to(ROOT).as_posix()]=sha(raw)
    for p in ('handoff/SOL-026/result.json','handoff/SOL-026/check-0.txt'):
        dest=ROOT/p;dest.parent.mkdir(parents=True,exist_ok=True)
        with dest.open('xb') as f:f.write(git('show',COMMIT+':'+p))
    record=dict(schema_version=1,task_id='SOL-026',reviewed_commit=COMMIT,base_commit=task['base_commit'],
        task_sha256=digest,checked_at=datetime.now(timezone.utc).isoformat(),canonical_receipt_structure='verified',
        artifact_count=len(names),source_hashes_checked=task['parameters']['source_sha256'],
        artifacts_sha256=r['artifacts_sha256'],artifact_bytes=sizes,missing_required_deliverables=missing,
        worker_failure='usage_limit_before_final_validation',worker_reset_hint='6:02 AM; timezone unspecified',
        cautious_probe_not_before='2026-10-20T06:05:00+08:00',worker_prescribed_checks_executed=False,
        chief_clean_environment_replay=checks,source_and_evidence_unchanged=True,quarantined_source_sha256=copied,
        code_verdict='incomplete_and_revalidation_required',decision='preserve_failed_attempt_do_not_accept',
        full_failed_branch_preserved=True,competition_input_read=False,final_data_open=False,
        note='Focused tests passing does not repair the missing bound evidence or certify production. Existing draft claims are unaccepted. No failed evidence is relabelled.')
    with (ROOT/'audit/chief/SOL-026-failure-review.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(record,f,indent=2);f.write('\n')
    print(json.dumps(dict(commit=COMMIT,artifacts=len(names),source_pins=len(task['parameters']['source_sha256']),missing=missing,replay_exit_codes=[c['exit_code'] for c in checks],decision=record['decision'])))
if __name__=='__main__':main()
