"""Provisional chief policy kernel; independent SOL design/code review is pending.

No files, fitted parameters, CLI, or competition outcomes are loaded here. This
module is deliberately not exported by safeinvest.__init__. The wrapper accepts
synthetic runs only. Production calibration/driver authorization is separate.
"""

from dataclasses import dataclass
import math

from .accounting import (
    apply_returns, compound_cpi, deflate, finite_number, keep, rebalance,
    validate_holdings, validate_target, vector3,
)
from .backtest import Decision, DecisionContext, INITIAL_HOLDINGS, simulate_policy

GAMMA = 4.0
EPSILON = 1e-12
TRANSFER_EPSILON = 1e-10
PRIOR_STRENGTH = 15
WINDOW = 5
TARGETS = {
    "conservative": (0.15, 0.20, 0.65),
    "balanced": (1 / 3, 1 / 3, 1 / 3),
    "growth": (0.60, 0.30, 0.10),
    "defensive": (0.20, 0.25, 0.55),
    "growth_tilt": (0.45, 0.30, 0.25),
}
CENTRAL_TARGET = {
    "conservative_cost": "conservative", "balanced_cost": "balanced",
    "growth_cost": "growth", "balanced_context": "balanced",
    "balanced_adaptive": "balanced",
}


def positive_gross(values):
    result = vector3(values, "real gross factors")
    if min(result) <= 0:
        raise ValueError("all real gross factors must be positive")
    return result


def real_gross(returns, inflation):
    r = vector3(returns, "annual returns")
    i = finite_number(inflation, "annual inflation")
    if min(r) <= -1 or i <= -1:
        raise ValueError("policy requires strictly positive asset and CPI factors")
    return positive_gross((1 + x) / (1 + i) for x in r)


def logsumexp(values):
    values = tuple(values)
    high = max(values)
    return finite_number(high + math.log(math.fsum(math.exp(x - high) for x in values)),
                         "log moment sum")


@dataclass(frozen=True)
class EmpiricalPrior:
    """An explicit equally weighted annual marginal distribution, never a path.

    The future driver must separately prove training-fold exclusion and input
    provenance. Merely constructing this object certifies neither property.
    """

    gross: tuple

    def __post_init__(self):
        rows = tuple(positive_gross(row) for row in self.gross)
        if not rows:
            raise ValueError("prior requires at least one observation")
        object.__setattr__(self, "gross", rows)

    def certainty_equivalent(self, weights, recent=()):
        w = validate_target(weights)
        recent = tuple(positive_gross(row) for row in recent)
        if len(recent) > WINDOW:
            raise ValueError("at most five completed annual observations")

        def log_power(row):
            gross = finite_number(math.fsum(x * g for x, g in zip(w, row)),
                                  "portfolio real gross factor")
            if gross <= 0:
                raise ValueError("portfolio gross factor must be positive")
            return (1 - GAMMA) * math.log(gross)

        prior_log_moment = logsumexp(log_power(row) for row in self.gross) - math.log(len(self.gross))
        if recent:
            log_moment = logsumexp((math.log(PRIOR_STRENGTH) + prior_log_moment,
                                   *(log_power(row) for row in recent))) - math.log(PRIOR_STRENGTH + len(recent))
        else:
            log_moment = prior_log_moment
        try:
            ce = finite_number(math.exp(log_moment / (1 - GAMMA)), "certainty equivalent")
        except OverflowError as exc:
            raise ValueError("certainty equivalent overflow") from exc
        if ce <= 0:
            raise ValueError("certainty equivalent underflow")
        return ce


@dataclass(frozen=True)
class TargetScore:
    name: str
    target: tuple
    ce_keep: float
    ce_target: float
    tau: float
    fee_fraction: float
    pre_cost_benefit: float
    modeled_fee_impact: float
    conservative_score: float
    true_net_ce: float


def score_target(name, target, current, prior, recent, fee_rate):
    w, u = validate_target(target), validate_target(current)
    k = finite_number(fee_rate, "fee_rate")
    if not 0 <= k < 0.5:
        raise ValueError("prototype fee rate must be in [0, 0.5)")
    ce_u = prior.certainty_equivalent(u, recent)
    ce_w = prior.certainty_equivalent(w, recent)
    tau = 0.5 * math.fsum(abs(a - b) for a, b in zip(w, u))
    f = k * tau
    return TargetScore(name, w, ce_u, ce_w, tau, f, ce_w - ce_u,
                       f * ce_w, (1 - 2 * f) * ce_w, (1 - f) * ce_w)


def choose_target(scores, ce_keep):
    """Input order is tie priority; every selected target must pass the keep gate.

    Compare ties to the global maximum, avoiding nontransitive pairwise ties.
    A preferred target that fails the strict keep gate cannot be executed.
    """
    eligible = tuple(s for s in scores if s.conservative_score > ce_keep + EPSILON)
    if not eligible:
        return None
    maximum = max(s.conservative_score for s in eligible)
    return next(s for s in eligible if maximum - s.conservative_score <= EPSILON)


@dataclass(frozen=True)
class PolicyReview:
    scenario_id: int
    period: int
    action: str
    active_before: str
    active_after: str
    proposed_target: str | None
    selected_target: str | None
    ce_keep: float | None
    scores: tuple
    prior_mass: float
    recent_count: int
    observed_max_drawdown_pct: float
    human_review_latched: bool
    initial_allocation_deferred: bool
    intended_transfer: float
    actual_fee: float
    is_trade: bool
    executed_target_change: bool
    reason: str
    first_deployment_year: int | None


class CostAwarePolicy:
    """One sequential scenario callback. A fresh instance is mandatory per run.

    Completed wealth is reconstructed from previous post-fee holdings and the
    latest context observation; incoming holdings must agree. Post-fee losses
    enter the running maximum immediately but affect actions only next review.
    """

    def __init__(self, mode, prior, *, fee_rate=0.0025, review_drawdown_pct=25.0):
        if mode not in CENTRAL_TARGET or not isinstance(prior, EmpiricalPrior):
            raise ValueError("use a declared mode and explicit empirical prior")
        self.mode, self.prior = mode, prior
        self.fee_rate = finite_number(fee_rate, "fee_rate")
        self.review_threshold = finite_number(review_drawdown_pct, "review threshold")
        if not 0 <= self.fee_rate < 0.5 or not 0 < self.review_threshold <= 100:
            raise ValueError("invalid fee or review threshold")
        self.active = CENTRAL_TARGET[mode]
        self.reviews = []
        self._scenario = None
        self._history = ()
        self._after = INITIAL_HOLDINGS
        self._cpi = 1.0
        self._peak = 100.0
        self._max_loss = 0.0
        self._latched = False
        self._initial_deferred = False
        self._first_deployment_year = None

    def _observe(self, real_wealth):
        self._peak = max(self._peak, real_wealth)
        self._max_loss = max(self._max_loss, 100 * (1 - real_wealth / self._peak))

    def __call__(self, context):
        if not isinstance(context, DecisionContext):
            raise ValueError("use the accepted engine decision context")
        if context.period != len(self.reviews) + 1 or len(context.history) != context.period - 1:
            raise ValueError("policy state must advance exactly one annual review")
        if any(row.scenario_id != context.scenario_id or row.period != i
               for i, row in enumerate(context.history, 1)):
            raise ValueError("history must be the current scenario's ordered prefix")
        holdings = validate_holdings(context.holdings)
        if context.period == 1:
            if holdings != INITIAL_HOLDINGS:
                raise ValueError("initial wealth must be 100 in bills")
            self._scenario = context.scenario_id
        else:
            if context.scenario_id != self._scenario or context.history[:-1] != self._history:
                raise ValueError("scenario or completed history changed; use fresh state")
            last = context.history[-1]
            real_gross(last.returns, last.inflation)  # fail even while suspended
            expected = apply_returns(self._after, last.returns)
            if any(not math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-9)
                   for a, b in zip(expected, holdings)):
                raise ValueError("incoming holdings disagree with prior decision/fee")
            self._cpi = compound_cpi(self._cpi, last.inflation)
            self._observe(deflate(math.fsum(holdings), self._cpi))
        self._history = tuple(context.history)
        observed_loss = self._max_loss
        self._latched |= observed_loss >= self.review_threshold
        before = self.active
        contextual = self.mode in ("balanced_context", "balanced_adaptive")
        recent = tuple(real_gross(row.returns, row.inflation)
                       for row in context.history[-WINDOW:]) if contextual else ()
        scores, chosen, proposal, ce_keep = (), None, None, None
        if self._latched:
            action, decision = "human_review", Decision("keep")
            trade = keep(holdings)
        else:
            wealth = math.fsum(holdings)
            u = tuple(h / wealth for h in holdings)
            names = [self.active]
            if self.mode == "balanced_adaptive" and len(recent) == WINDOW:
                names += [n for n in ("defensive", "balanced", "growth_tilt") if n != self.active]
            scores = tuple(score_target(n, TARGETS[n], u, self.prior, recent, self.fee_rate) for n in names)
            ce_keep = scores[0].ce_keep
            chosen = choose_target(scores, ce_keep)
            maximum = max(s.conservative_score for s in scores)
            proposal = next(s.name for s in scores if maximum - s.conservative_score <= EPSILON)
            if chosen is None:
                action, decision, trade = "keep", Decision("keep"), keep(holdings)
            else:
                action = "rebalance" if chosen.name == self.active else "target_change"
                decision = Decision("rebalance", chosen.target)
                trade = rebalance(holdings, chosen.target, self.fee_rate)
                # The transfer epsilon counts trades; it never cancels execution.
                self.active = chosen.name
                if self._first_deployment_year is None and trade.intended_transfer > 0:
                    self._first_deployment_year = context.period
        is_trade = trade.intended_transfer > TRANSFER_EPSILON
        if context.period == 1:
            self._initial_deferred = self._first_deployment_year is None
        self._after = trade.holdings_after_fee
        self._observe(deflate(trade.wealth_after_fee, self._cpi))
        self.reviews.append(PolicyReview(
            context.scenario_id, context.period, action, before, self.active,
            proposal, chosen.name if chosen else None, ce_keep, scores,
            PRIOR_STRENGTH / (PRIOR_STRENGTH + len(recent)), len(recent),
            observed_loss, self._latched, self._initial_deferred,
            trade.intended_transfer, trade.fee, is_trade,
            action == "target_change",
            ("human_review_latched" if self._latched else
             "benefit_gate_failed" if chosen is None else
             "initial_allocation" if self._first_deployment_year == context.period else action),
            self._first_deployment_year,
        ))
        return decision


def simulate_synthetic(rows, *, mode, prior, horizon, fee_rate=0.0025,
                       review_drawdown_pct=25.0):
    """Explicit toy seam only; does not expose a development/final execution CLI."""
    policy = CostAwarePolicy(mode, prior, fee_rate=fee_rate,
                             review_drawdown_pct=review_drawdown_pct)
    result = simulate_policy(rows, horizon=horizon, split="synthetic",
                             callback=policy, fee_rate=fee_rate)
    # Validate the final observation too; it has no subsequent callback.
    for entry in result.ledger:
        real_gross(entry.returns, entry.inflation)
    return result, tuple(policy.reviews)
