"""A single-scenario equal-weight baseline and a prefix-only decision boundary.

This module opens no files, selects no scenarios, and fits no parameters.
Use CSV DictReader-style mappings with the original six field names. Pass a
single already-selected scenario, ordered from period 1, and explicit horizon.
Only synthetic/development runs are supported in this implementation task.
"""

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
import math

from .accounting import (
    DEFAULT_FEE_RATE, Vector3, apply_returns, compound_cpi, deflate,
    finite_number, keep, rebalance, validate_holdings, validate_target,
)
from .metrics import PerformanceMetrics, _compute_metrics_arithmetic

INITIAL_HOLDINGS = (0.0, 0.0, 100.0)
EQUAL_WEIGHT = (1.0 / 3.0,) * 3
TRADE_THRESHOLD = 1e-10
RETURN_FIELDS = ("equity_return", "bond_return", "bill_proxy_return")


def _positive_integer(value: object, name: str) -> int:
    number = finite_number(value, name)
    if number < 1 or not number.is_integer():
        raise ValueError(f"{name} must be a positive integer")
    return int(number)


@dataclass(frozen=True)
class Observation:
    """One completed year, with annual decimal returns and inflation."""

    scenario_id: int
    period: int
    returns: Vector3
    inflation: float


@dataclass(frozen=True)
class Decision:
    """A keep or target rebalance request, made before the current outcomes."""

    action: str
    target: Vector3 | None = None

    def __post_init__(self) -> None:
        if self.action == "rebalance" and self.target is not None:
            object.__setattr__(self, "target", validate_target(self.target))
        elif self.action != "keep" or self.target is not None:
            raise ValueError("use Decision('keep') or Decision('rebalance', target)")


@dataclass(frozen=True)
class DecisionContext:
    """Only this scenario's t-1 completed observations, plus current holdings."""

    scenario_id: int
    period: int
    holdings: Vector3
    history: tuple[Observation, ...]


def decide_from_history(
    callback: Callable[[DecisionContext], Decision],
    *,
    scenario_id: int,
    period: int,
    holdings: Iterable[float],
    history: Sequence[Observation],
) -> Decision:
    """Invoke a decision callback with an immutable exact prefix through t-1.

    For example, a future keep callback is ``lambda context: Decision('keep')``.
    No current return/inflation argument exists. This is an API boundary, not
    a sandbox: a callback must not capture external future data in a closure.
    The baseline below uses this boundary before reading the current outcomes.
    """
    scenario = _positive_integer(scenario_id, "scenario_id")
    t = _positive_integer(period, "period")
    prefix = tuple(history)
    if len(prefix) != t - 1 or any(
        not isinstance(row, Observation) or row.scenario_id != scenario or row.period != i
        for i, row in enumerate(prefix, 1)
    ):
        raise ValueError("history must be this scenario's exact prefix through period t-1")
    # Copy nested vectors as tuples too; caller-supplied mutable values cannot
    # become a back door to current outcomes or be modified by the callback.
    prefix = tuple(
        Observation(row.scenario_id, row.period, tuple(row.returns), row.inflation)
        for row in prefix
    )
    decision = callback(DecisionContext(scenario, t, validate_holdings(holdings), prefix))
    if not isinstance(decision, Decision):
        raise ValueError("callback must return a Decision")
    return decision


@dataclass(frozen=True)
class LedgerEntry:
    """One annual review, fee, returns and exact CPI/real-wealth reconciliation."""

    scenario_id: int
    period: int
    decision: Decision
    holdings_before: Vector3
    wealth_before: float
    cpi_before: float
    real_wealth_before: float
    intended_transfer: float
    fee: float
    holdings_after_fee: Vector3
    wealth_after_fee: float
    real_wealth_after_fee: float
    returns: Vector3
    inflation: float
    holdings_end: Vector3
    wealth_end: float
    cpi_end: float
    real_wealth_end: float
    annual_net_real_return: float


@dataclass(frozen=True)
class BacktestResult:
    """One scenario only; trade shares count T>1e-10 and use percent units."""

    scenario_id: int
    horizon: int
    split: str
    fee_rate: float
    initial_holdings: Vector3
    initial_cpi: float
    ledger: tuple[LedgerEntry, ...]
    metrics: PerformanceMetrics
    trade_share_pct: float
    trade_share_ex_initial_pct: float | None
    wealth_units: str = "nominal units; real units at CPI_0=1"
    rate_units: str = "annual simple decimal returns and inflation"
    transfer_fee_units: str = "nominal wealth units"
    trade_share_units: str = "percent of annual reviews"


def _equal_weight_decision(context: DecisionContext) -> Decision:
    return Decision("rebalance", EQUAL_WEIGHT)


def simulate_policy(
    rows: Iterable[Mapping[str, object]],
    *,
    horizon: int,
    split: str,
    callback: Callable[[DecisionContext], Decision],
    fee_rate: float = DEFAULT_FEE_RATE,
) -> BacktestResult:
    """Simulate a prefix-only callback, deciding before current outcomes.

    Rows must all belong to one scenario and have consecutive periods 1..N;
    H<=N, and only the first H outcomes are consumed. Numeric CSV strings work.
    ``split`` is explicit: 'development' (IDs 1..120) or 'synthetic'. Final runs
    are deliberately unsupported pending a separately authorized frozen gate.
    Entire input metadata is checked to reject accidental scenario mixing, but
    each current outcome is read only after its Decision has been constructed.
    No sorting, silent filtering, concatenation, or annualization is performed.
    H=1 yields undefined sample volatility and ex-initial trade share (None).
    """
    h = _positive_integer(horizon, "horizon")
    if split not in ("synthetic", "development"):
        raise ValueError("this implementation supports synthetic/development splits only")
    k = finite_number(fee_rate, "fee_rate")
    if k < 0:
        raise ValueError("fee_rate must be nonnegative")
    selected = tuple(rows)
    if not selected or h > len(selected):
        raise ValueError("supply at least horizon rows for one scenario")
    scenario = _positive_integer(selected[0]["scenario_id"], "scenario_id")
    if split == "development" and scenario > 120:
        raise ValueError("development scenario_id must be in 1..120")
    for period, row in enumerate(selected, 1):
        if _positive_integer(row["scenario_id"], "scenario_id") != scenario:
            raise ValueError("rows must belong to exactly one scenario")
        if _positive_integer(row["period"], "period") != period:
            raise ValueError("rows must be consecutive and ordered from period 1")

    return _simulate_policy_arithmetic(
        selected, horizon=h, split=split, callback=callback, fee_rate=k,
    )


def _simulate_policy_arithmetic(
    selected, *, horizon, split, callback, fee_rate,
) -> BacktestResult:
    """Unchanged accounting loop after a lane-specific input validation.

    No file access or production authority is provided by this private seam.
    """
    h, k = horizon, fee_rate
    scenario = _positive_integer(selected[0]["scenario_id"], "scenario_id")
    holdings = INITIAL_HOLDINGS
    cpi = 1.0
    history = []
    ledger = []
    for t in range(1, h + 1):
        decision = decide_from_history(
            callback, scenario_id=scenario, period=t,
            holdings=holdings, history=history,
        )
        trade = (
            keep(holdings) if decision.action == "keep"
            else rebalance(holdings, decision.target, k)
        )
        # The Decision already exists before any access to r_t or inflation_t.
        row = selected[t - 1]
        returns = tuple(finite_number(row[name], name) for name in RETURN_FIELDS)
        inflation = finite_number(row["inflation"], "inflation")
        end_holdings = apply_returns(trade.holdings_after_fee, returns)
        end_cpi = compound_cpi(cpi, inflation)
        end_wealth = math.fsum(end_holdings)
        real_before = deflate(trade.wealth_before, cpi)
        real_after_fee = deflate(trade.wealth_after_fee, cpi)
        real_end = deflate(end_wealth, end_cpi)
        ledger.append(LedgerEntry(
            scenario, t, decision, trade.holdings_before, trade.wealth_before,
            cpi, real_before, trade.intended_transfer, trade.fee,
            trade.holdings_after_fee, trade.wealth_after_fee, real_after_fee,
            returns, inflation, end_holdings, end_wealth, end_cpi, real_end,
            real_end / real_before - 1.0,
        ))
        history.append(Observation(scenario, t, returns, inflation))
        holdings, cpi = end_holdings, end_cpi

    metrics = _compute_metrics_arithmetic(
        (entry.real_wealth_end for entry in ledger),
        (entry.real_wealth_after_fee for entry in ledger),
        split=split,
    )
    trades = [entry.intended_transfer > TRADE_THRESHOLD for entry in ledger]
    return BacktestResult(
        scenario, h, split, k, INITIAL_HOLDINGS, 1.0, tuple(ledger), metrics,
        100.0 * sum(trades) / h,
        100.0 * sum(trades[1:]) / (h - 1) if h > 1 else None,
    )


def simulate_equal_weight(
    rows: Iterable[Mapping[str, object]],
    *,
    horizon: int,
    split: str,
    fee_rate: float = DEFAULT_FEE_RATE,
) -> BacktestResult:
    """Restore thirds at every review; backward-compatible annual baseline."""
    return simulate_policy(
        rows, horizon=horizon, split=split, callback=_equal_weight_decision,
        fee_rate=fee_rate,
    )
