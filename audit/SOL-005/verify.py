"""SOL-005: pinned Git receipt/provenance review; standard library, no CSV analysis.
Initialize absent evidence with no arguments. --check recomputes without writing.
Git is invoked read-only with binary stdout; no checkout HEAD or branch is used.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'audit/SOL-005'
BASE = 'da96ea77bcc476f2970a982f037c2679a68522b7'
DISPATCH = 'fa7856618626b2534524d18ac25fbca6fcc4cdcb'
HY = '9fdd20e09f8c080b7d3381d3d545524084cb3955'
PRIOR = 'bb74c0f25cb18c3e02fef6d51416422514a8f503'
SOURCE = 'c651c67c30db1131c25641ac94631238cba0dd8d'
OLD = '2a0263c5822988c0385d32fe084b794f8d644bc5'
REG = '5de076351c7580f32ac46f8eae1afc2a12939116'
TASK_DIGEST = '39009df675c120d5fa46f19f1f6d540e885b1d63af48bb1582041a3ad6b42acd'
COMMITS = dict(chief_base=BASE, task_dispatch=DISPATCH, hy3_result=HY,
               independent_sol003=PRIOR, source_base=SOURCE,
               cancelled_hy3001=OLD, release_registration=REG)
LIMITS = [
    'Reuses only SOL-003 independent source/split metadata proof at the explicit accepted commit.',
    'No CSV numeric analysis, strategy run, numerical experiment or prior 32-test suite was rerun.',
    'Python 3.12.10 is supported by receipt, both retained preflight logs and environment JSON; these are retained evidence, not remote process attestation.',
    'Chief metadata-rerun equality is verified against its saved report; its separate process was not rerun or independently attested here.',
    'Git commits have no intrinsic branch: immutable queue branch/commit binding is checked; no current checkout branch is used.',
    'Cancelled HY3-001 receipts remain in their original Git objects; no old Python 3.13 execution is accepted.',
    'This review certifies neither investment performance, SOL-004 future driver nor any future HY3 result; it does not open the final gate.',
    'Final input bytes are hashed only; no strategy is applied to final inputs.',
]
checks = []
blobs = {}
source_hashes = {}

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def git(*args):
    result = subprocess.run(['git', *args], cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise RuntimeError('git ' + ' '.join(args) + ': ' + result.stderr.decode('utf-8', 'replace').strip())
    return result.stdout

def blob(commit, path):
    raw = git('show', commit + ':' + path)
    blobs[commit + ':' + path] = dict(sha256=sha(raw), bytes=len(raw))
    return raw

def obj(commit, path):
    return json.loads(blob(commit, path))

def digest(task):
    return sha(json.dumps(task, sort_keys=True, separators=(',', ':')).encode())

def check(name, expected, observed, fix='Chief must correct the evidence in a new immutable task/receipt; preserve this failed review and original artifacts.'):
    facts = lambda value: dict(sha256=sha(value), bytes=len(value)) if isinstance(value, bytes) else value
    checks.append(dict(id=name, status='passed' if expected == observed else 'failed',
                       expected=facts(expected), observed=facts(observed), fix=None if expected == observed else fix))

def audit():
    task = obj(DISPATCH, 'ops/tasks/SOL-005.json')
    check('review_task_digest', TASK_DIGEST, digest(task))
    check('review_task_identity', ['SOL-005', 1, 'sol', BASE, ['audit/SOL-005']],
          [task['id'], task['attempt'], task['owner'], task['base_commit'], task['allowed_paths']])
    check('review_task_pinned_results', [HY, PRIOR, False],
          [task['parameters']['hy3_result_commit'], task['parameters']['prior_independent_review_commit'], task['parameters']['final_outcomes_allowed']])
    for path, expected in task['parameters']['source_sha256'].items():
        check('task_source_pin:' + path, expected, sha(blob(BASE, path)))
    ht_raw = blob(BASE, 'ops/tasks/HY3-002.json')
    ht = json.loads(ht_raw)
    receipt = obj(HY, 'handoff/HY3-002/result.json')
    review = obj(BASE, 'audit/chief/HY3-002-review.json')
    release = obj(BASE, 'audit/chief/HY3-002-release.json')
    prior_raw = blob(PRIOR, 'audit/SOL-003/verification.json')
    pv = json.loads(prior_raw)
    sr = obj(BASE, 'audit/chief/SOL-003-review.json')
    queues = {c: {x['id']: x for x in obj(c, 'ops/queue.json')['tasks']} for c in [BASE, DISPATCH]}
    check('published_hy3_task_unchanged', ht_raw, blob(DISPATCH, 'ops/tasks/HY3-002.json'))
    check('hy3_task_digest', digest(ht), receipt['task_sha256'])
    check('hy3_task_identity', ['HY3-002', 1, 'hy3', 'commands', SOURCE],
          [ht['id'], ht['attempt'], ht['owner'], ht['kind'], ht['base_commit']])
    check('hy3_receipt_identity', [ht['id'], ht['attempt'], ht['owner'], SOURCE, ht['parameters']],
          [receipt['task_id'], receipt['attempt'], receipt['role'], receipt['base_commit'], receipt['task_parameters']])
    check('hy3_actual_parent', [SOURCE], git('show', '-s', '--format=%P', HY).decode().split())
    check('sol003_actual_parent', [SOURCE], git('show', '-s', '--format=%P', PRIOR).decode().split())
    check('hy3_receipt_completion', ['completed', None, True, 'canonical_git_blob'],
          [receipt['status'], receipt['failure'], receipt['started_from_pinned_source'], receipt['artifact_hash_basis']])
    for c, q in queues.items():
        row = q['HY3-002']
        check('hy3_queue_binding:' + c, ['hy3', 1, 'work/hy3/HY3-002-a1', HY, digest(ht), 'accepted'],
              [row['owner'], row['attempt'], row['branch'], row['reviewed_commit'], row['task_sha256'], row['state']])
        check('sol003_accepted_binding:' + c, [PRIOR, 'accepted'], [q['SOL-003']['reviewed_commit'], q['SOL-003']['state']])
        check('hy3001_cancelled:' + c, [OLD, 'cancelled'], [q['HY3-001']['reviewed_commit'], q['HY3-001']['state']])
    check('sol005_queue_binding', [TASK_DIGEST, 'sol', 1, 'work/sol/SOL-005-a1'],
          [queues[DISPATCH]['SOL-005'][k] for k in ['task_sha256', 'owner', 'attempt', 'branch']])
    logs = ['handoff/HY3-002/check-%d.txt' % i for i in range(4)]
    outputs = ['results/development/HY3-002/environment.json', 'results/development/HY3-002/input-check.json']
    expected_paths = sorted(logs + outputs + ['handoff/HY3-002/result.json'])
    actual_paths = git('diff-tree', '--no-commit-id', '--name-only', '-r', HY).decode().splitlines()
    check('hy3_exact_changed_paths', expected_paths, sorted(actual_paths))
    check('hy3_only_added_files', ['A'] * 7,
          [line.split('\t')[0] for line in git('diff-tree', '--no-commit-id', '--name-status', '-r', HY).decode().splitlines()])
    check('hy3_deliverables', outputs, ht['deliverables'])
    check('hy3_allowed_paths', ['results/development/HY3-002'], ht['allowed_paths'])
    check('hy3_scope_with_runner_handoff_exception', [],
          [p for p in actual_paths if not any(p == x or p.startswith(x + '/') for x in ht['allowed_paths'] + ['handoff/HY3-002'])])
    for p in expected_paths:
        mode = git('ls-tree', HY, '--', p).decode().split()[0]
        check('regular_blob:' + p, '100644', mode)
        check('integrated_bytes:' + p, sha(blob(HY, p)), sha(blob(BASE, p)))
    check('six_artifact_keys', sorted(logs + outputs), sorted(receipt['artifacts_sha256']))
    for p in logs + outputs:
        observed = sha(blob(HY, p))
        check('receipt_hash:' + p, receipt['artifacts_sha256'][p], observed)
        check('chief_hash:' + p, review['artifact_hashes'][p], observed)
    env = obj(HY, outputs[0])
    metadata = obj(HY, outputs[1])
    check('receipt_python_exact', '3.12.10', receipt['python'].split()[0])
    check('environment_exact', dict(status='passed', python='3.12.10', required_python='3.12', reason=None), env)
    check('required_python', '3.12', ht['parameters']['required_python'])
    commands = ht['commands'] + ht['validation_commands']
    expected_commands = [
        ['{python}', 'scripts/check_worker_env.py', '--output', outputs[0]],
        ['{python}', 'scripts/check_inputs.py', '--output', outputs[1]],
        ['{python}', 'scripts/check_worker_env.py'],
        ['{python}', 'scripts/check_inputs.py'],
    ]
    check('prescribed_commands', expected_commands, commands)
    check('command_count', 4, len(receipt['checks']))
    executable = receipt['checks'][0]['argv'][0]
    for i, command in enumerate(expected_commands):
        run = receipt['checks'][i]
        check('command_argv:%d' % i, [executable] + command[1:], run['argv'])
        check('command_exit:%d' % i, 0, run['exit_code'])
        check('command_retained_log:%d' % i, env if i % 2 == 0 else metadata, obj(HY, logs[i]))
        check('command_log_exact_print_bytes:%d' % i, blob(HY, outputs[i % 2]) + (b'' if i % 2 == 0 else b'\n'), blob(HY, logs[i]))
    check('environment_log_pair_bytes', sha(blob(HY, logs[0])), sha(blob(HY, logs[2])))
    check('metadata_log_pair_bytes', sha(blob(HY, logs[1])), sha(blob(HY, logs[3])))
    # Hash bytes only. Never parse source CSV values or execute the prior checker.
    manifest = obj(SOURCE, 'data/manifest.json')
    check('receipt_input_manifest', manifest, receipt['input_manifest'])
    check('manifest_same_as_prior', sha(blob(PRIOR, 'data/manifest.json')), sha(blob(HY, 'data/manifest.json')))
    for item in manifest['files']:
        p = item['path']
        versions = {c: dict(sha256=sha(blob(c, p)), bytes=len(blob(c, p))) for c in [SOURCE, HY, PRIOR, BASE]}
        source_hashes[p] = versions[HY]
        for c, fact in versions.items():
            check('source_manifest:' + c + ':' + p, dict(sha256=item['sha256'], bytes=item['bytes']), fact)
        check('prior_independent_source:' + p, pv['sources'][p], versions[HY])
        check('chief_source:' + p, review['source_hashes'][p], versions[HY]['sha256'])
    for p in ['scripts/check_inputs.py', 'scripts/check_worker_env.py']:
        expected = sha(blob(PRIOR, p))
        for c in [SOURCE, HY, BASE]:
            check('exact_prior_checker:' + c + ':' + p, expected, sha(blob(c, p)))
        if p in pv['pinned_inputs']:
            check('prior_review_pinned_checker:' + p, pv['pinned_inputs'][p]['git_blob_sha256'], expected)
    check('prior_verification_preserved', sha(prior_raw), sha(blob(BASE, 'audit/SOL-003/verification.json')))
    check('prior_verification_accepted_hash', sr['artifact_hashes']['audit/SOL-003/verification.json']['canonical_sha256'], sha(prior_raw))
    check('prior_acceptance', ['accepted', PRIOR], [sr['decision'], sr['reviewed_commit']])
    check('prior_independent_success', ['passed', 0, False, dict(source_hash_mismatches=0, key_errors=0, invalid_gross_cells=0, split_row_mismatches=0)],
          [pv['status'], pv['validation_exit_code'], pv['final_outcomes_computed'], pv['residuals']])
    check('metadata_same_as_independent_proof', pv['metadata'], metadata)
    old_output = blob(OLD, 'results/development/HY3-001/input-check.json')
    check('metadata_exact_old_blob', pv['hy3_output_blob_sha256'], sha(blob(HY, outputs[1])))
    check('metadata_old_output_bytes', sha(old_output), sha(blob(HY, outputs[1])))
    check('metadata_chief_saved_rerun', metadata, review['chief_metadata_rerun'])
    check('metadata_no_final_outcomes', False, metadata['final_outcomes_computed'])
    check('chief_identity_and_scope', ['HY3-002', 'accepted', HY, SOURCE, digest(ht), 'canonical_git_blob', 'passed'],
          [review[k] for k in ['task_id', 'decision', 'reviewed_commit', 'base_commit', 'task_sha256', 'artifact_hash_basis', 'identity_scope_source_and_commands']])
    check('chief_environment', env, review['worker_environment'])
    check('chief_accepted_paths', expected_paths, sorted(review['accepted_paths']))
    check('chief_excluded_paths', [], review['excluded_paths'])
    for c, q in queues.items():
        check('queue_accepted_paths:' + c, expected_paths, sorted(q['HY3-002']['accepted_paths']))
        check('queue_excluded_paths:' + c, [], q['HY3-002']['excluded_paths'])
    independent = review['independent_evidence']
    check('chief_carry_forward_binding', ['SOL-003', PRIOR, 'audit/SOL-003/verification.json', True, True, True],
          [independent[k] for k in ['accepted_task', 'reviewed_commit', 'path', 'same_source_bytes', 'same_exact_metadata', 'same_reviewed_checker_and_environment_preflight']])
    check('chief_carry_forward_scope', 'Carry forward independent numerical evidence for identical source and deterministic output; this does not accept any strategy outcome.', independent['scope'])
    check('chief_gate_claims', ['HY3-001', False], [review['predecessor_remains_cancelled'], review['final_outcomes_computed']])
    old_receipt = blob(OLD, 'handoff/HY3-001/result.json')
    check('old_receipt_preserved', pv['hy3_receipt_blob_sha256'], sha(old_receipt))
    check('old_runtime_remains_noncompliant', '3.13.14', json.loads(old_receipt)['python'].split()[0])
    check('prior_does_not_accept_old_runtime', [False, True, '3.13.14'],
          [pv['hy3_acceptance']['accepted'], pv['hy3_acceptance']['rerun_required'], pv['hy3_acceptance']['worker_python']])
    for p, fact in pv['hy3_artifacts'].items():
        check('old_artifact_preserved:' + p, fact['git_blob_sha256'], sha(blob(OLD, p)))
    check('old_chief_rejection_preserved', pv['chief_hy3_review_blob_sha256'], sha(blob(BASE, 'audit/chief/HY3-001-review.json')))
    check('old_chief_rejection', 'not_accepted_python_version', obj(BASE, 'audit/chief/HY3-001-review.json')['status'])
    registration = obj(REG, 'status.json')
    check('release_registration_exact', registration, release['registration'])
    check('release_prerequisites', ['HY3-002', PRIOR, True, REG],
          [release[k] for k in ['task_id', 'prerequisite_review_commit', 'task_unchanged', 'registration_commit']])
    check('registration_runtime', ['hy3', 'idle', '3.12.10'], [registration[k] for k in ['role', 'state', 'python']])
    check('release_within_registration_lease', True,
          dt.datetime.fromisoformat(registration['updated_at']) <= dt.datetime.fromisoformat(release['released_at']) < dt.datetime.fromisoformat(registration['lease_until']))
    check('release_before_result_finished', True,
          dt.datetime.fromisoformat(release['released_at']) < dt.datetime.fromisoformat(receipt['finished_at']))
    for c in [SOURCE, HY, PRIOR, BASE, DISPATCH]:
        control = obj(c, 'ops/control.json')
        check('final_gate_closed:' + c, False, control['final_data_open'])
        check('control_running:' + c, 'running', control['state'])
    # Reused proof is limited to deterministic metadata, not old execution acceptance.
    check('source_base_and_contract_pins', [SOURCE, False], [pv['reviewed_shas']['base'], task['parameters']['final_outcomes_allowed']])


def canonical_text(path):
    return path.read_text(encoding='utf-8').replace('\r\n', '\n')


def review_text(status, blockers):
    return '\n'.join([
        '# SOL-005 receipt and provenance review', '',
        'Status: ' + status + '. Material blockers: ' + str(len(blockers)) + '.', '',
        'Reviewed HY3-002 exactly at ' + HY + ', chief acceptance/release at ' + BASE +
        ', and accepted SOL-003 evidence at ' + PRIOR + '. SOL-005 dispatch is pinned to ' + DISPATCH + '.', '',
        'The binary Git audit checks the immutable task digest, role/attempt, queue branch binding, actual single parent, allowed paths plus the runner handoff exception, seven added files, six canonical artifact hashes, and integrated bytes. It checks all four prescribed argv/exit records and retained logs against both JSON outputs. Receipt Python and environment Python must both be 3.12.10; the preflight must explicitly pass. Exit labels alone are insufficient.', '',
        'The HY3 task was published after its source base and is read at the chief base, not assumed present in the result tree. The actual result parent is ' + SOURCE + '. Source PDF/CSV bytes, manifest and both exact checker scripts match the prior independent review. The input-check JSON has the same canonical hash b6bff43d5ad3ea27a5f103acfcd4ebc425a62788c0f6a70d7bb4d1790deaa3cf and matches SOL-003 metadata and chief saved rerun field for field.', '',
        'Reused proof: SOL-003 verification.json sources, metadata, zero residuals and its binding to the original HY3-001 metadata output; exact source/checker equality is established here. SOL-003 independently verified source hashes, schema, complete unique keys, valid finite gross cells and exact splits. The old execution remains rejected for Python 3.13.14. Its original receipt/artifacts and rejection remain available at pinned objects; cancellation remains recorded. The corrected environment is new receipt evidence, not a new investment experiment.', '',
        'The release registration is compared with its pinned status commit, including Python and lease timing. Chief equality and carry-forward scope are supported only for identical deterministic metadata under a corrected interpreter. The final gate is closed at the source/result/review/base/dispatch versions. This audit applied no strategy to any final data.', '',
        'Limitations:', '', *['- ' + s for s in LIMITS], '',
        'Validation: python -B audit/SOL-005/verify.py --check. Initializer writes each evidence file only if absent; check recomputes all facts from explicit Git objects, compares saved evidence and review text, and never rewrites them. Local review text/code hashes use UTF-8 LF normalization to permit ordinary Git CRLF checkouts; all source/receipt/output provenance hashes use exact binary git show bytes.', '',
        'Blockers and concrete fixes:', '',
        *(['- ' + x['id'] + ': ' + str(x['observed']) + '. Fix: ' + x['fix'] for x in blockers] or ['- None.']), '',
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 12):
        print('Python 3.12 is required for this audit.', file=sys.stderr)
        return 1
    try:
        audit()
    except Exception as error:
        check('audit_execution_complete', 'all pinned evidence readable and checks complete',
              type(error).__name__ + ': ' + str(error),
              'Restore missing exact Git objects/evidence or correct the audit implementation within audit/SOL-005; do not replace pinned commits or erase failure evidence.')
    blockers = [c for c in checks if c['status'] != 'passed']
    status = 'failed' if blockers else 'passed'
    verification = dict(schema_version=1, task_id='SOL-005', task_sha256=TASK_DIGEST,
                        reviewed_commits=COMMITS, status=status, validation_exit_code=int(bool(blockers)),
                        artifact_hash_basis='canonical_git_blob', checks=checks,
                        canonical_blob_evidence=blobs, source_hashes=source_hashes,
                        reused_proof=dict(commit=PRIOR, path='audit/SOL-003/verification.json',
                                          scope='Independent deterministic source/split metadata only'),
                        limitations=LIMITS, final_outcomes_computed=False,
                        verifier_text_lf_sha256=sha(canonical_text(Path(__file__)).encode()))
    findings = dict(schema_version=1, task_id='SOL-005', reviewed_commits=COMMITS,
                    status=status, blockers=blockers, source_hashes=source_hashes,
                    passed_checks=sum(c['status'] == 'passed' for c in checks),
                    reused_proof=verification['reused_proof'], limitations=LIMITS,
                    final_data_open=False, final_outcomes_computed=False)
    expected = {'verification.json': json.dumps(verification, indent=2, sort_keys=True) + '\n',
                'findings.json': json.dumps(findings, indent=2, sort_keys=True) + '\n',
                'review.md': review_text(status, blockers)}
    mismatches = []
    for name, content in expected.items():
        path = OUT / name
        if not args.check and not path.exists():
            with path.open('x', encoding='utf-8', newline='\n') as handle:
                handle.write(content)
        if not path.exists() or canonical_text(path) != content:
            mismatches.append(name)
    for name in mismatches:
        print('Saved evidence missing or different: ' + name + '; preserved without rewriting.', file=sys.stderr)
    print(json.dumps(dict(status='failed' if blockers or mismatches else 'passed', mode='check' if args.check else 'initialize',
                          checks=len(checks), blockers=len(blockers), mismatched_files=mismatches,
                          writes=0 if args.check else 'absent evidence only', python=sys.version.split()[0],
                          numerical_experiments_rerun=False, prior_suite_rerun=False)))
    return int(bool(blockers or mismatches))

if __name__ == '__main__':
    raise SystemExit(main())
