"""Pure fixed-v2 analysis of explicit canonical scenario metrics.

No input loading, simulation, provenance certification, or result writing occurs
here. 'development' checks shape only; it cannot authenticate caller data origin.
"""

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
from numbers import Real

from .experiments import COMMON_UNITS, METRIC_VALUES, PAIRED_UNITS
from .metrics import linear_quantile

# Semantic config pin, not a claim about source/input authenticity.
_CONFIG_DIGEST = "9ba5df43bba076eac1120e7aaafc7ea4c2c97797bf424f665be6d27f5c874abc"
_MODES = ("bills_keep", "equal_weight_annual", "equal_weight_buy_hold",
          "conservative_cost", "balanced_cost", "growth_cost",
          "balanced_context", "balanced_adaptive")
_FEES = (.0025, .005)
_HORIZONS = (5, 6, 15, 25, 30)
_CLASSES = ("conservative", "balanced", "growth")
_CONTRASTS = tuple((m, "equal_weight_annual") for m in _MODES if m != "equal_weight_annual") + (
    ("balanced_context", "balanced_cost"),
    ("balanced_adaptive", "balanced_context"),
    ("balanced_adaptive", "balanced_cost"))
_DIAGNOSTICS = ("human_review_count", "human_review_share_pct", "first_latch_year",
                "target_change_count", "first_deployment_year", "initial_allocation_deferred")
_DIFFERENCE_DIAGNOSTICS = ("human_review_count", "human_review_share_pct", "target_change_count")
_COUNTS = ("trade_count", "review_count", "later_trade_count", "later_review_count")
_LOCATIONS = ("drawdown_peak_year", "drawdown_peak_kind", "drawdown_trough_year", "drawdown_trough_kind")
_FIELDS = frozenset(("mode", "fee_rate", "scenario_id", "fold_id", "horizon", "split",
                     "annual_real_volatility_pct", *METRIC_VALUES, *_COUNTS, *_LOCATIONS,
                     *_DIAGNOSTICS, *COMMON_UNITS))
_GATE_UNITS = {"growth_difference_units": "percentage points per year",
               "loss_difference_units": "percentage points; positive is worse",
               "trade_share_difference_units": "percentage points",
               "human_review_share_difference_units": "percentage points",
               "count_difference_units": "reviews or executed requests"}


@dataclass(frozen=True)
class AnalysisTables:
    paired_differences: list
    comparison_gates: list
    selection: dict
    profile_screen: list
    profile_recommendations: list


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(name + " requires a finite real number, not a label/bool")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(name + " is nonfinite")
    return value


def _integer(value, name, minimum, maximum=None):
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        raise ValueError(name + " requires an integer in its prescribed range")


def _validate_config(config):
    if not isinstance(config, dict):
        raise ValueError("config must be the fixed v2 dictionary")
    try:
        encoded = json.dumps(config, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (ValueError, TypeError) as error:
        raise ValueError("invalid fixed v2 config") from error
    if hashlib.sha256(encoded).hexdigest() != _CONFIG_DIGEST:
        raise ValueError("fixed v2 config differs; parameter/schema changes require a successor")


def _validate_metrics(metrics, split):
    if type(split) is not str or split not in ("synthetic", "development"):
        raise ValueError("only explicit synthetic/development splits; no final support")
    indexed = {}
    ids = set()
    for supplied in metrics:
        if not isinstance(supplied, Mapping) or set(supplied) != _FIELDS:
            raise ValueError("exact canonical metric schema required (missing/extra keys)")
        row = dict(supplied)
        if row["split"] != split or type(row["split"]) is not str:
            raise ValueError("metric split mismatch")
        mode = row["mode"]
        if type(mode) is not str or mode not in _MODES:
            raise ValueError("unknown mode")
        fee = _number(row["fee_rate"], "fee_rate")
        if fee not in _FEES:
            raise ValueError("wrong fee_rate")
        sid, fold, h = row["scenario_id"], row["fold_id"], row["horizon"]
        _integer(sid, "scenario_id", 1)
        _integer(fold, "fold_id", 0, 3)
        _integer(h, "horizon", 1, 30)
        if fold != (sid - 1) % 4 or h not in _HORIZONS:
            raise ValueError("wrong fixed fold/horizon")
        for name in (*METRIC_VALUES, "annual_real_volatility_pct"):
            row[name] = _number(row[name], name)
        if not (0 <= row["max_real_drawdown_pct"] <= 100):
            raise ValueError("nonsensical real drawdown")
        if (row["net_real_cagr_pct"] <= -100 or row["terminal_real_wealth"] <= 0
                or row["nominal_fee_sum"] < 0 or row["annual_real_volatility_pct"] < 0):
            raise ValueError("nonsensical required metric")
        for name in _COUNTS:
            _integer(row[name], name, 0, h)
        if (row["review_count"] != h or row["later_review_count"] != h - 1
                or row["later_trade_count"] > h - 1
                or row["trade_count"] - row["later_trade_count"] not in (0, 1)):
            raise ValueError("inconsistent review/trade counts")
        for name, numerator, denominator in (
                ("trade_share_pct", row["trade_count"], h),
                ("trade_share_ex_initial_pct", row["later_trade_count"], h - 1)):
            if not 0 <= row[name] <= 100 or not math.isclose(
                    row[name], 100 * numerator / denominator, rel_tol=1e-10, abs_tol=1e-9):
                raise ValueError("inconsistent trade share")
        points = []
        for prefix in ("peak", "trough"):
            year = row["drawdown_" + prefix + "_year"]
            kind = row["drawdown_" + prefix + "_kind"]
            _integer(year, "drawdown year", 0, h)
            if type(kind) is not str or kind not in ("initial", "post_fee", "end"):
                raise ValueError("invalid drawdown location")
            if (year == 0) != (kind == "initial"):
                raise ValueError("invalid initial drawdown location")
            points.append((year, {"initial": 0, "post_fee": 1, "end": 2}[kind]))
        if points[0] > points[1]:
            raise ValueError("drawdown peak follows trough")
        for name, expected in COMMON_UNITS.items():
            if type(row[name]) is not str or row[name] != expected:
                raise ValueError("canonical units mismatch: " + name)
        if mode in _MODES[:3]:
            if any(row[name] is not None for name in _DIAGNOSTICS):
                raise ValueError("reference diagnostics must be null/inapplicable")
        else:
            for name in ("human_review_count", "target_change_count"):
                _integer(row[name], name, 0, h)
            share = _number(row["human_review_share_pct"], "human_review_share_pct")
            if not 0 <= share <= 100 or not math.isclose(
                    share, 100 * row["human_review_count"] / h, rel_tol=1e-10, abs_tol=1e-9):
                raise ValueError("inconsistent human-review share")
            row["human_review_share_pct"] = share
            for name in ("first_latch_year", "first_deployment_year"):
                if row[name] is not None:
                    _integer(row[name], name, 1, h)
            if type(row["initial_allocation_deferred"]) is not bool:
                raise ValueError("initial_allocation_deferred must be boolean")
            latch = row["first_latch_year"]
            if ((latch is None) != (row["human_review_count"] == 0)
                    or (latch is not None and row["human_review_count"] != h - latch + 1)):
                raise ValueError("inconsistent latched review diagnostics")
        key = (mode, fee, h, sid)
        if key in indexed:
            raise ValueError("duplicate metric key")
        indexed[key] = row
        ids.add(sid)
    n = len(ids)
    if n == 0 or n % 4 or ids != set(range(1, n + 1)):
        raise ValueError("scenario IDs must be consecutive 1..N, positive multiple of four")
    if split == "development" and n != 120:
        raise ValueError("development shape is exactly IDs 1..120; labels do not prove origin")
    if len(indexed) != len(_MODES) * len(_FEES) * len(_HORIZONS) * n:
        raise ValueError("missing/extra/mismatched scenario-case grid")
    return indexed, tuple(range(1, n + 1))


def _key(row):
    return {name: row[name] for name in ("mode", "fee_rate", "horizon", "scenario_id", "fold_id", "split")}


def _q(rows, name, p):
    return linear_quantile([r[name] for r in rows], p)


def _comparison(candidate, reference, fee, h, ids, indexed, split):
    aa = [indexed[candidate, fee, h, s] for s in ids]
    bb = [indexed[reference, fee, h, s] for s in ids]
    paired = []
    for a, b in zip(aa, bb):
        differences = {name + "_difference": a[name] - b[name] for name in METRIC_VALUES}
        for name in _DIFFERENCE_DIAGNOSTICS:
            differences[name + "_difference"] = (None if a[name] is None or b[name] is None
                                                 else a[name] - b[name])
        paired.append({"candidate_mode": candidate, "reference_mode": reference,
                       "fee_rate": fee, "horizon": h, "scenario_id": a["scenario_id"],
                       "fold_id": a["fold_id"], "split": split, **differences,
                       **PAIRED_UNITS, **_GATE_UNITS})
    gain = _q(paired, "net_real_cagr_pct_difference", .5)
    tail_growth = _q(aa, "net_real_cagr_pct", .1) - _q(bb, "net_real_cagr_pct", .1)
    tail_loss = _q(aa, "max_real_drawdown_pct", .9) - _q(bb, "max_real_drawdown_pct", .9)
    folds = []
    for f in range(4):
        rows = [r for r in paired if r["fold_id"] == f]
        median = _q(rows, "net_real_cagr_pct_difference", .5)
        folds.append({"fold_id": f, "scenario_count": len(rows),
                      "median_paired_growth_gain_pp": median, "positive": median > 0})
    positive = sum(f["positive"] for f in folds)
    flags = {"gain_at_least_0_10": gain >= .10,
             "tail_growth_at_least_minus_0_10": tail_growth >= -.10,
             "tail_loss_at_most_1_00": tail_loss <= 1.00,
             "at_least_three_positive_folds": positive >= 3}
    medians = {}
    for name in (*METRIC_VALUES, *_DIFFERENCE_DIAGNOSTICS):
        field = name + "_difference"
        medians[field] = None if paired[0][field] is None else _q(paired, field, .5)
    summary = {"candidate_mode": candidate, "reference_mode": reference,
               "fee_rate": fee, "horizon": h, "split": split,
               "scenario_count": len(ids), "scenario_ids": list(ids),
               "median_paired_growth_gain_pp": gain,
               "marginal_p10_growth_difference_pp": tail_growth,
               "marginal_p90_loss_difference_pp": tail_loss,
               "folds": folds, "positive_fold_count": positive,
               "flags": flags, "passed": all(flags.values()),
               "reasons": [name for name, passed in flags.items() if not passed],
               "median_paired_differences": medians, **PAIRED_UNITS, **_GATE_UNITS}
    return paired, summary


def _support(mode, fee, gates):
    controls = {"balanced_cost": (), "balanced_context": ("balanced_cost",),
                "balanced_adaptive": ("balanced_context", "balanced_cost")}[mode]
    facts = [deepcopy(gates[mode, ref, fee, 30]) for ref in controls]
    return {"mode": mode, "fee_rate": fee, "horizon": 30,
            "required_comparators": list(controls), "comparisons": facts,
            "supported": all(r["passed"] for r in facts) if facts else None,
            "reasons": (["no_added_complexity_selected"] if not facts else
                        [r["reference_mode"] + ":" + reason for r in facts for reason in r["reasons"]])}


def _profiles(indexed, ids, config, split):
    screens, recommendations = [], []
    rules = config["suitability"]
    for fee in _FEES:
        for profile, details in config["profiles"].items():
            h, tol, liquidity = details["horizon"], details["loss_tolerance_pct"], details["liquidity"]
            candidates = []
            for rank, cls in enumerate(_CLASSES):
                mode = cls + "_cost"
                rows = [indexed[mode, fee, h, s] for s in ids]
                severe = min(rows, key=lambda r: (-r["max_real_drawdown_pct"], r["scenario_id"]))
                p10 = _q(rows, "net_real_cagr_pct", .1)
                p90 = _q(rows, "max_real_drawdown_pct", .9)
                reserve = config["targets"][cls][2]
                if reserve == "1/3":
                    reserve = 1 / 3
                horizon_cap = 0 if h <= 6 else 1 if h < 20 else 2
                flags = {"horizon_eligible": rank <= horizon_cap,
                         "willingness_eligible": cls in rules["eligible_classes_before_outcome_screens"][profile],
                         "liquidity_pass": reserve >= rules["minimum_target_bill"][liquidity],
                         "risk_pass": p90 <= tol, "purchasing_power_pass": p10 >= 0}
                exceed = sum(r["max_real_drawdown_pct"] > tol for r in rows)
                screen = {"profile": profile, "candidate_class": cls, "mode": mode,
                          "fee_rate": fee, "horizon": h, "split": split,
                          "loss_tolerance_pct": tol, "liquidity": liquidity,
                          "target_bill_reserve": reserve,
                          "minimum_target_bill_reserve": rules["minimum_target_bill"][liquidity],
                          "median_growth_pct": _q(rows, "net_real_cagr_pct", .5),
                          "p10_growth_pct": p10, "median_loss_pct": _q(rows, "max_real_drawdown_pct", .5),
                          "p90_loss_pct": p90, "severe_loss_pct": severe["max_real_drawdown_pct"],
                          "severe_scenario_id": severe["scenario_id"],
                          "exceedance_count": exceed, "scenario_count": len(ids),
                          "exceedance_denominator": len(ids), "exceedance_fraction": exceed / len(ids),
                          "flags": flags, "qualified": all(flags.values()),
                          "reasons": [name for name, passed in flags.items() if not passed],
                          "source_metric_keys": [_key(r) for r in rows],
                          "status": "provisional", "personalized_overlay_pending": True,
                          "growth_units": "percent/year", "loss_units": "percent of running real peak",
                          "exceedance_units": "fraction of scenarios"}
                candidates.append(screen)
                screens.append(screen)
            qualifying = [r for r in candidates if r["qualified"]]
            best = max((r["median_growth_pct"] for r in qualifying), default=None)
            near = [r for r in qualifying if best - r["median_growth_pct"] <= .10]
            chosen = near[0] if near else None
            recommendations.append({"profile": profile, "fee_rate": fee, "horizon": h, "split": split,
                "loss_tolerance_pct": tol, "liquidity": liquidity,
                "selected_class": chosen["candidate_class"] if chosen else None,
                "selected_mode": chosen["mode"] if chosen else None,
                "action": "provisional_assignment" if chosen else "human_review",
                "status": "provisional", "personalized_overlay_pending": True,
                "qualifying_classes": [r["candidate_class"] for r in qualifying],
                "indifference_classes": [r["candidate_class"] for r in near],
                "maximum_qualifying_median_growth_pct": best,
                "indifference_pp_per_year": .10,
                "candidate_outcomes": [{"candidate_class": r["candidate_class"], "mode": r["mode"],
                    "qualified": r["qualified"], "reasons": list(r["reasons"]),
                    "median_growth_pct": r["median_growth_pct"],
                    "gap_from_best_pp_per_year": None if best is None else best - r["median_growth_pct"],
                    "source_metric_keys": deepcopy(r["source_metric_keys"])} for r in candidates],
                "reasons": ["within_0_10_prefer_least_growth"] if chosen else ["no_qualifying_class"],
                "failed_candidate_reasons": {r["candidate_class"]: list(r["reasons"]) for r in candidates},
                "pending_holdings_initial": "retain original bills",
                "pending_holdings_existing": "keep current component dollars",
                "personalized_follow_up": {"mode": chosen["mode"] if chosen else None,
                    "horizon": h, "review_drawdown_pct": tol,
                    "rescreen": ["risk", "purchasing_power"],
                    "failure_action": "human_review_no_reselection"}})
    return screens, recommendations


def build_analysis_tables(metrics, *, config, split):
    """Analyze a complete fixed-v2 grid; validate shape without authenticating origin.

    Returned records are detached from input/config and from other tables. Policy
    decisions use direct inclusive float comparisons, with no added tolerance.
    """
    _validate_config(config)
    indexed, ids = _validate_metrics(metrics, split)
    paired, comparisons, gates = [], [], {}
    for fee in _FEES:
        for candidate, reference in _CONTRASTS:
            for h in _HORIZONS:
                rows, summary = _comparison(candidate, reference, fee, h, ids, indexed, split)
                paired.extend(rows)
                comparisons.append(summary)
                gates[candidate, reference, fee, h] = summary
    context = _support("balanced_context", .0025, gates)
    adaptive = _support("balanced_adaptive", .0025, gates)
    primary = ("balanced_adaptive" if adaptive["supported"] else
               "balanced_context" if context["supported"] else "balanced_cost")
    selection = {"split": split, "primary_fee_rate": .0025, "comparison_horizon": 30,
                 "selected_mode": primary, "role": "research_comparison_only",
                 "context": context, "adaptive": adaptive,
                 "primary_support": _support(primary, .0025, gates),
                 "doubled_fee_support": _support(primary, .005, gates),
                 "sensitivity_may_reselect": False,
                 "reasons": ["adaptive_passes_both_fixed_controls"] if primary == "balanced_adaptive" else
                            ["context_passes_fixed_control"] if primary == "balanced_context" else
                            ["no_added_complexity_selected"]}
    screens, recommendations = _profiles(indexed, ids, config, split)
    return AnalysisTables(paired, comparisons, selection, screens, recommendations)
