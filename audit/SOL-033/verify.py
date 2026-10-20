"""SOL-033 format restriction review. Standard library only; --check never writes."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BASE = '65b54a5823765a676cb7c50947f7f46874484563'
TASK_SHA = '4def19be80f3c7211a1760db612d935a8810368629634483ece021814a474db6'
BINDING_SHA = '4cb27b08729e23d3108c16874cd60df0f7db2609ef7a954938b1081ecebc36ce'
PREFIX = 'report/figures/'
PUB = [PREFIX + 'baseline-h30-' + stem + ext for stem in ('summary', 'severe-path') for ext in ('.pdf', '.png')]
PREVIEW = [PREFIX + 'baseline-h30-' + stem + '.svg' for stem in ('summary', 'severe-path')]
ASSETS = PUB + PREVIEW


def sha(b):
    return hashlib.sha256(b).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def raw(p, overlay=None):
    if overlay and p in overlay:
        return overlay[p]
    return (ROOT / p).read_bytes()


def load(p, overlay=None):
    return json.loads(raw(p, overlay))


def git(*args):
    p = subprocess.run(['git', *args], cwd=ROOT, capture_output=True, check=False)
    require(p.returncode == 0, 'Git read failed: ' + ' '.join(args))
    return p.stdout


def canonical(b, expected):
    return b if sha(b) == expected else b.replace(b'\r\n', b'\n')


def words(p, overlay=None):
    return ' '.join(raw(p, overlay).decode('utf8').split())


def reconstruct(overlay=None, live=True):
    # Derive the publication decision from explicit fixed paths, suffixes, actual
    # bytes, predecessor task pins and current task pins, never from pass labels.
    tb = raw('audit/SOL-033/task-lock.json', overlay)
    require(sha(tb.strip()) == TASK_SHA, 'Exact task identity mismatch')
    t = json.loads(tb)
    require((t['id'], t['attempt'], t['owner'], t['base_commit']) == ('SOL-033', 1, 'sol', BASE), 'Task/base mismatch')
    if live and (ROOT / '.runtime/task.json').exists():
        lt = load('.runtime/task.json')
        if lt.get('id') == 'SOL-033':
            require(lt == t, 'Live task changed')
    bb = raw('audit/SOL-033/source-binding.json', overlay)
    require(sha(bb) == BINDING_SHA, 'Source binding changed')
    binding = json.loads(bb)
    require(binding['base_commit'] == BASE and binding['initial_head'] == BASE and binding['task_sha256'] == TASK_SHA, 'Source/base identity mismatch')
    require(binding['task_lock_sha256'] == sha(tb), 'Task lock bytes changed')
    mpath = PREFIX + 'publication-formats.json'
    m = load(mpath, overlay)
    require(m['schema_version'] == 1 and m['kind'] == 'report_figure_publication_format_restriction', 'Manifest kind mismatch')
    require(m['publication_paths'] == PUB, 'Publication paths must be exactly four PDF/PNG assets; SVG promotion rejected')
    require(m['editable_preview_paths'] == PREVIEW, 'Both SVG files must remain excluded previews')
    require(not set(PUB) & set(PREVIEW) and len(PUB) == 4 and len(PREVIEW) == 2, 'Asset partition mismatch')
    require(set(m['artifact_sha256']) == set(ASSETS), 'Manifest asset inventory mismatch')
    require(m['data_or_export_bytes_changed'] is False and m['full_report_acceptance'] is False, 'Manifest overclaims acceptance or changed exports')
    require(m['restriction_review_status'] == 'pending', 'Chief-owned pending status changed')
    require(m['original_review_commit'] == t['parameters']['predecessor_reviewed_commit'], 'Predecessor identity mismatch')
    old = load('ops/tasks/SOL-030.json', overlay)
    asset_facts = []
    for p in ASSETS:
        expected = old['parameters']['source_sha256'][p]
        require(t['parameters']['source_sha256'][p] == expected, 'Predecessor source pin mismatch: ' + p)
        require(m['artifact_sha256'][p] == expected, 'Manifest asset hash differs from predecessor: ' + p)
        b = raw(p, overlay)
        require(sha(b) == expected, 'Actual asset bytes changed: ' + p)
        require(sha(git('show', m['original_review_commit'] + ':' + p)) == expected, 'Exact predecessor asset differs: ' + p)
        asset_facts.append({'path': p, 'sha256': expected, 'bytes': len(b), 'publication_allowed': p in PUB})
    # Bind every pinned source and the entire prior evidence inventory to the
    # immutable base, while permitting harmless checkout CRLF on text elsewhere.
    for p, entry in binding['source'].items():
        h = entry['sha256']
        require(sha(git('show', BASE + ':' + p)) == h, 'Pinned base blob mismatch: ' + p)
        require(sha(canonical(raw(p, overlay), h)) == h, 'Source/evidence changed: ' + p)
    for p, h in t['parameters']['source_sha256'].items():
        require(binding['source'][p]['sha256'] == h, 'Task source pin mismatch: ' + p)
    readme = words(PREFIX + 'README.md', overlay)
    captions = words('report/baseline-figure-captions.md', overlay)
    rclaims = [
        'Use baseline-h30-summary.pdf and baseline-h30-severe-path.pdf for manuscript insertion, or their 300 dpi PNG counterparts.',
        'These versions were visually checked, and the PDFs embed their fonts.',
        'editable previews requiring the original DejaVu Sans font.',
        'wider fallback-font labels clipped at the summary figure edge.',
        'excluded from manuscript insertion and submission figure assets until a separate font-portability repair is reviewed.',
        'does not relabel the worker failure.',
        'Final report layout, policy outcomes and submission gates remain separate.'
    ]
    cclaims = [
        'Publication files: ' + chr(96) + 'figures/baseline-h30-summary.pdf' + chr(96) + ' and ' + chr(96) + '.png' + chr(96) + '.',
        'Publication files: ' + chr(96) + 'figures/baseline-h30-severe-path.pdf' + chr(96) + ' and ' + chr(96) + '.png' + chr(96) + ';',
        'Publication format: use the PDF exports with embedded fonts or the 300 dpi PNG exports.',
        'SVG previews depend on a locally available DejaVu Sans font.',
        'Font substitution can clip labels; SVG previews are excluded from manuscript insertion and submission figures pending a separate portability correction.',
        'check actual size again in the assembled A4 report.',
        'They do not represent new experiments, selected-policy results or final outcomes.'
    ]
    for phrase in rclaims:
        require(phrase in readme, 'README restriction wording missing: ' + phrase)
    for phrase in cclaims:
        require(phrase in captions, 'Caption restriction wording missing: ' + phrase)
    require(not re.search(r'SVG.{0,40}(now portable|is fixed|fully portable)|full (report|paper|manuscript) (is )?accepted', readme + ' ' + captions, re.I), 'Portability/full report overclaim')
    # Resolve abbreviated publication references and all local Markdown links.
    refs = []
    for stem in ('summary', 'severe-path'):
        for ext in ('.pdf', '.png'):
            p = PREFIX + 'baseline-h30-' + stem + ext
            require(p in PUB and (ROOT / p).is_file(), 'Unresolved publication reference')
            refs.append(p)
    link = re.findall(r'\[[^\]]+\]\(([^)]+)\)', raw('report/baseline-figure-captions.md', overlay).decode('utf8'))
    local_links = [x for x in link if '://' not in x]
    for x in local_links:
        require((ROOT / 'report' / x).is_file(), 'Broken local caption link: ' + x)
    require('baseline-development.md' in local_links, 'Missing saved baseline link')
    require('figures/baseline-h30-severe-points.csv' in captions, 'Missing event-table reference')
    require((ROOT / PREFIX / 'baseline-h30-severe-points.csv').is_file(), 'Missing event table')
    f = load('audit/SOL-030/findings.json', overlay)
    prior = load('audit/SOL-030/verification.json', overlay)
    receipt = load('handoff/SOL-030/result.json', overlay)
    replay = load('audit/chief/SOL-030-failed-receipt-replay.json', overlay)
    require(f['verdict'] == 'changes_required' and f['svg_review'] == 'changes_required', 'Original negative review lost')
    require('explicitly restrict publication to the verified PDF/PNG' in f['findings'][0]['required_action'], 'Restriction not a permitted F1 alternative')
    require(receipt['status'] == 'failed' and receipt['checks'][1]['exit_code'] == 1, 'Original worker failure lost')
    require('matplotlib' in f['findings'][1]['issue'] and prior['chief_renderer_check'] == 'blocked_missing_matplotlib', 'Original dependency failure lost')
    require(replay['reviewed_commit'] == m['original_review_commit'], 'Chief replay source mismatch')
    require([x['exit_code'] for x in replay['runs']] == [0, 0], 'Saved chief replay failure')
    require(replay['runs'][0]['argv'][-2:] == ['report/build_baseline_figures.py', '--check'], 'Renderer replay identity')
    require(replay['runs'][1]['argv'][-2:] == ['audit/SOL-030/verify.py', '--check'], 'Independent replay identity')
    require(len(prior['numerical']['statistics']) == 12 and len(prior['numerical']['points']) == 183, 'Original evidence scope mismatch')
    require(prior['simulation_rerun'] is False and prior['competition_inputs_read'] is False and prior['policy_or_final_approval'] is False, 'Original review scope overclaim')
    # Numeric evidence is preserved, not recomputed by this successor.
    return {'task_id': 'SOL-033', 'base_commit': BASE, 'task_sha256': TASK_SHA,
            'source_binding_sha256': BINDING_SHA, 'source_count': len(binding['source']),
            'publication_paths': PUB, 'preview_paths': PREVIEW, 'assets': asset_facts,
            'wording_facts': {'readme_required_phrases': rclaims, 'caption_required_phrases': cclaims,
                              'resolved_publication_refs': refs, 'local_caption_links': local_links},
            'predecessor_scope': {'receipt_status': receipt['status'], 'verdict': f['verdict'],
                'statistics_preserved_not_recomputed': 12, 'points_preserved_not_recomputed': 183,
                'chief_saved_replay_exit_codes': [0, 0], 'worker_renderer_exit_code': 1,
                'dependency_failure_retained': True},
            'format_restriction_resolves_F1_alternative': True,
            'svg_portability_fixed': False, 'full_report_accepted': False,
            'policy_or_final_gate_approval': False, 'simulation_or_renderer_run': False,
            'competition_input_reads': False}


def trials():
    p = PREFIX + 'publication-formats.json'
    m = load(p)
    promotion = copy.deepcopy(m)
    promotion['publication_paths'].append(PREVIEW[0])
    corruption = copy.deepcopy(m)
    corruption['artifact_sha256'][PUB[0]] = '0' * 64
    cases = [
        ('svg_promotion', {p: json.dumps(promotion).encode()}, 'Publication paths'),
        ('asset_corruption', {PUB[0]: raw(PUB[0]) + b'X'}, 'Actual asset bytes changed'),
        ('manifest_hash_corruption', {p: json.dumps(corruption).encode()}, 'Manifest asset hash'),
        ('wording_corruption', {PREFIX + 'README.md': raw(PREFIX + 'README.md').replace(b'DejaVu Sans', b'Any font')}, 'Source/evidence changed'),
        ('task_identity_corruption', {'audit/SOL-033/task-lock.json': b'{}'}, 'Exact task identity')
    ]
    results = []
    for name, overlay, expected in cases:
        try:
            reconstruct(overlay, live=False)
        except ValueError as e:
            require(expected in str(e), 'Unexpected corruption failure: ' + str(e))
            results.append({'case': name, 'rejected': True, 'error': str(e), 'overlay': 'isolated in-memory bytes; no source writes'})
        else:
            raise ValueError('Corruption accepted: ' + name)
    require(reconstruct(live=False) == reconstruct(), 'No-live-task replay differs')
    results.append({'case': 'no_live_task_or_current_HEAD_dependency', 'passed': True,
                    'method': 'live=False executes without consulting .runtime/task.json; all Git reads use exact BASE/predecessor, never HEAD'})
    return results


def inventory():
    b = load('audit/SOL-033/source-binding.json')
    names = sorted(set(b['source']) | {'audit/SOL-033/' + x for x in
        ('task-lock.json', 'source-binding.json', 'verify.py', 'findings.json', 'review.md', '.gitattributes')})
    return {p: sha(raw(p)) for p in names}


def write_new(name, obj):
    with (HERE / name).open('x', encoding='utf8', newline='\n') as fp:
        fp.write(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + '\n')


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--check', action='store_true')
    a.add_argument('--record', action='store_true')
    args = a.parse_args()
    require(args.check != args.record, 'Choose --check or initial --record')
    require(sys.version_info[:2] == (3, 12), 'Python 3.12 required')
    require(not any(k.upper() == 'PYTHONPATH' for k in os.environ), 'Remove all case-insensitive PYTHONPATH variables')
    before = inventory()
    facts = reconstruct()
    tests = trials()
    after = inventory()
    require(before == after, 'Read-only source/evidence inventory changed')
    if args.record:
        write_new('unchanged-inventories.json', {'before': before, 'after': after, 'unchanged': before == after,
                                               'scope': 'all 55 pinned source/history files and 6 initial audit files; actual checkout SHA256'})
        write_new('integrity-self-tests.json', tests)
        evidence = {p.name: sha(p.read_bytes()) for p in HERE.iterdir() if p.is_file() and p.name not in ('execution.json', 'verification.json')}
        write_new('verification.json', {'schema_version': 1, 'facts': facts, 'verifier_sha256': sha(Path(__file__).read_bytes()),
                                        'evidence_sha256': evidence})
    else:
        v = load('audit/SOL-033/verification.json')
        require(v['facts'] == facts, 'Stored facts differ from independent reconstruction')
        require(v['verifier_sha256'] == sha(Path(__file__).read_bytes()), 'Exact verifier changed')
        for name, h in v['evidence_sha256'].items():
            require(sha((HERE / name).read_bytes()) == h, 'Core evidence changed: ' + name)
        require(load('audit/SOL-033/integrity-self-tests.json') == tests, 'Corruption evidence changed')
        inv = load('audit/SOL-033/unchanged-inventories.json')
        require(inv['before'] == inv['after'] and inv['unchanged'] is True, 'Historical unchanged inventory differs')
        # Compare canonical source hashes above for portability across CRLF checkouts.
        require(all(p.stat().st_size < 10485760 for p in HERE.iterdir() if p.is_file()), 'Oversized audit artifact')
    print(json.dumps({'status': 'passed', 'read_only': bool(args.check), 'scope': 'format restriction only',
                      'publication_assets': 4, 'excluded_svg_previews': 2, 'source_pins': facts['source_count'],
                      'corruption_cases_rejected': 5, 'original_failure_retained': True,
                      'full_report_accepted': False, 'renderer_invoked': False}))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({'status': 'failed', 'error': str(exc)}), file=sys.stderr)
        sys.exit(1)
