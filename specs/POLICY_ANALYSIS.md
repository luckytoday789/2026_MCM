# Policy comparison and suitability component contract v2

A later assigned task implements src/safeinvest/policy_analysis.py and focused
synthetic tests. This pure module receives already validated scenario metrics;
it does not load inputs, simulate strategies, fit parameters, write bundles or
certify provenance. V2 design approval is required before production integration.
Use DEVELOPMENT_POLICY_PILOT_V2.md and development_policy_pilot_v2.json exactly.

## Input and API

    build_analysis_tables(metrics, *, config, split) -> AnalysisTables

Input is the flat canonical scenario-metric schema in POLICY_CASE_ENGINE.md:
mode, fee_rate, scenario_id, fold_id, horizon, split and accepted metric values.
Require all eight modes, both fees and five horizons for exactly the same scenario
set, with unique keys and fold=(scenario_id-1)%4. Development has IDs 1..120;
synthetic fixtures use an explicitly labelled positive multiple of four. Reject
missing/extra/duplicate/mismatched keys, booleans masquerading as numbers, invalid
splits, nonfinite required metrics and nonsensical losses. Null policy diagnostics
are allowed only where inapplicable for the three references. Do not silently
fill missing records or compare unmatched scenarios. No final support.

Outputs: paired_differences, comparison_gates, selection, profile_screen,
profile_recommendations. Dictionary/list records only, no filesystem writes.
Accepted source verification remains the responsibility of the future wrapper.
Pure callers cannot certify data origin merely by passing split='development'.

## Comparisons and promotion

Keep all ten contrasts per fee from policy_driver_layout_v2.json, all five H,
and all scenarios. Paired columns are candidate minus reference for accepted
METRIC_VALUES: net_real_cagr_pct, max_real_drawdown_pct, terminal_real_wealth,
nominal_fee_sum, trade_share_pct, trade_share_ex_initial_pct. Copy paired units;
include candidate_mode, reference_mode, fee, fold, H, scenario and split.
There are 12000 paired rows on production shape. Do not replace a marginal
quantile difference with a quantile of these paired rows.

For each contrast/fee/H, report scenario count, median paired CAGR gain,
marginal p10 CAGR difference, marginal p90 loss difference, all four within-fold
paired median gains and positive-fold count. Also retain trade/review differences
when applicable. There are 100 gate-summary rows. The four thresholds are exactly
v2: gain>=.10, tail growth>=-.10, tail loss<=1.00, positive folds>=3. A fold is
positive only if its paired median exceeds zero. No display rounding or extra
economic tolerance may decide these conditions; use the stored finite values and
inclusive comparisons at numeric boundaries. A numerical-check tolerance does
not silently enlarge a policy threshold. Tests must cover exact boundary values
and values on both sides, including a zero fold gain.

Only H=30 primary k=.0025 determines selection. Context requires its direct
balanced_cost comparison to pass all gates. Adaptive requires BOTH direct
comparisons against balanced_context AND balanced_cost. It can qualify when
context itself fails; the comparators never change with eligibility. Choose
qualifying adaptive, else qualifying context, else balanced_cost. Report all
four signed statistics, individual flags, reasons and the full comparator list.
Default selection is a research comparison choice, not customer suitability.

At k=.005 report the same gate facts and whether the already primary-selected
mode remains supported against its required controls. Do not replace the primary
mode using sensitivity. If primary is fixed balanced_cost, report no added
complexity was selected; its customer screens and absolute results can still
fail. Reference comparisons are descriptive, never a substitute for the controls.
No statistical significance claim, optimizer or extra candidate search.

## Customer screen and individualized follow-up

At each profile's own H, evaluate conservative_cost, balanced_cost, growth_cost
at both fees. This provisional class screen intentionally uses fixed classes;
it does not substitute the chosen adaptive research variant silently. Use v2's
exact eligibility sets, target bill reserves, p90 loss<=tolerance, p10 CAGR>=0.
For each of 30 rows retain all pass/fail reasons even if an early screen failed,
H/tolerance/liquidity, reserve, median/p10 growth, median/p90/severe loss, severe
scenario ID, count(loss>tolerance), denominator and exceedance fraction. Equality
passes the risk screen; equality is not counted as an exceedance.

Among qualifying classes find maximum median CAGR; retain all whose gap is <=.10
pp/year and choose the least growth-oriented (conservative, balanced, growth).
No qualifying class yields human_review, selected_class=null and exact reasons.
Produce ten profile/fee recommendation records, all marked provisional and
personalized_overlay_pending=true. Initially referred clients remain in bills;
existing clients keep current component dollars while review is pending.

Before freeze, each provisional assignment needs a separate run of its assigned
fixed-class policy at its OWN tolerance and H, followed by risk AND purchasing-
power rescreen. Failure causes referral, no fallback reselection. The later job
must state this exact mapping and preserve generic results. The common-H Balanced
research conclusion and individual class recommendations answer distinct tasks;
if a future final design proposes deploying an adaptive variant to a profile,
that is a new explicit suitability protocol requiring independent review and
own-horizon evidence, never an automatic substitution by this module.

## Synthetic acceptance and limits

Use deliberately constructed scenario records, not competition outcomes. Verify
paired versus marginal sign reversals; complementary folds; thresholds and ties;
adaptive fails one control; context fails but adaptive passes both; sensitivity
cannot alter primary choice; all five profile horizons; willingness/liquidity
vetoes; p90-pass with actual tolerance exceedances; p10 failure; least-growth
indifference; all-referral; missing/extra keys and nonfinite rejection. Expected
statistics must use independent arithmetic, not calls to the tested function.
These fixtures establish analysis behavior, not real investment performance.

A separately reviewed writer will bind all outputs to exact source/input/metric
hashes, detect corruption read-only and retain failed trials. This component's
artifact shape must match policy_driver_layout_v2.json. Task budget <=25 minutes,
CPU-only, no packages, actual strategy runs, original CSV reads or final support.
