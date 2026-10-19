# Policy driver implementation handoff — provisional, no execution authorization

This is chief preparation after the accepted negative SOL-009 design review.
The corrected v2 design and kernel require independent review. It is not a task, acceptance, change to the pilot design, or final
freeze. Reconcile it with the actual independent findings before publishing an
implementation task. The current design/config are DEVELOPMENT_POLICY_PILOT_V2.md and
development_policy_pilot_v2.json; v1 and previous tasks are historical evidence.

## Boundaries and proposed implementation split

1. **Calibration and provenance.** A new pure module builds four fold priors from
   the explicitly supplied development input. Keep the existing baseline loader,
   accounting, metrics, baseline CLI and accepted artifacts unchanged. Training
   fold for evaluation fold f uses only IDs whose (s-1) mod 4 differs from f:
   90 scenarios x 30 years = 2700 equally weighted annual real gross vectors.
   Store sorted training/evaluation IDs, all training row keys, exact source-file
   hash, a canonical digest of selected training rows and a digest of the derived
   gross vectors. Specify and test that canonical serialization (for example,
   IEEE float.hex strings with canonical JSON) rather than hashing ambiguous
   display-rounded values. Record input bytes and consumed source bytes separately.
   Numerical validation of all rows is not a license to fit on held-out rows.
   A synthetic perturbation to one evaluation fold must leave that fold's prior,
   training IDs and training digest unchanged. Its global input digest should
   change, as should calibrations for which those rows are legitimately training.
2. **Scenario execution and evidence bundle.** After kernel acceptance, create a
   fresh callback for each scenario and fee/mode. Run each 30-year path once and
   derive H=5,6,15,25,30 metrics from its prefixes through the accepted metric API.
   Prove prefix equality with direct shorter synthetic runs. Never carry state
   or the contextual window between scenarios. Export ordinary annual ledgers
   separately from decisions and target scores. Baselines retain their original
   rules and have no human-review overlay. Write complete outputs atomically to
   a new directory, preserve partial failures/diagnosis, and refuse overwrites.
3. **Comparisons, suitability and selection.** Consume verified keyed scenario
   metrics. Apply the exact predeclared gates and units; do not tune thresholds.
   Export all candidate facts and reasons, including failures. A selected profile
   still requires the separately specified personalized suspension follow-up.
   Final support, frozen all-development refit and final-data access are separate
   future work, never an extra flag quietly added to the development driver.

Each implementation/review attempt should be at most 30 minutes and scoped to
explicit files. The independent design reviewer may suggest a smaller split.
Chief must first commit/push any prerequisites and only then publish immutable
Sol tasks. HY3 commands are issued only after the relevant code is reviewed.
No command in this document authorizes running the prototype on competition data.

## Reuse the submitted baseline experiment after acceptance

HY3-003 already exists at 7652410d73425371110784ef5fa97c03470a074e and must not
be rerun to fill a new directory. SOL-008 and chief promotion have passed; reuse that accepted evidence.
At k=.0025, import its three reference policies by exact commit/file/hash/key;
verify scenario IDs, horizons, units, fee and severe-case convention. A manifest
can reference this accepted bundle without duplicating or overwriting it.
This baseline is unfitted, so its original scenario paths remain valid comparators
for out-of-fold policies. Its all-development summary was already seen before
policy design and must not be called an untouched validation result.

At k=.005, the same three baseline rules need their new fixed-fee calculation.
The five proposed policies need both fee rates. Thus there are 16 analytic cases
(8 modes x 2 fees), consisting of 13 new mode/fee computations and 3 exact primary
reference imports. Do not label an import as a new experiment or new acceptance.

## Output layout and exact keys

`specs/policy_driver_layout_v2.json` records structural counts derived from the
proposal, not produced experimental evidence. One new directory per fee/mode
keeps each artifact under the runner's 10 MB cap. Include these common keys:
`split`, `mode`, `fee_rate`, `scenario_id`, and `fold_id`; add `period` to annual
rows and `horizon` to metrics. Summary keys omit scenario_id but include horizon.
All floating values are full precision; only report display rounds numbers.

- Annual ledgers use the accepted engine's component holdings, one-way transfer,
  fee, post-fee state, returns, CPI and real wealth fields. Each case has 3600
  annual rows. Store the original scenario and year; never concatenate paths.
- Five new modes also have 3600 decision rows per case: action, active before/
  after, proposal/selection, CE_keep, reason, first_deployment_year, prior mass, recent count, observed prior
  maximum loss, latch, initial-deferred flag, transfer, actual fee, is_trade and
  executed_target_change. Keep empty score fields genuinely missing during human
  review; do not encode them as zero estimated benefit.
- Target scores are a separate long table keyed additionally by target name.
  Include target weights, CE_target, tau, fee fraction, pre-cost benefit, modeled
  fee impact, conservative score and true net CE. Rows exist for evaluated
  targets only. There are at most 3600 for each nonadaptive case, and at most
  9600 for the adaptive case (120 x [5 + 25 x 3]); suspension reduces these counts.
  There are no duplicated column names or JSON strings hidden inside CSV cells.
- Each case has 600 scenario/horizon rows and five summaries. Include the required
  growth, ordinary fluctuation, large loss, terminal real wealth, both trade
  shares, fee sum and review/target-change facts. Growth uses percent/year levels;
  paired growth differences use percentage points/year. Baseline human review is
  inapplicable, not an observed risk-control success.
- Paired differences require identical scenario/horizon keys. All seven other
  modes compare to annual thirds at both fees; contextual also compares to fixed
  Balanced, and adaptive also to contextual and fixed Balanced. Keep all those
  contrasts rather than select the favorable one. Compute each fold's median
  paired growth gain from its 30 scenarios, not pooled annual observations.
- Severe cases follow the existing exact metric/tie rule at each horizon. Select
  from that case's metrics, retain the complete underlying 30-year ledger and
  identify the chosen H prefix and real peak/trough locations including fees.
  A reference on the selected policy's path is not the reference's own severe case.
- Profile screen has 5 profiles x 3 target classes x 2 fees = 30 candidate rows.
  Preserve own horizon, tolerance, target bill reserve, each individual pass/fail,
  p90 loss, tolerance exceedance fraction, median/severe loss, p10 growth, median
  growth, choice and reasons. Exceedance means loss strictly greater than tolerance;
  the p90 screen passes on equality. Report proposed assignment/referral for each
  profile and fee, then mark personalized suspension evidence pending.
- Selection output records both marginal tail checks and paired median/fold
  checks with exact threshold values and signed differences. The adaptive gate
  must pass versus BOTH balanced_context AND balanced_cost even if context
  fails promotion; use paired median/fold gains and differences of marginal tails
  exactly as defined in v2. Fee sensitivity
  never retunes the primary candidate or changes the predeclared comparison set.

A top-level manifest binds input/config/source hashes, base and reviewed kernel
commits, calibration IDs/digests, commands, Python/dependency versions, exact
artifact bytes, file row counts, keys/units and timing. --check is read-only,
recomputes independent checks and rejects deliberate corruption while preserving
all artifacts. No complete file is silently regenerated to make hashes agree.

## Runtime and artifact-size evidence

`audit/chief/policy-kernel/synthetic-timing-01.json` records an actual local
Python 3.12 generated fixture: 2700 prior rows, one 30-year synthetic scenario,
five modes and two fees. It also records the exact source and fixture hashes.
The measured decision-core time was about 1.27 seconds; linear extrapolation to
120 scenarios is about 152 seconds. This is an estimate for this machine, excludes
calibration/IO/checking and is not an HY3 runtime guarantee. The largest projected
compact diagnostic JSONL case was 4,647,720 bytes; real data may serialize to
other lengths, so the driver must enforce the actual 10 MB cap and use the
separate long tables above. Do not copy these synthetic timing cases into any
competition performance table.

At most 30 minutes per immutable command attempt remains mandatory. Split fixed
fee/mode groups if the first measured real development job demonstrates a runtime
or size problem. Preserve that diagnosis; do not hide failed attempts or extend a
published task in place. Tests and checker runtime are part of the task budget.
