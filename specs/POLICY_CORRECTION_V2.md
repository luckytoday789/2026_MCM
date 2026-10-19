# Policy v2 correction and independent review handoff

SOL-009 at 3f79e07b87ec92a4a74049da6166093ba4e88e6f is accepted as a negative
independent design review. It does not approve the design or any implementation.
Original v1 specifications and SOL-011/SOL-012 task bytes remain unchanged.
Current contracts are DEVELOPMENT_POLICY_PILOT_V2.md and development_policy_pilot_v2.json.

D1 is resolved by eligible-first selection and ties anchored to the eligible
maximum. The existing kernel already uses this order. D2 now distinguishes paired
median/fold differences from differences of marginal tail quantiles and requires
adaptive comparisons against BOTH contextual and fixed Balanced, even when context
fails promotion. Primary selection and doubled-cost robustness are separate.

L1-L6 are disclosed/encoded in v2: normative parameters, pooling limitations,
explicit eligibility sets, complete screens, personalized own-horizon risk AND
purchasing-power rescreen without fallback searches, immutable calibration,
and all contrasts/outcomes preserved. L7 is resolved with exact tiny-request
accounting and active-state updates independent of the trade-count threshold;
first deployment and per-review reason are now explicit kernel diagnostics.
L8 uses the existing sequential prefix observer, still needing independent review.
No target, gamma, fee, suspension threshold, history window, fold or numeric
promotion threshold was tuned. No new competition policy outcome was computed.

The original POLICY_KERNEL_PROTOTYPE.md describes the historical prototype;
its tiny-transfer active-state rule is superseded only by this correction.
The corrected code still exposes a synthetic-only wrapper, no production loader
or final-evaluation API. Production driver/comparison/suitability implementation
and personalized evaluation remain outstanding. The calibration implementation
is unchanged; its new review must pin the corrected kernel and current contracts.

A new independent task must close D1/D2 and review the corrected kernel using its
own oracle, including a tiny executed target change, strict epsilon boundaries,
all five modes, prefix/state/fee consistency and review-latch behavior. Chief tests
are provisional evidence. Then release the separate calibration review promptly.
