"""Chief replay of exact SOL-002/003 deliveries in isolated pinned-base worktrees.

Usage: python audit/chief/replay_sol_reviews.py
Only the reviewer's branch-name probe is adapted for a detached chief worktree;
actual HEAD, remote ref/receipt, task digest and all numerical tests are checked.
Legacy checkout bytes are reconstructed solely inside ignored review worktrees.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
CASES = {'SOL-002': '54d90abd3d35f6578bab964cd54dcce42e578f53',
         'SOL-003': 'bb74c0f25cb18c3e02fef6d51416422514a8f503'}

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

def restore_bytes(path, digest):
    raw = path.read_bytes()
    for candidate in (raw, raw.replace(b'\r\n', b'\n'), raw.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')):
        if sha(candidate) == digest:
            path.write_bytes(candidate)
            return
    raise AssertionError('Cannot reconstruct exact recorded bytes: ' + str(path))

def prepare(tid, commit):
    """Verify public evidence and prepare a detached copy; never alter worker refs."""
    task = json.loads((ROOT / f'ops/tasks/{tid}.json').read_text())
    receipt = json.loads(git('show', f'{commit}:handoff/{tid}/result.json'))
    task_hash = sha(json.dumps(task, sort_keys=True, separators=(',', ':')).encode())
    queue_item = next(x for x in json.loads((ROOT / 'ops/queue.json').read_text())['tasks'] if x['id'] == tid)
    assert receipt['task_sha256'] == queue_item['task_sha256'] == task_hash
    assert (receipt['task_id'], receipt['role'], receipt['attempt'], receipt['base_commit']) == (tid, 'sol', task['attempt'], task['base_commit'])
    assert receipt['task_parameters'] == task['parameters'] and receipt['started_from_pinned_source'] is True
    assert receipt['status'] == 'completed' and receipt['failure'] is None and receipt['python'].startswith('3.12.')
    assert git('rev-parse', commit + '^').decode().strip() == task['base_commit']
    subprocess.run(['git', 'merge-base', '--is-ancestor', task['base_commit'], 'origin/main'], cwd=ROOT, check=True)
    assert receipt['input_manifest'] == json.loads(git('show', task['base_commit'] + ':data/manifest.json'))
    assert all(x['exit_code'] == 0 for x in receipt['checks'])
    assert receipt['checks'][-1]['argv'][1:] == task['validation_commands'][0][1:]
    names = git('diff', '--name-only', task['base_commit'], commit).decode().splitlines()
    permitted = task['allowed_paths'] + [f'handoff/{tid}']
    assert all(any(p == v or p.startswith(v + '/') for v in permitted) for p in names)
    assert set(task['deliverables']) <= set(names)
    assert set(names) == set(receipt['artifacts_sha256']) | {f'handoff/{tid}/result.json'}
    hashes = {}
    for name, digest in receipt['artifacts_sha256'].items():
        raw = git('show', commit + ':' + name)
        crlf = raw.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        basis = 'canonical_git_blob' if sha(raw) == digest else 'reconstructed_CRLF_checkout' if sha(crlf) == digest else 'unverified'
        assert basis != 'unverified', name
        hashes[name] = {'receipt_sha256': digest, 'canonical_sha256': sha(raw), 'reconstructed_crlf_sha256': sha(crlf), 'match': basis}
    for name, digest in task['parameters'].get('source_sha256', {}).items():
        assert sha(git('show', task['base_commit'] + ':' + name)) == digest
    info = {'task_id': tid, 'reviewed_commit': commit, 'base_commit': task['base_commit'],
            'task_sha256': task_hash, 'structural_checks': 'passed', 'artifact_hashes': hashes,
            'excluded_paths': [], 'accepted_paths': names, 'final_outcomes_computed': False}
    dest = ROOT / '.runtime/reviews' / (tid + '-acceptance')
    dest.mkdir(parents=True, exist_ok=True)
    work = dest / 'worktree'
    if not work.exists():
        subprocess.run(['git', 'worktree', 'add', '--detach', str(work), task['base_commit']], cwd=ROOT, check=True, capture_output=True)
    for name in names:
        path = work / name
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(git('show', commit + ':' + name))
    (work / '.runtime').mkdir(exist_ok=True)
    task_file = work / '.runtime/task.json'
    if task_file.exists():
        assert json.loads(task_file.read_text(encoding='utf-8')) == task
    else:
        task_file.write_text(json.dumps(task), encoding='utf-8')
    (dest / 'structure.json').write_text(json.dumps(info, indent=2) + '\n', encoding='utf-8')
    return info

def main():
    assert sys.version_info[:2] == (3, 12)
    for tid, commit in CASES.items():
        dest = ROOT / '.runtime/reviews' / (tid + '-acceptance')
        info = prepare(tid, commit)
        work = dest / 'worktree'
        task = json.loads((ROOT / f'ops/tasks/{tid}.json').read_text())
        receipt = json.loads(git('show', f'{commit}:handoff/{tid}/result.json'))
        assert info['reviewed_commit'] == commit
        assert git('rev-parse', f'origin/work/sol/{tid}-a1').decode().strip() == commit
        assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=work).decode().strip() == task['base_commit']
        canonical_task = json.dumps(task, sort_keys=True, separators=(',', ':')).encode()
        assert sha(canonical_task) == info['task_sha256'] == receipt['task_sha256']
        for name, digest in receipt['artifacts_sha256'].items():
            restore_bytes(work / name, digest)
        evidence_file = work / f'audit/{tid}/verification.json'
        evidence = json.loads(evidence_file.read_text(encoding='utf-8'))
        if tid == 'SOL-003':
            for name, hashes in evidence['pinned_inputs'].items():
                restore_bytes(work / name, hashes['working_file_sha256'])
        before = {name: sha((work / name).read_bytes()) for name in receipt['artifacts_sha256']}
        spec = importlib.util.spec_from_file_location(tid.replace('-', '_'), work / f'audit/{tid}/verify.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        actual_git = module.git
        def review_git(*args, **kwargs):
            if args == ('branch', '--show-current'):
                return f'work/sol/{tid}-a1\n'.encode()
            return actual_git(*args, **kwargs)
        with patch.object(module, 'git', side_effect=review_git), patch.object(sys, 'argv', [str(spec.origin), '--check']):
            exit_code = module.main()
        assert exit_code == 0
        after = {name: sha((work / name).read_bytes()) for name in receipt['artifacts_sha256']}
        assert before == after, 'Worker evidence must stay unchanged'
        info['chief_replay'] = {'exit_code': exit_code, 'python': sys.version.split()[0],
            'mode': 'Exact pinned-base detached worktree; branch-name probe adapted after independent remote-ref validation',
            'saved_worker_evidence_unchanged': True,
            'checkout_bytes': 'Reconstructed against recorded digests, including CRLF where necessary',
            'scope': 'Toy recomputation for SOL-002; source/split metadata and saved evidence for SOL-003; no final outcomes'}
        if tid == 'SOL-002':
            info['chief_replay'].update(check_count=evidence['check_count'], largest_absolute_residual=evidence['largest_absolute_residual'])
        (ROOT / f'audit/chief/{tid}-review.json').write_text(json.dumps(info, indent=2) + '\n', encoding='utf-8', newline='\n')
        print(tid + ': replay passed; worker artifacts unchanged')

if __name__ == '__main__':
    main()
