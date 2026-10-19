"""Pure case tables from explicit rows and preconstructed out-of-fold priors.

No input provenance is certified here. A later writer must bind original bytes
and accepted sources. No files, fitting, saved runs, or final split are supported.
"""

from collections.abc import Mapping
from dataclasses import dataclass, fields
import math
import re

from .backtest import simulate_policy
from .baselines import POLICIES
from .experiments import ledger_row, metric_row, summary_row
from .policy_calibration import CalibrationBundle, FoldCalibration, FIELDS, fold_id
from .policy_pilot import CENTRAL_TARGET, CostAwarePolicy, EmpiricalPrior, PolicyReview, real_gross


@dataclass(frozen=True)
class CaseTables:
    """Fresh ordinary record containers; output records may be edited by callers."""

    annual_ledgers: tuple
    scenario_metrics: tuple
    summary: tuple
    decisions: tuple
    target_scores: tuple
    counts: dict
    units: dict
    metadata: dict


def _rows(rows, split):
    rows = tuple(rows)
    if not rows:
        raise ValueError("nonempty complete scenario/period rectangle required")
    # Determine shape from keys only; no fit or policy computation occurs here.
    if any(not isinstance(row, Mapping) or tuple(row) != FIELDS for row in rows):
        raise ValueError("exact ordered six-field schema required")
    periods = 0
    for row in rows:
        if str(row["scenario_id"]) != "1":
            break
        periods += 1
    if periods < 1 or periods > 30 or len(rows) % periods:
        raise ValueError("complete ordered paths of 1..30 years required")
    scenarios = len(rows) // periods
    if (split == "development" and (scenarios, periods) != (120, 30)):
        raise ValueError("development requires IDs 1..120 and years 1..30")
    if scenarios < 4 or scenarios % 4:
        raise ValueError("scenario count must be a positive multiple of four")
    copied = []
    for index, row in enumerate(rows):
        s, t = divmod(index, periods)
        for key, expected in (("scenario_id", s+1), ("period", t+1)):
            v = row[key]
            if type(v) not in (int, str) or str(v) != str(expected):
                raise ValueError("complete unique ordered integer scenario/period keys required")
        numbers = []
        for name in FIELDS[2:]:
            value = row[name]
            if isinstance(value, bool):
                raise ValueError("boolean outcomes are invalid")
            try:
                number = float(value)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("finite numeric outcomes required") from exc
            if not math.isfinite(number) or number <= -1:
                raise ValueError("strictly positive finite nominal/CPI factors required")
            numbers.append(number)
        real_gross(numbers[:3], numbers[3])  # Includes unused future/last rows.
        copied.append(dict(zip(FIELDS, (s+1, t+1, *numbers))))
    return tuple(copied), scenarios, periods


def _priors(calibrations, scenarios, periods):
    if isinstance(calibrations, CalibrationBundle):
        if (calibrations.scenario_count, calibrations.periods) != (scenarios, periods):
            raise ValueError("calibration bundle shape differs from supplied rows")
        supplied = calibrations.folds
    else:
        try:
            supplied = tuple(calibrations)
        except TypeError as exc:
            raise ValueError("supply a bundle or four ordered FoldCalibration objects") from exc
    if len(supplied) != 4:
        raise ValueError("exactly four calibrations required")
    ids = tuple(range(1, scenarios+1))
    priors = []
    for f, c in enumerate(supplied):
        train = tuple(s for s in ids if fold_id(s) != f)
        evaluation = tuple(s for s in ids if fold_id(s) == f)
        keys = tuple((s,t) for s in train for t in range(1, periods+1))
        if (not isinstance(c, FoldCalibration) or type(c.fold) is not int or c.fold != f
                or c.training_ids != train or c.evaluation_ids != evaluation
                or c.training_keys != keys):
            raise ValueError("wrong fold, membership, complement, order or training keys")
        # Equality alone would admit bool/int aliases. Reject those as key types.
        if (any(type(s) is not int for s in (*c.training_ids, *c.evaluation_ids))
                or any(type(s) is not int or type(t) is not int for s,t in c.training_keys)):
            raise ValueError("calibration keys must be actual integers")
        if (not isinstance(c.prior, EmpiricalPrior) or len(c.prior.gross) != len(keys)):
            raise ValueError("actual prior row count differs from training keys")
        if any(not isinstance(h, str) or not re.fullmatch(r"[0-9a-f]{64}", h)
               for h in (c.training_rows_sha256, c.real_gross_sha256)):
            raise ValueError("calibration digests must be SHA256 strings")
        # Copy and validate supplied support, without re-fitting from any rows.
        priors.append(EmpiricalPrior(c.prior.gross))
    return tuple(priors)


def _normalize(row, mode, fee_rate, fold=None):
    rename = {"policy": "mode", "year": "period", "action": "engine_action"}
    normalized = {rename.get(k,k): (None if k.startswith("target_") and v == "" else v)
                  for k,v in row.items()}
    normalized["mode"] = mode
    normalized["fee_rate"] = fee_rate
    if fold is not None:
        normalized["fold_id"] = fold
    if "growth_units" in normalized:
        normalized["growth_units"] = "percent/year"
    return normalized


def _diagnostics(reviews, horizon):
    prefix = reviews[:horizon]
    if not prefix:
        return dict.fromkeys(("human_review_count", "human_review_share_pct",
                              "first_latch_year", "target_change_count",
                              "first_deployment_year", "initial_allocation_deferred"))
    count = sum(r.action == "human_review" for r in prefix)
    return {"human_review_count": count, "human_review_share_pct": 100*count/horizon,
            "first_latch_year": next((r.period for r in prefix if r.human_review_latched), None),
            "target_change_count": sum(r.executed_target_change for r in prefix),
            "first_deployment_year": prefix[-1].first_deployment_year,
            "initial_allocation_deferred": prefix[-1].initial_allocation_deferred}


def _summary(mode, horizon, group):
    # The accepted fixed-pilot helper assumes H>=2. Extend only its undefined
    # volatility/later-share seam for the explicit H=1 synthetic fixture.
    if horizon == 1:
        safe = [r | {"annual_real_volatility_pct": 0.0, "later_review_count": 1} for r in group]
        row = summary_row(mode, horizon, safe)
        row.update(median_volatility_pct=None, pooled_later_review_count=0,
                   pooled_trade_share_ex_initial_pct=None)
    else:
        row = summary_row(mode, horizon, group)
    return row


def build_case_tables(rows, *, calibrations, mode, fee_rate, split,
                      horizons=(5,6,15,25,30)):
    """Evaluate one declared case, with true split and fresh scenario callbacks.

    calibrations is a CalibrationBundle or four ordered FoldCalibration objects.
    Their metadata/support shape is checked, not their source authenticity.
    Primary development references must be imported by the future writer.
    """
    if split not in ("synthetic", "development"):
        raise ValueError("only synthetic/development splits are supported")
    if not isinstance(mode, str) or mode not in (*CENTRAL_TARGET, *POLICIES):
        raise ValueError("unknown mode")
    if isinstance(fee_rate, bool):
        raise ValueError("invalid fee")
    try:
        k = float(fee_rate)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("invalid fee") from exc
    if not math.isfinite(k) or k not in ((0, .0025, .005) if split == "synthetic" else (.0025,.005)):
        raise ValueError("only declared fees; zero is synthetic only")
    if split == "development" and k == .0025 and mode in POLICIES:
        raise ValueError("primary development references require exact accepted HY3-003 import")
    try:
        hs = tuple(horizons)
    except TypeError as exc:
        raise ValueError("nonempty unique positive horizons required") from exc
    if not hs or any(type(h) is not int or not 1 <= h <= 30 for h in hs) or len(set(hs)) != len(hs):
        raise ValueError("nonempty unique integer horizons in 1..30 required")
    hs = tuple(sorted(hs))
    selected, scenarios, periods = _rows(rows, split)
    if hs[-1] > periods:
        raise ValueError("paths shorter than requested horizon")
    priors = _priors(calibrations, scenarios, periods)
    annual, metrics, decisions, scores = [], [], [], []
    cost_aware = mode in CENTRAL_TARGET
    review_fields = tuple(f.name for f in fields(PolicyReview) if f.name != "scores")
    for s in range(1, scenarios+1):
        f = fold_id(s)
        policy = CostAwarePolicy(mode, priors[f], fee_rate=k, review_drawdown_pct=25.0) if cost_aware else None
        callback = policy if cost_aware else POLICIES[mode]
        result = simulate_policy(selected[(s-1)*periods:s*periods], horizon=hs[-1],
                                 split=split, callback=callback, fee_rate=k)
        reviews = tuple(policy.reviews) if cost_aware else ()
        annual.extend(_normalize(ledger_row(mode, split, e), mode, k, f) for e in result.ledger)
        for review in reviews:
            common = {"split": split, "mode": mode, "fee_rate": k,
                      "scenario_id": s, "fold_id": f, "period": review.period}
            decisions.append(common | {name: getattr(review,name) for name in review_fields
                                       if name not in ("scenario_id", "period")})
            for score in review.scores:
                scores.append(common | {"target_name": score.name,
                    **dict(zip(("target_equity","target_bond","target_bill_proxy"), score.target)),
                    **{name: getattr(score,name) for name in (
                        "ce_target","tau","fee_fraction","pre_cost_benefit","modeled_fee_impact",
                        "conservative_score","true_net_ce")}})
        for h in hs:
            metrics.append(_normalize(metric_row(mode,result,h),mode,k,f) | _diagnostics(reviews,h))
    summary = []
    for h in hs:
        group = [r for r in metrics if r["horizon"] == h]
        row = _normalize(_summary(mode,h,group),mode,k)
        count = sum(r["human_review_count"] for r in group) if cost_aware else None
        row.update(pooled_human_review_count=count,
                   pooled_human_review_share_pct=100*count/(scenarios*h) if cost_aware else None,
                   pooled_target_change_count=sum(r["target_change_count"] for r in group) if cost_aware else None)
        summary.append(row)
    tables = dict(annual_ledgers=tuple(annual), scenario_metrics=tuple(metrics),
                  summary=tuple(summary), decisions=tuple(decisions),
                  target_scores=tuple(sorted(scores, key=lambda r: (r["scenario_id"], r["period"], r["target_name"]))))
    return CaseTables(**tables, counts={name:len(records) for name,records in tables.items()},
        units={"growth": "percent/year", "growth_difference": "percentage points/year",
               "volatility": "percentage points; annual sample ddof=1", "loss": "percent of running real peak",
               "trade_share": "percent of annual reviews", "fee": "nominal wealth units",
               "ce": "annual real gross factor", "wealth": "nominal units; real at CPI_0=1"},
        metadata={"split": split, "mode": mode, "fee_rate": k, "horizons": hs,
                  "scenario_count": scenarios, "input_periods": periods,
                  "diagnostics_applicable": cost_aware, "source_verified": False,
                  "review_drawdown_pct": 25.0 if cost_aware else None})
