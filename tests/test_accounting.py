"""Synthetic-only contract checks; run with unittest discovery, without install."""

from dataclasses import FrozenInstanceError, asdict
from fractions import Fraction as F
import json
import math
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from safeinvest import (
    Decision, Observation, annual_real_returns, apply_returns, compound_cpi,
    compute_metrics, decide_from_history, deflate, keep, linear_quantile,
    maximum_real_drawdown, rebalance, simulate_equal_weight,
)


def toy_rows(returns, inflations=None, scenario=7):
    """Explicit synthetic input; never opens an original/development/final CSV."""
    if inflations is None:
        inflations = [0.0] * len(returns)
    return [
        dict(scenario_id=scenario, period=t, equity_return=r[0], bond_return=r[1],
             bill_proxy_return=r[2], inflation=inflation)
        for t, (r, inflation) in enumerate(zip(returns, inflations), 1)
    ]


class ContractAssertions(unittest.TestCase):
    def close(self, actual, expected):
        self.assertTrue(
            math.isclose(actual, float(expected), rel_tol=1e-10, abs_tol=1e-9),
            f"{actual!r} != {float(expected)!r}",
        )

    def vector_close(self, actual, expected):
        self.assertEqual(len(actual), len(expected))
        for a, e in zip(actual, expected):
            self.close(a, e)


class AccountingTests(ContractAssertions):
    def test_exact_twenty_unit_bill_to_equity_example(self):
        trade = rebalance((0, 0, 100), (0.2, 0, 0.8), 0.0025)
        self.close(trade.intended_transfer, 20)
        self.close(trade.fee, 0.05)
        self.close(trade.wealth_after_fee, 99.95)
        self.vector_close(trade.holdings_after_fee, (19.99, 0, 79.96))
        # Actual equity increase is 19.99, not the intended pre-fee 20.
        self.close(trade.wealth_before, trade.wealth_after_fee + trade.fee)

    def test_initial_equal_weight_exact_fractions(self):
        trade = rebalance((0, 0, 100), (1 / 3,) * 3)
        self.close(trade.intended_transfer, F(200, 3))
        self.close(trade.fee, F(1, 6))
        self.close(trade.wealth_after_fee, F(599, 6))
        self.vector_close(trade.holdings_after_fee, (F(599, 18),) * 3)

    def test_all_equity_and_keep_bills_examples(self):
        equity = rebalance((0, 0, 100), (1, 0, 0))
        self.close(equity.intended_transfer, 100)
        self.close(equity.fee, 0.25)
        self.vector_close(equity.holdings_after_fee, (99.75, 0, 0))
        bills = rebalance((0, 0, 100), (0, 0, 1))
        self.assertEqual(bills.intended_transfer, 0)
        self.assertEqual(bills.fee, 0)
        self.assertEqual(bills.holdings_after_fee, (0, 0, 100))

    def test_keep_preserves_dollars_and_inputs_exactly(self):
        holdings = [19.125, 31.25, 49.625]
        original = holdings.copy()
        trade = keep(holdings)
        self.assertEqual(trade.holdings_after_fee, tuple(original))
        self.assertEqual(holdings, original)
        self.assertEqual(trade.intended_transfer, 0)
        self.assertEqual(trade.fee, 0)
        self.assertIsNone(trade.target)
        self.assertEqual(trade.action, "keep")

    def test_rebalance_matching_weights_is_no_trade(self):
        trade = rebalance((20, 30, 50), (0.2, 0.3, 0.5))
        self.assertEqual(trade.intended_transfer, 0)
        self.assertEqual(trade.fee, 0)
        self.assertEqual(trade.holdings_after_fee, (20, 30, 50))

    def test_fee_precedes_return(self):
        trade = rebalance((0, 0, 100), (0.2, 0, 0.8))
        end = apply_returns(trade.holdings_after_fee, (0.1, 0, 0.05))
        self.vector_close(end, (21.989, 0, 83.958))
        self.close(math.fsum(end), 105.947)

    def test_zero_fees_zero_returns(self):
        trade = rebalance((0, 0, 100), (0.2, 0.3, 0.5), 0)
        self.assertEqual(trade.fee, 0)
        self.assertEqual(apply_returns(trade.holdings_after_fee, (0, 0, 0)), (20, 30, 50))

    def test_exact_compounded_inflation_and_deflation(self):
        cpi = compound_cpi(compound_cpi(1, 0.1), 0.2)
        self.close(cpi, F(33, 25))
        self.close(deflate(100, cpi), F(2500, 33))
        self.close(deflate(110, compound_cpi(1, 0.1)), 100)
        self.close(deflate(100, compound_cpi(1, -0.1)), F(1000, 9))

    def test_wealth_conservation_and_full_investment_seeded(self):
        rng = random.Random(20261019)
        for _ in range(200):
            holdings = [rng.uniform(0, 1000) for _ in range(3)]
            raw = [rng.uniform(0, 1) for _ in range(3)]
            weights = [v / math.fsum(raw) for v in raw]
            trade = rebalance(holdings, weights, rng.uniform(0, 0.02))
            self.close(trade.wealth_before, trade.wealth_after_fee + trade.fee)
            self.close(math.fsum(trade.holdings_after_fee), trade.wealth_after_fee)
            for holding, weight in zip(trade.holdings_after_fee, weights):
                self.assertTrue(math.isfinite(holding) and holding >= 0)
                self.close(holding / trade.wealth_after_fee, weight)
            end = apply_returns(trade.holdings_after_fee, [rng.uniform(-0.9, 1) for _ in range(3)])
            self.assertTrue(all(math.isfinite(v) and v >= 0 for v in end))

    def test_invalid_inputs_rejected(self):
        for holdings in [(-1, 1, 100), (math.nan, 0, 100), (1, 2)]:
            with self.subTest(holdings=holdings), self.assertRaises(ValueError):
                keep(holdings)
        for target in [(0.2, 0.2, 0.2), (-0.1, 0.1, 1), (1, 0, math.inf)]:
            with self.subTest(target=target), self.assertRaises(ValueError):
                rebalance((0, 0, 100), target)
        for fee in [-0.1, math.nan, math.inf, True, 2]:
            with self.subTest(fee=fee), self.assertRaises(ValueError):
                rebalance((0, 0, 100), (1, 0, 0), fee)
        for returns in [(-1.1, 0, 0), (math.nan, 0, 0)]:
            with self.subTest(returns=returns), self.assertRaises(ValueError):
                apply_returns((0, 0, 100), returns)
        with self.assertRaises(ValueError):
            compound_cpi(1, -1)
        with self.assertRaises(ValueError):
            deflate(100, 0)

    def test_exact_total_loss_formula_without_inventing_recovery(self):
        self.assertEqual(apply_returns((20, 30, 50), (-1, 0, 0)), (0, 30, 50))
        self.assertEqual(apply_returns((20, 30, 50), (-1, -1, -1)), (0, 0, 0))
        self.assertEqual(keep((0, 0, 0)).holdings_after_fee, (0, 0, 0))
        self.assertEqual(keep((0, 0, 0)).fee, 0)
        with self.assertRaises(ValueError):
            rebalance((0, 0, 0), (1 / 3,) * 3)


class MetricsTests(ContractAssertions):
    def test_cagr_sample_volatility_and_initial_peak(self):
        result = compute_metrics([110, 99], [100, 110], split="synthetic")
        self.close(result.net_real_cagr_pct, 100 * (math.sqrt(0.99) - 1))
        self.close(result.annual_real_volatility_pct, 100 * 0.2 / math.sqrt(2))
        self.close(result.max_real_drawdown_pct, 10)
        self.vector_close(annual_real_returns([110, 99]), (0.1, -0.1))

    def test_post_fee_loss_before_year_end_recovery_is_included(self):
        result = compute_metrics([110, 120], [99, 88], split="synthetic")
        self.close(result.max_real_drawdown_pct, 20)
        one_year = compute_metrics([110], [99], split="synthetic")
        self.close(one_year.max_real_drawdown_pct, 1)
        self.assertIsNone(one_year.annual_real_volatility_pct)

    def test_zero_terminal_wealth_and_invalid_metrics(self):
        terminal = compute_metrics([0], [99], split="synthetic")
        self.close(terminal.net_real_cagr_pct, -100)
        self.close(terminal.max_real_drawdown_pct, 100)
        for ends, trades in [([], []), ([100], []), ([100], [-1]), ([math.inf], [100]), ([0, 0], [100, 0])]:
            with self.subTest(ends=ends, trades=trades), self.assertRaises(ValueError):
                compute_metrics(ends, trades, split="synthetic")
        with self.assertRaises(ValueError):
            maximum_real_drawdown([])

    def test_linear_interpolated_quantiles(self):
        self.close(linear_quantile([30, 0, 10, 20], 0.1), 3)
        self.close(linear_quantile([30, 0, 10, 20], 0.5), 15)
        self.close(linear_quantile([30, 0, 10, 20], 0.9), 27)
        self.close(linear_quantile([5], 0.1), 5)
        for values, p in [([], 0.5), ([1], -0.1), ([1], 1.1), ([math.nan], 0.5)]:
            with self.assertRaises(ValueError):
                linear_quantile(values, p)


class BaselineTests(ContractAssertions):
    def test_two_period_hand_computable_default_fee_ledger(self):
        rows = toy_rows([(0.2, 0, 0), (-0.1, 0.05, 0)], [0.02, 0.03])
        result = simulate_equal_weight(rows, horizon=2, split="synthetic")
        first, second = result.ledger
        # Independently simplified rational balances, not calls to accounting.
        w1 = F(4792, 45)
        w2_plus = F(5749801, 54000)
        w2 = w2_plus * F(59, 60)
        cpi1, cpi2 = F(51, 50), F(5253, 5000)
        real1, real2 = w1 / cpi1, w2 / cpi2
        self.vector_close(first.holdings_after_fee, (F(599, 18),) * 3)
        self.vector_close(first.holdings_end, (F(599, 15), F(599, 18), F(599, 18)))
        self.close(first.wealth_before, 100)
        self.close(first.intended_transfer, F(200, 3))
        self.close(first.fee, F(1, 6))
        self.close(first.wealth_after_fee, F(599, 6))
        self.close(first.wealth_end, w1)
        self.close(first.cpi_end, cpi1)
        self.close(first.real_wealth_end, real1)
        self.close(second.intended_transfer, F(599, 135))
        self.close(second.fee, F(599, 54000))
        self.close(second.wealth_after_fee, w2_plus)
        self.vector_close(second.holdings_after_fee, (w2_plus / 3,) * 3)
        self.vector_close(second.holdings_end, (w2_plus * F(3, 10), w2_plus * F(7, 20), w2_plus / 3))
        self.close(second.wealth_end, w2)
        self.close(second.cpi_before, cpi1)
        self.close(second.cpi_end, cpi2)
        self.close(second.real_wealth_after_fee, w2_plus / cpi1)
        self.close(second.real_wealth_end, real2)
        r1, r2 = real1 / 100 - 1, real2 / real1 - 1
        self.close(first.annual_net_real_return, r1)
        self.close(second.annual_net_real_return, r2)
        self.close(result.metrics.net_real_cagr_pct, 100 * (math.sqrt(float(real2 / 100)) - 1))
        self.close(result.metrics.annual_real_volatility_pct, 100 * abs(float(r1 - r2)) / math.sqrt(2))
        self.close(result.metrics.max_real_drawdown_pct, -100 * r2)
        self.close(result.trade_share_pct, 100)
        self.close(result.trade_share_ex_initial_pct, 100)
        self.assertEqual(result.horizon, 2)
        self.assertEqual(result.metrics.horizon, 2)
        self.assertEqual(result.metrics.split, "synthetic")
        self.assertEqual(result.split, "synthetic")
        self.assertEqual(result.scenario_id, 7)

    def test_zero_market_returns_keep_initial_fee_loss_and_trade_shares(self):
        result = simulate_equal_weight(toy_rows([(0, 0, 0)] * 3), horizon=3, split="synthetic")
        self.close(result.ledger[-1].real_wealth_end, F(599, 6))
        self.close(result.metrics.max_real_drawdown_pct, F(1, 6))
        self.close(result.trade_share_pct, F(100, 3))
        self.close(result.trade_share_ex_initial_pct, 0)
        for entry in result.ledger[1:]:
            self.close(entry.intended_transfer, 0)
            self.close(entry.fee, 0)
        one = simulate_equal_weight(toy_rows([(0, 0, 0)]), horizon=1, split="synthetic")
        self.assertIsNone(one.trade_share_ex_initial_pct)
        self.assertIsNone(one.metrics.annual_real_volatility_pct)

    def test_zero_fees_returns_and_inflation(self):
        result = simulate_equal_weight(toy_rows([(0, 0, 0)] * 2), horizon=2, split="synthetic", fee_rate=0)
        for entry in result.ledger:
            self.close(entry.wealth_before, 100)
            self.close(entry.wealth_after_fee, 100)
            self.close(entry.wealth_end, 100)
            self.close(entry.real_wealth_end, 100)
            self.assertEqual(entry.decision.action, "rebalance")
            self.vector_close(entry.decision.target, (F(1, 3),) * 3)
        self.close(result.metrics.net_real_cagr_pct, 0)
        self.close(result.metrics.annual_real_volatility_pct, 0)
        self.close(result.metrics.max_real_drawdown_pct, 0)
        # Trade counting measures transfer, even with a zero cost rate.
        self.close(result.trade_share_pct, 50)

    def test_inflation_only_loss(self):
        result = simulate_equal_weight(toy_rows([(0, 0, 0)] * 2, [0.1, 0.2]), horizon=2, split="synthetic", fee_rate=0)
        self.close(result.ledger[-1].wealth_end, 100)
        self.close(result.ledger[-1].real_wealth_end, F(2500, 33))
        self.close(result.metrics.net_real_cagr_pct, 100 * (math.sqrt(float(F(25, 33))) - 1))
        self.close(result.metrics.max_real_drawdown_pct, F(800, 33))
        self.close(result.metrics.annual_real_volatility_pct, 100 * float(F(5, 66)) / math.sqrt(2))

    def test_complete_thirty_period_ledger_invariants(self):
        rng = random.Random(31)
        rows = toy_rows([tuple(rng.uniform(-0.3, 0.4) for _ in range(3)) for _ in range(30)], [rng.uniform(-0.02, 0.1) for _ in range(30)], scenario=11)
        result = simulate_equal_weight(rows, horizon=30, split="development")
        previous_wealth, previous_cpi, previous_real = 100.0, 1.0, 100.0
        previous_holdings = (0, 0, 100)
        for entry in result.ledger:
            self.close(entry.wealth_before, previous_wealth)
            self.vector_close(entry.holdings_before, previous_holdings)
            self.close(entry.wealth_before, entry.wealth_after_fee + entry.fee)
            self.close(entry.wealth_after_fee, math.fsum(entry.holdings_after_fee))
            self.close(entry.wealth_end, math.fsum(entry.holdings_end))
            self.vector_close([x / entry.wealth_after_fee for x in entry.holdings_after_fee], (F(1, 3),) * 3)
            self.assertTrue(all(math.isfinite(x) and x >= 0 for x in entry.holdings_after_fee + entry.holdings_end))
            self.close(entry.cpi_before, previous_cpi)
            self.close(entry.cpi_end, previous_cpi * (1 + entry.inflation))
            self.close(entry.real_wealth_after_fee, entry.wealth_after_fee / previous_cpi)
            self.close(entry.real_wealth_end, entry.wealth_end / entry.cpi_end)
            self.close(entry.annual_net_real_return, entry.real_wealth_end / previous_real - 1)
            previous_wealth, previous_cpi, previous_real = entry.wealth_end, entry.cpi_end, entry.real_wealth_end
            previous_holdings = entry.holdings_end
        # Structured results can be serialized without a third-party dependency.
        self.assertEqual(len(json.loads(json.dumps(asdict(result)))["ledger"]), 30)

    def test_explicit_horizon_csv_strings_and_future_outcomes_not_read(self):
        rows = [{k: str(v) for k, v in row.items()} for row in toy_rows([(0, 0, 0)])]
        rows.append({"scenario_id": "7", "period": "2"})  # no outcome fields
        result = simulate_equal_weight(rows, horizon=1, split="development")
        self.assertEqual(len(result.ledger), 1)
        self.close(result.ledger[0].real_wealth_end, F(599, 6))

    def test_reject_mixed_scenarios_even_beyond_horizon_and_invalid_metadata(self):
        rows = toy_rows([(0, 0, 0)] * 2)
        rows[1]["scenario_id"] = 8
        with self.assertRaisesRegex(ValueError, "exactly one scenario"):
            simulate_equal_weight(rows, horizon=1, split="synthetic")
        rows = toy_rows([(0, 0, 0)] * 2)
        rows[1]["period"] = 1
        with self.assertRaises(ValueError):
            simulate_equal_weight(rows, horizon=2, split="synthetic")
        for horizon in [0, 3, 1.5, True]:
            with self.subTest(horizon=horizon), self.assertRaises(ValueError):
                simulate_equal_weight(toy_rows([(0, 0, 0)] * 2), horizon=horizon, split="synthetic")
        with self.assertRaises(ValueError):
            simulate_equal_weight([], horizon=1, split="synthetic")

    def test_final_split_and_development_id_guards(self):
        # IDs only: no final outcome fixture or repository data is accessed.
        metadata_only = [{"scenario_id": 121, "period": 1}]
        with self.assertRaises(ValueError):
            simulate_equal_weight(metadata_only, horizon=1, split="development")
        with self.assertRaises(ValueError):
            simulate_equal_weight(metadata_only, horizon=1, split="final_holdout")

    def test_terminal_total_loss_is_measured_but_not_restarted(self):
        rows = toy_rows([(-1, -1, -1), (0, 0, 0)])
        result = simulate_equal_weight(rows, horizon=1, split="synthetic")
        self.assertEqual(result.ledger[0].holdings_end, (0, 0, 0))
        self.close(result.metrics.net_real_cagr_pct, -100)
        self.close(result.metrics.max_real_drawdown_pct, 100)
        with self.assertRaisesRegex(ValueError, "wealth must be positive"):
            simulate_equal_weight(rows, horizon=2, split="synthetic")


class PrefixBoundaryTests(ContractAssertions):
    def test_callback_gets_immutable_prefix_only(self):
        observation = Observation(7, 1, (0.1, 0.02, 0.01), 0.03)
        seen = []

        def callback(context):
            seen.append(context)
            self.assertEqual(context.history, (observation,))
            self.assertEqual(context.period, 2)
            self.assertFalse(hasattr(context, "current_returns"))
            with self.assertRaises(FrozenInstanceError):
                context.period = 3
            with self.assertRaises(TypeError):
                context.history[0].returns[0] = 999
            return Decision("keep")

        decision = decide_from_history(callback, scenario_id=7, period=2, holdings=(1, 2, 97), history=[observation])
        self.assertEqual(decision.action, "keep")
        self.assertEqual(len(seen), 1)
        for history in [[], [observation, observation], [Observation(8, 1, (0, 0, 0), 0)]]:
            with self.assertRaises(ValueError):
                decide_from_history(callback, scenario_id=7, period=2, holdings=(0, 0, 100), history=history)

    def test_decision_exists_before_current_outcomes_are_accessed(self):
        decided = set()

        class GuardedRow(dict):
            def __getitem__(self, key):
                if key in ("equity_return", "bond_return", "bill_proxy_return", "inflation"):
                    if dict.__getitem__(self, "period") not in decided:
                        raise AssertionError("outcome accessed before its decision")
                return super().__getitem__(key)

        def callback(context):
            self.assertEqual(len(context.history), context.period - 1)
            decision = Decision("rebalance", (1 / 3,) * 3)
            decided.add(context.period)
            return decision

        rows = [GuardedRow(row) for row in toy_rows([(0.1, 0, 0), (0, 0.1, 0)])]
        with patch("safeinvest.backtest._equal_weight_decision", callback):
            simulate_equal_weight(rows, horizon=2, split="synthetic")
        self.assertEqual(decided, {1, 2})

    def test_future_perturbation_preserves_earlier_contexts_and_ledgers(self):
        original = toy_rows([(0.1, 0, 0), (0, -0.1, 0), (0.2, 0.2, 0.2)])
        changed = [dict(row) for row in original]
        changed[2].update(equity_return=-0.8, bond_return=0.9, inflation=0.5)
        captured = []

        def callback(context):
            captured.append(context)
            return Decision("rebalance", (1 / 3,) * 3)

        with patch("safeinvest.backtest._equal_weight_decision", callback):
            first = simulate_equal_weight(original, horizon=3, split="synthetic")
            before = tuple(captured)
            captured.clear()
            second = simulate_equal_weight(changed, horizon=3, split="synthetic")
        self.assertEqual(before, tuple(captured))
        self.assertEqual(first.ledger[:2], second.ledger[:2])
        self.assertNotEqual(first.ledger[2].real_wealth_end, second.ledger[2].real_wealth_end)

    def test_invalid_decisions_rejected(self):
        for args in [("rebalance",), ("keep", (1, 0, 0)), ("unknown",)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                Decision(*args)
        with self.assertRaises(ValueError):
            decide_from_history(lambda context: None, scenario_id=7, period=1, holdings=(0, 0, 100), history=[])


if __name__ == "__main__":
    unittest.main()
