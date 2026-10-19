"""Render descriptive tables from accepted HY3-003 blobs; never simulate a run."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
COMMIT = '7652410d73425371110784ef5fa97c03470a074e'
REVIEW = '818af5d65bd8a271962d848dd552bd39ca561f68'
SOURCE = 'results/development/HY3-003/summary.csv'
LABELS = {
    'bills_keep': 'Bills held',
    'equal_weight_annual': 'Annual thirds',
    'equal_weight_buy_hold': 'Initial thirds held',
}


def build():
    queue = json.loads((ROOT / 'ops/queue.json').read_bytes())
    for task, commit in [('HY3-003', COMMIT), ('SOL-008', REVIEW)]:
        item = next(x for x in queue['tasks'] if x['id'] == task)
        assert item['state'] == 'accepted' and item['reviewed_commit'] == commit
    blob = subprocess.check_output(['git', 'show', COMMIT + ':' + SOURCE], cwd=ROOT)
    receipt = json.loads((ROOT / 'handoff/HY3-003/result.json').read_bytes())
    source_hash = hashlib.sha256(blob).hexdigest()
    assert source_hash == receipt['artifacts_sha256'][SOURCE]
    assert (ROOT / SOURCE).read_bytes() == blob
    rows = list(csv.DictReader(io.StringIO(blob.decode())))
    assert len(rows) == 15
    assert {(r['policy'], int(r['horizon'])) for r in rows} == {
        (p, h) for p in LABELS for h in (5, 6, 15, 25, 30)}
    assert all(r['split'] == 'development' and r['scenario_count'] == '120' for r in rows)
    rows.sort(key=lambda r: (int(r['horizon']), list(LABELS).index(r['policy'])))
    lines = [
        '# Accepted development baseline evidence', '',
        'This research note uses 120 original synthetic scenarios (IDs 1–120), '
        'with annual simple returns and initial wealth 100 in bills. It reports '
        'three predeclared references at five horizons. It is descriptive '
        'development evidence, not a final test, a suitability assignment, or '
        'evidence that automatic target changes add value.', '',
        'The one-way transfer fee is 0.25%, including initial allocation, paid '
        'before annual returns. Purchasing power uses exact compounded inflation. '
        'Each horizon uses its own prefix. A/B/C/D/E have horizons 5/15/30/25/6; '
        'the general policy comparison uses 30 years.', '',
        'Annual thirds restores equal weights at every annual review. Initial '
        'thirds held pays for its initial allocation, then keeps component dollars '
        'at reviews while returns change their values. Bills held never transfers. '
        'No reference has a human-review overlay.', '',
        'Growth is real CAGR (% per year). Loss is maximum decline from the running '
        'real wealth peak (%), including initial wealth and post-fee observations. '
        'The p10 and p90 are linear scenario quantiles, not confidence bounds. '
        'All display values below are rounded to two decimals; source values retain '
        'full precision.', '',
        '| Horizon | Reference | Median growth | p10 growth | Median loss | p90 loss | Trades incl. initial (%) | Trades later (%) |',
        '| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |',
    ]
    columns = ['median_growth_pct', 'p10_growth_pct', 'median_loss_pct', 'p90_loss_pct',
               'pooled_trade_share_pct', 'pooled_trade_share_ex_initial_pct']
    for r in rows:
        lines.append('| ' + ' | '.join([r['horizon'], LABELS[r['policy']],
                     *(f'{float(r[c]):.2f}' for c in columns)]) + ' |')
    lines += ['', 'Ordinary fluctuation is the sample standard deviation of annual '
              'net real wealth returns (percentage points, ddof=1). Each severe case '
              'below is that reference’s own largest loss at that horizon, with '
              'the prescribed exact tie rule. The same scenario number across '
              'references does not imply equal paths or peak/trough locations.', '',
              '| Horizon | Reference | Median fluctuation | Median fee sum (nominal) | Severe scenario | Severe loss (%) | Real peak (year, stage) | Real trough (year, stage) |',
              '| ---: | --- | ---: | ---: | ---: | ---: | --- | --- |']
    for r in rows:
        lines.append('| ' + ' | '.join([
            r['horizon'], LABELS[r['policy']],
            f"{float(r['median_volatility_pct']):.2f}",
            f"{float(r['median_nominal_fee_sum']):.2f}", r['severe_scenario_id'],
            f"{float(r['severe_max_real_drawdown_pct']):.2f}",
            r['severe_drawdown_peak_year'] + ', ' + r['severe_drawdown_peak_kind'],
            r['severe_drawdown_trough_year'] + ', ' + r['severe_drawdown_trough_kind'],
        ]) + ' |')
    common = {r['policy']: r for r in rows if r['horizon'] == '30'}
    annual = common['equal_weight_annual']
    held = common['equal_weight_buy_hold']
    bills = common['bills_keep']
    lines += ['',
        f"At 30 years, annual thirds has median real growth {float(annual['median_growth_pct']):.2f}% "
        f"and p90 loss {float(annual['p90_loss_pct']):.2f}%; initial thirds held has "
        f"{float(held['median_growth_pct']):.2f}% and {float(held['p90_loss_pct']):.2f}%, respectively. "
        'Their comparison changes both allocation drift and fees, so it does not '
        'isolate a causal fee effect. Differences of marginal medians are not '
        'median paired differences; the accepted paired_differences.csv retains '
        'all 1,200 scenario/horizon contrasts.', '',
        f"Bills held has a 30-year p90 real loss of {float(bills['p90_loss_pct']):.2f}% "
        f"and a severe loss of {float(bills['severe_max_real_drawdown_pct']):.2f}%. "
        'Keeping nominal bills therefore does not eliminate purchasing-power loss '
        'in these supplied scenarios. These observations alone do not establish '
        'which menu suits any customer.', '',
        'All-development baseline summaries were viewed before the policy pilot '
        'design. Later four-fold policy experiments remain development evidence, '
        'even though each fitted prior excludes its evaluated fold. No new policy '
        'has yet produced accepted outcomes. Scenarios 121–180 remain closed until '
        'the recorded final freeze.', '',
        f'Source: `{SOURCE}` at `{COMMIT}`, SHA256 `{source_hash}`. '
        f'Independent review: SOL-008 at `{REVIEW}`; chief acceptance: '
        '`audit/chief/HY3-003-review.json` and `audit/chief/SOL-008-review.json`. '
        'This note imports existing accepted artifacts and does not rerun the experiment.', '',
    ]
    note = '\n'.join(lines).encode()
    provenance = {
        'schema_version': 1, 'kind': 'accepted_development_descriptive_tables',
        'source_commit': COMMIT, 'source_path': SOURCE, 'source_sha256': source_hash,
        'independent_review_commit': REVIEW, 'fee_rate': .0025,
        'split': 'development', 'scenario_ids': [1, 120], 'scenario_count': 120,
        'display_decimals': 2, 'row_keys': ['policy', 'horizon'],
        'source_rows': rows, 'final_outcomes_read': False,
        'simulation_rerun': False, 'note_sha256': hashlib.sha256(note).hexdigest(),
        'generator_sha256': hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n')).hexdigest(),
    }
    return {'baseline-development.md': note,
            'baseline-development-provenance.json': (json.dumps(provenance, indent=2) + '\n').encode()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    for name, raw in build().items():
        path = ROOT / 'report' / name
        if args.check or path.exists():
            assert path.read_bytes().replace(b'\r\n', b'\n') == raw, name
        else:
            path.write_bytes(raw)
    print(json.dumps({'status': 'passed', 'read_only': args.check, 'summary_rows': 15,
                      'source_commit': COMMIT, 'simulation_rerun': False}))


if __name__ == '__main__':
    main()
