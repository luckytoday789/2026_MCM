"""Repeatable synthetic analysis audit. Initialization is exclusive; --check is read-only.

Pin explicit Git objects rather than current HEAD/branch. Accept only LF/CRLF
translation of text sources. No competition input or result bundle is opened.
"""
import argparse
from dataclasses import asdict
from fractions import Fraction as F
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import platform
import subprocess
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
AUDIT = Path(__file__).resolve().parent
BASE = "dd60066010f6904565fb51e99be8088285102e57"
RELEASE = "e018e2a70f9d1191d86e897df5f943228956139f"
PINS = {
  "specs/PROBLEM_LOCK.md": {
    "sha256_lf": "566c93ad1b5f79c9ec10a42725ab023953c9a02aeb1c91a459e740caf68c0e46",
    "git_blob_sha1": "1ba83723824afde3b29a5b3c8b0ac5d433a68c4b"
  },
  "specs/ACCOUNTING.md": {
    "sha256_lf": "a9c3ab8dbba3ad752336642061ead272e2c196de83f73eb410e39bd5b559f71e",
    "git_blob_sha1": "0627337a522651189b7a985e94b6af9a1f7a4a4d"
  },
  "specs/DEVELOPMENT_POLICY_PILOT_V2.md": {
    "sha256_lf": "ada0257f813091a01526e497e28ca3871bf9b13afa98487708be17ae8249bcb1",
    "git_blob_sha1": "d1f02265d988444c20a7d61595306c86b9fa33c4"
  },
  "specs/development_policy_pilot_v2.json": {
    "sha256_lf": "d7b20f38196831befc80dfdcc69c6653d1ae8352d1c87c79e19bcc09d5c84df3",
    "git_blob_sha1": "6e4fa5331624b7583584ccbcbb09a8a858dc2557"
  },
  "specs/policy_driver_layout_v2.json": {
    "sha256_lf": "f431e661c260f7f6e40330661e77724dc3ddcafeafed1a3f0b6c31781a4e8329",
    "git_blob_sha1": "dc8c5b8e98526c9bc8a8340abc4bb5b9ed5a8d09"
  },
  "specs/POLICY_CASE_ENGINE.md": {
    "sha256_lf": "c984e230eecb720613b864a910d95921af1aa805f79fa68c7044f905410dec62",
    "git_blob_sha1": "bafe77b5b0d31319ad8f43aad6059fd57232f8dd"
  },
  "src/safeinvest/accounting.py": {
    "sha256_lf": "0c73b143ed9755924be16d9c4fe9d9e8d8888931cb5c8a8c303434e2280389e5",
    "git_blob_sha1": "6ff55fed7cc0ab40f6e609dad7657efc92cd09e7"
  },
  "src/safeinvest/backtest.py": {
    "sha256_lf": "bbe2e602124adf068da424df0a28c9f40f970f81c126bed393f61ebb25b244b6",
    "git_blob_sha1": "87f5f107f5f76d5da155fc134c1b036b7c431987"
  },
  "src/safeinvest/metrics.py": {
    "sha256_lf": "efb7dad73e71515b9f164a95935231479ebca14b46c5b086a14de4bf5d38df9e",
    "git_blob_sha1": "383aa3fbeed74bce4d4ec1bce7bb091097fc5e05"
  },
  "src/safeinvest/baselines.py": {
    "sha256_lf": "a8e392111c7f206aa4be2a475b92db62d049ea7eb460c1d813f0d8033f5620ce",
    "git_blob_sha1": "5b1c5ffa310923da2866492145871977edffb2a5"
  },
  "src/safeinvest/experiments.py": {
    "sha256_lf": "8cfc463704decff7491e3f2ef5f9ec208318294eb0254363a98c6df50550abca",
    "git_blob_sha1": "f9d28e72ce2cbf6ae0bb08b80f8ffab486b192da"
  },
  "specs/POLICY_ANALYSIS.md": {
    "sha256_lf": "a2220482c861799280815b4e65d73e79e53666816ac9e7e72a38d5f48a6e53b8",
    "git_blob_sha1": "0100c2f07fd8754687f2ec641ae59bfc4f1d9ede"
  },
  "src/safeinvest/__init__.py": {
    "sha256_lf": "b986566f8c42973164639cc7e296ed70fbc64479411e79a81f522cfc27ec14ef",
    "git_blob_sha1": "177f42cd6d15de17cadda7bd49382921a27e565d"
  }
}
DELIVERED = ("src/safeinvest/policy_analysis.py", "tests/test_policy_analysis.py",
             "audit/SOL-016/verify.py", "audit/SOL-016/findings.json",
             "audit/SOL-016/implementation.md", "audit/SOL-016/task-binding.json",
             "audit/SOL-016/history/infrastructure-001.json",
             "audit/SOL-016/history/trial-001-tests.json")


def digest(b):
    return hashlib.sha256(b).hexdigest()


def lf(b):
    return b.replace(b"\r\n", b"\n")


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True).stdout


def blob_sha(b):
    return hashlib.sha1(b"blob " + str(len(b)).encode() + b"\0" + b).hexdigest()


def source_binding():
    if git("cat-file", "-t", BASE).strip() != b"commit":
        raise RuntimeError("upstream base is not a Git commit")
    sources = {}
    for name, pin in PINS.items():
        original = git("show", BASE + ":" + name)
        actual = (ROOT / name).read_bytes()
        if digest(lf(original)) != pin["sha256_lf"] or blob_sha(original) != pin["git_blob_sha1"]:
            raise RuntimeError("upstream Git object mismatch: " + name)
        if lf(actual) != lf(original):
            raise RuntimeError("consumed upstream source differs: " + name)
        sources[name] = dict(pin)
    task = json.loads(git("show", RELEASE + ":ops/tasks/SOL-016.json"))
    binding = json.loads((AUDIT / "task-binding.json").read_bytes())
    if task != binding["task_json"] or task["base_commit"] != BASE or task["id"] != "SOL-016":
        raise RuntimeError("immutable task mismatch")
    task_hash = digest(json.dumps(task, sort_keys=True, separators=(",", ":")).encode())
    queue = json.loads(git("show", RELEASE + ":ops/queue.json"))
    released = next(t for t in queue["tasks"] if t["id"] == "SOL-016")
    if released != binding["release_queue_entry"] or released["state"] != "ready" or released["task_sha256"] != task_hash:
        raise RuntimeError("release/immutable task checksum mismatch")
    review = git("show", RELEASE + ":audit/chief/SOL-021-review.json")
    if digest(lf(review)) != binding["release_review"]["sha256_lf"] or json.loads(review)["code_verdict"] != "approve":
        raise RuntimeError("release review mismatch")
    files = {name: digest(lf((ROOT / name).read_bytes())) for name in DELIVERED}
    return {"base_commit": BASE, "release_metadata_commit": RELEASE,
            "task_sha256_canonical_json": task_hash,
            "task_git_blob_sha1": blob_sha(git("show", RELEASE + ":ops/tasks/SOL-016.json")),
            "upstream": sources, "delivered_sha256_lf": files,
            "normalization": "only CRLF to LF; no whitespace stripping of delivered/source files"}


def load_tests():
    spec = importlib.util.spec_from_file_location("sol016_fixtures", ROOT / "tests/test_policy_analysis.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rational(x):
    return F(x)  # exact binary64 operands, independent rational interpolation


def quantile(values, probability):
    ordered = sorted(map(rational, values))
    position = (len(ordered) - 1) * probability
    left = position.numerator // position.denominator
    right = min(left + 1, len(ordered) - 1)
    return ordered[left] + (position - left) * (ordered[right] - ordered[left])


class Checks:
    def __init__(self):
        self.count = 0
        self.max_absolute_residual = 0.

    def equal(self, a, b):
        self.count += 1
        if a != b:
            raise AssertionError((a, b))

    def close(self, actual, expected):
        self.count += 1
        expected = float(expected)
        if not math.isfinite(actual) or not math.isclose(actual, expected, abs_tol=1e-11, rel_tol=1e-12):
            raise AssertionError((actual, expected))
        self.max_absolute_residual = max(self.max_absolute_residual, abs(actual - expected))


def numeric_fixture(fx):
    rows = fx.grid(8)
    for r in rows:
        m, s, h = fx.MODES.index(r["mode"]), r["scenario_id"], r["horizon"]
        doubled = int(r["fee_rate"] == .005)
        r.update(net_real_cagr_pct=(m - 3) / 4 + (s - 4) / 8 + h / 32 - doubled / 8,
                 max_real_drawdown_pct=m + s / 2 + h / 16,
                 terminal_real_wealth=100 + m * 3 + s / 2 + h / 4,
                 nominal_fee_sum=m / 4 + doubled / 2,
                 annual_real_volatility_pct=m + s / 4)
        r["trade_count"] = s % 3
        r["later_trade_count"] = max(0, r["trade_count"] - 1)
        r["trade_share_pct"] = 100 * r["trade_count"] / h
        r["trade_share_ex_initial_pct"] = 100 * r["later_trade_count"] / (h - 1)
        if m >= 3:
            count = s % 3
            r.update(human_review_count=count, human_review_share_pct=100 * count / h,
                     first_latch_year=None if not count else h - count + 1,
                     target_change_count=s % 2, first_deployment_year=1,
                     initial_allocation_deferred=False)
    return rows


def behavior_fixtures(fx):
    """Retain actual negative/positive facts, not just a suite success count."""
    facts = {}
    for name, context, adaptive in (("fails_context_only", .2, .25),
            ("fails_cost_only", -.2, .05), ("context_fails_adaptive_passes_both", .05, .25)):
        rows = fx.grid()
        fx.set_case(rows, "balanced_context", net_real_cagr_pct=context)
        fx.set_case(rows, "balanced_adaptive", net_real_cagr_pct=adaptive)
        facts[name] = fx.build(rows).selection
    rows = fx.grid()
    fx.set_case(rows, "balanced_context", net_real_cagr_pct=.3)
    fx.set_case(rows, "balanced_adaptive", net_real_cagr_pct=.6)
    fx.set_case(rows, "balanced_adaptive", fee=.005, net_real_cagr_pct=.2)
    facts["sensitivity_failure_no_reselection"] = fx.build(rows).selection
    boundaries = []
    for statistic, center, direction in (("gain",.1,1), ("tail_growth",-.1,1), ("tail_loss",1.,-1)):
        for side, value in (("below",math.nextafter(center,-math.inf)), ("equal",center),
                            ("above",math.nextafter(center,math.inf))):
            rows = fx.grid()
            if statistic == "tail_loss":
                fx.set_case(rows,"balanced_cost",max_real_drawdown_pct=0.)
                fx.set_case(rows,"balanced_context",max_real_drawdown_pct=value)
            else:
                fx.set_case(rows,"balanced_context",net_real_cagr_pct=value)
            boundaries.append({"statistic":statistic,"side":side,"stored_input":value,
                               "comparison":fx.gate(fx.build(rows))})
    facts["thresholds"] = boundaries
    rows = fx.grid(8)
    fx.set_case(rows,"balanced_context",net_real_cagr_pct=[0,.2,.2,.2,0,.4,-.1,.2])
    facts["zero_fold_excluded"] = fx.gate(fx.build(rows))
    rows = fx.grid(12)
    fx.set_case(rows,"conservative_cost",max_real_drawdown_pct=[10.]*11+[50.])
    facts["p90_pass_with_actual_exceedance"] = fx.screen(fx.build(rows),"A")
    rows = fx.grid()
    for mode in fx.MODES[3:6]:
        fx.set_case(rows,mode,net_real_cagr_pct=-.01,max_real_drawdown_pct=60.)
    t = fx.build(rows)
    facts["all_referral"] = {"profile_screen":t.profile_screen,
                             "profile_recommendations":t.profile_recommendations}
    facts["indifference"] = []
    for side, value in (("below",math.nextafter(.1,-math.inf)),("equal",.1),
                        ("above",math.nextafter(.1,math.inf))):
        rows=fx.grid()
        fx.set_case(rows,"balanced_cost",net_real_cagr_pct=value)
        facts["indifference"].append({"side":side,"stored_input":value,
                                      "recommendation":fx.recommendation(fx.build(rows),"B")})
    # Rejections record the actual exception; no missing rows are fabricated.
    invalid = []
    for field, value in (("fee_rate",.01),("horizon",7),("fold_id",1),
                         ("net_real_cagr_pct",None),("max_real_drawdown_pct",101)):
        rows=fx.grid()
        rows[0][field]=value
        try:
            fx.build(rows)
        except ValueError as error:
            invalid.append({"field":field,"value":value,"rejected":True,"error":str(error)})
        else:
            raise AssertionError("invalid fixture accepted")
    for label in ("final","raw"):
        try:
            fx.build(fx.grid(),label)
        except ValueError as error:
            invalid.append({"split":label,"rejected":True,"error":str(error)})
        else:
            raise AssertionError("invalid split accepted")
    facts["rejections"] = invalid
    return facts


def recompute():
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("Python 3.12 is required")
    binding = source_binding()
    fx = load_tests()
    checks = Checks()
    rows = numeric_fixture(fx)
    tables = fx.build(rows)
    # Establish loaded code identity, not a caller-supplied arbitrary copy.
    import safeinvest.policy_analysis as analysis
    checks.equal(Path(analysis.__file__).resolve(), (ROOT / "src/safeinvest/policy_analysis.py").resolve())
    checks.equal((len(rows), len(tables.paired_differences), len(tables.comparison_gates),
                  len(tables.profile_screen), len(tables.profile_recommendations)), (640, 800, 100, 30, 10))
    bykey = {(r["mode"], r["fee_rate"], r["horizon"], r["scenario_id"]): r for r in rows}
    for p in tables.paired_differences:
        a = bykey[p["candidate_mode"], p["fee_rate"], p["horizon"], p["scenario_id"]]
        b = bykey[p["reference_mode"], p["fee_rate"], p["horizon"], p["scenario_id"]]
        checks.equal(p["fold_id"], (p["scenario_id"] - 1) % 4)
        checks.equal(p["split"], "synthetic")
        for field in fx.VALUES + ("human_review_count", "human_review_share_pct", "target_change_count"):
            if a[field] is None or b[field] is None:
                checks.equal(p[field + "_difference"], None)
            else:
                checks.close(p[field + "_difference"], rational(a[field]) - rational(b[field]))
    for g in tables.comparison_gates:
        aa = [bykey[g["candidate_mode"], g["fee_rate"], g["horizon"], s] for s in range(1, 9)]
        bb = [bykey[g["reference_mode"], g["fee_rate"], g["horizon"], s] for s in range(1, 9)]
        gains = [rational(a["net_real_cagr_pct"]) - rational(b["net_real_cagr_pct"]) for a, b in zip(aa, bb)]
        gain = quantile(gains, F(1, 2))
        tg = quantile([a["net_real_cagr_pct"] for a in aa], F(1, 10)) - quantile([b["net_real_cagr_pct"] for b in bb], F(1, 10))
        tl = quantile([a["max_real_drawdown_pct"] for a in aa], F(9, 10)) - quantile([b["max_real_drawdown_pct"] for b in bb], F(9, 10))
        checks.close(g["median_paired_growth_gain_pp"], gain)
        checks.close(g["marginal_p10_growth_difference_pp"], tg)
        checks.close(g["marginal_p90_loss_difference_pp"], tl)
        positive = 0
        for fold in range(4):
            median = (gains[fold] + gains[fold + 4]) / 2
            positive += median > 0
            checks.close(g["folds"][fold]["median_paired_growth_gain_pp"], median)
            checks.equal(g["folds"][fold]["positive"], median > 0)
            checks.equal(g["folds"][fold]["scenario_count"], 2)
        flags = {"gain_at_least_0_10": gain >= rational(.1),
                 "tail_growth_at_least_minus_0_10": tg >= rational(-.1),
                 "tail_loss_at_most_1_00": tl <= 1,
                 "at_least_three_positive_folds": positive >= 3}
        checks.equal(g["flags"], flags)
        checks.equal(g["positive_fold_count"], positive)
        checks.equal(g["passed"], all(flags.values()))
        for field in fx.VALUES + ("human_review_count", "human_review_share_pct", "target_change_count"):
            if aa[0][field] is None or bb[0][field] is None:
                checks.equal(g["median_paired_differences"][field + "_difference"], None)
            else:
                expected = quantile([rational(a[field]) - rational(b[field]) for a, b in zip(aa, bb)], F(1, 2))
                checks.close(g["median_paired_differences"][field + "_difference"], expected)
    # All thirty profile rows independently checked at the published horizon.
    profiles = {"A":(5,10,"high"), "B":(15,25,"medium"), "C":(30,40,"low"),
                "D":(25,15,"medium"), "E":(6,35,"high")}
    reserves = {"conservative": .65, "balanced": 1/3, "growth": .1}
    eligible = {"A":["conservative"], "B":["conservative","balanced"],
                "C":["conservative","balanced","growth"], "D":["conservative","balanced"], "E":["conservative"]}
    for p in tables.profile_screen:
        h, tol, liquidity = profiles[p["profile"]]
        data = [bykey[p["mode"], p["fee_rate"], h, s] for s in range(1,9)]
        checks.equal(p["horizon"], h)
        checks.equal(p["loss_tolerance_pct"], tol)
        checks.equal(p["source_metric_keys"], [{k:r[k] for k in ("mode","fee_rate","horizon","scenario_id","fold_id","split")} for r in data])
        for field, source, probability in (("median_growth_pct","net_real_cagr_pct",F(1,2)),
                ("p10_growth_pct","net_real_cagr_pct",F(1,10)),
                ("median_loss_pct","max_real_drawdown_pct",F(1,2)),
                ("p90_loss_pct","max_real_drawdown_pct",F(9,10))):
            checks.close(p[field], quantile([r[source] for r in data], probability))
        severe = max(r["max_real_drawdown_pct"] for r in data)
        checks.equal(p["severe_loss_pct"], severe)
        checks.equal(p["severe_scenario_id"], min(r["scenario_id"] for r in data if r["max_real_drawdown_pct"] == severe))
        exceed = sum(r["max_real_drawdown_pct"] > tol for r in data)
        checks.equal(p["exceedance_count"], exceed)
        checks.close(p["exceedance_fraction"], F(exceed, 8))
        checks.equal(p["target_bill_reserve"], reserves[p["candidate_class"]])
        rank = ("conservative","balanced","growth").index(p["candidate_class"])
        flags = {"horizon_eligible":rank <= (0 if h<=6 else 1 if h<20 else 2),
                 "willingness_eligible":p["candidate_class"] in eligible[p["profile"]],
                 "liquidity_pass":reserves[p["candidate_class"]] >= {"high":.6,"medium":.25,"low":.1}[liquidity],
                 "risk_pass":float(quantile([r["max_real_drawdown_pct"] for r in data],F(9,10))) <= tol,
                 "purchasing_power_pass":float(quantile([r["net_real_cagr_pct"] for r in data],F(1,10))) >= 0}
        checks.equal(p["flags"], flags)
        checks.equal(p["qualified"], all(flags.values()))
    # Additional independent sign-reversal scalar expectations.
    reverse = fx.grid()
    fx.set_case(reverse, "balanced_cost", net_real_cagr_pct=[0,10,20,30], max_real_drawdown_pct=[0,10,20,30])
    fx.set_case(reverse, "balanced_context", net_real_cagr_pct=[31,1,11,21], max_real_drawdown_pct=[30,0,10,20])
    reversed_gate = fx.gate(fx.build(reverse))
    checks.close(reversed_gate["median_paired_growth_gain_pp"], -9)
    checks.close(reversed_gate["marginal_p10_growth_difference_pp"], 1)
    checks.close(reversed_gate["marginal_p90_loss_difference_pp"], 0)
    suite = unittest.defaultTestLoader.loadTestsFromModule(fx)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
    if not result.wasSuccessful():
        raise AssertionError(stream.getvalue())
    data = asdict(tables)
    schema = {name: sorted(records[0]) for name, records in data.items() if isinstance(records, list)}
    schema["selection"] = sorted(data["selection"])
    return {"schema_version":1, "task_id":"SOL-016", "status":"synthetic_checks_passed",
            "python_major_minor":[3,12], "binding":binding,
            "input_fixture_sha256":digest(canonical(rows)),
            "input_metric_field_count":len(rows[0]), "input_metric_fields":sorted(rows[0]),
            "table_schemas":schema, "table_schema_sha256":digest(canonical(schema)),
            "checks":{"scalar_rational_comparisons":checks.count,
                      "max_absolute_residual":checks.max_absolute_residual,
                      "numeric_absolute_tolerance":1e-11,"numeric_relative_tolerance":1e-12,
                      "policy_threshold_tolerance":0,
                      "unittest_tests_run":result.testsRun, "unittest_failures":len(result.failures),
                      "unittest_errors":len(result.errors)},
            "paired_marginal_reversal":reversed_gate,
            "behavior_fixtures":behavior_fixtures(fx),
            "generated_tables":data,
            "limitations":["Generated metric grids only; no path simulation or performance evidence.",
                "Pure split labels enforce shape only; source provenance belongs to the future writer.",
                "No final support, production execution, personalized overlay or chief acceptance."]}


def compare(actual, saved, path="root"):
    # Keys, types, strings, booleans, integers and hashes compare exactly. Numeric
    # tolerance is for recomputed measurements, never policy decisions/thresholds.
    if type(actual) is not type(saved):
        raise RuntimeError("evidence type mismatch: " + path)
    if isinstance(actual, dict):
        if actual.keys() != saved.keys():
            raise RuntimeError("evidence keys mismatch: " + path)
        for key in actual:
            compare(actual[key], saved[key], path + "." + key)
    elif isinstance(actual, list):
        if len(actual) != len(saved):
            raise RuntimeError("evidence count mismatch: " + path)
        for i, (a,b) in enumerate(zip(actual,saved)):
            compare(a,b,path + "[" + str(i) + "]")
    elif isinstance(actual, float):
        decision_fields = {"stored_input", "fee_rate", "primary_fee_rate", "indifference_pp_per_year",
            "median_paired_growth_gain_pp", "marginal_p10_growth_difference_pp",
            "marginal_p90_loss_difference_pp", "p90_loss_pct", "p10_growth_pct",
            "median_growth_pct", "maximum_qualifying_median_growth_pct",
            "gap_from_best_pp_per_year", "loss_tolerance_pct", "review_drawdown_pct",
            "target_bill_reserve", "minimum_target_bill_reserve"}
        exact = path.rsplit(".", 1)[-1] in decision_fields
        if not math.isfinite(saved) or (actual != saved if exact else not math.isclose(actual,saved,abs_tol=1e-11,rel_tol=1e-12)):
            raise RuntimeError("evidence number mismatch: " + path)
    elif actual != saved:
        raise RuntimeError("evidence exact mismatch: " + path)


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise RuntimeError("duplicate saved evidence key: " + key)
            result[key] = value
        return result
    return json.loads(path.read_bytes(), object_pairs_hook=unique,
                      parse_constant=lambda x: (_ for _ in ()).throw(RuntimeError("nonfinite saved evidence: " + x)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--evidence", type=Path, default=AUDIT / "verification.json")
    args = parser.parse_args()
    if args.check:
        original = args.evidence.read_bytes()
        expected = read_json(args.evidence)
        compare(recompute(), expected)
        if args.evidence.read_bytes() != original:
            raise RuntimeError("evidence bytes changed during read-only check")
        print(json.dumps({"status":"passed","read_only":True,"evidence_unchanged":True,
                          "scalar_rational_comparisons":expected["checks"]["scalar_rational_comparisons"],
                          "tests":expected["checks"]["unittest_tests_run"]}))
    else:
        # Refuse an existing artifact before expensive work. The x-mode write
        # below remains the authoritative race-safe exclusive-creation check.
        if args.evidence.exists():
            raise FileExistsError("verification already exists; use --check")
        facts = recompute()
        with args.evidence.open("xb") as stream:
            stream.write(canonical(facts))
        print(json.dumps({"status":"created_exclusively","checks":facts["checks"]}))


if __name__ == "__main__":
    main()
