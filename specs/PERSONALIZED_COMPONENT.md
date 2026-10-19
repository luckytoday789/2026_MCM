# Personalized pure adapter: provisional implementation boundary

Status: chief-authored component, pending targeted independent Sol code review.
This follows the design accepted in SOL-020 and PERSONALIZED_OUTPUT_NOTES.md.
It does not change v2 policy parameters, the generic case API, the accepted
analysis, or any published attempt. No competition outcomes were read to build it.

## Scope and interface

`src/safeinvest/policy_personalized.py` exposes:

    build_personalized_case_tables(rows, *, calibrations, profile_id,
        proposed_class, fee_rate, split, upstream_reasons=()) -> PersonalizedCase

`PersonalizedCase.case` is an ordinary `CaseTables` or null for an upstream
referral. `rescreen` is the pure computational result for one profile/fee pair.
All records retain split, own H/tolerance/liquidity, fee and source_verified=false.
No source hashes, completed saved bundle, ten-row root or authenticated upstream
assignment are claimed. The future production bridge must validate the exact
accepted generic assignment/candidate screen, hashes and four fold priors BEFORE
calling this function. Invalid provenance must fail there, never become a referral.
The present function cannot authenticate the origin of a caller's explicit rows.

Only A/B/C/D/E, conservative/balanced/growth, and fees .0025/.005 are accepted.
The fixed H/liquidity eligibility is checked again. Only the review threshold
changes relative to the generic case. Each scenario has a fresh policy, unchanged
full training prior, and evaluation only through its own H. Synthetic fixtures
use multiples of four scenarios with enough years; development shape is exactly
120 by 30. No final split, file reads/writes, CLI or fitting is provided. This
pure seam's development shape support is not production execution authorization.

The adapter imports the accepted private `_rows`, `_priors`, `_normalize` and
`_diagnostics` helpers from policy_cases to preserve their exact validation and
column semantics. The future execution source closure must pin policy_cases and
all its transitive imports. There is no refactor of that reviewed component.

A null proposed_class requires rows=calibrations=null and nonempty original
upstream reasons. It returns no case and no simulation. Personalized statistics,
flags and exceedances are null; count/denominator are zero. Pending holdings are
original bills for an initial investor and current component dollars otherwise.
Those instructions are not a successful investment outcome.

Executed cases retain all H-period ledgers, policy decisions, evaluated target
scores, one metric per scenario and one summary. Keys add profile_id and
review_threshold_pct. Policy action remains distinct from engine_action. The
rescreen computes inclusive p90 loss <= tolerance AND p10 growth >= 0 without
rounding, separately reporting strict loss>tolerance counts. Every failed screen
is listed, proposed_class retained, recommended_class null, with no fallback.
An eligible status on a synthetic row is only a synthetic mathematical result;
it is never a production or final recommendation.

## Validation and remaining gates

Chief generated tests cover all profile H/tolerances and both fees, rational
real-wealth paths, exact B generic H15 prefixes, fee deduction before returns,
full state reset, threshold equality, an early post-fee breach followed by market
recovery, final-year breach without fictional H+1, unchanged decisions at t when
only t outcomes change, suffix independence at fixed priors, inclusive boundaries,
strict exceedances, no-run nulls, and invalid input rejection. Scalar outcome
fixtures test risk-only/power-only/both failures. No claim is made that synthetic
priors were fitted to their illustrative evaluation paths.

Validation tier: diagnostic-only until independent source review and later
accepted development execution. No model/parameter selection is performed here.
The failed test draft and real failure log remain in
`audit/chief/personalized-component/`; a typo added an extra column and correctly
tripped the ordered-schema validator. Subsequent results do not erase it.

Sol must independently challenge arithmetic, chronology, eligibility, all fixed
classes, fold membership, counts, nulls, input immutability and the unresolved
production boundary. Reuse of chief tests is a regression check, not independent
numeric evidence. Compare independent scalar/rational references to actual code;
retain a negative verdict if warranted. A positive component review does not
accept generic results, establish an upstream assignment or unlock final data.

Future work still requires the accepted 16 generic fee/mode cases, authenticated
analysis assembly and its review, the personalized production bridge/writer,
exact task configurations, HY3 commands and independent review of actual results.
The unchanged generic Balanced same-primary-mode cost-robustness result remains
separate from fee-specific personalized suitability assignments. No ten-row
production summary or report claim may bypass these boundaries.
