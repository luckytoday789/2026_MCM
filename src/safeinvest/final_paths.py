"""Generated-only true-final arithmetic lane; no files or production authority.

An independently authenticated production loader is deliberately not provided.
Passing original competition rows here does not authenticate or authorize them.
All old public development and synthetic entry points retain their guards.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from .accounting import finite_number
from .backtest import BacktestResult, _simulate_policy_arithmetic
from .baselines import POLICIES
from .metrics import _compute_metrics_arithmetic
from .policy_calibration import FIELDS, canonical_bytes, digest
from .policy_pilot import CENTRAL_TARGET, CostAwarePolicy, EmpiricalPrior, real_gross


@dataclass(frozen=True)
class GeneratedFinalPath:
    result: BacktestResult
    reviews: tuple
    prior_support_sha256: str
    prior_support_count: int
    mode: str
    review_drawdown_pct: float
    input_periods: int

    def metadata(self):
        return {
            "split": "final", "input_origin": "program_generated",
            "source_verified": False, "production_execution_authorized": False,
            "refit_verified": False, "mode": self.mode,
            "fee_rate": self.result.fee_rate,
            "horizon": self.result.horizon,
            "review_drawdown_pct": self.review_drawdown_pct,
            "input_periods": self.input_periods,
            "prior_support_sha256": self.prior_support_sha256,
            "prior_support_count": self.prior_support_count,
            "fold_id": None, "fold_status": "not_applicable",
            "promotion": None, "promotion_status": "not_applicable",
        }


def prior_support_digest(prior):
    """Digest support order and exact binary64 values, distinct from row hashes."""
    if not isinstance(prior, EmpiricalPrior):
        raise ValueError("explicit immutable EmpiricalPrior required")
    return digest(canonical_bytes({
        "schema": "all-development-prior-support-v1",
        "asset_order": list(FIELDS[2:5]),
        "rows": [[v.hex() for v in row] for row in prior.gross],
    }))


def _outcomes(row):
    numbers = tuple(finite_number(row[name], name) for name in FIELDS[2:])
    if any(value <= -1 for value in numbers):
        raise ValueError("strictly positive nominal/CPI gross factors required")
    real_gross(numbers[:3], numbers[3])
    return numbers


class _OutcomeRow(Mapping):
    """Delay reading current outcomes until the accepted engine asks for them."""

    def __init__(self, original):
        self.original = original
        self.validated = None

    def __iter__(self):
        return iter(FIELDS)

    def __len__(self):
        return len(FIELDS)

    def __getitem__(self, name):
        if name in FIELDS[:2]:
            return self.original[name]
        if name not in FIELDS:
            raise KeyError(name)
        if self.validated is None:
            self.validated = _outcomes(self.original)
        return self.validated[FIELDS.index(name) - 2]


def _generated_path(rows, *, mode, prior, horizon, fee_rate,
                    review_drawdown_pct, split, periods):
    if split != "final":
        raise ValueError("this explicit generated lane requires split=final")
    if type(horizon) is not int or not 1 <= horizon <= periods:
        raise ValueError("integer horizon in 1..input periods required")
    if (not isinstance(mode, str) or mode not in (*POLICIES, *CENTRAL_TARGET)):
        raise ValueError("unknown fixed mode")
    k = finite_number(fee_rate, "fee_rate")
    threshold = finite_number(review_drawdown_pct, "review_drawdown_pct")
    if k not in (.0025, .005) or not 0 < threshold <= 100:
        raise ValueError("fixed fee and review threshold in (0,100] required")
    support_digest = prior_support_digest(prior)
    selected = tuple(rows)
    if len(selected) != periods:
        raise ValueError("complete one-scenario input shape required")
    scenario = None
    for period, row in enumerate(selected, 1):
        if not isinstance(row, Mapping) or tuple(row) != FIELDS:
            raise ValueError("exact ordered six-field schema required")
        s, t = row["scenario_id"], row["period"]
        if (type(s) not in (int, str) or type(t) not in (int, str)
                or str(s) not in tuple(str(n) for n in range(121,181))
                or str(t) != str(period)):
            raise ValueError("canonical final ID121..180 and ordered integer periods required")
        if scenario is None:
            scenario = int(s)
        elif int(s) != scenario:
            raise ValueError("exactly one scenario required")
    policy = (CostAwarePolicy(mode, prior, fee_rate=k,
                             review_drawdown_pct=threshold)
              if mode in CENTRAL_TARGET else None)
    callback = policy if policy is not None else POLICIES[mode]
    wrapped = tuple(_OutcomeRow(row) for row in selected)
    result = _simulate_policy_arithmetic(
        wrapped, horizon=horizon, split="final", callback=callback, fee_rate=k,
    )
    # The suffix is validated separately after all requested decisions. Its
    # observations never enter a callback, history or the shared support.
    for row in wrapped:
        if row.validated is None:
            row.validated = _outcomes(row.original)
    return GeneratedFinalPath(
        result, tuple(policy.reviews) if policy is not None else (),
        support_digest, len(prior.gross), mode, threshold, periods,
    )


def simulate_generated_final_path(rows, *, mode, prior, horizon, fee_rate,
                                  review_drawdown_pct=25.0, split):
    """Simulate 30 explicit generated rows with fresh state and a shared prior.

    Decisions and metrics really carry split=final. Separate metadata truthfully
    says generated, unverified and unauthorized; scenario IDs prove no origin.
    The supplied prior is used by identity without any refit or mutation.
    """
    return _generated_path(rows, mode=mode, prior=prior, horizon=horizon,
                           fee_rate=fee_rate, review_drawdown_pct=review_drawdown_pct,
                           split=split, periods=30)


def _simulate_generated_final_fixture(rows, *, periods, **kwargs):
    """Private short-fixture test seam; never a production input adapter."""
    if type(periods) is not int or not 1 <= periods <= 30:
        raise ValueError("generated fixture periods in 1..30 required")
    return _generated_path(rows, periods=periods, **kwargs)


def final_prefix_metrics(path, horizon):
    """Pure true-final prefix metrics; performs no selection or promotion."""
    if (not isinstance(path, GeneratedFinalPath) or path.result.split != "final"
            or type(horizon) is not int or not 1 <= horizon <= path.result.horizon):
        raise ValueError("generated final path and an available integer prefix required")
    ledger = path.result.ledger[:horizon]
    return _compute_metrics_arithmetic(
        (entry.real_wealth_end for entry in ledger),
        (entry.real_wealth_after_fee for entry in ledger), split="final",
    )
