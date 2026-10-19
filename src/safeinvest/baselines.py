"""The entire fixed candidate set. No outcomes, files, fitting or forecasts."""

from .backtest import Decision, DecisionContext, EQUAL_WEIGHT


def bills_keep(context: DecisionContext) -> Decision:
    return Decision("keep")


def equal_weight_annual(context: DecisionContext) -> Decision:
    return Decision("rebalance", EQUAL_WEIGHT)


def equal_weight_buy_hold(context: DecisionContext) -> Decision:
    return equal_weight_annual(context) if context.period == 1 else bills_keep(context)


POLICIES = {
    "bills_keep": bills_keep,
    "equal_weight_annual": equal_weight_annual,
    "equal_weight_buy_hold": equal_weight_buy_hold,
}
