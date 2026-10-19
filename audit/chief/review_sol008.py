"""Replay exact SOL-008 evidence at its pinned base, without worker mutations."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from verify_canonical_receipt import verify, git

ROOT = Path(__file__).resolve().parents[2]
COMMIT = '818af5d65bd8a271962d848dd552bd39ca561f68'
HY3 = '7652410d73425371110784ef5fa97c03470a074e'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new_or_equal(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        assert path.read_bytes() == raw, str(path)
    else:
        path.write_bytes(raw)


def main():
    assert sys.version_info[:2] == (3, 12)
    info = verify('SOL-008', COMMIT)
    hy3 = verify('HY3-003', HY3)
    dest = ROOT / '.runtime/reviews/SOL-008-acceptance'
    work = dest / 'worktree'
    dest.mkdir(parents=True, exist_ok=True)
    if not work.exists():
        subprocess.run(['git', 'worktree', 'add', '--detach', str(work), info['base_commit']],
                       cwd=ROOT, check=True, capture_output=True)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=work).decode().strip()
    assert head == info['base_commit']
    for name in info['accepted_paths']:
        write_new_or_equal(work / name, git('show', COMMIT + ':' + name))
    before = {p: digest(work / p) for p in info['accepted_paths']}
    command = [sys.executable, '-B', 'audit/SOL-008/verify.py', '--check']
    result = subprocess.run(command, cwd=work, capture_output=True, text=True, timeout=180)
    (dest / 'replay.txt').write_text(result.stdout + result.stderr, encoding='utf-8')
    assert result.returncode == 0, result.stdout + result.stderr
    replay = json.loads(result.stdout)
    assert replay['status'] == 'passed' and replay['read_only'] is True
    evidence = json.loads((work / 'audit/SOL-008/verification.json').read_bytes())
    assert evidence['numerical_verdict'] == evidence['scheduler_verdict'] == 'pass'
    assert evidence['blockers'] == []
    assert evidence['numerical']['forward_prefixes'] == 165
    assert evidence['corruption']['rejected'] == 7

    # Chief independently challenges the published CLI's refusal to repair a
    # mismatched saved record. The original worker evidence remains untouched.
    scratch = dest / 'corrupted-evidence'
    scratch.mkdir(exist_ok=True)
    for name in ('verification.json', 'scheduler-review.json', 'findings.json'):
        raw = (work / 'audit/SOL-008' / name).read_bytes()
        if name == 'verification.json':
            obj = json.loads(raw)
            obj['numerical']['forward_prefixes'] += 1
            raw = (json.dumps(obj, indent=2) + '\n').encode()
        write_new_or_equal(scratch / name, raw)
    scratch_before = {p.name: digest(p) for p in scratch.iterdir()}
    bad = subprocess.run(command + ['--evidence-dir', str(scratch)], cwd=work,
                         capture_output=True, text=True, timeout=180)
    (dest / 'corruption.txt').write_text(bad.stdout + bad.stderr, encoding='utf-8')
    assert bad.returncode != 0 and 'saved verification.json mismatch' in bad.stderr
    assert scratch_before == {p.name: digest(p) for p in scratch.iterdir()}
    assert before == {p: digest(work / p) for p in info['accepted_paths']}
    info.update(
        status='accepted_independent_review',
        final_outcomes_computed=False,
        chief_replay={
            'python': sys.version.split()[0], 'exit_code': result.returncode,
            'pinned_base_worktree': True, 'worker_artifacts_unchanged': True,
            'result': replay, 'corrupted_record_exit_code': bad.returncode,
            'corrupted_record_unchanged': True,
            'replay_log_sha256': digest(dest / 'replay.txt'),
            'corruption_log_sha256': digest(dest / 'corruption.txt'),
        },
        numerical=evidence['numerical'], residuals=evidence['residuals'],
        scheduler_commit=evidence['commits']['scheduler_commit'],
        preserved_failures='SOL-006 quota failure and SOL-008 audit-tool defects retained verbatim.',
        limits='Development descriptive evidence only; no policy selection, significance or future guarantee.',
    )
    hy3.update(
        status='accepted_development_baseline_evidence',
        final_outcomes_computed=False,
        independent_review_task='SOL-008', independent_review_commit=COMMIT,
        independent_review_evidence='audit/chief/SOL-008-review.json',
        earlier_chief_checks='audit/chief/HY3-003-preliminary.json',
        evidence_scope='Three predeclared static references, five horizons, development scenarios 1-120.',
        production_experiment_rerun=False,
        limits='No fitted-policy validation, suitability decision, significance or final-data access.',
    )
    for name, obj in [('SOL-008-review.json', info), ('HY3-003-review.json', hy3)]:
        write_new_or_equal(ROOT / 'audit/chief' / name,
                           (json.dumps(obj, indent=2) + '\n').encode())
    print(json.dumps({'SOL-008': replay, 'HY3-003': hy3['status'],
                      'chief_corruption_rejected': True}))


if __name__ == '__main__':
    main()
