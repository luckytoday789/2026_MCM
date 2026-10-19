"""Accounting contract v1, using equity/bond/bill dollar holdings in that order.

Rates are annual simple returns in decimals. No implicit cash, withdrawals,
liquidation fee, or additional fee on the pro-rata fee-funding adjustment exists.
Only the Python standard library is required.
"""

from dataclasses import dataclass
import math
from collections.abc import Iterable

ASSETS = ("equity", "bond", "bill")
DEFAULT_FEE_RATE = 0.0025
WEIGHT_SUM_TOLERANCE = 1e-12
Vector3 = tuple[float, float, float]


def finite_number(value: float, name: str) -> float:
    """Convert numeric input (including CSV numeric strings); reject NaN/inf/bool."""
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number, not bool")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def vector3(values: Iterable[float], name: str) -> Vector3:
    """Copy exactly three finite numbers into an immutable tuple."""
    result = tuple(finite_number(x, name) for x in values)
    if len(result) != 3:
        raise ValueError(f"{name} must contain exactly three values")
    return result


def validate_holdings(
    holdings: Iterable[float], *, positive_total: bool = True
) -> Vector3:
    """Require long-only finite holdings; rebalancing needs positive wealth."""
    result = vector3(holdings, "holdings")
    if min(result) < 0:
        raise ValueError("holdings must be nonnegative")
    total = finite_number(math.fsum(result), "total wealth")
    if positive_total and total <= 0:
        raise ValueError("total wealth must be positive")
    return result


def validate_target(target: Iterable[float]) -> Vector3:
    """Require long-only unit-sum weights; normalize only roundoff within 1e-12.

    Targets outside that absolute sum tolerance are rejected, never projected.
    """
    result = vector3(target, "target")
    total = math.fsum(result)
    if min(result) < 0 or not math.isclose(
        total, 1.0, rel_tol=0.0, abs_tol=WEIGHT_SUM_TOLERANCE
    ):
        raise ValueError("target must be nonnegative and sum to one")
    return tuple(x / total for x in result)


@dataclass(frozen=True)
class TradeResult:
    """An intended pre-fee transfer and the resulting fully invested holdings."""

    action: str
    holdings_before: Vector3
    target: Vector3 | None
    wealth_before: float
    intended_transfer: float
    fee: float
    holdings_after_fee: Vector3
    wealth_after_fee: float


def rebalance(
    holdings: Iterable[float], target: Iterable[float], fee_rate: float = DEFAULT_FEE_RATE
) -> TradeResult:
    """Apply T=W/2*sum(abs(w-h/W)), c=k*T, h_plus=(W-c)*w.

    The transfer is measured BEFORE fees. The pro-rata fee-funding adjustment
    is not charged again. Fee rates must be finite/nonnegative and leave
    positive wealth. Inputs are copied, not mutated; no turnover is rounded.
    """
    h = validate_holdings(holdings)
    w = validate_target(target)
    k = finite_number(fee_rate, "fee_rate")
    if k < 0:
        raise ValueError("fee_rate must be nonnegative")
    wealth = math.fsum(h)
    transfer = wealth / 2.0 * math.fsum(abs(wi - hi / wealth) for hi, wi in zip(h, w))
    fee = finite_number(k * transfer, "fee")
    if fee >= wealth:
        raise ValueError("fee must leave positive wealth")
    remaining = wealth - fee
    after = validate_holdings(remaining * wi for wi in w)
    return TradeResult("rebalance", h, w, wealth, transfer, fee, after, math.fsum(after))


def keep(holdings: Iterable[float]) -> TradeResult:
    """Preserve all dollar holdings exactly; charge no fee or transfer."""
    h = validate_holdings(holdings, positive_total=False)
    wealth = math.fsum(h)
    return TradeResult("keep", h, None, wealth, 0.0, 0.0, h, wealth)


def apply_returns(holdings: Iterable[float], returns: Iterable[float]) -> Vector3:
    """Apply annual simple returns, h_end[i]=h[i]*(1+r[i]), after any fee.

    Gross returns must be nonnegative. An exact -100% return is applied
    literally; zero holdings can be kept, but cannot define rebalance weights.
    """
    h = validate_holdings(holdings, positive_total=False)
    r = vector3(returns, "returns")
    if min(r) < -1:
        raise ValueError("annual simple returns must be at least -1")
    return validate_holdings(
        (hi * (1.0 + ri) for hi, ri in zip(h, r)), positive_total=False
    )


def compound_cpi(cpi_before: float, inflation: float) -> float:
    """Compound CPI exactly by its annual gross inflation factor; CPI_0=1."""
    cpi = finite_number(cpi_before, "cpi_before")
    rate = finite_number(inflation, "inflation")
    if cpi <= 0 or rate <= -1:
        raise ValueError("CPI must be positive and inflation greater than -1")
    result = finite_number(cpi * (1.0 + rate), "compounded CPI")
    if result <= 0:
        raise ValueError("compounded CPI underflowed to zero")
    return result


def deflate(nominal_wealth: float, cpi: float) -> float:
    """Return nominal wealth / compounded CPI, without subtracting inflation."""
    wealth = finite_number(nominal_wealth, "nominal_wealth")
    price = finite_number(cpi, "cpi")
    if wealth < 0 or price <= 0:
        raise ValueError("wealth must be nonnegative and CPI positive")
    return finite_number(wealth / price, "real wealth")
