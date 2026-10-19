# Personalized development follow-up and rescreen contract

This handoff makes the already approved v2 suitability requirement executable.
It is not an implementation task, outcome finding, freeze or run authorization.
Preserve the generic 25% pilot and all original results. A later immutable task
must bind accepted policy, calibration, case/analysis and writer sources and the
exact independently accepted generic analysis result. No final data are used.
The machine-readable design companion is personalized_review_v1.json.

## Fixed mapping and decision sequence

Read the ten accepted generic profile recommendations keyed by profile_id and
fee_rate. Each must remain provisional/personalized_overlay_pending and match
its exact candidate screen. Primary recommendations use k=.0025. The k=.005
recommendations are separate counterfactual cost-sensitivity records and must
never replace the primary choice automatically. If their selected classes differ,
report the difference; comparing different classes does not measure robustness
of the same fixed strategy. Preserve this limitation in the sensitivity text.

For an initially referred profile/fee, retain selected_class=null and the original
reasons, set status=upstream_referral, and run no candidate or substitute. The
initial holding instruction is bills; for an existing investor it is current
component dollars. Do not create a simulated bills result under the selected
policy label or claim that this holding instruction passed a purchasing-power
screen. Reference bills results, if discussed, keep their original provenance.

For each non-null assignment, map only conservative/balanced/growth to the
corresponding fixed _cost mode. Use its existing own horizon, own loss tolerance
as review_drawdown_pct, same fee, same fold priors and all other v2 parameters.
Do not substitute the selected adaptive research comparator for a fixed class.
Do not choose another class if personalization fails. A mismatch between the
accepted assignment and its candidate screen is invalid input, not a referral.

Run all 120 development scenarios with fresh state for this profile/fee and
exactly its H annual reviews; no outcome past H enters metrics or diagnostics.
The prior continues to use the other 90 scenarios' full training rows, as fixed
by v2; it is not refitted to the evaluated profile or scenario. This is an OOF
development check, not untouched validation or a personalized loss guarantee.
Only the review threshold changes from the generic run. It can alter actions,
fees and terminal growth; a lower threshold is not assumed to improve risk.

## Timing, metrics and rescreen

The threshold applies to the running maximum REAL drawdown observed through
period t-1, including initial wealth and earlier post-fee and year-end values.
At equality the next annual review latches human_review. Pending reviews keep
component dollars with zero transfer and fee; existing assets continue to earn
returns. Crossing first observed at the final year end need not produce a latch
within H. Report the actual observed loss and null first_latch_year honestly.
Never clip outcomes at the threshold or count a fictional review at H+1.

Recompute all accepted metrics at H, including both trade shares, ordinary
ddof=1 fluctuation, maximum real loss, fees and policy diagnostics. From these
120 scenario metrics independently obtain median and p10 real CAGR, median and
p90 maximum loss, severe loss and its exact scenario/peak/trough, and strict
count(loss>tolerance)/120. Recheck p90_loss<=tolerance AND p10_growth>=0,
with inclusive comparisons and no rounding in the decision. Record fixed
horizon and target-reserve eligibility again. Both outcome screens must pass.
A passing p90 can coexist with actual exceedances; always display the count.

If all screens pass, status=eligible_after_personalized_development_rescreen.
This is evidence eligible for the later freeze decision, not a guarantee, final
validation, permission to trade or instruction to submit. If either fails,
status=human_review_after_rescreen, retain proposed_class for traceability and
set recommended_class=null. List every failure, with no re-ranking, fallback,
new target search or tolerance relaxation. Policy outcomes and negative findings
remain saved. Primary and doubled-fee decisions are always separate records.

## Evidence and output contract

One root summary has exactly ten profile/fee rows, including upstream referrals.
Each row records upstream generic result/assignment hash, profile, H, tolerance,
liquidity, fee, proposed_class/mode or null, threshold, status, recommended_class,
all screen flags/reasons, denominator, units and source case path or null. For
upstream referrals numerical personalized metrics and source path are null,
scenario_count=0 and simulation_status=not_run_upstream_referral. For executed
cases scenario_count=120; every metric and required source path is present.
Never turn a failed/incomplete computation into a referral or a zero-valued row.

Each executed profile/fee directory contains H*120 annual ledger and decision
rows, 120 scenario-metric rows, one summary, and all evaluated target scores
(up to H*120 for these fixed modes, fewer after suspension). Reuse canonical
column meanings and add profile_id and review_threshold_pct; common key is
(profile_id,fee_rate,scenario_id,period) or (...,horizon) for metrics. Preserve
both policy action and engine action. Source inputs, four calibrations and
original generic recommendation files are hash-bound, not copied and relabelled.
Record exact imported code bytes, immutable command, Python/dependency versions,
actual elapsed time, file hashes, units, keys and counts. One file <=10 MiB.

The generic case builder has a deliberately fixed 25% threshold. Do not extend
its published in-flight task or silently change its API. A later narrow adapter
may use the accepted CostAwarePolicy explicit threshold and generic simulator;
any code/refactor needs its own assigned paths, tests and independent review.
No unrecorded threshold option or sweep is allowed in the production CLI.

Output creation refuses overwrite and preserves failed staging, original logs
and exact diagnoses. Read-only verification must reject corrupted inputs,
assignment mapping, thresholds, keys, metrics, counts, hashes or completion state.
It must not repair evidence. Tasks stay CPU-only and <=30 minutes; a chief-issued
execution configuration can split profile/fee cases before dispatch based on
measured runtime, never silently extend or restart a failed attempt.

## Targeted independent checks before acceptance

Use generated fixtures for early fee-induced crossing followed by recovery,
pure-inflation crossing, exact equality, final-year crossing without a later
review, full versus direct prefix metrics, and state isolation across profiles.
Verify H and tolerance for all five profiles. Profile B uses the same 25% as
the generic run; matching mode/fee/prior must reproduce its H=15 prefix. A shorter
H must never inherit a later first deployment or latch. Validate strict tolerance
exceedance counts separately from inclusive p90 eligibility. Independently test
risk-only failure, purchasing-power-only failure, both failure, exact boundary
pass, upstream referral without simulation, and no fallback after failure.

Use independently computed rational/scalar expected values. Chief checks of
Sol implementation and Sol review of actual HY3 results remain separate gates.
Positive synthetic evidence authorizes no production run by itself. The report
must distinguish original generic screening, personalized follow-up, cost
sensitivity and eventual final evaluation without mixing their denominators.
