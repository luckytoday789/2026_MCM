"""Structural verification of immutable canonical Git receipts; no checkout mutation."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def verify(task_id, commit):
    task = json.loads((ROOT / f'ops/tasks/{task_id}.json').read_bytes())
    q = next(t for t in json.loads((ROOT / 'ops/queue.json').read_bytes())['tasks'] if t['id'] == task_id)
    receipt = json.loads(git('show', f'{commit}:handoff/{task_id}/result.json'))
    digest = sha(json.dumps(task, sort_keys=True, separators=(',', ':')).encode())
    branch = f"work/{task['owner']}/{task_id}-a{task['attempt']}"
    assert git('rev-parse', 'origin/' + branch).decode().strip() == commit
    assert len(commit) == 40 and git('cat-file', '-t', commit).strip() == b'commit'
    assert git('rev-parse', commit + '^').decode().strip() == task['base_commit']
    subprocess.run(['git', 'merge-base', '--is-ancestor', task['base_commit'], 'origin/main'], cwd=ROOT, check=True)
    assert receipt['task_sha256'] == q['task_sha256'] == digest
    assert (receipt['task_id'], receipt['role'], receipt['attempt'], receipt['base_commit']) == (task_id, task['owner'], task['attempt'], task['base_commit'])
    assert receipt['task_parameters'] == task['parameters']
    assert receipt['started_from_pinned_source'] is True
    assert receipt['artifact_hash_basis'] == 'canonical_git_blob'
    assert receipt['status'] == 'completed' and receipt['failure'] is None
    assert receipt['python'].startswith('3.12.')
    assert receipt['input_manifest'] == json.loads(git('show', task['base_commit'] + ':data/manifest.json'))
    expected_commands = task['commands'] + task['validation_commands']
    actual = receipt['checks'][1:] if task['kind'] == 'agent' else receipt['checks']
    assert len(actual) == len(expected_commands)
    assert all(c['exit_code'] == 0 for c in receipt['checks'])
    for command, check in zip(expected_commands, actual):
        assert check['argv'][1:] == command[1:]
    names = git('diff', '--name-only', task['base_commit'], commit).decode().splitlines()
    permitted = task['allowed_paths'] + [f'handoff/{task_id}']
    assert all(any(n == p or n.startswith(p + '/') for p in permitted) for n in names)
    assert set(task['deliverables']) <= set(names)
    assert set(names) == set(receipt['artifacts_sha256']) | {f'handoff/{task_id}/result.json'}
    hashes = {}
    for name, expected in receipt['artifacts_sha256'].items():
        blob = git('show', commit + ':' + name)
        assert sha(blob) == expected, name
        mode = git('ls-tree', commit, '--', name).decode().split()[0]
        assert mode in ('100644', '100755'), (name, mode)
        hashes[name] = expected
    for name, expected in task['parameters'].get('source_sha256', {}).items():
        assert sha(git('show', task['base_commit'] + ':' + name)) == expected, name
    return dict(task_id=task_id, reviewed_commit=commit, base_commit=task['base_commit'],
                task_sha256=digest, branch=branch, structural_checks='passed',
                source_hashes_checked=task['parameters'].get('source_sha256', {}),
                artifacts_sha256=hashes, accepted_paths=names, excluded_paths=[],
                receipt_python=receipt['python'], prescribed_command_count=len(actual))
