"""Chief read-only replay of a published SOL-031 candidate; not automatic acceptance.

Runs both immutable commands in real Git worktrees with opposite autocrlf modes,
checks published fixture hashes/sizes, and independently recomputes persisted
synthetic accounting using the already-qualified Fraction/Decimal oracle.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from verify_canonical_receipt import verify, git, sha
from writer_persisted_oracle import audit_fixture

ROOT = Path(__file__).resolve().parents[2]


def save_new(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def inventory(work, names):
    return {name: {'sha256': sha((work / name).read_bytes()),
                   'bytes': (work / name).stat().st_size}
            for name in names}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('commit')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    assert sys.version_info[:2] == (3, 12), 'Python 3.12 required'
    output = Path(args.output).resolve()
    assert output.is_relative_to(ROOT / 'audit/chief')
    assert not output.exists(), 'Preserve previous review evidence'
    result = {'schema_version': 1, 'reviewed_commit': args.commit,
              'checked_at': datetime.now(timezone.utc).isoformat(),
              'status': 'started', 'decision': 'manual_review_required',
              'competition_input_read': False, 'production_execution_authorized': False,
              'final_data_open': False, 'runs': []}
    try:
        info = verify('SOL-031', args.commit)
        result['structural'] = info
        task = json.loads((ROOT / 'ops/tasks/SOL-031.json').read_bytes())
        queue = json.loads((ROOT / 'ops/queue.json').read_bytes())['tasks']
        for name, commit in task['parameters']['accepted_dependencies'].items():
            q = next(q for q in queue if q['id'] == name)
            assert q['state'] == 'accepted' and q['reviewed_commit'] == commit, name
        evidence = json.loads(git('show', args.commit + ':audit/SOL-031/verification.json'))
        fixture = evidence['fixture_root']
        assert fixture.startswith('audit/SOL-031/synthetic-')
        published = {}
        failures = []
        for name, expected in evidence['fixture_bytes_sha256'].items():
            raw = git('show', args.commit + ':' + fixture + '/' + name)
            assert sha(raw) == expected, ('canonical fixture hash', name)
            assert len(raw) == evidence['fixture_actual_bytes'][name], ('fixture size', name)
            published[name] = {'sha256': sha(raw), 'bytes': len(raw)}
            if name.endswith('/failure.json'):
                assert b'\r' not in raw, ('non-LF failure JSON', name)
                json.loads(raw)
                failures.append(name)
        assert len(failures) >= 3, 'Retain partial, timeout, oversize fixtures'
        result['published_fixture_inventory'] = published
        result['deterministic_failed_staging_files'] = failures
        result['oracle_source_sha256'] = sha((ROOT / 'audit/chief/writer_persisted_oracle.py').read_bytes())
        result['independent_arithmetic'] = audit_fixture(args.commit, fixture)
        env = {k: v for k, v in os.environ.items() if k.lower() != 'pythonpath'}
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        protected = sorted(set(info['source_hashes_checked']) | set(info['accepted_paths']))
        for autocrlf in ('false', 'true'):
            work = ROOT / '.runtime' / ('r31-' + args.commit[:8] + '-' + autocrlf)
            assert not work.exists(), ('Preserve prior scratch worktree', str(work))
            checkout = ['git', '-c', 'core.autocrlf=' + autocrlf,
                        'worktree', 'add', '--detach', str(work), args.commit]
            run = subprocess.run(checkout, cwd=ROOT, capture_output=True, text=True)
            item = {'autocrlf': autocrlf, 'checkout_argv': checkout,
                    'checkout_exit_code': run.returncode, 'checkout_stdout': run.stdout,
                    'checkout_stderr': run.stderr, 'commands': []}
            result['runs'].append(item)
            assert run.returncode == 0, item
            assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=work).decode().strip() == args.commit
            assert not (work / '.runtime/task.json').exists()
            before = inventory(work, protected)
            item['protected_before'] = before
            for name, record in published.items():
                raw = (work / fixture / name).read_bytes()
                assert sha(raw) == record['sha256'] and len(raw) == record['bytes'], ('checkout fixture', autocrlf, name)
            for command in task['validation_commands']:
                argv = [sys.executable if a == '{python}' else a for a in command]
                start = time.monotonic()
                run = subprocess.run(argv, cwd=work, env=env, capture_output=True,
                                     text=True, timeout=240)
                record = {'argv': command, 'exit_code': run.returncode,
                          'seconds': time.monotonic() - start,
                          'stdout': run.stdout, 'stderr': run.stderr}
                item['commands'].append(record)
                assert run.returncode == 0, record
            after = inventory(work, protected)
            item['source_audit_reference_bytes_unchanged'] = before == after
            assert before == after, 'Read-only checks changed protected bytes'
            new_files = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard'], cwd=work).decode().splitlines()
            assert not new_files, ('Unexpected untracked artifacts', new_files)
        result['PYTHONPATH_absent'] = True
        result['status'] = 'passed'
    except Exception as exc:
        result['status'] = 'failed'
        result['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        raise
    finally:
        save_new(output, result)
    print(json.dumps({'status': result['status'], 'reviewed_commit': args.commit,
                      'independent_numeric_checks': result['independent_arithmetic']['independent_numeric_checks'],
                      'git_checkout_modes': len(result['runs']), 'decision': result['decision']}))


if __name__ == '__main__':
    main()
