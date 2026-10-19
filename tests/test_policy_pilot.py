"""Chief-authored synthetic checks, not an independent acceptance of chief code."""

from dataclasses import replace
from fractions import Fraction as F
import json
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from safeinvest.backtest import DecisionContext, Observation
from safeinvest.policy_pilot import (
    CostAwarePolicy, EmpiricalPrior, EPSILON, TARGETS, choose_target,
    real_gross, score_target, simulate_synthetic,
)


def rows(n=30, *, rates=(0.0, 0.0, 0.0), inflation=0.0, scenario=1):
    return [dict(scenario_id=scenario, period=t, equity_return=rates[0],
                 bond_return=rates[1], bill_proxy_return=rates[2], inflation=inflation)
            for t in range(1, n + 1)]


def run(data, mode="balanced_cost", prior=None, horizon=None, **kwargs):
    prior = prior if prior is not None else EmpiricalPrior(((1.1, 1.02, 1.0),))
    return simulate_synthetic(data, mode=mode, prior=prior,
                              horizon=horizon or len(data), **kwargs)


class PolicyKernelTests(unittest.TestCase):
    def test_rational_initial_fee_and_ce(self):
        result, reviews = run(rows(1, rates=(.1, .02, 0)))
        score = reviews[0].scores[0]
        expected = {
            "ce_keep": F(1), "ce_target": F(26, 25), "tau": F(2, 3),
            "fee_fraction": F(1, 600), "pre_cost_benefit": F(1, 25),
            "modeled_fee_impact": F(13, 7500),
            "conservative_score": F(3887, 3750), "true_net_ce": F(7787, 7500),
        }
        for name, value in expected.items():
            self.assertAlmostEqual(getattr(score, name), float(value), places=12)
        entry = result.ledger[0]
        self.assertAlmostEqual(entry.fee, float(F(1, 6)), places=12)
        self.assertAlmostEqual(entry.wealth_end, float(F(7787, 75)), places=12)
        self.assertEqual(reviews[0].action, "rebalance")
        self.assertFalse(reviews[0].initial_allocation_deferred)
        self.assertGreater(score.pre_cost_benefit, 2 * score.modeled_fee_impact)
        self.assertGreater(score.true_net_ce, score.conservative_score)

    def test_inverse_cube_mixture_and_homogeneity(self):
        prior = EmpiricalPrior(((.9, .9, .9), (1.1, 1.1, 1.1)))
        recent = tuple((x, x, x) for x in (.8, 1.05, 1., 1.2, 1.02))
        exact = (F(15, 2) * (F(9, 10) ** -3 + F(11, 10) ** -3)
                 + sum(x ** -3 for x in (F(4, 5), F(21, 20), F(1), F(6, 5), F(51, 50)))) / 20
        ce = prior.certainty_equivalent((.2, .3, .5), recent)
        self.assertAlmostEqual(ce, float(exact) ** (-1 / 3), places=12)
        scale = .997
        scaled = EmpiricalPrior(tuple(tuple(scale*x for x in row) for row in prior.gross))
        self.assertAlmostEqual(scaled.certainty_equivalent((.2, .3, .5),
                               tuple(tuple(scale*x for x in row) for row in recent)), scale*ce, places=12)
        for scale in (1e-100, 1e100):
            stable = EmpiricalPrior(((scale, scale, scale),))
            self.assertTrue(math.isclose(stable.certainty_equivalent((.2,.3,.5)), scale, rel_tol=1e-12))

    def test_subnormal_gross_is_not_lost_before_log_moment(self):
        smallest = float.fromhex("0x0.0000000000001p-1022")
        for weights in ((.2, .3, .5), (0., 0., 1.), (1/3, 1/3, 1/3)):
            for factor in (smallest, 2*smallest, 16*smallest):
                prior = EmpiricalPrior(((factor, factor, factor),))
                for n in range(6):
                    recent = ((factor, factor, factor),)*n
                    # A constant support has this CE for every mixture mass.
                    self.assertEqual(prior.certainty_equivalent(weights, recent), factor)
        # With a single observation CE equals its exact weighted gross.
        weights = (.25, .25, .5)
        row = (smallest, 3*smallest, 6*smallest)
        expected = float(sum(F(w)*F(g) for w,g in zip(weights,row)))
        self.assertEqual(EmpiricalPrior((row,)).certainty_equivalent(weights), expected)
        # A zero-weight enormous asset cannot mask tiny held support.
        self.assertEqual(EmpiricalPrior(((sys.float_info.max,smallest,smallest),))
                         .certainty_equivalent((0.,.5,.5)), smallest)

    def test_exact_inflation_conversion(self):
        gross = real_gross((.1, .02, 0), .02)
        for actual, expected in zip(gross, (F(55,51), F(1), F(50,51))):
            self.assertAlmostEqual(actual, float(expected), places=14)

    def test_strict_keep_gate_and_tie_priority(self):
        prior = EmpiricalPrior(((1.1, 1.02, 1),))
        base = score_target("active", TARGETS["balanced"], (0,0,1), prior, (), .0025)
        threshold = 1.0 + EPSILON
        below = replace(base, conservative_score=math.nextafter(threshold, -math.inf))
        at = replace(base, conservative_score=threshold)
        above = replace(base, conservative_score=math.nextafter(threshold, math.inf))
        self.assertIsNone(choose_target((below, at), 1.0))
        self.assertIs(choose_target((above,), 1.0), above)
        first = replace(base, name="active", conservative_score=1.02)
        second = replace(base, name="defensive", conservative_score=1.02+EPSILON/2)
        self.assertIs(choose_target((first, second), 1.), first)
        # A preferred target that cannot beat keep never inherits another's pass.
        self.assertIs(choose_target((at, above), 1.0), above)

    def test_equal_returns_keep_at_both_fee_rates_and_zero(self):
        for fee in (0, .0025, .005):
            result, reviews = run(rows(7, rates=(.02,.02,.02)),
                                  prior=EmpiricalPrior(((1.02,1.02,1.02),)), fee_rate=fee)
            self.assertTrue(all(r.action == "keep" and r.initial_allocation_deferred for r in reviews))
            self.assertTrue(all(e.fee == 0 and e.holdings_after_fee == e.holdings_before for e in result.ledger))

    def test_deferred_initial_allocation_can_retry_using_completed_history(self):
        data = rows(2)
        data[0]["equity_return"] = 1.0
        prior = EmpiricalPrior(((1,1,1),))
        _, reviews = run(data, mode="balanced_context", prior=prior)
        self.assertEqual([r.action for r in reviews], ["keep", "rebalance"])
        self.assertTrue(all(r.initial_allocation_deferred for r in reviews))
        self.assertEqual([r.first_deployment_year for r in reviews], [None, 2])
        self.assertEqual([r.reason for r in reviews], ["benefit_gate_failed", "initial_allocation"])
        self.assertEqual(reviews[1].recent_count, 1)
        self.assertEqual(reviews[1].prior_mass, 15/16)
        _, fixed = run(data, mode="balanced_cost", prior=prior)
        self.assertEqual([r.action for r in fixed], ["keep", "keep"])

    def test_adaptive_first_eligible_review_and_active_target(self):
        _, reviews = run(rows(8), mode="balanced_adaptive",
                         prior=EmpiricalPrior(((1.3,1.02,1),)))
        self.assertTrue(all(len(r.scores) == 1 for r in reviews[:5]))
        self.assertEqual(reviews[5].recent_count, 5)
        self.assertEqual(reviews[5].prior_mass, .75)
        self.assertEqual(reviews[5].action, "target_change")
        self.assertEqual(reviews[5].active_after, "growth_tilt")
        self.assertTrue(reviews[5].executed_target_change)
        self.assertEqual(reviews[6].scores[0].name, "growth_tilt")

    def test_failing_proposals_never_change_active_target(self):
        _, reviews = run(rows(8), mode="balanced_adaptive", prior=EmpiricalPrior(((1,1,1),)))
        self.assertTrue(all(r.active_after == "balanced" and not r.executed_target_change for r in reviews))
        self.assertEqual(len(reviews[5].scores), 3)

    def test_real_loss_review_lags_and_latches(self):
        data = rows(5)
        data[0]["inflation"] = .4
        data[1]["equity_return"] = 1.0
        result, reviews = run(data)
        self.assertEqual(reviews[0].action, "rebalance")
        self.assertTrue(all(r.action == "human_review" for r in reviews[1:]))
        self.assertGreater(reviews[1].observed_max_drawdown_pct, 25)
        for entry in result.ledger[1:]:
            self.assertEqual(entry.holdings_after_fee, entry.holdings_before)
            self.assertEqual(entry.intended_transfer, 0)
            self.assertEqual(entry.fee, 0)
        self.assertNotEqual(result.ledger[1].holdings_end, result.ledger[1].holdings_after_fee)

    def test_post_fee_loss_survives_same_year_recovery(self):
        result, reviews = run(rows(3, rates=(.5,.5,.5)), review_drawdown_pct=.1)
        self.assertGreater(result.ledger[0].real_wealth_end, 100)
        self.assertEqual(reviews[0].action, "rebalance")
        self.assertAlmostEqual(reviews[1].observed_max_drawdown_pct, float(F(1,6)), places=12)
        self.assertEqual(reviews[1].action, "human_review")

    def test_prefix_and_fresh_state_for_all_declared_modes(self):
        data = rows(30)
        for i, row in enumerate(data):
            row["equity_return"] = (.05, -.08, .03)[i%3]
            row["bond_return"] = (.01, .02)[i%2]
            row["inflation"] = .015
        for mode in ("conservative_cost","balanced_cost","growth_cost","balanced_context","balanced_adaptive"):
            full, diagnostics = run(data, mode=mode)
            for h in (1,5,6,15,25,30):
                prefix, partial = run(data[:h], mode=mode)
                self.assertEqual(prefix.ledger, full.ledger[:h])
                self.assertEqual(partial, diagnostics[:h])
            other = [dict(row, scenario_id=2) for row in data]
            repeated, _ = run(other, mode=mode)
            self.assertEqual(repeated.metrics, full.metrics)

    def test_future_perturbation_does_not_change_current_decision(self):
        data = rows(10)
        changed = [dict(row) for row in data]
        for row in changed[5:]:
            row.update(equity_return=-.7, bond_return=.5, inflation=.6)
        first, before = run(data, mode="balanced_adaptive")
        second, after = run(changed, mode="balanced_adaptive")
        self.assertEqual(before[:6], after[:6])
        self.assertEqual(first.ledger[:5], second.ledger[:5])
        self.assertEqual(first.ledger[5].decision, second.ledger[5].decision)
        self.assertNotEqual(first.ledger[5].wealth_end, second.ledger[5].wealth_end)

    def test_state_reuse_and_mismatched_accounting_are_rejected(self):
        prior = EmpiricalPrior(((1.1,1.02,1),))
        callback = CostAwarePolicy("balanced_cost", prior)
        first = DecisionContext(1,1,(0.,0.,100.),())
        callback(first)
        with self.assertRaises(ValueError):
            callback(first)
        history = (Observation(2,1,(0,0,0),0),)
        with self.assertRaises(ValueError):
            callback(DecisionContext(2,2,callback._after,history))
        with self.assertRaises(ValueError):
            callback(DecisionContext(1,2,(0,0,100),(Observation(1,1,(0,0,0),0),)))

    def test_invalid_gross_including_final_observation_is_rejected(self):
        for gross in ((), ((1,1,0),), ((1,float("nan"),1),), ((1,1,float("inf")),)):
            with self.assertRaises(ValueError):
                EmpiricalPrior(gross)
        for key, bad in (("equity_return",-1), ("inflation",-1), ("bond_return",float("nan"))):
            data = rows(1)
            data[0][key] = bad
            with self.assertRaises(ValueError):
                run(data)
        with self.assertRaises(ValueError):
            EmpiricalPrior(((1,1,1),)).certainty_equivalent((.2,.3,.5), ((1,1,1),)*6)

    def test_global_tie_anchor_rejects_nontransitive_chain(self):
        base = score_target("active", TARGETS["balanced"], (0,0,1),
                            EmpiricalPrior(((1.1,1.02,1),)), (), .0025)
        scores = tuple(replace(base, name=name, conservative_score=1.02+x*EPSILON)
                       for name,x in (("active",0),("defensive",.75),("growth_tilt",1.5)))
        self.assertEqual(choose_target(scores,1).name,"defensive")

    def test_tiny_executed_request_preserves_fee_despite_reporting_threshold(self):
        data=rows(2)
        data[0].update(equity_return=-1+1e-13,bond_return=-1+1e-12,bill_proxy_return=-1+1e-13)
        result,reviews=run(data,prior=EmpiricalPrior(((1.3,1.02,1),)),review_drawdown_pct=100)
        entry=result.ledger[1]
        self.assertEqual(reviews[1].action,"rebalance")
        self.assertFalse(reviews[1].is_trade)
        self.assertGreater(entry.intended_transfer,0)
        self.assertLess(entry.intended_transfer,1e-10)
        self.assertGreater(entry.fee,0)
        self.assertNotEqual(entry.holdings_after_fee,entry.holdings_before)
        self.assertEqual(reviews[1].first_deployment_year,1)

    def test_k2_exact_subnormal_midpoint_grid_and_recent_mixture(self):
        # Exact constant support reduces CE to its rational weighted gross.
        # This tests both midpoint directions and heterogeneous support.
        import itertools
        tiny = math.ulp(0.)
        for weights in ((.25,.25,.5),(.2,.3,.5),(0.,.5,.5),(1/3,)*3):
            total = sum(F(x) for x in weights)
            for units in itertools.product(range(1,9), repeat=3):
                support = tuple(x*tiny for x in units)
                expected = float(sum(F(w)*F(g) for w,g in zip(weights,support))/total)
                actual = EmpiricalPrior((support,)).certainty_equivalent(weights)
                self.assertEqual(actual, expected, (weights, units))
        # For all 15:n mixtures, independently compare cubed midpoints with
        # the exact inverse-cube moment; no production rounding helper used.
        weights = (.25,.25,.5)
        prior_row = (tiny,tiny,4*tiny)
        recent_row = (tiny,3*tiny,5*tiny)
        prior_gross = F(5,2)*F(tiny)
        recent_gross = F(7,2)*F(tiny)
        for n in range(6):
            actual = EmpiricalPrior((prior_row,)).certainty_equivalent(weights,(recent_row,)*n)
            moment = (15/prior_gross**3+n/recent_gross**3)/(15+n)
            lower = (F(math.nextafter(actual,0.))+F(actual))/2
            upper = (F(math.nextafter(actual,math.inf))+F(actual))/2
            self.assertLessEqual(lower**3*moment,1)
            self.assertGreaterEqual(upper**3*moment,1)
            constant = EmpiricalPrior((prior_row,)).certainty_equivalent(weights,(prior_row,)*n)
            self.assertEqual(constant,2*tiny)

    def test_parameters_match_published_proposal(self):
        config = json.loads((ROOT / "specs/development_policy_pilot_v2.json").read_bytes())
        mapping = {"defensive":"balanced_defensive", "growth_tilt":"balanced_growth_tilt"}
        for name, target in TARGETS.items():
            expected = tuple(float(F(str(x))) for x in config["targets"][mapping.get(name,name)])
            self.assertEqual(target, expected)
        self.assertEqual(config["gamma"],4)
        self.assertEqual(config["prior_equivalent_years"],15)
        self.assertEqual(config["history_window"],5)
        self.assertFalse(config["production_execution_authorized"])


if __name__ == "__main__":
    unittest.main()
