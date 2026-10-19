"""Fixed development pilot: stdlib computation, strict input and saved-evidence checks.

The production loader is the only CSV input boundary. Unit callers pass explicit
synthetic rows to build_tables/produce_bundle; fixture generation lives in tests.
Accounting is delegated to the accepted engine. Scalar formulas below are audit
checks, never an alternative trading or accounting implementation.
"""

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

from .accounting import rebalance
from .backtest import RETURN_FIELDS, TRADE_THRESHOLD, simulate_policy, simulate_equal_weight
from .baselines import POLICIES
from .metrics import compute_metrics, linear_quantile

CONFIG_PATH = "specs/development_baselines_v1_1.json"
CONFIG_SHA256 = "3e26809be9822e8a0dd1c0a89ccfdff09b51e03079a9aaaf025b4762e3863224"
EFFECTIVE_CONFIG_SHA256 = "b6a64187aeb82c0a56f4da6979b32cb1a1474418526e2905d67af35e2f40bd0f"
INPUT_PATH = "data/development/scenarios_001_120.csv"
INPUT_SHA256 = "9c4ad83f5dda86251a754e126528a71dd930ae88ed7cdb8a0663a327b6bfb7c7"
FIELDS = ("scenario_id", "period", *RETURN_FIELDS, "inflation")
HORIZONS = (5, 6, 15, 25, 30)
COUNTS = {"annual_ledgers.csv": 10800, "scenario_metrics.csv": 1800,
          "summary.csv": 15, "paired_differences.csv": 1200}
SOURCE_PATHS = (
    "src/safeinvest/__init__.py", "src/safeinvest/accounting.py",
    "src/safeinvest/backtest.py", "src/safeinvest/metrics.py",
    "src/safeinvest/baselines.py", "src/safeinvest/experiments.py",
    "scripts/run_development_baselines.py", CONFIG_PATH,
    "specs/ACCOUNTING.md", "specs/PROBLEM_LOCK.md",
    "specs/DEVELOPMENT_BASELINES.md", "specs/DEVELOPMENT_BASELINE_DRIVER.md",
    "audit/chief/accounting_oracle.json",
)
COMMON_UNITS = {
    "monetary_units": "nominal units; real wealth in CPI_0 purchasing power",
    "return_units": "annual simple decimal",
    "cpi_units": "price index; CPI_0=1",
    "growth_units": "percentage points per year",
    "volatility_units": "percentage points; annual sample ddof=1",
    "loss_units": "percent of running real peak",
    "trade_share_units": "percent of annual reviews",
}
PAIRED_UNITS = {
    "growth_difference_units": "percentage points per year",
    "loss_difference_units": "percentage points; positive is worse",
    "terminal_real_wealth_difference_units": "CPI_0 purchasing-power units",
    "nominal_fee_difference_units": "nominal units",
    "trade_share_difference_units": "percentage points",
}
METRIC_VALUES = ("net_real_cagr_pct", "max_real_drawdown_pct", "terminal_real_wealth",
                 "nominal_fee_sum", "trade_share_pct", "trade_share_ex_initial_pct")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def lf(data):
    return data.replace(b"\r\n", b"\n")


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def csv_bytes(rows):
    if not rows:
        raise ValueError("empty table")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def load_config(root, config_path):
    root = Path(root).resolve()
    expected = root / CONFIG_PATH
    supplied = Path(config_path)
    supplied = supplied if supplied.is_absolute() else root / supplied
    if supplied.resolve() != expected or expected.is_symlink():
        raise ValueError("only the fixed v1.1 config path is allowed")
    data = expected.read_bytes()
    if digest(lf(data)) != CONFIG_SHA256:
        raise ValueError("fixed v1.1 configuration bytes changed")
    config = json.loads(data)
    # The canonical config digest freezes every field, including descriptive rules.
    if (config["input_path"] != INPUT_PATH or config["input_sha256"] != INPUT_SHA256
            or config["split"] != "development"):
        raise ValueError("fixed development input contract changed")
    return config


def validate_rows(rows):
    rows = tuple(rows)
    if len(rows) != 3600:
        raise ValueError("expected exactly 3600 input rows")
    for index, row in enumerate(rows):
        if tuple(row) != FIELDS:
            raise ValueError("input requires the exact ordered six-field schema")
        scenario, period = divmod(index, 30)
        for field, expected in (("scenario_id", scenario + 1), ("period", period + 1)):
            value = row[field]
            if isinstance(value, bool) or str(value) != str(expected):
                raise ValueError("input keys must be complete, unique, ordered IDs 1..120/years 1..30")
        for field in FIELDS[2:]:
            value = row[field]
            if isinstance(value, bool):
                raise ValueError("boolean outcome")
            number = float(value)
            if not math.isfinite(number) or number <= -1:
                raise ValueError("outcomes require finite positive gross factors")
    return rows


@dataclass(frozen=True)
class LoadedInput:
    rows: tuple
    split: str
    sha256: str
    origin: str
    fixture_generator_sha256: str | None = None


def load_development(root, config):
    # Guard path/hash before opening; never follow a configured alternate path.
    if (config.get("input_path") != INPUT_PATH or config.get("input_sha256") != INPUT_SHA256
            or config.get("split") != "development"):
        raise ValueError("frozen development path/hash/split required")
    root = Path(root).resolve()
    target = root / INPUT_PATH
    if target.resolve() != target or any(p.is_symlink() for p in (target, target.parent, target.parent.parent)):
        raise ValueError("development input may not escape via symlinks")
    data = target.read_bytes()
    if digest(data) != INPUT_SHA256:
        raise ValueError("development input SHA256 mismatch")
    reader = csv.DictReader(io.StringIO(data.decode("utf-8"), newline=""))
    if tuple(reader.fieldnames or ()) != FIELDS:
        raise ValueError("development input schema mismatch")
    return LoadedInput(validate_rows(reader), "development", digest(data), INPUT_PATH)


def git(root, *args):
    result = subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
    return result.stdout


def source_snapshot(root, source_commit=None):
    """Compare explicit Git objects, never require a worker branch or old HEAD.

    LF/CRLF translations are permitted and recorded separately. Other changed
    bytes fail even when the working tree is marked clean by local Git settings.
    """
    root = Path(root)
    sha = source_commit or git(root, "rev-parse", "HEAD").decode().strip()
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("source commit must be an explicit full Git SHA")
    if git(root, "cat-file", "-t", sha).strip() != b"commit":
        raise ValueError("source SHA is not a commit")
    canonical, consumed = {}, {}
    for name in SOURCE_PATHS:
        blob = git(root, "show", sha + ":" + name)
        actual = (root / name).read_bytes()
        if actual not in (blob, blob.replace(b"\n", b"\r\n")):
            raise ValueError("changed production source/config relative to source SHA: " + name)
        canonical[name] = {"sha256": digest(blob),
                           "git_blob_sha1": digest_git_blob(blob),
                           "crlf_checkout_sha256": digest(blob.replace(b"\n", b"\r\n"))}
        consumed[name] = digest(actual)
    # Bind executed modules too, rather than trusting a caller-supplied root copy.
    package = Path(__file__).resolve().parent
    for name in SOURCE_PATHS:
        if name.startswith("src/safeinvest/"):
            if digest(lf((package / Path(name).name).read_bytes())) != canonical[name]["sha256"]:
                raise ValueError("loaded module differs from recorded source: " + name)
    return {"source_commit": sha, "canonical_git_sources": canonical,
            "consumed_source_sha256": consumed}


def digest_git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def drawdown_locations(ledger):
    peak = 100.0
    peak_at = selected_peak = selected_trough = (0, "initial")
    loss = 0.0
    for entry in ledger:
        for kind, value in (("post_fee", entry.real_wealth_after_fee), ("end", entry.real_wealth_end)):
            if value > peak:
                peak, peak_at = value, (entry.period, kind)
            current = 1.0 - value / peak
            if current > loss:
                loss, selected_peak, selected_trough = current, peak_at, (entry.period, kind)
    return {"drawdown_peak_year": selected_peak[0], "drawdown_peak_kind": selected_peak[1],
            "drawdown_trough_year": selected_trough[0], "drawdown_trough_kind": selected_trough[1]}


def ledger_row(policy, split, entry):
    row = {"split": split, "policy": policy, "scenario_id": entry.scenario_id,
           "year": entry.period, "action": entry.decision.action}
    for prefix, vector in (("target", entry.decision.target), ("holdings_before", entry.holdings_before),
                           ("holdings_after_fee", entry.holdings_after_fee), ("holdings_end", entry.holdings_end),
                           ("return", entry.returns)):
        for index, asset in enumerate(("equity", "bond", "bill_proxy")):
            row[prefix + "_" + asset] = "" if vector is None else vector[index]
    for name in ("wealth_before", "cpi_before", "real_wealth_before", "intended_transfer", "fee",
                 "wealth_after_fee", "real_wealth_after_fee", "inflation", "wealth_end", "cpi_end",
                 "real_wealth_end", "annual_net_real_return"):
        row[name] = getattr(entry, name)
    return row | COMMON_UNITS


def metric_row(policy, result, horizon):
    if isinstance(horizon, bool) or not isinstance(horizon, int) or not 1 <= horizon <= len(result.ledger):
        raise ValueError("horizon must select a nonempty ledger prefix")
    ledger = result.ledger[:horizon]
    metric = compute_metrics([e.real_wealth_end for e in ledger],
                             [e.real_wealth_after_fee for e in ledger], split=result.split)
    trades = [e.intended_transfer > TRADE_THRESHOLD for e in ledger]
    later_count = sum(trades[1:])
    return {"split": result.split, "policy": policy, "scenario_id": result.scenario_id, "horizon": horizon,
            "net_real_cagr_pct": metric.net_real_cagr_pct,
            "annual_real_volatility_pct": metric.annual_real_volatility_pct,
            "max_real_drawdown_pct": metric.max_real_drawdown_pct,
            "terminal_real_wealth": ledger[-1].real_wealth_end,
            "nominal_fee_sum": math.fsum(e.fee for e in ledger),
            "trade_count": sum(trades), "review_count": horizon,
            "later_trade_count": later_count, "later_review_count": horizon - 1,
            "trade_share_pct": 100.0 * sum(trades) / horizon,
            "trade_share_ex_initial_pct": 100.0 * later_count / (horizon - 1) if horizon > 1 else None,
            **drawdown_locations(ledger), **COMMON_UNITS}


def summary_row(policy, horizon, rows):
    severe = min(rows, key=lambda r: (-r["max_real_drawdown_pct"], r["scenario_id"]))
    row = {"split": rows[0]["split"], "policy": policy, "horizon": horizon, "scenario_count": len(rows)}
    for name, metric, probability in (
        ("median_growth_pct", "net_real_cagr_pct", .5), ("p10_growth_pct", "net_real_cagr_pct", .1),
        ("median_loss_pct", "max_real_drawdown_pct", .5), ("p90_loss_pct", "max_real_drawdown_pct", .9),
        ("median_volatility_pct", "annual_real_volatility_pct", .5),
        ("median_terminal_real_wealth", "terminal_real_wealth", .5),
        ("median_nominal_fee_sum", "nominal_fee_sum", .5)):
        row[name] = linear_quantile((r[metric] for r in rows), probability)
    for key in ("trade_count", "review_count", "later_trade_count", "later_review_count"):
        row["pooled_" + key] = sum(r[key] for r in rows)
    row["pooled_trade_share_pct"] = 100.0 * row["pooled_trade_count"] / row["pooled_review_count"]
    row["pooled_trade_share_ex_initial_pct"] = (100.0 * row["pooled_later_trade_count"] /
                                               row["pooled_later_review_count"])
    for key in ("scenario_id", "net_real_cagr_pct", "max_real_drawdown_pct", "terminal_real_wealth",
                "drawdown_peak_year", "drawdown_peak_kind", "drawdown_trough_year", "drawdown_trough_kind",
                "trade_share_pct", "trade_share_ex_initial_pct"):
        row["severe_" + key] = severe[key]
    return row | COMMON_UNITS


def paired_row(alternative, reference):
    if any(alternative[key] != reference[key] for key in ("split", "scenario_id", "horizon")):
        raise ValueError("paired keys differ")
    return {"split": alternative["split"], "alternative_policy": alternative["policy"],
            "reference_policy": reference["policy"], "scenario_id": alternative["scenario_id"],
            "horizon": alternative["horizon"],
            **{key + "_difference": alternative[key] - reference[key] for key in METRIC_VALUES},
            **PAIRED_UNITS}


class CheckBook:
    def __init__(self):
        self.groups = {}

    def add(self, name, ok, residual=0.0, scaled=0.0):
        group = self.groups.setdefault(name, {"status": "passed", "count": 0, "failures": 0,
            "max_absolute_residual": 0.0, "max_scaled_residual": 0.0})
        group["count"] += 1
        group["max_absolute_residual"] = max(group["max_absolute_residual"], residual)
        group["max_scaled_residual"] = max(group["max_scaled_residual"], scaled)
        if not ok:
            group["status"] = "failed"
            group["failures"] += 1

    def close(self, name, actual, expected, *, toy=False):
        residual = abs(actual - expected)
        scale = max(abs(actual), abs(expected))
        scaled = residual / scale if scale else 0.0
        self.add(name, math.isfinite(actual) and math.isclose(actual, expected, abs_tol=1e-9, rel_tol=0.0 if toy else 1e-10),
                 residual, scaled)

    def report(self):
        return {"status": "failed" if any(g["failures"] for g in self.groups.values()) else "passed",
                "thresholds": {"absolute_toy": 1e-9, "absolute_ledger": 1e-9,
                               "relative_ledger": 1e-10, "trade_amount_epsilon": TRADE_THRESHOLD,
                               "selection_ties": "exact float equality; tolerances are not tie thresholds"},
                "checks": self.groups, "count": sum(g["count"] for g in self.groups.values()),
                "failures": sum(g["failures"] for g in self.groups.values())}


def audit_ledger(checks, result):
    previous_holdings, previous_cpi, previous_real = (0.0, 0.0, 100.0), 1.0, 100.0
    for e in result.ledger:
        for actual, expected in zip(e.holdings_before, previous_holdings):
            checks.close("holdings_continuity", actual, expected)
        for vector in (e.holdings_before, e.holdings_after_fee, e.holdings_end):
            checks.add("finite_nonnegative_holdings", all(math.isfinite(x) and x >= 0 for x in vector))
        checks.close("budget", e.wealth_before, e.wealth_after_fee + e.fee)
        for wealth, vector in ((e.wealth_before, e.holdings_before),
                               (e.wealth_after_fee, e.holdings_after_fee), (e.wealth_end, e.holdings_end)):
            checks.close("fully_invested", wealth, sum(vector))
        if e.decision.action == "keep":
            checks.add("keep_exact_dollars", e.holdings_before == e.holdings_after_fee and
                       e.fee == 0 and e.intended_transfer == 0 and e.decision.target is None)
        else:
            expected_transfer = e.wealth_before / 2 * sum(abs(w - h / e.wealth_before)
                               for w, h in zip(e.decision.target, e.holdings_before))
            checks.close("intended_transfer", e.intended_transfer, expected_transfer)
            checks.close("fee", e.fee, result.fee_rate * expected_transfer)
            for amount, weight in zip(e.holdings_after_fee, e.decision.target):
                checks.close("target_after_fee", amount, (e.wealth_before - e.fee) * weight)
        for end, after, rate in zip(e.holdings_end, e.holdings_after_fee, e.returns):
            checks.close("fee_before_returns", end, after * (1 + rate))
        checks.close("cpi_continuity", e.cpi_before, previous_cpi)
        checks.close("compounded_cpi", e.cpi_end, previous_cpi * (1 + e.inflation))
        for real, nominal, cpi in ((e.real_wealth_before, e.wealth_before, e.cpi_before),
                                    (e.real_wealth_after_fee, e.wealth_after_fee, e.cpi_before),
                                    (e.real_wealth_end, e.wealth_end, e.cpi_end)):
            checks.close("exact_deflation", real, nominal / cpi)
        checks.close("net_annual_return", e.annual_net_real_return, e.real_wealth_end / previous_real - 1)
        previous_holdings, previous_cpi, previous_real = e.holdings_end, e.cpi_end, e.real_wealth_end


def scalar_metric_check(checks, row, ledger):
    # Independent elementary arithmetic from ledger observations, not compute_metrics.
    previous, peak, loss = 100.0, 100.0, 0.0
    returns = []
    for e in ledger:
        returns.append(e.real_wealth_end / previous - 1)
        previous = e.real_wealth_end
        for value in (e.real_wealth_after_fee, e.real_wealth_end):
            peak = max(peak, value)
            loss = max(loss, 1 - value / peak)
    h = len(ledger)
    mean = sum(returns) / h
    checks.close("scalar_growth", row["net_real_cagr_pct"], 100 * ((previous / 100) ** (1 / h) - 1))
    checks.close("scalar_volatility", row["annual_real_volatility_pct"],
                 100 * math.sqrt(sum((x - mean) ** 2 for x in returns) / (h - 1)))
    checks.close("scalar_loss", row["max_real_drawdown_pct"], 100 * loss)


def build_tables(rows, config, *, split):
    if split not in ("synthetic", "development"):
        raise ValueError("only explicit synthetic/development labels are supported")
    # Unit callers use the same full effective contract, including every rule.
    if digest(json.dumps(config, sort_keys=True, separators=(",", ":"),
                         allow_nan=False).encode()) != EFFECTIVE_CONFIG_SHA256:
        raise ValueError("unsupported fixed pilot parameters or rules")
    rows = validate_rows(rows)
    tables = {name: [] for name in COUNTS}
    checks = CheckBook()
    results = {}
    metrics = {}
    for policy, callback in sorted(POLICIES.items()):
        for scenario in range(1, 121):
            selected = rows[(scenario - 1) * 30:scenario * 30]
            result = simulate_policy(selected, horizon=30, split=split, callback=callback, fee_rate=config["fee_rate"])
            results[policy, scenario] = result
            audit_ledger(checks, result)
            tables["annual_ledgers.csv"].extend(ledger_row(policy, split, e) for e in result.ledger)
            for h in HORIZONS:
                row = metric_row(policy, result, h)
                metrics[policy, scenario, h] = row
                tables["scenario_metrics.csv"].append(row)
                checks.add("finite_pilot_metrics", all(math.isfinite(row[key]) for key in
                           (*METRIC_VALUES, "annual_real_volatility_pct")))
                if scenario in (1, 60, 120):
                    fresh = simulate_policy(selected, horizon=h, split=split, callback=callback)
                    checks.add("prefix_rerun", fresh.ledger == result.ledger[:h])
                    checks.add("single_scenario_batch", metric_row(policy, fresh, h) == row)
                    scalar_metric_check(checks, row, result.ledger[:h])
            if scenario in (1, 60, 120):
                altered = [dict(r) for r in selected]
                for r in altered[9:]:
                    for field in FIELDS[2:]:
                        r[field] = .07 if field == "inflation" else -.15
                changed = simulate_policy(altered, horizon=30, split=split, callback=callback)
                checks.add("no_lookahead_decisions", all(a.decision == b.decision for a, b in
                           zip(result.ledger[:10], changed.ledger[:10])))
                checks.add("no_lookahead_states", result.ledger[:9] == changed.ledger[:9] and
                           result.ledger[9].holdings_before == changed.ledger[9].holdings_before)
                if policy == "equal_weight_annual":
                    checks.add("annual_wrapper_agreement", simulate_equal_weight(selected, horizon=30, split=split) == result)
        for h in HORIZONS:
            group = [metrics[policy, s, h] for s in range(1, 121)]
            tables["summary.csv"].append(summary_row(policy, h, group))
            summary = tables["summary.csv"][-1]
            checks.add("pooled_denominators", summary["pooled_review_count"] == 120*h and
                       summary["pooled_later_review_count"] == 120*(h-1))
    for policy in sorted(set(POLICIES) - {"equal_weight_annual"}):
        for scenario in range(1, 121):
            for h in HORIZONS:
                tables["paired_differences.csv"].append(paired_row(metrics[policy, scenario, h],
                                                              metrics["equal_weight_annual", scenario, h]))
    key_fields = {"annual_ledgers.csv": ("policy", "scenario_id", "year"),
                  "scenario_metrics.csv": ("policy", "scenario_id", "horizon"),
                  "summary.csv": ("policy", "horizon"),
                  "paired_differences.csv": ("alternative_policy", "scenario_id", "horizon")}
    for name, expected in COUNTS.items():
        keys = [tuple(row[k] for k in key_fields[name]) for row in tables[name]]
        checks.add("count_" + name, len(keys) == expected)
        checks.add("keys_" + name, len(set(keys)) == expected and keys == sorted(keys))
    # Exact independent rational toy expectations, also checked in unit tests/oracle.
    trade = rebalance((0, 0, 100), (.2, 0, .8))
    checks.close("toy_twenty_transfer", trade.intended_transfer, 20, toy=True)
    checks.close("toy_twenty_fee", trade.fee, 1/20, toy=True)
    toy = ({"scenario_id": 1, "period": 1, "equity_return": .1, "bond_return": .1,
            "bill_proxy_return": .1, "inflation": 0},)
    recovery = simulate_equal_weight(toy, horizon=1, split="synthetic")
    checks.close("toy_initial_fee", recovery.ledger[0].wealth_after_fee, 599/6, toy=True)
    checks.close("toy_fee_recovery", recovery.metrics.max_real_drawdown_pct, 1/6, toy=True)
    checks.add("h1_nulls", recovery.metrics.annual_real_volatility_pct is None and
               recovery.trade_share_ex_initial_pct is None)
    for p, value in ((.1, 3), (.5, 15), (.9, 27)):
        checks.close("toy_linear_quantiles", linear_quantile([0, 10, 20, 30], p), value, toy=True)
    report = checks.report() | {"split": split, "plan_id": config["plan_id"],
                               "output_counts": {name: len(rows) for name, rows in tables.items()}}
    if report["status"] != "passed":
        raise ValueError("deterministic checks failed: " + json.dumps(report))
    return tables, report


def produce_bundle(loaded, config, output, provenance, *, command):
    """Create six files. Explicit synthetic inputs remain synthetic in every file."""
    output = Path(output)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("refusing nonempty output directory")
    output.mkdir(parents=True, exist_ok=True)
    started, elapsed, cpu = datetime.now(timezone.utc), time.perf_counter(), time.process_time()
    manifest = {"schema_version": 1, "plan_id": config["plan_id"], **provenance,
                "effective_config": config, "profile_horizons": config["profile_horizons"],
                "comparison_horizon": config["comparison_horizon"], "horizons": config["horizons"],
                "split": loaded.split, "input": {"origin": loaded.origin, "sha256": loaded.sha256,
                    "fixture": loaded.split == "synthetic",
                    "fixture_generator_sha256": loaded.fixture_generator_sha256},
                "command": command, "python_version": platform.python_version(),
                "packages": {"stdlib": platform.python_version()}, "utc_start": started.isoformat(),
                "status": "running", "output_sha256": {}}
    try:
        tables, checks = build_tables(loaded.rows, config, split=loaded.split)
        for name, rows in tables.items():
            (output / name).write_bytes(csv_bytes(rows))
        (output / "checks.json").write_bytes(json_bytes(checks))
        manifest["output_sha256"] = {name: digest((output / name).read_bytes())
                                     for name in (*COUNTS, "checks.json")}
        manifest["output_counts"] = {name: len(rows) for name, rows in tables.items()}
        manifest["status"] = "completed"
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["diagnosis"] = {"exception": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        manifest["utc_end"] = datetime.now(timezone.utc).isoformat()
        manifest["elapsed_seconds"] = time.perf_counter() - elapsed
        manifest["cpu_seconds"] = time.process_time() - cpu
        (output / "run_manifest.json").write_bytes(json_bytes(manifest))
    return manifest


def read_manifest(output):
    return json.loads((Path(output) / "run_manifest.json").read_bytes())


def validate_manifest_metadata(manifest):
    required = {"command", "python_version", "packages", "utc_start", "utc_end",
                "elapsed_seconds", "cpu_seconds"}
    if not required <= manifest.keys():
        raise ValueError("saved manifest metadata schema incomplete")
    version = manifest["python_version"]
    if not isinstance(version, str) or not re.fullmatch(r"3\.12\.[0-9]+", version):
        raise ValueError("saved Python version is not 3.12")
    if manifest["packages"] != {"stdlib": version}:
        raise ValueError("saved package version metadata mismatch")
    command = manifest["command"]
    if (not isinstance(command, list) or len(command) < 6 or
            any(not isinstance(arg, str) or not arg for arg in command) or
            command[:2] != ["python", "scripts/run_development_baselines.py"] or
            "--config" not in command or "--output" not in command or "--check" in command):
        raise ValueError("saved creation command schema invalid")
    start, end = (datetime.fromisoformat(manifest[key]) for key in ("utc_start", "utc_end"))
    if start.utcoffset() != timezone.utc.utcoffset(start) or end.utcoffset() != timezone.utc.utcoffset(end) or end < start:
        raise ValueError("saved UTC timing metadata invalid")
    for key in ("elapsed_seconds", "cpu_seconds"):
        value = manifest[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError("saved duration invalid: " + key)


def check_bundle(loaded, config, output, provenance):
    """Read-only comparison against saved evidence; no write or repair operations."""
    output = Path(output)
    manifest = read_manifest(output)
    required_files = set(COUNTS) | {"checks.json", "run_manifest.json"}
    if {p.name for p in output.iterdir()} != required_files:
        raise ValueError("saved bundle has missing or unexpected files")
    for key, expected in (("status", "completed"), ("schema_version", 1), ("plan_id", config["plan_id"]),
                          ("effective_config", config), ("split", loaded.split),
                          ("profile_horizons", config["profile_horizons"]),
                          ("comparison_horizon", config["comparison_horizon"]), ("horizons", list(HORIZONS)),
                          ("source_commit", provenance["source_commit"]),
                          ("canonical_git_sources", provenance["canonical_git_sources"]),
                          ("output_counts", COUNTS)):
        if manifest.get(key) != expected:
            raise ValueError("saved manifest mismatch: " + key)
    if manifest.get("input") != {"origin": loaded.origin, "sha256": loaded.sha256,
                                  "fixture": loaded.split == "synthetic",
                                  "fixture_generator_sha256": loaded.fixture_generator_sha256}:
        raise ValueError("saved input provenance mismatch")
    validate_manifest_metadata(manifest)
    consumed = manifest.get("consumed_source_sha256", {})
    if set(consumed) != set(SOURCE_PATHS) or any(not re.fullmatch(r"[0-9a-f]{64}", v) for v in consumed.values()):
        raise ValueError("invalid consumed source hash evidence")
    for name, value in consumed.items():
        blob = provenance["canonical_git_sources"][name]
        if value not in (blob["sha256"], blob["crlf_checkout_sha256"]):
            raise ValueError("saved consumed source hash is inconsistent with Git bytes: " + name)
    if set(manifest.get("output_sha256", {})) != required_files - {"run_manifest.json"}:
        raise ValueError("saved output hash map mismatch")
    stored = {}
    for name, expected_hash in manifest["output_sha256"].items():
        data = (output / name).read_bytes()
        if b"\r" in data or digest(data) != expected_hash:
            raise ValueError("saved output hash/UTF-8 LF mismatch: " + name)
        data.decode("utf-8")
        stored[name] = data
    tables, checks = build_tables(loaded.rows, config, split=loaded.split)
    for name, rows in tables.items():
        # Exact serialization comparison also checks schema, sorted complete keys,
        # units, all defined values, signs, locations and detached identities.
        if stored[name] != csv_bytes(rows):
            raise ValueError("saved schema/keys/numeric values differ: " + name)
    if stored["checks.json"] != json_bytes(checks):
        raise ValueError("saved deterministic checks differ")
    return {"status": "passed", "read_only": True, "output_counts": COUNTS,
            "source_commit": provenance["source_commit"], "checks": checks}
