# Policy case engine contract v2

This is an implementation contract, not a task or execution authorization. The
corrected v2 policy design and kernel require SOL-013 approval; the calibration
requires SOL-014 approval. Source changes invalidate tasks pinning older bytes.
No final support or competition outcome access is authorized by this document.

## One bounded component

Implement src/safeinvest/policy_cases.py and tests/test_policy_cases.py only in a
later assigned task. This component receives explicit rows and already constructed
fold calibrations. It opens no files, changes no accepted engine, and writes no
result bundle. Production path/hash binding, reference imports and CLI are a later
component. It must not call a synthetic wrapper and relabel its output development.

Public API:

    build_case_tables(rows, *, calibrations, mode, fee_rate, split,
                      horizons=(5,6,15,25,30)) -> CaseTables

CaseTables holds annual_ledgers, scenario_metrics, summary, decisions and
target_scores as ordinary records, plus counts/units metadata. It is computational
evidence, not a source-verified saved run. Accept only split synthetic/development,
never final. Caller provenance cannot be authenticated by a pure function; do not
claim this API itself enforces the final-data gate. Development IDs must be exactly
1..120 and years 1..30. Explicit synthetic fixtures may use a positive multiple of
four scenario IDs starting at 1 and shorter paths sufficient for requested H.
All keys are complete/unique/ordered; invalid/nonpositive/nonfinite factors fail.
Reject unknown modes, duplicate horizons, invalid fees and wrong prior fold IDs.
Production fees are exactly .0025 and .005; zero fees are a synthetic test seam.

Each scenario gets the matching fold's prior and a FRESH CostAwarePolicy callback
for each fee/mode. Verify the calibration's evaluation IDs contain the scenario,
training/evaluation sets are disjoint complete complements, and keys/row counts
match the supplied shape. This check does not replace calibration provenance.
Never re-fit from an evaluation path or capture future rows in the callback.
Run simulate_policy once at the largest requested horizon, with its true split,
and derive shorter metrics through the accepted prefix API. Independently test
against direct shorter runs. Validate every supplied gross factor, including the
last year, without giving future values to decisions. Keep all failed attempts.

The five cost-aware modes use the declared 25% generic threshold. Personalized
threshold jobs remain separate; no optional unrecorded threshold sweep. Baselines
use POLICIES callbacks without human-review overlay. At development k=.0025 the
three baseline modes MUST be imported later from accepted HY3-003; this case
builder refuses those new runs. Synthetic reference calculations and development
k=.005 reference cases are allowed only within their later authorized task.

## Canonical table schema

Use current accepted ledger_row, metric_row, summary_row and drawdown_locations
as pure helpers where useful; do not mutate their existing source or fixed CLI.
Normalize policy -> mode, year -> period, retain each field's original numerical
meaning. Add fee_rate and fold_id to scenario records. Summary rows aggregate all
folds and have no fold_id; preserve scenario_count and both pooled trade shares.
Ledger action is renamed engine_action, distinguishing it from policy actions in
the sidecar. All tables carry split; round-trip floats, no display rounding.
Units for CAGR levels are percent/year; CAGR differences are percentage points/year.

Annual ledgers preserve every accepted target/holding/return/CPI/fee/real-wealth
field and original period. No JSON payloads inside CSV cells and no duplicate
columns. Target columns may be null for keep. Production case has 3600 rows.

Metrics retain accepted growth, ddof=1 fluctuation, drawdown, wealth, fees, trade
counts/shares and exact severe-location fields, for 600 rows per production case.
Add human_review_count/share_pct, first_latch_year, target_change_count,
first_deployment_year, initial_allocation_deferred. Derive these from only reviews
through H: no future deployment or latch may leak into a shorter horizon. For
references these policy diagnostics are null/inapplicable, not zero successes.
Counts for target_change follow executed requests; tiny executed target changes
can coexist with is_trade=false under v2. Trade frequency remains T>1e-10.

Summary has five rows and accepted quantile/severe fields per case. Include
pooled human-review share and target-change counts for cost-aware modes; null for
references. Severe selection is max loss, then smallest exact scenario ID, with
the accepted earliest peak/trough convention. No epsilon tie for severe cases.

Decisions for cost-aware modes have common keys plus action, reason,
active_before/after, proposed_target, selected_target, ce_keep, prior_mass,
recent_count, observed_max_drawdown_pct, human_review_latched,
initial_allocation_deferred, first_deployment_year, intended_transfer,
actual_fee, is_trade, executed_target_change. There are 3600 rows per production
case; baseline decision/target-score tables are empty and explicitly inapplicable.
Human-review score fields are null and target-score rows absent, not fabricated
zero estimated benefits. Retain other meaningful state diagnostics.

Target-score rows add target_name and three weight columns, ce_target, tau,
fee_fraction, pre_cost_benefit, modeled_fee_impact, conservative_score, true_net_ce.
Link each to exactly one decision; retain all evaluated targets including rejected
ones. At most 3600 rows in nonadaptive modes or 9600 adaptive rows; suspension can
reduce the count. Every logged selected target must satisfy the strict gate.

## Necessary synthetic acceptance

Use own rational/scalar checks beyond self-consistency. Verify fee and growth
fixtures, metric prefix equality, all five modes and references, unchanged baseline
callbacks, explicit rejection of primary development baseline reruns, t-1/fold
boundary, fresh state across scenarios/fees, malformed calibration membership,
review lag/latch and prefix-only deployment/latch fields. Check every row key,
count, score/decision link, units and null semantics. Test saved-output concerns
only in the future writer task; this component has no file-writing permission.

The task must stay within 25 minutes, CPU-only. No actual competition data reads,
production CLI, package installation, policy tuning or final functionality. Its
chief acceptance must independently inspect precise code and numeric evidence.
