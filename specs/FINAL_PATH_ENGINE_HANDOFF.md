# Final path implementation handoff: generated fixtures only

Status: chief preparation, not a published worker task or an accepted final
implementation. SOL-024's exact reviewed design, FINAL_EVALUATION.md,
FINAL_OUTPUT_NOTES.md and ACCOUNTING.md remain authoritative. This handoff
adds no policy, tuned parameter, production loader, freeze or final-data access.
SOL-042 still supplies the independent single-prior component; its exact code
must be accepted before publishing a task which depends on that API.

## Scope and arithmetic seam

Implement a narrow path engine before final tables, persistence or production
commands. The existing backtest.simulate_policy and metrics.compute_metrics
explicitly reject split=final. The current experiments.metric_row also calls
the guarded metric entry point. Do not run these public entries with a false
synthetic/development label and rewrite the result, metadata or CSV afterward.
Existing case/calibration/personalized/development writer public guards remain.

A later immutable Sol attempt may allow only a new policy_final_paths.py,
focused tests, and the smallest explicitly reviewed private arithmetic extraction
from backtest.py and metrics.py. Public signatures, guards, arithmetic ordering
and old synthetic/development behavior must remain unchanged. Reuse accepted
accounting functions, DecisionContext, LedgerEntry, BacktestResult and metrics;
avoid a second accounting loop or a separate fee implementation. A private
arithmetic helper can serve the existing guarded wrapper and the explicit new
final adapter. Check the entire existing accounting/baseline/policy/case test
closure after extraction. If a pure final metric-prefix adapter is necessary,
put it in the new module; do not broaden experiments.py without a new task.
The precise private signature is an implementation choice, reviewed by chief.
A Python private function is an API boundary, not a security sandbox.

The new generated-facing entry accepts explicit one-scenario rows, explicit
mode, explicit immutable EmpiricalPrior, fixed fee .0025 or .005, H in 1..30,
and an explicit review threshold. Default generic threshold is exactly 25%;
a future personalized call supplies its frozen own tolerance without selection.
Reject bool/NaN/inf or thresholds outside (0,100]. No files, path argument,
default input, CLI, refit, selection, comparison promotion or model subprocess.
Do not add a public production entry or assertion of authenticated refit here.

The generated wrapper truthfully records split=final in the actual path/metric
objects AND records input_origin=program_generated, source_verified=false,
production_execution_authorized=false, refit_verified=false separately. Its
name and docstring must make the generated-only origin explicit. This tests
a genuine final arithmetic lane without certifying any original bytes. Nothing
may infer production authority from scenario IDs, a caller's boolean or a
matching fixture. Production authentication remains a distinct later task.

Accept all 30 ordered six-field source rows for exactly one ID in 121..180,
even when H is shorter. Reject missing/extra/duplicate/reordered periods,
mixed IDs, wrong ordered fields, boolean/noncanonical keys and wrong split
labels. Generated one-path fixtures may be short only through a separate
explicit test-only seam; the real-shape adapter always requires 30 rows.
Outcome factors must be finite and strictly positive, matching the accepted
case/refit requirements. Preserve binary64 (1+r)/(1+inflation) order. Construct
each period's Decision before reading that period's outcomes for simulation;
metadata preflight cannot expose outcomes to the callback. Validate unused
suffix numerical fields separately without using them in any decision or fit.
An access-tracing Mapping fixture must prove the current-outcome ordering.
Do not weaken old accounting support for a literal -100% fixture globally.

A path starts at 100 in bills with CPI=1 and fresh callback/state. Bills, annual
thirds and initial-only thirds use the unchanged fixed callbacks. Each of the
five cost-aware modes uses a fresh CostAwarePolicy with exactly the supplied
same prior and threshold. Preserve inverse-cube kernel, prior mass15,
window5, fee buffer, target order, tie epsilon, initial deferral, and latch.
Never construct OOF calibrations, fold IDs, training complements or a recent
mixture from another path. The prior support is never mutated; final observed
rows cannot be appended to it. Contextual recent rows are only this path's
last min(5,t-1) completed observations. A new case/fee/horizon/scenario resets
all state. Reusing a mutable callback across paths must be impossible through
the wrapper. Failure is explicit; no catch-and-continue partial success.

## Outputs and invariants

Return an immutable path container holding the true-final BacktestResult,
immutable complete PolicyReview tuple (empty for fixed callbacks), separate
generated-origin metadata and the supplied prior identity digest/count.
A detached metadata view cannot mutate later views or the prior. For H=1,
sample volatility and ex-initial trade share remain null. For every H retain
initial/post-fee/end real wealth, exact CPI, fees before returns, transfer
threshold1e-10 for trade counts only, no fee on keep, and own-horizon metrics.
The initial buy and any post-fee drawdown cannot disappear. Target changes and
review-latch actions retain distinct diagnostics although engine action=keep
or rebalance. No final fold/promotion fields are fabricated; when represented,
use null with not_applicable status. This narrow path component does not yet
produce the 100 comparison or ten profile summary rows.

A later final-table component must consume these actual final-labelled paths
and independent final metric-prefix adapter, keeping FINAL_OUTPUT_NOTES.md
null/denominator semantics. Its existing development selection routine cannot
be reused on final statistics. A path component approval does not approve that
component, persistence, refit artifact, freeze attestation or final execution.

## Independent reference and required generated checks

`audit/chief/final_path_reference.py` uses only stdlib Fraction and Decimal;
it imports no safeinvest module, opens no competition CSV and fits no prior.
The saved24-row/4-scenario toy contains inflation drag with zero nominal return,
unequal asset returns, drawdown/recovery, and a flat path with initial fee loss.
Its 32 fixed-action paths have192 ledger rows and96 metrics at H=1,3,6,
three fixed baselines plus a clearly labelled diagnostic prefix callback,
and both fixed fees. The diagnostic callback is not an investment candidate.
The 60-by-30 shape is generated in memory; expected.json binds its CSV digest
and all keys121..180/1..30 without reading a holdout observation.

Reproduce with the selected Python3.12:

```
python -B audit/chief/final_path_reference.py --check
```

The rational oracle specifies accounting expectations; it does not replace the
accepted binary64 severe rule. Two separate float witnesses show exact-tie
smallest-ID selection and a one-ULP-greater loss winning despite the decision
epsilon. Retain strict chronological initial/post_fee/end location updates,
earliest maximizing locations and initial sentinel for zero loss. Independent
Sol must recompute selected rational facts without importing this builder;
chief independently checks exact new code and representative numerical facts.
Comparisons need stated binary64 tolerances; never round before selection.

A later bounded attempt (<=1500s, CPU only) must include:

- all three baselines at both fees against every saved toy ledger/metric through
  an explicitly generated test seam; >=6 independently recomputed facts;
- generated full60-by-30 shape, all eight fixed modes, small immutable reviewed
  prior, both fees, and each profile's own horizon/tolerance without screening;
- a representative generated3600-row refit prior from accepted SOL-042, with
  exact support identity and selected n=0,1,5 contextual scores; no competition
  refit and no outcome-driven parameter changes;
- current/future outcome perturbations including the perturbed-period decision,
  another scenario's full perturbation, reversed evaluation order, second fee
  and repeated horizon runs, proving fresh state and prior isolation;
- final-year/post-fee review latch timing, human-review holdings carried with
  zero trades, first deployment/deferral, target-change diagnostics and H=1 nulls;
- malformed keys/factors/prior/fees/thresholds, source/task/reference/result
  corruption, clean Python3.12 actual exits, bounded runtime and byte inventories;
- unchanged existing public final rejections and exact synthetic/development
  regression behavior after any private extraction.

Task publication waits for exact prerequisite source acceptance. Push the
handoff/reference commit first; only then create any immutable task with a real
already-pushed40-character base and pinned source closure. Keep the source C,
configuration E and computation publication P sequence for future actual runs.
No task identity or parameters may be invented in advance of those sources.

## Evidence and remaining gates

This preparation is consistent with the already pinned backtest-validation
(artheras/skills825040f3cc7eb4179a8ee86e0158d9828f427f7b) and
quality-assurance-auditor (yushui2022/MathModel-Skill
b13a23e2ccae39a1f13ceb5dbd41fa74ed61eac0) evidence principles. No new skill,
code template or service was installed. Their generic historical/daily metrics
and paper_output workflow are inapplicable: the original annual-scenario
SafeInvest protocol, immutable tasks and project-specific paths govern.
The development choices/rescreens, actual all-development refit, final path
code, final tables/persistence, external freeze review, gate and one authorized
final evaluation all remain separate. Preserve failures and disclose any real
final access/bug correction. Humans alone submit; private identities stay local.
