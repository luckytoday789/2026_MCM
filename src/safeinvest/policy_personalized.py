"""Provisional pure personalized adapter; independent review pending.

Explicit rows/priors only, no files, source authentication, production CLI or
final support. A future bridge must authenticate the upstream assignment before
calling this seam. Synthetic success is not a personalized recommendation.
"""
from dataclasses import dataclass, fields
import math
from numbers import Real

from .backtest import simulate_policy
from .experiments import COMMON_UNITS, ledger_row, metric_row, summary_row
from .metrics import linear_quantile
from .policy_calibration import fold_id
from .policy_cases import CaseTables, _rows, _priors, _normalize, _diagnostics
from .policy_pilot import CostAwarePolicy, PolicyReview, TARGETS

PROFILES = {"A": (5, 10, "high"), "B": (15, 25, "medium"),
            "C": (30, 40, "low"), "D": (25, 15, "medium"), "E": (6, 35, "high")}
CLASSES = ("conservative", "balanced", "growth")
RESERVES = {"high": .6, "medium": .25, "low": .1}
_STATISTICS = ("median_growth_pct", "p10_growth_pct", "median_loss_pct", "p90_loss_pct",
    "median_volatility_pct", "median_terminal_real_wealth", "median_nominal_fee_sum",
    "pooled_trade_count", "pooled_review_count", "pooled_later_trade_count",
    "pooled_later_review_count", "pooled_trade_share_pct", "pooled_trade_share_ex_initial_pct",
    "pooled_human_review_count", "pooled_human_review_share_pct", "pooled_target_change_count",
    "severe_scenario_id", "severe_net_real_cagr_pct", "severe_max_real_drawdown_pct",
    "severe_terminal_real_wealth", "severe_drawdown_peak_year", "severe_drawdown_peak_kind",
    "severe_drawdown_trough_year", "severe_drawdown_trough_kind", "severe_trade_share_pct",
    "severe_trade_share_ex_initial_pct")


@dataclass(frozen=True)
class PersonalizedCase:
    case: CaseTables | None
    rescreen: dict


def _outcome_screen(growth, loss, tolerance):
    """Pure scalar screen; direct inclusive comparisons, strict exceedances."""
    growth, loss = tuple(growth), tuple(loss)
    if not growth or len(growth) != len(loss):
        raise ValueError("paired nonempty scenario outcomes required")
    if any(isinstance(x, bool) or not isinstance(x, Real) or not math.isfinite(x)
           for x in (*growth, *loss, tolerance)):
        raise ValueError("finite numeric outcomes/tolerance required")
    if not 0 <= tolerance <= 100 or any(not 0 <= x <= 100 for x in loss):
        raise ValueError("loss/tolerance must be percentages in 0..100")
    p10 = linear_quantile(growth, .1)
    p90 = linear_quantile(loss, .9)
    risk, power = p90 <= tolerance, p10 >= 0
    exceeded = sum(x > tolerance for x in loss)
    return {"risk_pass": risk, "purchasing_power_pass": power,
            "exceedance_count": exceeded, "exceedance_fraction": exceeded / len(loss),
            "reasons": ([] if risk else ["p90_loss_exceeds_tolerance"]) +
                       ([] if power else ["p10_growth_negative"])}


def build_personalized_case_tables(rows, *, calibrations, profile_id, proposed_class,
                                   fee_rate, split, upstream_reasons=()):
    """Compute one own-horizon case or preserve an explicit no-run referral.

    This checks fixed profile eligibility, not upstream assignment authenticity.
    The generic case source/API stays unchanged. Priors retain their full training
    horizon; only evaluation ends at H. Passing split='development' validates shape,
    not origin. Referrals require rows=calibrations=None and cannot execute a policy.
    """
    if type(split) is not str or split not in ("synthetic", "development"):
        raise ValueError("only synthetic/development supported; no final support")
    if type(profile_id) is not str or profile_id not in PROFILES:
        raise ValueError("unknown fixed profile")
    if type(proposed_class) not in (str, type(None)) or (proposed_class is not None and proposed_class not in CLASSES):
        raise ValueError("only fixed conservative/balanced/growth class or referral")
    if isinstance(fee_rate, bool) or not isinstance(fee_rate, Real) or fee_rate not in (.0025, .005):
        raise ValueError("only the two fixed fee rates")
    if not isinstance(upstream_reasons, (tuple, list)) or any(type(r) is not str or not r for r in upstream_reasons):
        raise ValueError("upstream reasons must be explicit nonempty strings")
    h, tolerance, liquidity = PROFILES[profile_id]
    k = float(fee_rate)
    mode = None if proposed_class is None else proposed_class + "_cost"
    common = {"profile_id": profile_id, "split": split, "fee_rate": k,
              "horizon": h, "loss_tolerance_pct": tolerance, "liquidity": liquidity,
              "review_threshold_pct": tolerance, "proposed_class": proposed_class, "mode": mode,
              "upstream_reasons": list(upstream_reasons), "source_verified": False,
              "pending_holdings_initial": "retain original bills",
              "pending_holdings_existing": "keep current component dollars",
              **COMMON_UNITS, "growth_units": "percent/year"}
    if proposed_class is None:
        if rows is not None or calibrations is not None or not upstream_reasons:
            raise ValueError("referral requires absent rows/priors and preserved upstream reasons")
        return PersonalizedCase(None, common | dict.fromkeys(_STATISTICS) | {
            "status": "upstream_referral", "simulation_status": "not_run_upstream_referral",
            "recommended_class": None, "scenario_count": 0, "denominator": 0,
            "risk_pass": None, "purchasing_power_pass": None, "horizon_pass": None,
            "reserve_pass": None, "exceedance_count": None, "exceedance_fraction": None,
            "reasons": list(upstream_reasons)})
    cap = 0 if h <= 6 else 1 if h <= 19 else 2
    horizon_pass = CLASSES.index(proposed_class) <= cap
    reserve_pass = TARGETS[proposed_class][2] >= RESERVES[liquidity]
    if not (horizon_pass and reserve_pass):
        raise ValueError("upstream fixed class violates horizon/reserve eligibility")
    selected, scenarios, periods = _rows(rows, split)
    if periods < h:
        raise ValueError("scenario paths shorter than own horizon")
    priors = _priors(calibrations, scenarios, periods)
    annual, metrics, decisions, scores = [], [], [], []
    review_fields = tuple(f.name for f in fields(PolicyReview) if f.name != "scores")
    def tag(row):
        return row | {"profile_id": profile_id, "review_threshold_pct": tolerance}
    for s in range(1, scenarios + 1):
        f = fold_id(s)
        policy = CostAwarePolicy(mode, priors[f], fee_rate=k, review_drawdown_pct=tolerance)
        result = simulate_policy(selected[(s-1)*periods:s*periods], horizon=h,
                                 split=split, callback=policy, fee_rate=k)
        reviews = tuple(policy.reviews)
        annual.extend(tag(_normalize(ledger_row(mode, split, e), mode, k, f)) for e in result.ledger)
        metrics.append(tag(_normalize(metric_row(mode, result, h), mode, k, f) | _diagnostics(reviews, h)))
        for review in reviews:
            key = {"split": split, "mode": mode, "fee_rate": k, "scenario_id": s,
                   "fold_id": f, "period": review.period, "profile_id": profile_id,
                   "review_threshold_pct": tolerance}
            decisions.append(key | {name: getattr(review, name) for name in review_fields
                                    if name not in ("scenario_id", "period")})
            for score in review.scores:
                scores.append(key | {"target_name": score.name,
                    **dict(zip(("target_equity", "target_bond", "target_bill_proxy"), score.target)),
                    **{name: getattr(score, name) for name in ("ce_target", "tau", "fee_fraction",
                        "pre_cost_benefit", "modeled_fee_impact", "conservative_score", "true_net_ce")}})
    summary = tag(_normalize(summary_row(mode, h, metrics), mode, k))
    count = sum(r["human_review_count"] for r in metrics)
    summary.update(pooled_human_review_count=count, pooled_human_review_share_pct=100*count/(scenarios*h),
                   pooled_target_change_count=sum(r["target_change_count"] for r in metrics))
    screen = _outcome_screen([r["net_real_cagr_pct"] for r in metrics],
                             [r["max_real_drawdown_pct"] for r in metrics], tolerance)
    passes = screen["risk_pass"] and screen["purchasing_power_pass"]
    rescreen = common | {name: summary[name] for name in _STATISTICS} | screen | {
        "status": "eligible_after_personalized_development_rescreen" if passes else "human_review_after_rescreen",
        "simulation_status": "completed", "recommended_class": proposed_class if passes else None,
        "scenario_count": scenarios, "denominator": scenarios, "horizon_pass": True, "reserve_pass": True}
    tables = dict(annual_ledgers=tuple(annual), scenario_metrics=tuple(metrics), summary=(summary,),
                  decisions=tuple(decisions), target_scores=tuple(scores))
    case = CaseTables(**tables, counts={name: len(records) for name, records in tables.items()},
        units={"growth": "percent/year", "loss": "percent of running real peak",
               "volatility": "percentage points; annual sample ddof=1", "fee": "nominal wealth units",
               "trade_share": "percent of annual reviews", "ce": "annual real gross factor",
               "wealth": "nominal units; real at CPI_0=1"},
        metadata={"split": split, "mode": mode, "fee_rate": k, "horizons": (h,),
                  "scenario_count": scenarios, "input_periods": periods, "profile_id": profile_id,
                  "diagnostics_applicable": True, "source_verified": False,
                  "review_drawdown_pct": tolerance})
    return PersonalizedCase(case, rescreen)
