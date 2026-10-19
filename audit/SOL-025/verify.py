"""SOL-025 synthetic replay. Explicit Git objects; no worker HEAD dependency.

Evidence is exclusively created. --check only reads and never repairs. Numeric
replay has no absolute tolerance floor, so a positive tiny fee cannot equal zero.
"""
import argparse
from fractions import Fraction as F
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'audit/SOL-025'
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tests'))
BASE = 'a065805163f01eeffd73ca0ea5ac420454493a94'
PUBLISHED = '88b4c7d921c5b3c615d4a481ac41c585a4ee11fd'
BRANCH = 'work/sol/SOL-025-a1'
TEST_MODULES = ('test_accounting', 'test_policy_pilot', 'test_policy_calibration',
                'test_policy_analysis', 'test_policy_cases')
BOOTSTRAP = ('from pathlib import Path\nimport sys\n\n'
             'sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))\n\n')


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def lf(data):
    return data.replace(b'\r\n', b'\n')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def reject_constant(value):
    raise ValueError('nonfinite JSON number: ' + value)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key: ' + key)
        result[key] = value
    return result


def load_bytes(data):
    return json.loads(data, parse_constant=reject_constant, object_pairs_hook=unique_object)


def strict(actual, expected, path='$'):
    require(type(actual) is type(expected), 'type mismatch at ' + path)
    if isinstance(expected, dict):
        require(set(actual) == set(expected), 'keys mismatch at ' + path)
        for key in expected:
            strict(actual[key], expected[key], path + '.' + key)
    elif isinstance(expected, list):
        require(len(actual) == len(expected), 'length mismatch at ' + path)
        for index, (a, b) in enumerate(zip(actual, expected)):
            strict(a, b, path + '[' + str(index) + ']')
    elif isinstance(expected, float):
        require(math.isfinite(actual) and math.isfinite(expected), 'nonfinite at ' + path)
        require(math.isclose(actual, expected, rel_tol=1e-12, abs_tol=0),
                'number mismatch at ' + path + ': ' + repr((actual, expected)))
    else:
        require(actual == expected, 'value mismatch at ' + path)


def module_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def binding_and_sources():
    binding = load_bytes((HERE / 'task-binding.json').read_bytes())
    task = binding['task']
    require((task['id'], task['attempt'], task['owner'], task['base_commit']) ==
            ('SOL-025', 1, 'sol', BASE), 'wrong immutable task identity')
    require(binding['published_commit'] == PUBLISHED, 'wrong task publication')
    require(binding['published_path'] == 'ops/tasks/SOL-025.json', 'wrong task path')
    require((binding['started_head'], binding['started_branch']) == (BASE, BRANCH), 'wrong start')
    published = git('show', PUBLISHED + ':ops/tasks/SOL-025.json')
    strict(load_bytes(published), task)
    require(sha(published) == binding['published_blob_sha256'], 'published bytes mismatch')
    require(git('rev-parse', PUBLISHED + ':ops/tasks/SOL-025.json').decode().strip() ==
            binding['published_blob_oid'], 'published Git blob mismatch')
    source_hashes, objects = {}, {}
    extra = ['src/safeinvest/__init__.py', 'src/safeinvest/policy_analysis.py']
    extra += ['tests/' + name + '.py' for name in TEST_MODULES if name != 'test_policy_cases']
    for path in dict.fromkeys([*task['parameters']['source_sha256'], *extra]):
        blob = git('show', BASE + ':' + path)
        expected = task['parameters']['source_sha256'].get(path, sha(blob))
        require(sha(blob) == expected, 'base pin mismatch: ' + path)
        require(sha(lf((ROOT/path).read_bytes())) == expected, 'checkout pin mismatch: ' + path)
        source_hashes[path] = expected
        objects[path] = git('rev-parse', BASE + ':' + path).decode().strip()
    source = (ROOT/'src/safeinvest/policy_cases.py').read_bytes()
    draft = (ROOT/'audit/chief/quarantine/SOL-023/src/safeinvest/policy_cases.py').read_bytes()
    require(source == draft, 'implementation bytes changed')
    test_draft = (ROOT/'audit/chief/quarantine/SOL-023/tests/test_policy_cases.py').read_text(encoding='utf-8')
    expected_test = test_draft.replace('from safeinvest.backtest import simulate_policy',
                                     BOOTSTRAP + 'from safeinvest.backtest import simulate_policy')
    require((ROOT/'tests/test_policy_cases.py').read_text(encoding='utf-8') == expected_test,
            'test change exceeds portable bootstrap')
    delivered = {path: sha(lf((ROOT/path).read_bytes())) for path in
                 ('src/safeinvest/policy_cases.py', 'tests/test_policy_cases.py',
                  'audit/SOL-025/verify.py', 'audit/SOL-025/task-binding.json')}
    return dict(task_id=task['id'], attempt=task['attempt'], owner=task['owner'],
                base_commit=BASE, published_task_commit=PUBLISHED,
                published_task_blob_oid=binding['published_blob_oid'],
                published_task_sha256=sha(published), local_task_raw_sha256=binding['local_task_raw_sha256'],
                local_task_lf_sha256=binding['local_task_lf_sha256'],
                task_canonical_sha256=sha(json.dumps(task, sort_keys=True, separators=(',', ':')).encode()),
                started_head=binding['started_head'], started_branch=binding['started_branch'],
                source_sha256_lf=source_hashes, base_blob_oids=objects,
                delivered_sha256_lf=delivered, implementation_identical_to_quarantine=(source == draft))


class RecordedResult(unittest.TextTestResult):
    def startTest(self, test):
        self.ids.append(test.id())
        super().startTest(test)


class Comparisons:
    def __init__(self):
        self.count = 0
        self.roundoff_fields = {}

    def eq(self, actual, expected, name='', roundoff=0):
        self.count += 1
        if type(expected) in (int, float, F) and type(expected) is not bool:
            require(type(actual) in (int, float) and math.isfinite(actual), 'invalid scalar: ' + name)
            require(math.isclose(actual, float(expected), rel_tol=1e-10, abs_tol=roundoff),
                    'independent mismatch ' + name + ': ' + repr((actual, expected)))
            if roundoff:
                self.roundoff_fields[name] = roundoff
        else:
            require(type(actual) is type(expected) and actual == expected,
                    'independent mismatch ' + name + ': ' + repr((actual, expected)))


def numeric_checks():
    from safeinvest.backtest import Decision, simulate_policy
    from safeinvest.baselines import POLICIES
    from safeinvest.policy_pilot import CENTRAL_TARGET
    import test_policy_cases as test
    reference = module_file('sol025_chief_reference', ROOT/'audit/chief/case_reference.py')
    calculated = reference.calculate()
    strict(load_bytes((ROOT/'audit/chief/case-reference.json').read_bytes()), calculated)
    facts = calculated['facts']
    c = Comparisons()
    assets = ('equity', 'bond', 'bill_proxy')
    diagnostic_names = ('human_review_count', 'human_review_share_pct', 'first_latch_year',
                        'target_change_count', 'first_deployment_year', 'initial_allocation_deferred')

    transfer_roundoff = []

    def ledger_check(actual, rational):
        for key, expected in rational.items():
            if isinstance(expected, list):
                for a, value in zip(assets, expected):
                    c.eq(actual[key+'_'+a], F(value), key+'_'+a)
            elif isinstance(expected, str):
                if key in ('intended_transfer', 'fee') and F(expected) == 0 and actual[key] != 0:
                    require(actual['mode'] == 'equal_weight_annual', 'unexpected rational-zero transfer')
                    bound = 8*math.ulp(actual['wealth_before'])
                    require(0 < actual['intended_transfer'] <= bound, 'excess binary64 transfer roundoff')
                    c.eq(actual['fee'], actual['fee_rate']*actual['intended_transfer'], 'roundoff_fee_identity')
                    if key == 'intended_transfer' and actual['scenario_id'] == 1:
                        transfer_roundoff.append({k:actual[k] for k in ('mode','fee_rate','period','wealth_before','intended_transfer','fee')})
                else:
                    c.eq(actual[key], F(expected), key)
            else:
                c.eq(actual[key], expected, key)

    def metric_check(actual, rational):
        # Rational plateaus can differ from exact binary64 earliest locations.
        # Locations are checked separately from actual binary64 wealth values.
        for key, expected in rational.items():
            if key in ('drawdown_peak', 'drawdown_trough', 'annual_real_returns', 'annual_return_sample_variance'):
                continue
            value = F(expected) if isinstance(expected, str) else expected
            c.eq(actual[key], value, key, 1e-11 if key == 'annual_real_volatility_pct' else 0)

    def locations(case, metric):
        entries = [r for r in case.annual_ledgers if r['scenario_id'] == metric['scenario_id']
                   and r['period'] <= metric['horizon']]
        values, places = [100.0], [(0, 'initial')]
        for row in entries:
            values.extend((row['real_wealth_after_fee'], row['real_wealth_end']))
            places.extend(((row['period'], 'post_fee'), (row['period'], 'end')))
        loss, j, i = min(((1-values[j]/values[i], j, i) for j in range(len(values))
                         for i in range(j+1)), key=lambda x: (-x[0], x[1], x[2]))
        c.eq(metric['max_real_drawdown_pct'], 100*loss, 'binary64_loss')
        c.eq([metric['drawdown_peak_year'], metric['drawdown_peak_kind']], list(places[i]), 'binary64_peak')
        c.eq([metric['drawdown_trough_year'], metric['drawdown_trough_kind']], list(places[j]), 'binary64_trough')

    forced = facts['two_year_forced_target_accounting_only']
    rows = [dict(zip(test.FIELDS, (1, t, *[float(F(x)) for x in values], float(F(inflation)))))
            for t, (values, inflation) in enumerate(forced['outcomes'], 1)]
    target = tuple(float(F(x)) for x in forced['targets'][0])
    result = simulate_policy(rows, horizon=2, split='synthetic',
                             callback=lambda context: Decision('rebalance', target), fee_rate=.0025)
    for entry, rational in zip(result.ledger, forced['ledger']):
        actual = {key: getattr(entry, key) for key in rational}
        for key, value in rational.items():
            if isinstance(value, list):
                for a, b in zip(actual[key], value): c.eq(a, F(b), 'forced.'+key)
            else: c.eq(actual[key], F(value) if isinstance(value, str) else value, 'forced.'+key)
    c.eq(result.ledger[-1].real_wealth_end, F('100.7400048'), 'forced_terminal')
    c.eq(result.metrics.max_real_drawdown_pct, F('16.049996'), 'forced_loss')
    c.eq(sum(e.fee for e in result.ledger), F('0.059995'), 'forced_fee')

    rows = [dict(zip(test.FIELDS, (s, t, .125, .125, .125, .25)))
            for s in range(1, 5) for t in range(1, 7)]
    cal = test.calibrate(rows)
    horizons = (2, 3, 4, 6)
    cases = []
    for mode in test.MODES:
        for fee in (.0025, .005):
            aware = mode in CENTRAL_TARGET
            out = test.tables(rows, cal, mode, fee, horizons)
            expected_counts = dict(annual_ledgers=24, scenario_metrics=16, summary=4,
                                   decisions=24 if aware else 0, target_scores=12 if aware else 0)
            c.eq(out.counts, expected_counts, 'chief.counts')
            if aware or mode == 'bills_keep':
                oracle_ledger = facts['deferred_then_latched_all_five_modes']['ledger']
                oracle_metrics = facts['deferred_then_latched_all_five_modes']['metrics']
            else:
                exact = reference.exact_path([((F(1,8),)*3, F(1,4))]*6,
                         [(F(1,3),)*3]*6 if mode == 'equal_weight_annual' else [(F(1,3),)*3]+[None]*5,
                         F(str(fee)))
                oracle_ledger = reference.encode(exact)
                oracle_metrics = reference.encode([reference.exact_metrics(exact, h) for h in horizons])
                saved = next(r for r in facts['equal_asset_reference_controls'] if F(r['fee_rate']) == F(str(fee)))
                strict(oracle_metrics, saved['annual_metrics' if mode == 'equal_weight_annual' else 'buy_hold_metrics'])
            for row in out.annual_ledgers:
                ledger_check(row, oracle_ledger[row['period']-1])
            for row in out.scenario_metrics:
                metric_check(row, oracle_metrics[horizons.index(row['horizon'])])
                locations(out, row)
                h = row['horizon']
                if aware:
                    diagnostic = next(r for r in facts['deferred_then_latched_all_five_modes']['diagnostics'] if r['horizon'] == h)
                    for key in diagnostic_names:
                        value = diagnostic[key]
                        c.eq(row[key], F(value) if isinstance(value, str) else value, 'diagnostic.'+key)
                else:
                    for key in diagnostic_names: c.eq(row[key], None, 'baseline_null.'+key)
            for row in out.decisions:
                t = row['period']
                c.eq(row['action'], facts['deferred_then_latched_all_five_modes']['actions'][t-1], 'review_action')
                c.eq(row['observed_max_drawdown_pct'], F(facts['deferred_then_latched_all_five_modes']['observed_losses_before_review'][t-1]), 'review_lag')
                c.eq(row['actual_fee'], 0, 'review_fee')
                if t >= 4:
                    for key in ('ce_keep', 'proposed_target', 'selected_target'):
                        c.eq(row[key], None, 'review_null.'+key)
                n = t-1 if mode in ('balanced_context', 'balanced_adaptive') else 0
                c.eq(row['recent_count'], n, 'recent_count')
                c.eq(row['prior_mass'], F(15,15+n), 'prior_mass')
            for row in out.target_scores:
                wanted = next(r for r in facts['identical_asset_scores']['rows'] if r['target_name'] == row['target_name'] and F(r['fee_rate']) == F(str(fee)))
                for key in ('ce_target', 'tau', 'fee_fraction', 'pre_cost_benefit', 'modeled_fee_impact', 'conservative_score', 'true_net_ce'):
                    c.eq(row[key], F(wanted[key]), 'score.'+key, 1e-14 if key == 'pre_cost_benefit' else 0)
            for row in out.summary:
                h = row['horizon']
                c.eq(row['scenario_count'], 4, 'scenario_count')
                c.eq(row['severe_scenario_id'], 1, 'severe_id')
                c.eq(row['pooled_review_count'], 4*h, 'prefix_review_count')
                c.eq(row['pooled_human_review_count'], 4*max(0,h-3) if aware else None, 'pooled_review')
                c.eq(row['pooled_human_review_share_pct'], 100*max(0,h-3)/h if aware else None, 'pooled_review_share')
                c.eq(row['pooled_target_change_count'], 0 if aware else None, 'pooled_changes')
            cases.append(dict(mode=mode, fee_rate=fee, counts=out.counts,
                              scenario_1_metrics=[{key: r[key] for key in ('horizon', 'terminal_real_wealth', 'nominal_fee_sum', 'max_real_drawdown_pct', *diagnostic_names)}
                                                  for r in out.scenario_metrics if r['scenario_id'] == 1]))
    tiny_rows = test.generated(8, kind='flat')
    for row in tiny_rows:
        if row['period'] == 1:
            for key in test.FIELDS[2:]: row[key] = -1+1e-13
    tiny = test.tables(tiny_rows, test.calibrate(tiny_rows, ((1.3,1.02,1.),)), horizons=(5,6,8))
    d, e = tiny.decisions[5], tiny.annual_ledgers[5]
    require(0 < e['intended_transfer'] < 1e-10 and e['fee'] > 0, 'missing tiny positive fee')
    c.eq(e['fee'], .0025*e['intended_transfer'], 'tiny_fee')
    c.eq(d['executed_target_change'], True, 'tiny_executed')
    c.eq(d['is_trade'], False, 'tiny_trade')
    require(not math.isclose(e['fee'], 0, rel_tol=1e-12, abs_tol=0), 'tiny equals zero')
    return dict(chief_reference_groups=calculated['reference_groups'], chief_cases=cases,
                binary64_rational_zero_transfer_roundoff=transfer_roundoff,
                independent_comparisons=c.count, explicitly_bounded_roundoff_fields=c.roundoff_fields,
                forced_scalar_facts=dict(fee_sum=sum(e.fee for e in result.ledger),
                                        terminal_real_wealth=result.ledger[-1].real_wealth_end,
                                        max_real_drawdown_pct=result.metrics.max_real_drawdown_pct),
                tiny_fee_facts={key:e[key] for key in ('intended_transfer', 'fee', 'wealth_before')},
                tiny_executed_target_change=d['executed_target_change'], tiny_is_trade=d['is_trade'])


def calculate():
    require(sys.version_info[:2] == (3, 12), 'Python 3.12 required')
    identity = binding_and_sources()
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in TEST_MODULES)
    stream = io.StringIO()
    def factory(*args):
        result = RecordedResult(*args)
        result.ids = []
        return result
    result = unittest.TextTestRunner(stream=stream, verbosity=1, resultclass=factory).run(suite)
    require(result.wasSuccessful() and not result.skipped, 'regression tests failed: ' + stream.getvalue())
    focused = [name for name in result.ids if name.startswith('test_policy_cases.')]
    require(len(focused) == 14, 'inherited tests missing')
    numeric = numeric_checks()
    imported = {}
    for name, module in sorted(sys.modules.items()):
        if name == 'safeinvest' or name.startswith('safeinvest.'):
            path = Path(module.__file__).resolve()
            relative = path.relative_to(ROOT).as_posix()
            require(relative.startswith('src/safeinvest/'), 'foreign import: ' + str(path))
            imported[name] = dict(path=relative, sha256=sha(path.read_bytes()))
    return dict(schema_version=1, identity=identity, imported_sources=imported,
                regression=dict(tests_run=result.testsRun, failures=len(result.failures),
                                errors=len(result.errors), skipped=len(result.skipped), test_ids=result.ids,
                                focused_tests=len(focused), generated_mode_fee_cases=len(sys.modules['test_policy_cases'].CaseTests.cases)),
                numeric=numeric,
                limits=dict(inputs='generated synthetic fixtures only', source_verified_case_api=False,
                            production_writer_accepted=False, final_evaluation_authorized=False,
                            policy_benefit_evaluated=False))


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true')
    group.add_argument('--create', action='store_true')
    parser.add_argument('--evidence', type=Path, default=HERE/'verification.json')
    args = parser.parse_args()
    if args.create:
        require(not args.evidence.exists(), 'exclusive create: evidence already exists')
        binding = load_bytes((HERE/'task-binding.json').read_bytes())
        require(sha((ROOT/'.runtime/task.json').read_bytes()) == binding['local_task_raw_sha256'], 'runtime task changed')
        strict(load_bytes((ROOT/'.runtime/task.json').read_bytes()), binding['task'])
        require(git('rev-parse', 'HEAD').decode().strip() == BASE, 'wrong creation base')
        require(git('branch', '--show-current').decode().strip() == BRANCH, 'wrong creation branch')
    before = args.evidence.read_bytes() if args.check else None
    saved = load_bytes(before) if args.check else None
    expected = calculate()
    if args.check:
        strict(saved, expected)
        require(args.evidence.read_bytes() == before, 'evidence bytes changed')
    else:
        with args.evidence.open('x', encoding='utf-8', newline='\n') as file:
            json.dump(expected, file, indent=2, allow_nan=False)
            file.write('\n')
    print(json.dumps(dict(task_id='SOL-025', read_only=args.check,
                          regression_tests=expected['regression']['tests_run'],
                          focused_tests=expected['regression']['focused_tests'],
                          independent_comparisons=expected['numeric']['independent_comparisons'],
                          imported_sources=expected['imported_sources'],
                          evidence_sha256=sha(args.evidence.read_bytes()))))


if __name__ == '__main__':
    main()
