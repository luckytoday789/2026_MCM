"""Generated personalized fixtures only; no competition data reads."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
import csv
import io
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from safeinvest.policy_calibration import FIELDS, build_synthetic_calibrations
from safeinvest.policy_cases import build_case_tables
from safeinvest.policy_personalized import build_personalized_case_tables as build, _outcome_screen, PROFILES
from safeinvest.policy_pilot import EmpiricalPrior


def fixture(returns=0., inflation=0.):
    rows = [dict(zip(FIELDS, (s, t, returns, returns, returns, inflation)))
            for s in range(1, 5) for t in range(1, 31)]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader(); writer.writerows(rows)
    cal = build_synthetic_calibrations(stream.getvalue().encode(), scenario_count=4, periods=30)
    return rows, cal


def run_case(rows, cal, profile="A", cls="conservative", fee=.0025):
    return build(rows, calibrations=cal, profile_id=profile, proposed_class=cls,
                 fee_rate=fee, split="synthetic", upstream_reasons=["fixture_assignment"])


class PersonalizedTests(unittest.TestCase):
    def test_profiles_fees_counts_and_rational_inflation(self):
        rows, cal = fixture(.125, .25)
        original = deepcopy(rows)
        for profile, (h, tol, _) in PROFILES.items():
            for fee in (.0025, .005):
                out = run_case(rows, cal, profile, fee=fee)
                self.assertEqual(out.case.counts["annual_ledgers"], 4*h)
                self.assertEqual(out.case.counts["decisions"], 4*h)
                self.assertEqual(out.case.counts["scenario_metrics"], 4)
                self.assertEqual(out.case.counts["summary"], 1)
                self.assertEqual(out.rescreen["denominator"], 4)
                for r in out.case.scenario_metrics:
                    terminal = float(100 * Fraction(9, 10)**h)
                    self.assertAlmostEqual(r["terminal_real_wealth"], terminal, places=9)
                    self.assertAlmostEqual(r["max_real_drawdown_pct"], 100-terminal, places=9)
                    self.assertEqual(r["nominal_fee_sum"], 0)
                    self.assertEqual(r["review_threshold_pct"], tol)
                self.assertEqual(out.rescreen["recommended_class"], None)
                self.assertEqual(out.rescreen["exceedance_count"], 4)
                self.assertEqual(out.case.counts["target_scores"],
                                 sum(r["action"] != "human_review" for r in out.case.decisions))
        self.assertEqual(rows, original)

    def test_B_exact_generic_prefix_all_fixed_classes_and_fees(self):
        rows, cal = fixture(.125, .25)
        for cls in ("conservative", "balanced"):
            for fee in (.0025, .005):
                own = run_case(rows, cal, "B", cls, fee).case
                generic = build_case_tables(rows, calibrations=cal, mode=cls+"_cost",
                                           fee_rate=fee, split="synthetic", horizons=(15, 30))
                for name in ("annual_ledgers", "decisions", "target_scores", "scenario_metrics", "summary"):
                    actual = [{k:v for k,v in r.items() if k not in ("profile_id", "review_threshold_pct")}
                              for r in getattr(own, name)]
                    expected = [r for r in getattr(generic, name)
                                if r.get("period", 0) <= 15 and r.get("horizon", 15) == 15]
                    self.assertEqual(actual, expected, name)

    def test_exact_equality_latch_and_pending_holdings(self):
        rows, cal = fixture()
        # Every return is -25% in year 1: exact 25% loss, then recovery.
        for r in rows:
            for name in FIELDS[2:5]: r[name] = -.25 if r["period"] == 1 else .125
        out = run_case(rows, cal, "B")
        for r in out.case.decisions:
            self.assertEqual(r["action"], "keep" if r["period"] == 1 else "human_review")
            if r["period"] > 1:
                self.assertEqual(r["actual_fee"], 0)
                self.assertEqual(r["observed_max_drawdown_pct"], 25.)
        for r in out.case.annual_ledgers:
            self.assertEqual(r["fee"], 0)
            for asset in ("equity", "bond", "bill_proxy"):
                self.assertEqual(r["holdings_before_"+asset], r["holdings_after_fee_"+asset])
        self.assertTrue(all(r["first_latch_year"] == 2 for r in out.case.scenario_metrics))
        self.assertEqual(out.rescreen["exceedance_count"], 0)
        self.assertTrue(out.rescreen["risk_pass"])

    def test_final_year_crossing_no_fictional_review_or_suffix_leak(self):
        rows, cal = fixture()
        for r in rows:
            if r["period"] == 5:
                r["inflation"] = 1.
        out = run_case(rows, cal)
        self.assertTrue(all(r["first_latch_year"] is None for r in out.case.scenario_metrics))
        self.assertTrue(all(r["max_real_drawdown_pct"] == 50 for r in out.case.scenario_metrics))
        changed = deepcopy(rows)
        for r in changed:
            if r["period"] > 5:
                r["equity_return"] = 2.
                r["inflation"] = 3.
        self.assertEqual(out, run_case(changed, cal))

    def test_fee_before_returns_and_fresh_state(self):
        rows, cal = fixture()
        # An explicit favorable prior forces initial deployment; metadata is
        # illustrative and does not purport to certify source provenance.
        folds = tuple(replace(f, prior=EmpiricalPrior(((2., 1., 1.),)*len(f.training_keys)))
                      for f in cal.folds)
        for fee in (.0025, .005):
            out = run_case(rows, folds, fee=fee)
            first = [r for r in out.case.annual_ledgers if r["period"] == 1]
            self.assertEqual(len(first), 4)
            for r in first:
                self.assertAlmostEqual(r["intended_transfer"], 35., places=12)
                self.assertAlmostEqual(r["fee"], 35*fee, places=12)
                self.assertAlmostEqual(r["wealth_after_fee"], 100-35*fee, places=12)
                self.assertEqual(r["wealth_after_fee"], r["wealth_end"])
            self.assertTrue(all(r["first_deployment_year"] == 1 for r in out.case.scenario_metrics))
            self.assertEqual(out, run_case(rows, folds, fee=fee))

    def test_inclusive_screens_strict_count_and_failure_combinations(self):
        for growth, loss, flags in ((0., 10., (True, True)), (-.1, 10., (True, False)),
                                    (0., 11., (False, True)), (-.1, 11., (False, False))):
            out = _outcome_screen([growth]*120, [loss]*120, 10.)
            self.assertEqual((out["risk_pass"], out["purchasing_power_pass"]), flags)
            self.assertEqual(len(out["reasons"]), flags.count(False))
        out = _outcome_screen([0.]*120, [10.]*119+[11.], 10.)
        self.assertTrue(out["risk_pass"])
        self.assertEqual(out["exceedance_count"], 1)
        self.assertEqual(out["exceedance_fraction"], 1/120)
        self.assertFalse(_outcome_screen([math.nextafter(0., -1.)]*120, [10.]*120, 10.)["purchasing_power_pass"])
        self.assertFalse(_outcome_screen([0.]*120, [math.nextafter(10., math.inf)]*120, 10.)["risk_pass"])

    def test_referral_does_not_touch_rows_or_priors_and_null_semantics(self):
        reasons = ["no_qualifying_class"]
        with patch("safeinvest.policy_personalized._rows", side_effect=AssertionError("must not run")), \
             patch("safeinvest.policy_personalized._priors", side_effect=AssertionError("must not fit")):
            out = build(None, calibrations=None, profile_id="A", proposed_class=None,
                        fee_rate=.0025, split="synthetic", upstream_reasons=reasons)
        self.assertIsNone(out.case)
        self.assertEqual(out.rescreen["denominator"], 0)
        for name in ("recommended_class", "risk_pass", "purchasing_power_pass", "exceedance_count",
                     "exceedance_fraction", "median_growth_pct", "p90_loss_pct"):
            self.assertIsNone(out.rescreen[name])
        reasons.append("changed")
        self.assertEqual(out.rescreen["upstream_reasons"], ["no_qualifying_class"])

    def test_post_fee_crossing_survives_recovery_until_next_review(self):
        for fee in (.0025, .005):
            rows, cal = fixture()
            folds = tuple(replace(f, prior=EmpiricalPrior(((2., 1., 1.),)*len(f.training_keys)))
                          for f in cal.folds)
            # Construct year 1's end at 90.001, just above A's loss threshold.
            # Equity loses 50%; the exact remaining-asset factor balances wealth.
            post = Fraction(100) - 35*Fraction(str(fee))
            other = (Fraction(90001,1000) - post*Fraction(15,100)*Fraction(1,2)) / (post*Fraction(85,100))
            for r in rows:
                if r["period"] == 1:
                    r["equity_return"] = -.5
                    r["bond_return"] = r["bill_proxy_return"] = float(other-1)
                elif r["period"] == 2:
                    for name in FIELDS[2:5]: r[name] = .25
            out = run_case(rows, folds, fee=fee)
            annual = [r for r in out.case.annual_ledgers if r["scenario_id"] == 1]
            decisions = [r for r in out.case.decisions if r["scenario_id"] == 1]
            self.assertAlmostEqual(annual[0]["real_wealth_end"], 90.001, places=10)
            self.assertEqual(decisions[1]["action"], "rebalance")
            self.assertLess(annual[1]["real_wealth_after_fee"], 90.)
            self.assertGreater(annual[1]["real_wealth_end"], 100.)
            self.assertEqual(decisions[2]["action"], "human_review")
            self.assertEqual(annual[2]["fee"], 0.)
            self.assertGreater(out.case.scenario_metrics[0]["max_real_drawdown_pct"], 10.)

    def test_current_year_cannot_change_its_own_decision(self):
        rows, cal = fixture()
        changed = deepcopy(rows)
        for r in changed:
            if r["period"] == 3: r["inflation"] = 1.
        before = run_case(rows, cal).case
        after = run_case(changed, cal).case
        self.assertEqual([r for r in before.decisions if r["period"] <= 3],
                         [r for r in after.decisions if r["period"] <= 3])
        self.assertNotEqual(before.scenario_metrics, after.scenario_metrics)
    def test_invalid_inputs_fail_not_referral(self):
        rows, cal = fixture()
        kwargs = dict(calibrations=cal, profile_id="A", proposed_class="conservative", fee_rate=.0025, split="synthetic")
        for change in (dict(split="final"), dict(split="development"), dict(profile_id="Z"),
                       dict(proposed_class="balanced_adaptive"), dict(proposed_class="balanced"),
                       dict(proposed_class=None), dict(fee_rate=True), dict(fee_rate="0.0025"),
                       dict(fee_rate=float("nan")), dict(upstream_reasons="reason")):
            with self.subTest(change=change), self.assertRaises(ValueError): build(rows, **(kwargs|change))
        broken = list(cal.folds); broken[0] = replace(broken[0], training_ids=(1,))
        with self.assertRaises(ValueError): build(rows, **(kwargs|dict(calibrations=broken)))
        for growth, loss, tol in (([], [], 10), ([True], [10], 10), ([0], [float("nan")], 10),
                                  ([0], [-1], 10), ([0], [10], True)):
            with self.assertRaises(ValueError): _outcome_screen(growth, loss, tol)


if __name__ == "__main__": unittest.main()
