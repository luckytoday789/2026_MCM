"""SafeInvest accounting and single-scenario simulation (annual decimal returns).

Use ``from safeinvest import simulate_equal_weight, rebalance`` with ``src`` on
PYTHONPATH. No files are opened and no strategy parameters are fitted on import.
"""

from .accounting import (
    ASSETS, DEFAULT_FEE_RATE, TradeResult, apply_returns, compound_cpi, deflate,
    keep, rebalance,
)
from .backtest import (
    BacktestResult, Decision, DecisionContext, LedgerEntry, Observation,
    decide_from_history, simulate_equal_weight, simulate_policy,
)
from .metrics import (
    PerformanceMetrics, annual_real_returns, compute_metrics, linear_quantile,
    maximum_real_drawdown,
)

__all__ = [
    "ASSETS", "DEFAULT_FEE_RATE", "TradeResult", "apply_returns", "compound_cpi",
    "deflate", "keep", "rebalance", "BacktestResult", "Decision",
    "DecisionContext", "LedgerEntry", "Observation", "decide_from_history",
    "simulate_equal_weight", "simulate_policy", "PerformanceMetrics", "annual_real_returns",
    "compute_metrics", "linear_quantile", "maximum_real_drawdown",
]
