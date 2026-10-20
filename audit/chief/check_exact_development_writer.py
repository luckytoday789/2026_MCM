"""Run one exact, read-only development writer check with durable logs."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]

def main():
    p = argparse.ArgumentParser()
    p.add_argument('task_id', choices=('HY3-004', 'HY3-006'))
    p.add_argument('commit')
    args = p.parse_args()
    assert len(args.commit) == 40 and all(c in '0123456789abcdef' for c in args.commit)
    def git(*items):
        return subprocess.check_output(['git', *items], cwd=ROOT)
    def sha(raw):
        return hashlib.sha256(raw).hexdigest()
    task = json.loads(git('show', 'HEAD:ops/tasks/' + args.task_id + '.json'))
    receipt = json.loads(git('show', args.commit + ':handoff/' + args.task_id + '/result.json'))
    assert receipt['status'] == 'completed' and receipt['base_commit'] == task['base_commit']
    assert git('rev-parse', args.commit + '^').decode().strip() == task['base_commit']
    prefix = 'audit/chief/' + args.task_id + '-isolated-writer-check'
    record_path = ROOT / (prefix + '.json')
    assert not record_path.exists()
    worktree = ROOT / '.runtime/chief-reviews' / (args.task_id + '-' + args.commit[:7])
    assert not worktree.exists()
    subprocess.run(['git', 'worktree', 'add', '--detach', str(worktree), args.commit], cwd=ROOT, check=True)
    config = task['parameters']['config_path']
    protected = sorted(set(task['parameters']['source_sha256']) | set(task['deliverables']) |
        {task['parameters']['input']['path'], config, 'scripts/check_worker_env.py',
         'handoff/' + args.task_id + '/result.json'})
    def inventory():
        return {name:sha((worktree / name).read_bytes()) for name in protected}
    before = inventory()
    env = {key:value for key,value in os.environ.items() if key.upper() != 'PYTHONPATH'}
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    assert not any(key.upper() == 'PYTHONPATH' for key in env)
    assert not (worktree / '.runtime/task.json').exists()
    argv = [sys.executable, '-B', 'scripts/run_development_policy.py', '--config', config,
            '--output', 'results/development/' + args.task_id, '--check']
    stdout_path, stderr_path = ROOT / (prefix + '.stdout.txt'), ROOT / (prefix + '.stderr.txt')
    assert not stdout_path.exists() and not stderr_path.exists()
    record = dict(schema_version=1,task_id=args.task_id,reviewed_commit=args.commit,
        working_tree=str(worktree.relative_to(ROOT)),python=sys.version,argv=argv,
        PYTHONPATH_present=False,runtime_task_present=False,
        started_at=datetime.now(timezone.utc).isoformat(),before_sha256=before,
        status='started',timeout_seconds=600,production_acceptance=False)
    def save():
        record_path.write_text(json.dumps(record, indent=2, allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    save()
    start=time.monotonic()
    try:
        with stdout_path.open('xb') as out, stderr_path.open('xb') as err:
            run = subprocess.run(argv,cwd=worktree,env=env,stdout=out,stderr=err,timeout=600)
        record['exit_code']=run.returncode
        record['status']='passed' if run.returncode==0 else 'failed'
    except Exception as exc:
        record['status']='failed'
        record['failure']=dict(type=type(exc).__name__,message=str(exc))
    finally:
        record['elapsed_seconds']=time.monotonic()-start
        record['after_sha256']=inventory()
        record['unchanged']=before==record['after_sha256']
        record['stdout']=dict(path=str(stdout_path.relative_to(ROOT)).replace('\\','/'),sha256=sha(stdout_path.read_bytes()))
        record['stderr']=dict(path=str(stderr_path.relative_to(ROOT)).replace('\\','/'),sha256=sha(stderr_path.read_bytes()))
        record['finished_at']=datetime.now(timezone.utc).isoformat()
        if not record['unchanged']:
            record['status']='failed'
        save()
    print(json.dumps({k:record[k] for k in ('task_id','reviewed_commit','status','elapsed_seconds','unchanged')}))
    return 0 if record['status']=='passed' else 1

if __name__=='__main__':
    raise SystemExit(main())
