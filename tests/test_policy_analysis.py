"""Generated grids only: no competition input or saved outcome reads."""
from copy import deepcopy
import json
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from safeinvest.policy_analysis import AnalysisTables, build_analysis_tables

MODES = ("bills_keep", "equal_weight_annual", "equal_weight_buy_hold", "conservative_cost",
         "balanced_cost", "growth_cost", "balanced_context", "balanced_adaptive")
FEES = (.0025, .005)
HORIZONS = (5, 6, 15, 25, 30)
VALUES = ("net_real_cagr_pct", "max_real_drawdown_pct", "terminal_real_wealth",
          "nominal_fee_sum", "trade_share_pct", "trade_share_ex_initial_pct")
UNITS = {"monetary_units": "nominal units; real wealth in CPI_0 purchasing power",
         "return_units": "annual simple decimal", "cpi_units": "price index; CPI_0=1",
         "growth_units": "percentage points per year",
         "volatility_units": "percentage points; annual sample ddof=1",
         "loss_units": "percent of running real peak", "trade_share_units": "percent of annual reviews"}


def config():
    return json.loads((ROOT / "specs/development_policy_pilot_v2.json").read_text())


def grid(n=4, split="synthetic"):
    # Explicit metric-level seam. These are deliberately assigned test statistics,
    # not claims of a coherent simulated return path or source authenticity.
    result = []
    for mode in MODES:
        for fee in FEES:
            for h in HORIZONS:
                for s in range(1, n + 1):
                    result.append({"mode": mode, "fee_rate": fee, "horizon": h,
                        "scenario_id": s, "fold_id": (s - 1) % 4, "split": split,
                        "net_real_cagr_pct": 0., "annual_real_volatility_pct": 2.,
                        "max_real_drawdown_pct": 5., "terminal_real_wealth": 100.,
                        "nominal_fee_sum": 0., "trade_count": 0, "review_count": h,
                        "later_trade_count": 0, "later_review_count": h - 1,
                        "trade_share_pct": 0., "trade_share_ex_initial_pct": 0.,
                        "drawdown_peak_year": 0, "drawdown_peak_kind": "initial",
                        "drawdown_trough_year": 1, "drawdown_trough_kind": "end",
                        "human_review_count": None if mode in MODES[:3] else 0,
                        "human_review_share_pct": None if mode in MODES[:3] else 0.,
                        "first_latch_year": None, "target_change_count": None if mode in MODES[:3] else 0,
                        "first_deployment_year": None,
                        "initial_allocation_deferred": None if mode in MODES[:3] else True, **UNITS})
    return result


def set_case(rows, mode, *, fee=None, h=None, **changes):
    for row in rows:
        if row["mode"] == mode and (fee is None or row["fee_rate"] == fee) and (h is None or row["horizon"] == h):
            for name, value in changes.items():
                row[name] = value[row["scenario_id"] - 1] if isinstance(value, (tuple, list)) else value
    return rows


def build(rows, split="synthetic"):
    return build_analysis_tables(rows, config=config(), split=split)


def gate(tables, candidate="balanced_context", reference="balanced_cost", fee=.0025, h=30):
    return next(r for r in tables.comparison_gates if (r["candidate_mode"], r["reference_mode"],
                r["fee_rate"], r["horizon"]) == (candidate, reference, fee, h))


def screen(tables, profile, cls="conservative", fee=.0025):
    return next(r for r in tables.profile_screen if (r["profile"], r["candidate_class"], r["fee_rate"]) == (profile, cls, fee))


def recommendation(tables, profile, fee=.0025):
    return next(r for r in tables.profile_recommendations if (r["profile"], r["fee_rate"]) == (profile, fee))


class AnalysisTests(unittest.TestCase):
    def test_complete_counts_contrasts_units_and_source_differences(self):
        rows = grid()
        set_case(rows, "balanced_context", net_real_cagr_pct=.25, max_real_drawdown_pct=6.,
                 terminal_real_wealth=120., nominal_fee_sum=2., trade_count=1, trade_share_pct=0.)
        # Shares must reflect each own horizon, not one common H.
        for r in rows:
            if r["mode"] == "balanced_context":
                r["trade_share_pct"] = 100 / r["horizon"]
                r["human_review_count"] = 1
                r["human_review_share_pct"] = 100 / r["horizon"]
                r["first_latch_year"] = r["horizon"]
                r["target_change_count"] = 1
        t = build(rows)
        self.assertIsInstance(t, AnalysisTables)
        self.assertEqual((len(t.paired_differences), len(t.comparison_gates), len(t.profile_screen),
                          len(t.profile_recommendations)), (400, 100, 30, 10))
        contrasts = {(r["candidate_mode"], r["reference_mode"]) for r in t.comparison_gates}
        self.assertEqual(len(contrasts), 10)
        self.assertIn(("balanced_adaptive", "balanced_cost"), contrasts)
        self.assertEqual({r["horizon"] for r in t.comparison_gates}, set(HORIZONS))
        p = next(r for r in t.paired_differences if (r["candidate_mode"], r["reference_mode"],
                     r["fee_rate"], r["horizon"], r["scenario_id"]) ==
                     ("balanced_context", "balanced_cost", .0025, 5, 1))
        for field, expected in zip(VALUES, (.25, 1., 20., 2., 20., 0.)):
            self.assertEqual(p[field + "_difference"], expected)
        self.assertEqual(p["human_review_share_pct_difference"], 20.)
        self.assertEqual(p["target_change_count_difference"], 1)
        self.assertEqual(p["growth_difference_units"], "percentage points per year")
        self.assertIsNone(next(r for r in t.paired_differences if r["candidate_mode"] == "balanced_context"
                              and r["reference_mode"] == "equal_weight_annual")["human_review_count_difference"])
        for r in t.profile_screen + t.profile_recommendations:
            self.assertEqual(r["status"], "provisional")
            self.assertIs(r["personalized_overlay_pending"], True)

    def test_opposite_paired_and_marginal_growth_conclusions(self):
        rows = grid()
        set_case(rows, "balanced_cost", net_real_cagr_pct=[0, 10, 20, 30])
        set_case(rows, "balanced_context", net_real_cagr_pct=[31, 1, 11, 21])
        r = gate(build(rows))
        self.assertEqual(r["median_paired_growth_gain_pp"], -9)
        self.assertAlmostEqual(r["marginal_p10_growth_difference_pp"], 1.)
        # Reversing the pair reverses both conclusions, not their definitions.
        set_case(rows, "balanced_cost", net_real_cagr_pct=[31, 1, 11, 21])
        set_case(rows, "balanced_context", net_real_cagr_pct=[0, 10, 20, 30])
        r = gate(build(rows))
        self.assertEqual(r["median_paired_growth_gain_pp"], 9)
        self.assertAlmostEqual(r["marginal_p10_growth_difference_pp"], -1.)

    def test_marginal_loss_not_quantile_of_pairs(self):
        rows = grid()
        set_case(rows, "balanced_cost", max_real_drawdown_pct=[0, 10, 20, 30])
        set_case(rows, "balanced_context", max_real_drawdown_pct=[30, 0, 10, 20])
        r = gate(build(rows))
        self.assertEqual(r["marginal_p90_loss_difference_pp"], 0.)
        # Independent scalar quantile of paired losses would be 18, which is wrong here.
        self.assertAlmostEqual((-10) * .3 + 30 * .7, 18.)

    def test_gain_and_tail_loss_exact_boundaries_and_neighbors(self):
        for value, expected in ((math.nextafter(.1, -math.inf), False), (.1, True),
                                (math.nextafter(.1, math.inf), True)):
            rows = grid()
            set_case(rows, "balanced_context", net_real_cagr_pct=value)
            self.assertEqual(gate(build(rows))["flags"]["gain_at_least_0_10"], expected)
        for value, expected in ((math.nextafter(1., -math.inf), True), (1., True),
                                (math.nextafter(1., math.inf), False)):
            rows = grid()
            set_case(rows, "balanced_cost", max_real_drawdown_pct=0.)
            set_case(rows, "balanced_context", max_real_drawdown_pct=value)
            self.assertEqual(gate(build(rows))["flags"]["tail_loss_at_most_1_00"], expected)

    def test_tail_growth_exact_boundary_and_neighbors(self):
        for value, expected in ((math.nextafter(-.1, -math.inf), False), (-.1, True),
                                (math.nextafter(-.1, math.inf), True)):
            rows = grid()
            set_case(rows, "balanced_context", net_real_cagr_pct=value)
            r = gate(build(rows))
            self.assertEqual(r["flags"]["tail_growth_at_least_minus_0_10"], expected)

    def test_four_fold_medians_and_strict_zero_exclusion(self):
        rows = grid(8)
        set_case(rows, "balanced_context", net_real_cagr_pct=[0, .2, .2, .2, 0, .4, -.1, .2])
        r = gate(build(rows))
        self.assertEqual([f["scenario_count"] for f in r["folds"]], [2] * 4)
        for actual, expected in zip(r["folds"], [0., .3, .05, .2]):
            self.assertAlmostEqual(actual["median_paired_growth_gain_pp"], expected)
        self.assertEqual(r["positive_fold_count"], 3)
        self.assertFalse(r["folds"][0]["positive"])
        set_case(rows, "balanced_context", net_real_cagr_pct=[0, 0, .2, .2, 0, 0, .2, .2])
        self.assertEqual(gate(build(rows))["positive_fold_count"], 2)
        self.assertFalse(gate(build(rows))["passed"])

    def test_adaptive_fails_only_context_control(self):
        rows = grid()
        set_case(rows, "balanced_context", net_real_cagr_pct=.2)
        set_case(rows, "balanced_adaptive", net_real_cagr_pct=.25)
        t = build(rows)
        self.assertTrue(gate(t, "balanced_adaptive", "balanced_cost")["passed"])
        self.assertFalse(gate(t, "balanced_adaptive", "balanced_context")["passed"])
        self.assertEqual(t.selection["selected_mode"], "balanced_context")
        self.assertEqual(t.selection["adaptive"]["required_comparators"], ["balanced_context", "balanced_cost"])
        self.assertEqual(len(t.selection["adaptive"]["comparisons"]), 2)

    def test_adaptive_fails_only_cost_control(self):
        rows = grid()
        set_case(rows, "balanced_context", net_real_cagr_pct=-.2)
        set_case(rows, "balanced_adaptive", net_real_cagr_pct=.05)
        t = build(rows)
        self.assertTrue(gate(t, "balanced_adaptive", "balanced_context")["passed"])
        self.assertFalse(gate(t, "balanced_adaptive", "balanced_cost")["passed"])
        self.assertEqual(t.selection["selected_mode"], "balanced_cost")

    def test_adaptive_passes_both_when_context_fails(self):
        rows = grid()
        set_case(rows, "balanced_context", net_real_cagr_pct=.05)
        set_case(rows, "balanced_adaptive", net_real_cagr_pct=.25)
        t = build(rows)
        self.assertFalse(t.selection["context"]["supported"])
        self.assertTrue(t.selection["adaptive"]["supported"])
        self.assertEqual(t.selection["selected_mode"], "balanced_adaptive")

    def test_only_h30_primary_and_sensitivity_cannot_reselect(self):
        rows = grid()
        set_case(rows, "balanced_context", net_real_cagr_pct=.3)
        set_case(rows, "balanced_adaptive", net_real_cagr_pct=.6)
        set_case(rows, "balanced_adaptive", fee=.005, net_real_cagr_pct=.2)
        t = build(rows)
        self.assertEqual(t.selection["selected_mode"], "balanced_adaptive")
        self.assertFalse(t.selection["doubled_fee_support"]["supported"])
        self.assertEqual(t.selection["doubled_fee_support"]["mode"], "balanced_adaptive")
        set_case(rows, "balanced_context", fee=.0025, h=30, net_real_cagr_pct=0.)
        set_case(rows, "balanced_adaptive", fee=.0025, h=30, net_real_cagr_pct=0.)
        t = build(rows)
        self.assertEqual(t.selection["selected_mode"], "balanced_cost")
        self.assertIsNone(t.selection["doubled_fee_support"]["supported"])
        self.assertEqual(t.selection["doubled_fee_support"]["reasons"], ["no_added_complexity_selected"])

    def test_all_five_own_horizons_and_fixed_modes(self):
        rows = grid()
        for mode, growth in zip(MODES[3:6], (1., 2., 3.)):
            set_case(rows, mode, net_real_cagr_pct=growth)
        set_case(rows, "balanced_context", net_real_cagr_pct=20.)
        set_case(rows, "balanced_adaptive", net_real_cagr_pct=40.)
        t = build(rows)
        for profile, horizon, cls in (("A", 5, "conservative"), ("B", 15, "balanced"),
                ("C", 30, "growth"), ("D", 25, "balanced"), ("E", 6, "conservative")):
            r = recommendation(t, profile)
            self.assertEqual((r["horizon"], r["selected_class"], r["selected_mode"]), (horizon, cls, cls + "_cost"))
            self.assertEqual(r["personalized_follow_up"]["review_drawdown_pct"], {"A":10,"B":25,"C":40,"D":15,"E":35}[profile])
        set_case(rows, "conservative_cost", h=5, net_real_cagr_pct=-1.)
        t = build(rows)
        self.assertEqual(recommendation(t, "A")["action"], "human_review")
        self.assertEqual(recommendation(t, "E")["selected_class"], "conservative")

    def test_liquidity_horizon_and_willingness_vetoes_all_retained(self):
        t = build(grid())
        a = screen(t, "A", "growth")
        self.assertFalse(a["flags"]["horizon_eligible"])
        self.assertFalse(a["flags"]["willingness_eligible"])
        self.assertFalse(a["flags"]["liquidity_pass"])
        d = screen(t, "D", "growth")
        self.assertTrue(d["flags"]["horizon_eligible"])
        self.assertFalse(d["flags"]["willingness_eligible"])
        self.assertFalse(d["qualified"])
        self.assertEqual(len(a["reasons"]), 3)

    def test_p90_equality_passes_despite_real_exceedance_and_exact_severe_id(self):
        rows = grid(12)
        set_case(rows, "conservative_cost", max_real_drawdown_pct=[10.] * 11 + [50.])
        r = screen(build(rows), "A")
        self.assertEqual((r["p90_loss_pct"], r["exceedance_count"], r["exceedance_denominator"]), (10., 1, 12))
        self.assertEqual(r["exceedance_fraction"], 1 / 12)
        self.assertTrue(r["flags"]["risk_pass"])
        self.assertEqual((r["severe_loss_pct"], r["severe_scenario_id"]), (50., 12))
        set_case(rows, "conservative_cost", max_real_drawdown_pct=10.)
        r = screen(build(rows), "A")
        self.assertEqual((r["exceedance_count"], r["severe_scenario_id"]), (0, 1))

    def test_p10_failure_and_all_referral_keep_all_negative_evidence(self):
        rows = grid()
        for mode in MODES[3:6]:
            set_case(rows, mode, net_real_cagr_pct=-.01, max_real_drawdown_pct=60.)
        t = build(rows)
        self.assertEqual(len(t.profile_screen), 30)
        self.assertEqual(len(t.profile_recommendations), 10)
        for r in t.profile_screen:
            self.assertIn("purchasing_power_pass", r["reasons"])
            self.assertIn("risk_pass", r["reasons"])
            self.assertFalse(r["qualified"])
            self.assertEqual(len(r["source_metric_keys"]), 4)
        for r in t.profile_recommendations:
            self.assertIsNone(r["selected_class"])
            self.assertEqual(r["action"], "human_review")
            self.assertEqual(r["pending_holdings_initial"], "retain original bills")
            self.assertEqual(r["pending_holdings_existing"], "keep current component dollars")
            self.assertEqual(len(r["failed_candidate_reasons"]), 3)

    def test_inclusive_point_ten_indifference_and_each_side(self):
        for balanced, expected in ((math.nextafter(.1, -math.inf), "conservative"),
                                   (.1, "conservative"), (math.nextafter(.1, math.inf), "balanced")):
            rows = grid()
            set_case(rows, "balanced_cost", net_real_cagr_pct=balanced)
            self.assertEqual(recommendation(build(rows), "B")["selected_class"], expected)
        rows = grid()
        set_case(rows, "balanced_cost", net_real_cagr_pct=.1)
        set_case(rows, "growth_cost", net_real_cagr_pct=.2)
        self.assertEqual(recommendation(build(rows), "C")["selected_class"], "balanced")

    def test_missing_extra_duplicate_and_mismatched_grids(self):
        original = grid()
        changes = [lambda r:r.pop(), lambda r:r.append(deepcopy(r[0])),
                   lambda r:r[0].pop("fold_id"), lambda r:r[0].update(extra=1),
                   lambda r:r[0].update(scenario_id=5, fold_id=0),
                   lambda r:r[0].update(mode="unknown"), lambda r:r[0].update(fold_id=1),
                   lambda r:r[0].update(fee_rate=.01), lambda r:r[0].update(horizon=7)]
        for change in changes:
            r = deepcopy(original)
            change(r)
            with self.subTest(change=change), self.assertRaises(ValueError):
                build(r)
        self.assertEqual(len(original), 320)

    def test_nonfinite_bool_null_numeric_and_unit_rejections(self):
        fields = (*VALUES, "annual_real_volatility_pct", "fee_rate")
        for field in fields:
            for value in (math.nan, math.inf, -math.inf, True, None, "0"):
                rows = grid()
                rows[0][field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    build(rows)
        for field, value in (("max_real_drawdown_pct", -1), ("max_real_drawdown_pct", 101),
              ("terminal_real_wealth", 0), ("net_real_cagr_pct", -100), ("nominal_fee_sum", -1),
              ("annual_real_volatility_pct", -1), ("scenario_id", True), ("horizon", 5.),
              ("fold_id", False), ("review_count", True), ("growth_units", "percent"),
              ("trade_count", 1), ("human_review_count", 0), ("drawdown_peak_year", True)):
            rows = grid()
            rows[0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                build(rows)
        for field, value in (("human_review_count", None), ("human_review_share_pct", math.nan),
               ("initial_allocation_deferred", 1), ("first_latch_year", 1),
               ("first_deployment_year", 31), ("target_change_count", True)):
            rows = grid()
            set_case(rows, "balanced_cost", **{field:value})
            with self.subTest(field=field), self.assertRaises(ValueError):
                build(rows)

    def test_strict_split_rejection_and_generated_development_shape(self):
        for split in ("final", "raw", "", None, True):
            with self.assertRaises(ValueError):
                build(grid(), split)
        with self.assertRaises(ValueError):
            build(grid(), "development")
        with self.assertRaises(ValueError):
            build(grid(4, "development"), "development")
        with self.assertRaises(ValueError):
            build(grid(3))
        # Still generated synthetic numbers; labels verify shape, never authenticity.
        t = build(grid(120, "development"), "development")
        self.assertEqual(len(t.paired_differences), 12000)
        self.assertEqual(len(t.comparison_gates), 100)
        self.assertEqual(t.selection["split"], "development")

    def test_config_is_pinned_and_records_have_no_aliases_or_io(self):
        rows, c = grid(), config()
        original, initial_config = deepcopy(rows), deepcopy(c)
        with patch("builtins.open", side_effect=AssertionError("pure API opened a file")):
            t = build_analysis_tables(iter(rows), config=c, split="synthetic")
        self.assertEqual(rows, original)
        self.assertEqual(c, initial_config)
        t.selection["context"]["comparisons"][0]["folds"][0]["positive"] = "changed"
        self.assertIs(gate(t)["folds"][0]["positive"], False)
        t.profile_screen[0]["reasons"].append("changed")
        self.assertNotIn("changed", t.profile_recommendations[0]["candidate_outcomes"][0]["reasons"])
        t.profile_screen[0]["source_metric_keys"][0]["scenario_id"] = 99
        self.assertEqual(t.profile_recommendations[0]["candidate_outcomes"][0]["source_metric_keys"][0]["scenario_id"], 1)
        self.assertEqual(build(rows).selection["context"]["comparisons"][0]["folds"][0]["positive"], False)
        c["selection"]["median_paired_growth_gain_min_pp"] = .01
        with self.assertRaises(ValueError):
            build_analysis_tables(rows, config=c, split="synthetic")
        c = config()
        c["extra"] = 1
        with self.assertRaises(ValueError):
            build_analysis_tables(rows, config=c, split="synthetic")


if __name__ == "__main__":
    unittest.main()
