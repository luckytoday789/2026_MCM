"""Net real metrics under specs/ACCOUNTING.md; outputs use percentage units."""

from collections.abc import Iterable
from dataclasses import dataclass
import math
from statistics import stdev

from .accounting import finite_number


@dataclass(frozen=True)
class PerformanceMetrics:
    """H annual intervals, with undefined sample volatility at H=1."""

    horizon: int
    split: str
    net_real_cagr_pct: float
    annual_real_volatility_pct: float | None
    max_real_drawdown_pct: float
    growth_units: str = "percent per year"
    volatility_units: str = "percentage points (annual returns, sample ddof=1)"
    drawdown_units: str = "percent of running real wealth peak"


def annual_real_returns(
    year_end_real_wealth: Iterable[float], *, initial_wealth: float = 100.0
) -> tuple[float, ...]:
    """Decimal end-to-end real returns, including each period's trading fee.

    Post-fee observations do not constitute extra annual return intervals.
    Prior end wealth must be positive; terminal zero is permitted.
    """
    previous = finite_number(initial_wealth, "initial_wealth")
    if previous <= 0:
        raise ValueError("initial_wealth must be positive")
    result = []
    for value in year_end_real_wealth:
        current = finite_number(value, "year_end_real_wealth")
        if current < 0 or previous <= 0:
            raise ValueError("wealth must be nonnegative with positive prior wealth")
        result.append(finite_number(current / previous - 1.0, "annual real return"))
        previous = current
    return tuple(result)


def maximum_real_drawdown(observations: Iterable[float]) -> float:
    """Percent loss from a running peak, in supplied chronological order.

    Supply initial wealth, then post-fee/year-end pairs; do not sort the path.
    """
    path = tuple(finite_number(x, "real wealth observation") for x in observations)
    if not path or path[0] <= 0 or min(path) < 0:
        raise ValueError("path must start positive and remain nonnegative")
    peak = path[0]
    loss = 0.0
    for wealth in path:
        peak = max(peak, wealth)
        loss = max(loss, 1.0 - wealth / peak)
    return 100.0 * loss


def compute_metrics(
    year_end_real_wealth: Iterable[float],
    post_fee_real_wealth: Iterable[float],
    *,
    split: str,
    initial_wealth: float = 100.0,
) -> PerformanceMetrics:
    """Compute CAGR, sample annual volatility and initial/post-fee-aware MDD.

    Both series must contain exactly H entries (H>=1); split must be explicitly
    labeled synthetic/development. Initial wealth defaults
    to the locked 100. Fees are included via end-to-end annual wealth ratios.
    At H=1 sample volatility is undefined (None), never silently set to zero.
    """
    if split not in ("synthetic", "development"):
        raise ValueError("this implementation supports synthetic/development splits only")
    ends = tuple(finite_number(x, "year_end_real_wealth") for x in year_end_real_wealth)
    trades = tuple(finite_number(x, "post_fee_real_wealth") for x in post_fee_real_wealth)
    initial = finite_number(initial_wealth, "initial_wealth")
    horizon = len(ends)
    if horizon < 1 or len(trades) != horizon or initial <= 0:
        raise ValueError("positive initial wealth and equal nonempty H-length series required")
    returns = annual_real_returns(ends, initial_wealth=initial)
    path = [initial]
    for post_fee, end in zip(trades, ends):
        path.extend((post_fee, end))
    cagr = 100.0 * ((ends[-1] / initial) ** (1.0 / horizon) - 1.0)
    volatility = 100.0 * stdev(returns) if horizon >= 2 else None
    return PerformanceMetrics(
        horizon, split, cagr, volatility, maximum_real_drawdown(path)
    )


def linear_quantile(values: Iterable[float], probability: float) -> float:
    """Linear-interpolated scenario quantile at index (n-1)*p; p is in [0,1].

    The caller supplies one metric per independent scenario, not annual rows.
    """
    ordered = sorted(finite_number(x, "quantile value") for x in values)
    p = finite_number(probability, "probability")
    if not ordered or not 0 <= p <= 1:
        raise ValueError("nonempty values and probability in [0,1] required")
    index = (len(ordered) - 1) * p
    left = math.floor(index)
    right = math.ceil(index)
    fraction = index - left
    return (1.0 - fraction) * ordered[left] + fraction * ordered[right]
