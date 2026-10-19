"""SOL-004: generated synthetic fixtures only; never opens competition outcomes.

Full CLI computations run in-process against an isolated Git repository with only
the input-loader boundary replaced by an explicit synthetic LoadedInput. All
production config/source validation remains active. No actual refs are touched.
"""

from collections.abc import Mapping
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from fractions import Fraction as F
import builtins
import copy
import csv
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from safeinvest import Decision, rebalance, simulate_equal_weight, simulate_policy
from safeinvest.baselines import POLICIES
import safeinvest.experiments as ex

spec = importlib.util.spec_from_file_location("baseline_cli", ROOT / "scripts/run_development_baselines.py")
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)
CONFIG = json.loads((ROOT / ex.CONFIG_PATH).read_bytes())
AUDIT = ROOT / "audit/SOL-004"
EVIDENCE = {"label": "synthetic", "negative_probes": [], "toy_comparisons": [], "cli_invocations": []}


def fixture_rows():
    """Deterministic generated 120x30 fixture; no production input dependency."""
    return tuple(dict(scenario_id=s, period=t,
        equity_return=((s*7+t*3) % 29-14)/1000 - (.12 if (s+t) % 19 == 0 else 0),
        bond_return=((s*3+t) % 17-7)/2000,
        bill_proxy_return=((s+t) % 5)/2000,
        inflation=((s*2+t) % 11-3)/1000)
        for s in range(1, 121) for t in range(1, 31))


def toy_rows(returns, inflation=None):
    inflation = inflation if inflation is not None else [0]*len(returns)
    return [dict(scenario_id=1, period=t, equity_return=r[0], bond_return=r[1],
                 bill_proxy_return=r[2], inflation=i)
            for t, (r, i) in enumerate(zip(returns, inflation), 1)]


def rational_path(policy, returns, inflation):
    """Independent exact scalar arithmetic for expectations, no production imports."""
    holdings, cpi = [F(0), F(0), F(100)], F(1)
    entries, ends, posts, annual, previous = [], [], [], [], F(100)
    for t, (rates, inf) in enumerate(zip(returns, inflation), 1):
        wealth = sum(holdings)
        before = tuple(holdings)
        if policy == "bills_keep" or (policy == "equal_weight_buy_hold" and t > 1):
            transfer = fee = F(0)
        else:
            transfer = sum(abs(wealth/F(3) - h) for h in holdings)/2
            fee = transfer/F(400)
            holdings = [(wealth-fee)/3]*3
        post = sum(holdings)/cpi
        after = tuple(holdings)
        holdings = [h*(1+r) for h, r in zip(holdings, rates)]
        cpi *= 1+inf
        end = sum(holdings)/cpi
        annual.append(end/previous-1)
        previous = end
        posts.append(post)
        ends.append(end)
        entries.append(dict(before=before, after=after, end=tuple(holdings), cpi=cpi,
                            transfer=transfer, fee=fee, real_end=end, real_post=post))
    peak, loss = F(100), F(0)
    for post, end in zip(posts, ends):
        for value in (post, end):
            peak = max(peak, value)
            loss = max(loss, 1-value/peak)
    h = len(ends)
    mean = sum(annual)/h
    volatility = 100*math.sqrt(float(sum((r-mean)**2 for r in annual)/(h-1))) if h > 1 else None
    return entries, dict(net_real_cagr_pct=100*(float(ends[-1]/100)**(1/h)-1),
                         annual_real_volatility_pct=volatility, max_real_drawdown_pct=float(100*loss))


def snapshot(directory):
    return {str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob("*") if p.is_file()}


def invoke(args, root, loaded):
    stdout, stderr = io.StringIO(), io.StringIO()
    with patch.object(cli, "ROOT", root), patch.object(cli, "load_development", return_value=loaded), \
            redirect_stdout(stdout), redirect_stderr(stderr):
        code = cli.main(args)
    EVIDENCE["cli_invocations"].append({"args": args, "exit_code": code,
        "stdout": stdout.getvalue(), "stderr": stderr.getvalue(),
        "execution": "in-process main; isolated synthetic repository; synthetic input-loader seam"})
    return code, stdout.getvalue(), stderr.getvalue()


class BaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runtime = ROOT / ".runtime"
        runtime.mkdir(exist_ok=True)
        cls.workspace = Path(tempfile.mkdtemp(prefix="SOL-004-synthetic-", dir=runtime))
        cls.repo = cls.workspace / "repository"
        cls.repo.mkdir()
        for name in ex.SOURCE_PATHS:
            dest = cls.repo / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(ex.lf((ROOT / name).read_bytes()))
        # Archive the separate generator source in the isolated fixture commit.
        (cls.repo / "tests").mkdir()
        (cls.repo / "tests/test_development_baselines.py").write_bytes(Path(__file__).read_bytes())
        def git(*args, **kwargs):
            return subprocess.run(["git", *args], cwd=cls.repo, check=True, capture_output=True, **kwargs).stdout
        cls.git = staticmethod(git)
        git("init", "--quiet")
        git("-c", "core.autocrlf=false", "add", ".")
        tree = git("write-tree").strip().decode()
        env = dict(os.environ, GIT_AUTHOR_NAME="synthetic", GIT_AUTHOR_EMAIL="synthetic@example.invalid",
                   GIT_COMMITTER_NAME="synthetic", GIT_COMMITTER_EMAIL="synthetic@example.invalid")
        cls.sha = git("commit-tree", tree, input=b"Synthetic source fixture only\n", env=env).strip().decode()
        git("update-ref", "HEAD", cls.sha)  # Only this newly created isolated repository.
        cls.provenance = ex.source_snapshot(cls.repo, cls.sha)
        cls.rows = fixture_rows()
        cls.loaded = ex.LoadedInput(cls.rows, "synthetic", ex.digest(ex.csv_bytes(cls.rows)),
                                    "generated:tests/test_development_baselines.py:fixture_rows",
                                    ex.digest(Path(__file__).read_bytes()))
        cls.bundle = cls.workspace / "valid-synthetic-bundle"
        args = ["--config", ex.CONFIG_PATH, "--output", "../valid-synthetic-bundle"]
        code, out, err = invoke(args, cls.repo, cls.loaded)
        if code:
            raise AssertionError("synthetic CLI creation failed: " + err)
        cls.tables, cls.checks = ex.build_tables(cls.rows, CONFIG, split="synthetic")
        EVIDENCE.update(source_fixture_commit=cls.sha,
                        fixture_workspace=cls.workspace.relative_to(ROOT).as_posix(), actual_ref_changes=False,
                        output_counts={name: len(rows) for name, rows in cls.tables.items()},
                        output_hashes=ex.read_manifest(cls.bundle)["output_sha256"],
                        checks=cls.checks, schemas={name:list(rows[0]) for name, rows in cls.tables.items()})

    @classmethod
    def tearDownClass(cls):
        AUDIT.mkdir(parents=True, exist_ok=True)
        (AUDIT / "test_evidence.json").write_bytes(ex.json_bytes(EVIDENCE))

    def setUp(self):
        # Cover Path.open/read_bytes (io.open) and direct open throughout each test.
        self.real_open, self.real_io_open = builtins.open, io.open
        def guarded(original):
            def inner(file, *args, **kwargs):
                if not isinstance(file, int):
                    value = os.fspath(file).replace("\\", "/").lower()
                    if "/data/raw/" in value or "/data/final_holdout/" in value or "scenarios_121_180.csv" in value:
                        raise PermissionError("test file-open guard rejects raw/final access")
                return original(file, *args, **kwargs)
            return inner
        self.guards = [patch("builtins.open", guarded(self.real_open)), patch("io.open", guarded(self.real_io_open))]
        for guard in self.guards:
            guard.start()
            self.addCleanup(guard.stop)

    def close(self, actual, expected, name="toy"):
        residual = abs(actual-float(expected))
        self.assertLessEqual(residual, 1e-9)
        EVIDENCE["toy_comparisons"].append(dict(name=name, expected=float(expected), observed=actual,
                                                  absolute_residual=residual, tolerance=1e-9))

    def test_three_fixed_candidates_and_backward_wrapper(self):
        self.assertEqual(set(POLICIES), {"bills_keep", "equal_weight_annual", "equal_weight_buy_hold"})
        rows = self.rows[:30]
        generic = simulate_policy(rows, horizon=30, split="synthetic", callback=POLICIES["equal_weight_annual"])
        self.assertEqual(generic, simulate_equal_weight(rows, horizon=30, split="synthetic"))

    def test_all_policies_against_independent_rational_two_year_path_and_oracle(self):
        returns = [(F(1,10), F(0), F(-1,20)), (F(-1,5), F(1,10), F(0))]
        inflation = [F(1,50), F(0)]
        rows = toy_rows(returns, inflation)
        oracle = json.loads((ROOT / "audit/chief/accounting_oracle.json").read_bytes())["equal_weight_two_year"]
        for policy, callback in POLICIES.items():
            result = simulate_policy(rows, horizon=2, split="synthetic", callback=callback)
            expected, metrics = rational_path(policy, returns, inflation)
            for entry, exact in zip(result.ledger, expected):
                for key, actual in (("transfer", entry.intended_transfer), ("fee", entry.fee),
                                    ("cpi", entry.cpi_end), ("real_end", entry.real_wealth_end),
                                    ("real_post", entry.real_wealth_after_fee)):
                    self.close(actual, exact[key], policy+":"+key)
                for vector, key in ((entry.holdings_before,"before"), (entry.holdings_after_fee,"after"),
                                    (entry.holdings_end,"end")):
                    for a, b in zip(vector, exact[key]):
                        self.close(a,b,policy+":"+key)
            for key, value in metrics.items():
                self.close(getattr(result.metrics, key), value, policy+":"+key)
            if policy == "equal_weight_annual":
                self.close(result.ledger[-1].real_wealth_end, F(oracle["terminal_real_wealth"]["rational"]), "locked_oracle_terminal")
                self.close(result.metrics.net_real_cagr_pct, oracle["growth_pct_pa"], "locked_oracle_growth")
                self.close(result.metrics.annual_real_volatility_pct, oracle["volatility_pct_pa_ddof1"], "locked_oracle_volatility")

    def test_fee_before_returns_and_initial_fixtures(self):
        for target, transfer, fee, after in (((.2,0,.8),F(20),F(1,20),F(1999,20)),
                                            ((1/3,)*3,F(200,3),F(1,6),F(599,6)),
                                            ((1,0,0),F(100),F(1,4),F(399,4))):
            result = simulate_policy(toy_rows([(.1,.1,.1)]), horizon=1, split="synthetic",
                                     callback=lambda ctx: Decision("rebalance", target))
            entry = result.ledger[0]
            self.close(entry.intended_transfer, transfer)
            self.close(entry.fee, fee)
            self.close(entry.wealth_after_fee, after)
            self.close(entry.wealth_end, after*F(11,10))
        self.close(result.ledger[0].holdings_end[0], F(4389,40))

    def test_keep_exact_dollars_and_buy_hold_drift(self):
        rows = toy_rows([(.2,-.1,.01),(-.3,.2,.02),(0,0,0)])
        for policy in ("bills_keep", "equal_weight_buy_hold"):
            result = simulate_policy(rows, horizon=3, split="synthetic", callback=POLICIES[policy])
            for e in result.ledger[1:]:
                self.assertEqual(e.holdings_after_fee, e.holdings_before)
                self.assertEqual((e.fee,e.intended_transfer),(0,0))
            if policy == "equal_weight_buy_hold":
                self.assertNotEqual(result.ledger[1].holdings_before[0], result.ledger[1].holdings_before[1])

    def test_exact_compounded_inflation_and_h1_nulls(self):
        rows = toy_rows([(0,0,0),(0,0,0)], [F(1,10),F(1,5)])
        result = simulate_policy(rows, horizon=2, split="synthetic", callback=POLICIES["bills_keep"])
        self.close(result.ledger[-1].cpi_end, F(33,25))
        self.close(result.ledger[-1].real_wealth_end, F(2500,33))
        self.assertNotAlmostEqual(result.ledger[-1].real_wealth_end, 100*(1-.1-.2))
        one = ex.metric_row("bills_keep",result,1)
        self.assertIsNone(one["annual_real_volatility_pct"])
        self.assertIsNone(one["trade_share_ex_initial_pct"])
        self.assertEqual((one["later_trade_count"],one["later_review_count"]),(0,0))
        self.close(one["max_real_drawdown_pct"], F(100,11), "inflation_only_loss")

    def test_initial_post_fee_loss_then_recovery_and_zero_transfer(self):
        result = simulate_equal_weight(toy_rows([(.1,.1,.1),(0,0,0)]),horizon=2,split="synthetic")
        row = ex.metric_row("equal_weight_annual",result,2)
        self.close(row["max_real_drawdown_pct"],F(1,6))
        self.assertEqual((row["drawdown_peak_year"],row["drawdown_peak_kind"]),(0,"initial"))
        self.assertEqual((row["drawdown_trough_year"],row["drawdown_trough_kind"]),(1,"post_fee"))
        self.close(result.ledger[1].intended_transfer,0)
        self.assertEqual(row["trade_count"],1)

    def test_guarded_rows_decide_before_current_outcome_and_do_not_consume_future(self):
        decided = set()
        class Guarded(Mapping):
            def __init__(self,row): self.row=row
            def __iter__(self): return iter(self.row)
            def __len__(self): return len(self.row)
            def __getitem__(self,key):
                if key not in ("scenario_id","period") and self.row["period"] not in decided:
                    raise AssertionError("current/future outcome accessed before Decision")
                return self.row[key]
        def callback(context):
            self.assertEqual(len(context.history),context.period-1)
            self.assertEqual([o.period for o in context.history],list(range(1,context.period)))
            self.assertIsInstance(context.history,tuple)
            self.assertIsInstance(context.holdings,tuple)
            decided.add(context.period)
            return Decision("keep")
        rows = [Guarded(r) for r in self.rows[:30]]
        result = simulate_policy(rows,horizon=5,split="synthetic",callback=callback)
        self.assertEqual(decided,set(range(1,6)))
        self.assertEqual(len(result.ledger),5)

    def test_prefixes_batch_and_year10_perturbation_actual_checks(self):
        for key,count in (("prefix_rerun",45),("single_scenario_batch",45),
                          ("no_lookahead_decisions",9),("no_lookahead_states",9)):
            self.assertEqual(self.checks["checks"][key]["count"],count)
            self.assertEqual(self.checks["checks"][key]["failures"],0)
        # Also test a callback that actually uses the prefix, rather than fixed actions.
        def adaptive(ctx):
            return Decision("rebalance", (1,0,0)) if ctx.history and ctx.history[-1].returns[0] > 0 else Decision("keep")
        original = list(self.rows[:30])
        changed = copy.deepcopy(original)
        for row in changed[9:]:
            row.update(equity_return=-.8,inflation=.5)
        a=simulate_policy(original,horizon=30,split="synthetic",callback=adaptive)
        b=simulate_policy(changed,horizon=30,split="synthetic",callback=adaptive)
        self.assertEqual(a.ledger[:9],b.ledger[:9])
        self.assertEqual(a.ledger[9].holdings_before,b.ledger[9].holdings_before)
        self.assertEqual([e.decision for e in a.ledger[:10]],[e.decision for e in b.ledger[:10]])

    def test_drawdown_earliest_repeated_and_zero_loss_locations(self):
        base=simulate_equal_weight(toy_rows([(0,0,0)]*3),horizon=3,split="synthetic").ledger
        entries=[replace(base[0],real_wealth_after_fee=120,real_wealth_end=120),
                 replace(base[1],real_wealth_after_fee=90,real_wealth_end=90),
                 replace(base[2],real_wealth_after_fee=120,real_wealth_end=90)]
        selected=ex.drawdown_locations(entries)
        self.assertEqual(selected,dict(drawdown_peak_year=1,drawdown_peak_kind="post_fee",
                                       drawdown_trough_year=2,drawdown_trough_kind="post_fee"))
        entries=[replace(e,real_wealth_after_fee=100+e.period,real_wealth_end=101+e.period) for e in base]
        self.assertEqual(ex.drawdown_locations(entries),dict(drawdown_peak_year=0,drawdown_peak_kind="initial",
                                                            drawdown_trough_year=0,drawdown_trough_kind="initial"))

    def test_quantiles_exact_severe_ties_and_pooled_denominators(self):
        rows=copy.deepcopy(self.tables["scenario_metrics.csv"][:4])
        for index,row in enumerate(rows):
            row.update(scenario_id=index+1,net_real_cagr_pct=index*10,max_real_drawdown_pct=20,
                       trade_count=index,review_count=5,later_trade_count=index,later_review_count=4)
        summary=ex.summary_row("bills_keep",5,list(reversed(rows)))
        self.close(summary["p10_growth_pct"],F(3),"linear_p10")
        self.close(summary["median_growth_pct"],F(15),"linear_median")
        self.assertEqual(summary["severe_scenario_id"],1)
        rows[3]["max_real_drawdown_pct"]=math.nextafter(20,math.inf)
        self.assertEqual(ex.summary_row("bills_keep",5,rows)["severe_scenario_id"],4)
        self.assertEqual(summary["pooled_review_count"],20)
        self.assertEqual(summary["pooled_later_review_count"],16)
        self.assertEqual(summary["pooled_trade_share_pct"],30)
        self.assertEqual(summary["pooled_trade_share_ex_initial_pct"],37.5)
        self.assertTrue(all(r["pooled_review_count"] == 120*r["horizon"] and
                            r["pooled_later_review_count"] == 120*(r["horizon"]-1)
                            for r in self.tables["summary.csv"]))

    def test_paired_signs_units_and_reference_identity(self):
        reference=dict(split="synthetic",policy="equal_weight_annual",scenario_id=1,horizon=5,
                       **{k:10 for k in ex.METRIC_VALUES})
        alternative=dict(reference,policy="bills_keep",**{k:12 for k in ex.METRIC_VALUES})
        row=ex.paired_row(alternative,reference)
        self.assertTrue(all(row[k+"_difference"]==2 for k in ex.METRIC_VALUES))
        self.assertEqual(row["reference_policy"],"equal_weight_annual")
        self.assertIn("positive is worse",row["loss_difference_units"])
        self.assertIn("percentage points",row["trade_share_difference_units"])
        with self.assertRaises(ValueError): ex.paired_row(dict(alternative,scenario_id=2),reference)

    def test_counts_keys_finite_units_deterministic_lf_and_labels(self):
        self.assertEqual({k:len(v) for k,v in self.tables.items()},ex.COUNTS)
        for name,rows in self.tables.items():
            self.assertTrue(all(r["split"]=="synthetic" for r in rows))
            self.assertTrue(any(k.endswith("units") for k in rows[0]))
            data=(self.bundle/name).read_bytes()
            self.assertNotIn(b"\r",data)
            self.assertEqual(data,ex.csv_bytes(rows))
            self.assertTrue(all(not isinstance(value,float) or math.isfinite(value) for r in rows for value in r.values()))
        self.assertEqual(ex.read_manifest(self.bundle)["input"]["fixture"],True)

    def test_saved_valid_bundle_cli_check_is_read_only(self):
        before=snapshot(self.bundle)
        with patch.object(Path,"write_bytes",side_effect=AssertionError("--check attempted write")), \
                patch.object(Path,"write_text",side_effect=AssertionError("--check attempted write")):
            code,out,err=invoke(["--config",ex.CONFIG_PATH,"--output","../valid-synthetic-bundle","--check"],self.repo,self.loaded)
        self.assertEqual(code,0,err)
        self.assertEqual(before,snapshot(self.bundle))
        self.assertIn('"read_only": true',out)

    def corrupt_probe(self,name,mutate):
        directory=self.workspace/("corrupt-"+name)
        if directory.exists(): shutil.rmtree(directory)
        shutil.copytree(self.bundle,directory)
        mutate(directory)
        before=snapshot(directory)
        code,out,err=invoke(["--config",ex.CONFIG_PATH,"--output","../"+directory.name,"--check"],self.repo,self.loaded)
        self.assertEqual(code,1,name)
        self.assertEqual(before,snapshot(directory),name+" modified evidence")
        EVIDENCE["negative_probes"].append(dict(name=name,exit_code=code,diagnosis=err.strip(),
            unchanged=True,before_hashes={k:ex.digest(v) for k,v in before.items()}))

    def test_corrupt_output_hash_is_rejected_without_repair(self):
        self.corrupt_probe("hash",lambda d:(d/"summary.csv").write_bytes((d/"summary.csv").read_bytes()+b"x"))

    def test_missing_output_is_rejected_without_repair(self):
        self.corrupt_probe("missing",lambda d:(d/"scenario_metrics.csv").unlink())

    def test_missing_rows_even_with_rehashed_manifest_are_rejected(self):
        def mutate(d):
            p=d/"annual_ledgers.csv"
            p.write_bytes(b"\n".join(p.read_bytes().split(b"\n")[:-2])+b"\n")
            m=ex.read_manifest(d)
            m["output_sha256"][p.name]=ex.digest(p.read_bytes())
            (d/"run_manifest.json").write_bytes(ex.json_bytes(m))
        self.corrupt_probe("missing-row-rehashed",mutate)

    def test_numeric_corruption_even_with_rehashed_manifest_is_rejected(self):
        def mutate(d):
            p=d/"paired_differences.csv"
            rows=list(csv.DictReader(io.StringIO(p.read_text(encoding="utf-8"))))
            rows[0]["max_real_drawdown_pct_difference"]="999.0"
            p.write_bytes(ex.csv_bytes(rows))
            m=ex.read_manifest(d)
            m["output_sha256"][p.name]=ex.digest(p.read_bytes())
            (d/"run_manifest.json").write_bytes(ex.json_bytes(m))
        self.corrupt_probe("numeric-rehashed",mutate)

    def test_invalid_manifest_is_rejected_without_repair(self):
        self.corrupt_probe("manifest-json",lambda d:(d/"run_manifest.json").write_bytes(b"{invalid\n"))

    def test_missing_manifest_metadata_is_rejected_without_repair(self):
        def mutate(d):
            m=ex.read_manifest(d)
            del m["command"]
            (d/"run_manifest.json").write_bytes(ex.json_bytes(m))
        self.corrupt_probe("missing-manifest-metadata",mutate)

    def test_forged_consumed_source_hash_is_rejected_without_repair(self):
        def mutate(d):
            m=ex.read_manifest(d)
            m["consumed_source_sha256"]["src/safeinvest/baselines.py"]="0"*64
            (d/"run_manifest.json").write_bytes(ex.json_bytes(m))
        self.corrupt_probe("forged-consumed-source-hash",mutate)

    def test_nonempty_output_is_refused_and_preserved(self):
        before=snapshot(self.bundle)
        with self.assertRaisesRegex(ValueError,"nonempty"):
            ex.produce_bundle(self.loaded,CONFIG,self.bundle,self.provenance,command=["synthetic"])
        self.assertEqual(before,snapshot(self.bundle))

    def test_failure_after_directory_creation_keeps_failed_manifest(self):
        bad=ex.LoadedInput(self.rows[:-1],"synthetic","0"*64,"generated-invalid")
        directory=self.workspace/"failed-incomplete-fixture"
        with self.assertRaisesRegex(ValueError,"3600"):
            ex.produce_bundle(bad,CONFIG,directory,self.provenance,command=["synthetic-negative"])
        manifest=ex.read_manifest(directory)
        self.assertEqual(manifest["status"],"failed")
        self.assertEqual(set(p.name for p in directory.iterdir()),{"run_manifest.json"})
        EVIDENCE["negative_probes"].append(dict(name="failed-new-run",exit_code=1,manifest=manifest))

    def test_config_is_frozen_and_invalid_policy_split_horizon_are_rejected(self):
        for change in ({"split":"final"},{"fee_rate":.005},{"initial_holdings":[100,0,0]},
                       {"horizons":[1,30]},{"policies":[{"id":"unknown"}]}):
            changed=copy.deepcopy(CONFIG)
            changed.update(change)
            with self.assertRaises(ValueError): ex.build_tables(self.rows,changed,split="synthetic")
        target=self.repo/ex.CONFIG_PATH
        original=target.read_bytes()
        try:
            target.write_bytes(ex.json_bytes(dict(CONFIG,split="final")))
            with self.assertRaisesRegex(ValueError,"configuration bytes changed"): ex.load_config(self.repo,ex.CONFIG_PATH)
        finally: target.write_bytes(original)
        with self.assertRaises(ValueError): ex.load_config(self.repo,"wrong-config.json")
        with self.assertRaises(ValueError): ex.build_tables(self.rows,CONFIG,split="final")

    def test_complete_keys_ids_schema_numeric_domains_rejected(self):
        for kind in ("duplicate","id121","unordered","schema","nan","minusone","missing"):
            rows=[dict(r) for r in self.rows]
            if kind=="duplicate": rows[1]=dict(rows[0])
            if kind=="id121": rows[-1]["scenario_id"]=121
            if kind=="unordered": rows[0],rows[1]=rows[1],rows[0]
            if kind=="schema": rows[0]["extra"]=1
            if kind=="nan": rows[0]["inflation"]=float("nan")
            if kind=="minusone": rows[0]["equity_return"]=-1
            if kind=="missing": rows.pop()
            with self.subTest(kind=kind),self.assertRaises(ValueError): ex.validate_rows(rows)
            EVIDENCE["negative_probes"].append(dict(name="input-"+kind,rejected=True))

    def test_loader_frozen_path_hash_and_explicit_file_open_guard(self):
        for name in ("data/raw/SafeInvest_Synthetic_Data.csv","data/final_holdout/scenarios_121_180.csv"):
            with self.assertRaisesRegex(ValueError,"frozen"):
                ex.load_development(self.repo,dict(CONFIG,input_path=name))
            with self.assertRaisesRegex(PermissionError,"file-open guard"):
                (self.repo/name).read_bytes()
            with self.assertRaisesRegex(PermissionError,"file-open guard"):
                builtins.open(self.repo/name,"rb")
        for changed in (dict(CONFIG,input_sha256="0"*64),dict(CONFIG,split="final")):
            with self.assertRaisesRegex(ValueError,"frozen"): ex.load_development(self.repo,changed)
        target=self.repo/ex.INPUT_PATH
        target.parent.mkdir(parents=True,exist_ok=True)
        fixture=ex.csv_bytes(self.rows)
        target.write_bytes(fixture)
        with self.assertRaisesRegex(ValueError,"SHA256 mismatch"): ex.load_development(self.repo,CONFIG)
        # Unit-only loader fixture: explicit hash seam, never a production override.
        with patch.object(ex,"INPUT_SHA256",ex.digest(fixture)):
            loaded=ex.load_development(self.repo,dict(CONFIG,input_sha256=ex.digest(fixture)))
            self.assertEqual(len(loaded.rows),3600)
            target.write_bytes(fixture+b"x")
            with self.assertRaisesRegex(ValueError,"SHA256 mismatch"):
                ex.load_development(self.repo,dict(CONFIG,input_sha256=ex.digest(fixture)))
        EVIDENCE["negative_probes"].append(dict(name="raw-final-open-guard",intentional_rejections=4,
            production_alternate_paths_rejected_before_open=True,frozen_hash_rejected=True))

    def test_provenance_rejects_changed_source_and_config_but_allows_advanced_head(self):
        for name in ("src/safeinvest/baselines.py",ex.CONFIG_PATH):
            p=self.repo/name
            before=p.read_bytes()
            try:
                p.write_bytes(before+b" ")
                with self.assertRaisesRegex(ValueError,"changed production source/config"):
                    ex.source_snapshot(self.repo,self.sha)
            finally: p.write_bytes(before)
        # Actual checkout remains untouched. Only the isolated fixture HEAD advances.
        old=self.git("rev-parse","HEAD").strip().decode()
        tree=self.git("rev-parse",old+"^{tree}").strip().decode()
        env=dict(os.environ,GIT_AUTHOR_NAME="synthetic",GIT_AUTHOR_EMAIL="synthetic@example.invalid",
                 GIT_COMMITTER_NAME="synthetic",GIT_COMMITTER_EMAIL="synthetic@example.invalid")
        new=self.git("commit-tree",tree,"-p",old,input=b"Unrelated synthetic history advance\n",env=env).strip().decode()
        self.git("update-ref","HEAD",new)
        try:
            code,out,err=invoke(["--config",ex.CONFIG_PATH,"--output","../valid-synthetic-bundle","--check"],self.repo,self.loaded)
            self.assertEqual(code,0,err)
            self.assertEqual(ex.read_manifest(self.bundle)["source_commit"],self.sha)
        finally: self.git("update-ref","HEAD",old)
        EVIDENCE["negative_probes"].append(dict(name="changed-source-config",rejected=True,
                                                saved_sha_check_after_head_advance=True))

    def test_source_lf_crlf_hashes_and_consumed_bytes_are_distinct(self):
        p=self.repo/"src/safeinvest/baselines.py"
        before=p.read_bytes()
        try:
            p.write_bytes(before.replace(b"\n",b"\r\n"))
            snap=ex.source_snapshot(self.repo,self.sha)
            name="src/safeinvest/baselines.py"
            self.assertEqual(snap["canonical_git_sources"],self.provenance["canonical_git_sources"])
            self.assertNotEqual(snap["consumed_source_sha256"][name],self.provenance["consumed_source_sha256"][name])
        finally: p.write_bytes(before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
