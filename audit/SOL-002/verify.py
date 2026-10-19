"""SOL-002: independent, standard-library toy review of the pinned chief design.

No chief Python or production module is imported/executed. JSON is comparison data
only. Expected amounts come from a separate exact cash-flow engine; dispersion
uses the pairwise-difference identity, and drawdown enumerates earlier peaks.
Default initializes evidence once. --check recomputes and NEVER rewrites it.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
BASE = "297fc5d846bfc218795238e567875e49b18e7053"
ABS = Decimal("1e-9")
PINNED = {
    "specs/DEVELOPMENT_BASELINES.md": "aa745e6dceeaa1d6b04168e54e3af55ba5ec4f46825d38ae4962428c6b7bc25f",
    "specs/development_baselines_v1.json": "725f6eed64bbf49d7cad19d5f1cc233c7e0d80aa82c39c6aabd3b8864b2007bd",
    "audit/chief/accounting_oracle.json": "85caa997e09b1cf2a02118f4f101137919ad7b38ce662caed7a594c569ed1377",
    "audit/chief/accounting_reference.py": "c7a62e8f8453280e867758aed968b5041dea4f6d3ac6fca07e6e856bc5e85b07",
    "specs/PROBLEM_LOCK.md": "566c93ad1b5f79c9ec10a42725ab023953c9a02aeb1c91a459e740caf68c0e46",
    "specs/ACCOUNTING.md": "a9c3ab8dbba3ad752336642061ead272e2c196de83f73eb410e39bd5b559f71e",
    "AGENTS.md": "92ab36877ad51c32b6393d7955e84d20ff34b59b82ed2905c0f0dd0a29dac078",
    "ops/PROTOCOL.md": "1d26831e0679dfc7a285f6408d274b0382566928428f9963bb1c04122b0eaa32",
}
K = F(1, 400)
START = (F(0), F(0), F(100))
THIRDS = (F(1, 3),) * 3
POLICIES = ("bills_keep", "equal_weight_annual", "equal_weight_buy_hold")
RATES = ((F(1, 10), F(0), -F(1, 20)), (-F(1, 5), F(1, 10), F(0)))
INFLATION = (F(1, 50), F(0))


def dec(x):
    if isinstance(x, F):
        return Decimal(x.numerator) / Decimal(x.denominator)
    return Decimal(str(x))


def exact(x):
    x = F(x)
    return {"rational": str(x), "value": dec(x)}


def plain(x):
    if isinstance(x, (F, Decimal)):
        return str(x)
    if isinstance(x, dict):
        return {k: plain(v) for k, v in x.items()}
    if isinstance(x, (tuple, list)):
        return [plain(v) for v in x]
    return x


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def source_blobs():
    hashes, blobs = {}, {}
    for name in PINNED:
        body = git("show", BASE + ":" + name)
        blobs[name] = body
        hashes[name] = {
            "sha256": hashlib.sha256(body).hexdigest(),
            "git_blob_sha1": hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest(),
        }
    return hashes, blobs


def action(policy, year):
    # This decision function takes neither current-year outcomes nor horizon.
    if policy == "bills_keep" or (policy == "equal_weight_buy_hold" and year > 1):
        return "keep", None
    return "rebalance", THIRDS


def settle(holdings, target):
    wealth = sum(holdings)
    if target is None:
        return tuple(holdings), F(0), F(0)
    desired = tuple(wealth * weight for weight in target)
    # Fund purchases by intended sales; never add the fee-funding adjustment.
    transferred = sum(max(F(0), wanted - held) for wanted, held in zip(desired, holdings))
    fee = K * transferred
    funded = tuple(wanted - fee * weight for wanted, weight in zip(desired, target))
    return funded, transferred, fee


def path_for(policy, rates=RATES, inflation=INFLATION):
    holdings, cpi, rows = START, F(1), []
    for t in range(len(rates)):
        kind, target = action(policy, t + 1)  # before reading rates[t]/inflation[t]
        post, transfer, fee = settle(holdings, target)
        new_cpi = cpi * (1 + inflation[t])
        end = tuple(post[i] * (1 + rates[t][i]) for i in range(3))
        rows.append({"year": t + 1, "action": kind, "target": target,
                     "pre": holdings, "post": post, "end": end,
                     "transfer": transfer, "fee": fee, "cpi_before": cpi,
                     "cpi_after": new_cpi, "real_post": sum(post) / cpi,
                     "real_end": sum(end) / new_cpi})
        holdings, cpi = end, new_cpi
    return rows


def maximum_drawdown(values):
    return max([F(0)] + [1 - values[j] / values[i]
               for j in range(len(values)) for i in range(j + 1)])


def metrics(rows):
    n = len(rows)
    previous, net, observations = F(100), [], [F(100)]
    for row in rows:
        net.append(row["real_end"] / previous - 1)
        previous = row["real_end"]
        observations.extend((row["real_post"], row["real_end"]))
    # sum_{i<j}(x_i-x_j)^2/[n(n-1)] equals the sample variance.
    variance = (sum((net[i] - net[j]) ** 2 for i in range(n) for j in range(i))
                / (n * (n - 1))) if n > 1 else None
    trades = [int(row["transfer"] > F(1, 10**10)) for row in rows]
    return {"real_path": observations, "net_returns": net,
            "terminal": previous,
            "growth": 100 * ((dec(previous / 100).ln() / n).exp() - 1),
            "volatility": 100 * dec(variance).sqrt() if variance is not None else None,
            "drawdown": 100 * maximum_drawdown(observations),
            "fee_sum": sum(row["fee"] for row in rows),
            "trade_count": sum(trades), "reviews": n,
            "later_trade_count": sum(trades[1:]), "later_reviews": n - 1,
            "trade_in": F(100 * sum(trades), n),
            "trade_ex": F(100 * sum(trades[1:]), n - 1) if n > 1 else None}


def quantile(values, probability):
    ordered = sorted(values)
    location = (len(values) - 1) * probability
    lower = location.numerator // location.denominator
    upper = min(lower + 1, len(values) - 1)
    return ordered[lower] + (location - lower) * (ordered[upper] - ordered[lower])


def expected_oracle():
    post20, t20, f20 = settle(START, (F(1, 5), F(0), F(4, 5)))
    posteq, teq, feq = settle(START, (F(1), F(0), F(0)))
    bills = path_for("bills_keep", ((F(0),) * 3,), (F(1, 10),))
    bm = metrics(bills)
    recovery = path_for("equal_weight_annual", ((F(1, 10),) * 3,), (F(0),))
    rm = metrics(recovery)
    rows = path_for("equal_weight_annual")
    m = metrics(rows)
    return {
        "schema_version": 1, "author_role": "chief",
        "purpose": "Independent toy oracle; no scenario outcomes or production imports",
        "fee_rate": exact(K),
        "twenty_unit_transfer": {
            "pre_holdings": list(START), "target": ["1/5", "0", "4/5"],
            "transfer": exact(t20), "fee": exact(f20),
            "post_fee_holdings": [exact(x) for x in post20]},
        "all_equity_initial": {"transfer": exact(teq), "fee": exact(feq),
                               "post_fee_wealth": exact(sum(posteq))},
        "keep_bills_inflation_only": {
            "inflation": exact(F(1, 10)), "fee": exact(bills[0]["fee"]),
            "real_terminal": exact(bm["terminal"]),
            "growth_pct_pa": exact(100 * bm["net_returns"][0]),
            "max_real_drawdown_pct": exact(bm["drawdown"]),
            "volatility_pct_pa": bm["volatility"],
            "volatility_note": "Undefined at H=1; do not substitute zero."},
        "initial_fee_then_recovery": {
            "returns": ["1/10"] * 3, "inflation": "0",
            "real_post_fee": exact(recovery[0]["real_post"]),
            "real_terminal": exact(rm["terminal"]),
            "max_real_drawdown_pct": exact(rm["drawdown"])},
        "equal_weight_two_year": {
            "returns": [["1/10", "0", "-1/20"], ["-1/5", "1/10", "0"]],
            "inflation": ["1/50", "0"], "initial_holdings": list(START),
            "transfer": [exact(row["transfer"]) for row in rows],
            "fees": [exact(row["fee"]) for row in rows],
            "post_fee_each_holding": [exact(row["post"][0]) for row in rows],
            "end_holdings": [[exact(v) for v in row["end"]] for row in rows],
            "real_path_initial_trade_end_trade_end": [exact(v) for v in m["real_path"]],
            "annual_net_real_returns": [exact(v) for v in m["net_returns"]],
            "terminal_real_wealth": exact(m["terminal"]),
            "growth_pct_pa": m["growth"], "volatility_pct_pa_ddof1": m["volatility"],
            "max_real_drawdown_pct": exact(m["drawdown"]),
            "trade_share_including_initial_pct": m["trade_in"],
            "trade_share_excluding_initial_pct": m["trade_ex"]},
        "quantile_linear_fixture": {
            "values": [0, 10, 20, 30],
            "p10": quantile([F(0), F(10), F(20), F(30)], F(1, 10)),
            "median": quantile([F(0), F(10), F(20), F(30)], F(1, 2)),
            "p90": quantile([F(0), F(10), F(20), F(30)], F(9, 10))},
        "comparison_tolerance": {"absolute_toy": ABS, "relative_ledger": Decimal("1e-10")}}


class Checks:
    def __init__(self):
        self.rows = []

    def add(self, name, expected, observed, tolerance=None):
        numeric = (isinstance(expected, (int, float, F, Decimal))
                   and not isinstance(expected, bool)
                   and isinstance(observed, (int, float, F, Decimal))
                   and not isinstance(observed, bool))
        residual = abs(dec(expected) - dec(observed)) if numeric else None
        ok = (residual <= (tolerance if tolerance is not None else Decimal(0))) if numeric else expected == observed
        self.rows.append({"name": name, "expected": plain(expected), "observed": plain(observed),
                          "absolute_tolerance": str(tolerance or Decimal(0)) if numeric else None,
                          "absolute_residual": str(residual) if residual is not None else None,
                          "status": "passed" if ok else "failed"})

    def tree(self, name, expected, observed):
        if isinstance(expected, dict):
            self.add(name + ".keys", sorted(expected), sorted(observed) if isinstance(observed, dict) else None)
            if isinstance(observed, dict):
                for key, value in expected.items():
                    self.tree(name + "." + key, value, observed.get(key))
        elif isinstance(expected, (list, tuple)):
            self.add(name + ".length", len(expected), len(observed) if isinstance(observed, list) else None)
            if isinstance(observed, list):
                for i, value in enumerate(expected):
                    self.tree(name + "." + str(i), value, observed[i] if i < len(observed) else None)
        else:
            # Rational strings are checked exactly; floating JSON values at abs 1e-9.
            self.add(name, expected, observed, ABS if isinstance(expected, (F, Decimal, float)) else None)


def plan_checks(c, cfg, text):
    fixed = {
        "schema_version": 1, "plan_id": "development-baselines-v1",
        "status": "specified_pending_independent_review", "split": "development",
        "input_path": "data/development/scenarios_001_120.csv",
        "input_sha256": "9c4ad83f5dda86251a754e126528a71dd930ae88ed7cdb8a0663a327b6bfb7c7",
        "scenario_ids": {"first": 1, "last": 120}, "horizons": [5, 6, 15, 25, 30],
        "comparison_horizon": 30, "profile_horizons": {"A": 5, "B": 15, "C": 30, "D": 25, "E": 6},
        "initial_holdings": [0, 0, 100], "asset_order": ["equity", "bond", "bill_proxy"],
        "fee_rate": 0.0025, "trade_amount_epsilon": 1e-10,
        "fit_parameters": [], "random_seed": None, "metric_contract": "specs/ACCOUNTING.md",
        "quantiles": {"method": "linear", "growth": [0.1, 0.5], "loss": [0.5, 0.9]},
        "severe_case": {"criterion": "maximum_real_drawdown_within_policy_and_horizon", "tie_break": "smallest_scenario_id"},
        "execution": {"cpu_only": True, "max_seconds": 300, "requires_accepted_core": "SOL-001",
                      "requires_input_verification": "HY3-001", "requires_review_of_this_plan": "SOL-002", "final_data_allowed": False},
        "output_files": ["run_manifest.json", "annual_ledgers.csv", "scenario_metrics.csv", "summary.csv", "paired_differences.csv", "checks.json"]}
    for key, value in fixed.items():
        c.add("plan." + key, value, cfg.get(key))
    expected_policies = [
        (POLICIES[0], "keep", "keep", None),
        (POLICIES[1], "rebalance", "rebalance", ["1/3"] * 3),
        (POLICIES[2], "rebalance", "keep", ["1/3"] * 3)]
    c.add("plan.policies", expected_policies,
          [(p["id"], p["first_action"], p["later_action"], p["target"]) for p in cfg["policies"]])
    n = cfg["scenario_ids"]["last"] - cfg["scenario_ids"]["first"] + 1
    p, h, t = len(cfg["policies"]), len(cfg["horizons"]), max(cfg["horizons"])
    computed = {"annual_ledger_rows": p * n * t, "scenario_metric_rows": p * n * h,
                "policy_horizon_summary_rows": p * h, "paired_difference_rows": (p - 1) * n * h}
    c.add("counts.independent_from_config", {"annual_ledger_rows": 10800, "scenario_metric_rows": 1800,
           "policy_horizon_summary_rows": 15, "paired_difference_rows": 1200}, computed)
    c.add("counts.config_matches", computed, cfg["expected_counts"])
    # These are textual consistency checks, not a claim to parse mathematics from prose.
    for phrase in ("H=5,6,15,25,30", "H=5/15/30/25/6", "120*H", "120*(H-1)",
                   "Positive loss difference means worse", "exact ties", "smallest scenario ID",
                   "10,800", "1,800", "1,200", "15 policy/horizon", "No H=1 metrics here",
                   "not the final", "no significance claim", "Prefixes", "before obtaining"):
        c.add("plan.prose." + phrase, True, phrase in text)
    return computed


def supplementary(c):
    policy_metrics = {}
    for policy in POLICIES:
        rows = path_for(policy)
        m = metrics(rows)
        policy_metrics[policy] = m
        c.add("toy." + policy + ".actions", [action(policy, t) for t in (1, 2)],
              [(row["action"], row["target"]) for row in rows])
        for i, row in enumerate(rows):
            stem = "toy." + policy + ".year" + str(i + 1)
            c.add(stem + ".budget", sum(row["pre"]), sum(row["post"]) + row["fee"])
            c.add(stem + ".nonnegative", True, all(v >= 0 for v in row["post"] + row["end"]))
            c.add(stem + ".fee_before_returns", sum(row["end"]),
                  sum(row["post"][j] * (1 + RATES[i][j]) for j in range(3)))
            if row["action"] == "keep":
                c.add(stem + ".keep_dollars", row["pre"], row["post"])
                c.add(stem + ".keep_fee", F(0), row["fee"])
            else:
                c.add(stem + ".exact_target", THIRDS, tuple(v / sum(row["post"]) for v in row["post"]))
                intended = tuple(sum(row["pre"]) / 3 for _ in range(3))
                c.add(stem + ".prorata_fee_funding", (row["fee"] / 3,) * 3,
                      tuple(intended[j] - row["post"][j] for j in range(3)))
        c.add("toy." + policy + ".cpi_compounded", F(51, 50), rows[-1]["cpi_after"])
    # Independently specified trade patterns: the second annual review trades on drift.
    for policy, inclusion, exclusion in ((POLICIES[0], 0, 0), (POLICIES[1], 100, 100), (POLICIES[2], 50, 0)):
        c.add("trade." + policy + ".including", F(inclusion), policy_metrics[policy]["trade_in"])
        c.add("trade." + policy + ".excluding", F(exclusion), policy_metrics[policy]["trade_ex"])
    c.add("trade.threshold_is_strict", [False, False, True],
          [v > F(1, 10**10) for v in (F(0), F(1, 10**10), F(2, 10**10))])
    c.add("trade.zero_transfer_rebalance", (THIRDS, F(0), F(0)), settle(THIRDS, THIRDS))
    c.add("trade.pooled_including_denominator", 240, 120 * 2)
    c.add("trade.pooled_excluding_denominator", 120, 120 * (2 - 1))
    # Distinct end-year net returns: fees belong in the year's wealth ratio.
    annual = policy_metrics[POLICIES[1]]
    c.add("returns.net_year1", -F(181, 36720), annual["net_returns"][0])
    c.add("returns.net_year2", -F(14669, 439200), annual["net_returns"][1])
    c.add("volatility.H1_undefined", None, metrics(path_for(POLICIES[0], RATES[:1], INFLATION[:1]))["volatility"])
    mean = sum(annual["net_returns"]) / 2
    v = sum((x - mean) ** 2 for x in annual["net_returns"])
    c.add("volatility.ddof1_crosscheck", 100 * dec(v).sqrt(), annual["volatility"], ABS)
    c.add("drawdown.post_fee_above_initial_peak", F(1, 4),
          100 * maximum_drawdown([F(100), F(120), F(1197, 10), F(130)]))
    c.add("drawdown.increasing_path_zero", F(0), maximum_drawdown([F(100), F(110), F(120)]))
    c.add("quantiles.unsorted_input", [F(3), F(15), F(27)],
          [quantile([F(30), F(0), F(20), F(10)], q) for q in (F(1, 10), F(1, 2), F(9, 10))])
    severe = [(8, F(12)), (3, F(20)), (2, F(20)), (1, F(5))]
    chosen = min(severe, key=lambda pair: (-pair[1], pair[0]))
    c.add("severe.maximum_then_smallest_id", (2, F(20)), chosen)
    c.add("severe.exact_tie_only", 9,
          min([(1, F(20)), (9, F(20) + F(1, 10**12))], key=lambda pair: (-pair[1], pair[0]))[0])
    # Expose the non-unique locator issue without pretending it changes loss size.
    plateau = [F(100), F(120), F(120), F(90), F(90)]
    maximizers = [(i, j) for j in range(len(plateau)) for i in range(j + 1)
                  if 1 - plateau[j] / plateau[i] == maximum_drawdown(plateau)]
    c.add("suggestion.S1.ambiguous_maximizing_locations", 4, len(maximizers))
    c.add("suggestion.S1.increasing_zero_loss_locations", 3,
          sum(1 for j in range(3) for i in range(j + 1)
              if 1 - [F(100), F(110), F(120)][j] / [F(100), F(110), F(120)][i] == 0))
    paired = {}
    for alt in (POLICIES[0], POLICIES[2]):
        paired[alt] = {key: policy_metrics[alt][key] - annual[key]
                       for key in ("growth", "drawdown", "terminal", "fee_sum", "trade_in", "trade_ex")}
    # Raw toy expected bills holdings are 100*.95 after year 1, then unchanged.
    bills_terminal = F(95) / F(51, 50)
    c.add("paired.bills.terminal_sign_and_amount", bills_terminal - annual["terminal"], paired[POLICIES[0]]["terminal"])
    c.add("paired.bills.loss_sign_and_amount", (100 - bills_terminal) - annual["drawdown"], paired[POLICIES[0]]["drawdown"])
    c.add("paired.bills.signs_growth_loss_wealth_fee_trade_trade", [-1, 1, -1, -1, -1, -1],
          [int(v > 0) - int(v < 0) for v in paired[POLICIES[0]].values()])
    # Buy/hold year 2: initial thirds times (1.10*.80, 1*1.10, .95*1).
    bh_terminal = F(599, 18) * (F(88, 100) + F(11, 10) + F(95, 100)) / F(51, 50)
    c.add("paired.buy_hold.terminal_difference", bh_terminal - annual["terminal"], paired[POLICIES[2]]["terminal"])
    c.add("paired.buy_hold.fee_difference", -F(599, 86400), paired[POLICIES[2]]["fee_sum"])
    c.add("paired.buy_hold.trade_in_difference", F(-50), paired[POLICIES[2]]["trade_in"])
    c.add("paired.buy_hold.trade_ex_difference", F(-100), paired[POLICIES[2]]["trade_ex"])
    c.add("trade.H1_excluding_undefined", None, metrics(path_for(POLICIES[0], RATES[:1], INFLATION[:1]))["trade_ex"])
    comp = path_for(POLICIES[0], ((F(0),) * 3,) * 2, (F(1, 10),) * 2)
    c.add("inflation.compounded_not_added.CPI", F(121, 100), comp[-1]["cpi_after"])
    c.add("inflation.compounded_not_added.real_wealth", F(10000, 121), comp[-1]["real_end"])
    c.add("scenarios.reset_drawdown_peak", [F(0), F(50)],
          [100 * maximum_drawdown(v) for v in ([F(100), F(200)], [F(100), F(50)])])
    c.add("scenarios.concatenation_would_be_wrong", F(75),
          100 * maximum_drawdown([F(100), F(200), F(100), F(50)]))
    for horizon in (5, 6, 15, 25, 30):
        c.add("trade.pooled_denominators.H" + str(horizon), [120 * horizon, 120 * (horizon - 1)],
              [sum(horizon for _ in range(120)), sum(horizon - 1 for _ in range(120))])
    # All horizons use synthetic toy repetitions only; no input CSV is opened.
    long_rates, long_inflation = RATES * 15, INFLATION * 15
    for policy in POLICIES:
        full = path_for(policy, long_rates, long_inflation)
        for horizon in (5, 6, 15, 25, 30):
            short = path_for(policy, long_rates[:horizon], long_inflation[:horizon])
            c.add("prefix." + policy + ".H" + str(horizon), metrics(short), metrics(full[:horizon]))
            expected_in, expected_ex = ((F(0), F(0)) if policy == POLICIES[0] else
                                        (F(100), F(100)) if policy == POLICIES[1] else
                                        (F(100, horizon), F(0)))
            c.add("trade." + policy + ".H" + str(horizon) + ".including", expected_in, metrics(short)["trade_in"])
            c.add("trade." + policy + ".H" + str(horizon) + ".excluding", expected_ex, metrics(short)["trade_ex"])
        changed_rates = long_rates[:9] + ((F(1, 2), F(-1, 4), F(1, 5)),) * 21
        changed_pi = long_inflation[:9] + (F(1, 3),) * 21
        perturbed = path_for(policy, changed_rates, changed_pi)
        c.add("timing." + policy + ".states_through_year9", full[:9], perturbed[:9])
        c.add("timing." + policy + ".actions_through_year10",
              [(r["action"], r["target"]) for r in full[:10]],
              [(r["action"], r["target"]) for r in perturbed[:10]])
        c.add("timing." + policy + ".pre_year10", full[9]["pre"], perturbed[9]["pre"])
        c.add("timing." + policy + ".perturbation_changes_outcome", True, full[9]["real_end"] != perturbed[9]["real_end"])
        independent = path_for(policy, tuple(reversed(RATES)), tuple(reversed(INFLATION)))
        batch = {"toy_left": path_for(policy), "toy_right": independent}
        c.add("scenarios." + policy + ".separate_initial_wealth", [START, START],
              [batch[k][0]["pre"] for k in batch])
        c.add("scenarios." + policy + ".single_equals_batch", path_for(policy), batch["toy_left"])
    return {"policy_metrics_two_year": plain(policy_metrics), "paired_differences_two_year": plain(paired)}


def mutation_checks(c, expected, observed, cfg, text):
    bad = deepcopy(observed)
    bad["equal_weight_two_year"]["fees"][1]["value"] += Decimal("0.000001")
    local = Checks()
    local.tree("oracle", expected, bad)
    c.add("detector.material_oracle_mutation_rejected", True, any(r["status"] == "failed" for r in local.rows))
    bad = deepcopy(observed)
    bad["keep_bills_inflation_only"]["volatility_pct_pa"] = 0
    local = Checks()
    local.tree("oracle", expected, bad)
    c.add("detector.H1_zero_substitution_rejected", True, any(r["status"] == "failed" for r in local.rows))
    bad = deepcopy(cfg)
    bad["profile_horizons"]["E"] = 30
    local = Checks()
    plan_checks(local, bad, text)
    c.add("detector.wrong_profile_horizon_rejected", True, any(r["status"] == "failed" for r in local.rows))


def corrections():
    return [
        {"id": "S1", "severity": "minor", "blocking": False,
         "location": "specs/DEVELOPMENT_BASELINES.md: severe-case peak/trough output",
         "finding": "The required drawdown value and severe scenario are well-defined, but repeated peaks/troughs and zero loss do not determine unique reported locations.",
         "evidence": "Toy [100,120,120,90,90] has four maximizing pairs and 25% loss. [100,110,120] has zero loss and three coincident peak/trough choices.",
         "proposed_correction": "Before accepting the future driver, specify: scan initial (year 0), then each year's post_fee and end observations; update peak only on a strict increase and selected drawdown only on a strict increase; initialize both selected locations to (0,initial). This selects earliest peak/trough, including the zero-loss case. The scenario tie-break remains exact loss then smallest scenario ID.",
         "reason_not_blocking": "Every maximizing pair reports the same numeric loss. The plan explicitly requires a separate driver review before dispatch; fix this reporting convention there."},
        {"id": "S2", "severity": "minor", "blocking": False,
         "location": "specs/DEVELOPMENT_BASELINES.md: annual_ledgers.csv / paired_differences.csv",
         "finding": "Net annual real returns are derivable but not explicitly named as ledger columns; paired CSV split and baseline identity are implicit in the manifest/prose.",
         "proposed_correction": "Make the future CSV schema explicit: annual_net_real_return=real_end_t/real_end_(t-1)-1 with real_end_0=100; name this a decimal return, optionally add annual_net_real_return_pct=100*annual_net_real_return. Include split, alternative_policy, reference_policy=equal_weight_annual and horizon in paired_differences.csv, plus units for each difference. Add profile-to-horizon mapping to the run manifest. These columns make detached evidence self-describing.",
         "reason_not_blocking": "All quantities and identities are already recoverable exactly from specified holdings, CPI, keys and manifest. No new mathematical parameter is needed."},
        {"id": "S3", "severity": "minor", "blocking": False,
         "location": "specs/ACCOUNTING.md: trade share excluding initial / H=1",
         "finding": "H=1 fluctuation is explicitly undefined in the oracle; H=1 trade share excluding initial would also have a zero denominator.",
         "proposed_correction": "For any later H=1 consumer, return null for volatility and trade_share_excluding_initial_pct, retain later_trade_count=0 and later_review_count=0, and reject attempts to coerce either undefined statistic to zero. The present pilot remains restricted to H in {5,6,15,25,30} and finite defined metrics.",
         "reason_not_blocking": "The present plan explicitly excludes H=1 metrics; all actual denominators are positive."}]


def build():
    c = Checks()
    hashes, blobs = source_blobs()
    c.add("environment.python_major_minor", [3, 12], list(sys.version_info[:2]))
    c.add("provenance.head", BASE, git("rev-parse", "HEAD").decode().strip())
    c.add("provenance.branch", "work/sol/SOL-002-a1", git("branch", "--show-current").decode().strip())
    for name, digest in PINNED.items():
        c.add("provenance.sha256." + name, digest, hashes[name]["sha256"])
        index_oid = git("rev-parse", BASE + ":" + name).decode().strip()
        c.add("provenance.git_blob." + name, index_oid, hashes[name]["git_blob_sha1"])
        # Normalize checkout newlines only for comparison; hashes always use Git bytes.
        c.add("provenance.worktree_matches." + name, blobs[name].replace(b"\r\n", b"\n").decode(),
              (ROOT / name).read_bytes().replace(b"\r\n", b"\n").decode())
    task = json.loads((ROOT / ".runtime/task.json").read_text(encoding="utf-8-sig"))
    c.add("task.base", BASE, task["base_commit"])
    c.add("task.identity", ["SOL-002", 1, "sol"], [task["id"], task["attempt"], task["owner"]])
    c.add("task.paths", ["audit/SOL-002"], task["allowed_paths"])
    for name, digest in task["parameters"]["source_sha256"].items():
        c.add("task.pinned_source." + name, digest, hashes[name]["sha256"])
    cfg = json.loads(blobs["specs/development_baselines_v1.json"])
    chief = json.loads(blobs["audit/chief/accounting_oracle.json"], parse_float=Decimal)
    text = blobs["specs/DEVELOPMENT_BASELINES.md"].decode()
    expected = expected_oracle()
    c.tree("oracle", expected, chief)
    counts = plan_checks(c, cfg, text)
    toys = supplementary(c)
    mutation_checks(c, expected, chief, cfg, text)
    failures = [r for r in c.rows if r["status"] == "failed"]
    residuals = [(Decimal(r["absolute_residual"]), r["name"]) for r in c.rows if r["absolute_residual"] is not None]
    largest, largest_name = max(residuals)
    report = {"schema_version": 1, "task_id": "SOL-002", "reviewed_base_commit": BASE,
              "hash_basis": "Canonical Git blob bytes", "source_git_blobs": hashes,
              "verifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "arithmetic": "Fraction exact money/CPI/returns; Decimal precision 70 for roots and dispersion; no third-party imports",
              "oracle_comparison_absolute_tolerance": str(ABS),
              "status": "failed" if failures else "passed", "check_count": len(c.rows),
              "oracle_leaf_check_count": sum(r["name"].startswith("oracle.") and not r["name"].endswith((".keys", ".length")) for r in c.rows),
              "largest_absolute_residual": str(largest), "largest_residual_check": largest_name,
              "counts": counts, "failures": failures, "checks": c.rows, "toy_results": toys,
              "limitations": ["Pinned design and toy arithmetic only; not a production implementation review.",
                              "No scenario CSV, raw data, final data, performance or later production code read.",
                              "Input hash declaration checked against pinned configuration/task only; actual dataset hash remains HY3's separate responsibility.",
                              "Toy prefix, separation and timing checks validate this independent mathematical interpretation only."]}
    return report


def findings_for(report):
    return {"schema_version": 1, "task_id": "SOL-002", "reviewed_base_commit": BASE,
            "hash_basis": "Canonical Git blob bytes", "source_git_blobs": report["source_git_blobs"],
            "status": report["status"],
            "verdict": "Chief design and all toy numeric expectations pass this review; no material mathematical defect found." if report["status"] == "passed" else "Review failed; inspect saved diagnosis before dispatch.",
            "blockers": [{"id": "validation:" + r["name"], "evidence": r, "proposed_correction": "Resolve this discrepancy against the locked contract; preserve failed evidence and require chief acceptance."} for r in report["failures"]],
            "corrections": corrections(), "unsupported_recommendations": [],
            "missing_mathematical_parameters": [],
            "evidence": {"verification_file": "audit/SOL-002/verification.json", "checks": report["check_count"],
                         "largest_absolute_residual": report["largest_absolute_residual"], "absolute_tolerance": str(ABS)},
            "limitations": report["limitations"]}


def dump(file, value):
    file.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="recompute and verify existing evidence; never regenerate it")
    args = parser.parse_args()
    with localcontext() as context:
        context.prec = 70
        report = build()
    findings = findings_for(report)
    saved_report, saved_findings = OUT / "verification.json", OUT / "findings.json"
    if args.check:
        errors = []
        for file, expected in ((saved_report, report), (saved_findings, findings)):
            try:
                observed = json.loads(file.read_text(encoding="utf-8"))
                if observed != expected:
                    errors.append(file.name + ": saved evidence differs from independent recomputation")
            except (OSError, ValueError) as exc:
                errors.append(file.name + ": " + str(exc))
        if report["status"] == "failed" or errors:
            # Save diagnosis under its content hash, preserving both original artifacts.
            diagnosis = {"schema_version": 1, "status": "failed", "errors": errors,
                         "recomputed_findings": findings, "recomputed_verification": report}
            content = json.dumps(diagnosis, sort_keys=True).encode()
            diagnostic_path = OUT / ("diagnosis-" + hashlib.sha256(content).hexdigest()[:16] + ".json")
            if not diagnostic_path.exists():
                dump(diagnostic_path, diagnosis)
            print("FAILED: " + "; ".join(errors + [r["name"] for r in report["failures"]]))
            print("Diagnosis preserved: " + diagnostic_path.name)
            return 1
        print("PASS: " + str(report["check_count"]) + " checks; chief oracle and saved evidence verified; max residual " + report["largest_absolute_residual"])
        return 0
    if saved_report.exists() or saved_findings.exists():
        print("Refusing to overwrite evidence. Use --check. Preserve any earlier failed evidence explicitly.")
        return 2
    dump(saved_report, report)
    dump(saved_findings, findings)
    print(report["status"].upper() + ": initialized " + str(report["check_count"]) + " checks; max residual " + report["largest_absolute_residual"])
    if report["failures"]:
        print(json.dumps(report["failures"], indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
