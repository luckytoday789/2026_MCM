# SOL-017 independent K1 closure

code_verdict: **changes_required**. Corrected design remains **approve** under accepted SOL-013.
Evidence integrity is separate from the mathematical code verdict.

The original constant minimum-subnormal underflow rejection is closed. A new
heterogeneous subnormal rounding blocker K2 remains: let u=2^-1074, with weights
(1/4,1/4,1/2) and support (u,u,4u). The exact single-support CE is 5u/2.
Binary64 ties-to-even rounds it to 2u (0x0.0000000000002p-1022); the reviewed
code returns 3u (0x0.0000000000003p-1022), a 50% error against the rounded oracle.
The exact gross has 20% relative error. Log/exp roundoff crosses the rounding
midpoint. A bounded 2048-case rational subnormal grid finds
475 mismatches. Exact fixture
observations for every n=0..5 remain in verification.json. This is a true new
blocker under the requested tiny-value comparisons; no production fix, clipping,
new support bound or parameter adjustment was attempted.

Reviewed exact base 315b7072e98f4d6aafd8573507074fc023477918, policy SHA256 9026abd22818fb420ce75dcf100b461c1833eab8be03526366dd3faadaa77bba.
The only mathematical source diff is log_power. For positive weights,
log(sum(w*g)) = logsumexp(log(w)+log(g)); zero weights contribute no terms.
This avoids underflow of individual products before the inverse-cube moment.
CE = [(15*mean_prior(gross^-3)+sum_recent(gross^-3))/(15+n)]^(-1/3).
There is no clipping or imputation. Source outside log_power is byte-identical
to accepted SOL-013. New test bytes are pinned but chief tests do not count as
independent acceptance.

3581 focused checks; 487 failed comparisons
are retained by exact name and expected/observed values in verification.json.
Minimum-subnormal support (0x0.0000000000001p-1022) is checked with exact positive
equality, including zero and minimum-positive weights, duplicate supports and
every n=0..5. Minimum normal through maximum finite factors, heterogeneous
subnormal rational products, mixed extremes and tiny-weight dominant products
use independent exact Fraction moments and 160/240-digit Decimal agreement.
CE up to 1024 minimum-subnormal units is compared exactly; all numeric absolute tolerances
are zero (relative tolerance at most 3e-12, except tiny path 2e-11).
For identical portfolio support the extreme oracle returns the exact Fraction
CE directly, avoiding any Decimal-root approximation at exact midpoints.

Unchanged SOL-013 helpers reused: ce (80-digit Decimal; ordinary factors only), score, choose, oracle_path (tiny-transfer path only), rows, toy_run, TARGETS. The old exact verifier
blob is executed unchanged in its own module; its old task, BASE and hash
constraints are neither overwritten nor invoked. Only named scalar functions
are reused with the independently imported NEW production bytes. No historical
saved evidence is replayed as new acceptance or edited. No broad scheduler,
accounting, screening, or calibration suite was rerun.

The ordinary fixture (prior gross 1.10/1.02/1, one annual return .10/.02/0,
zero inflation, initial 100 bills, thirds target, k=.0025) independently gives
T=200/3, actual fee=1/6, each post-fee holding=599/18, buffered score=3887/3750,
actual net CE=7787/7500 and terminal wealth=7787/75. The twice-fee buffer is a
decision score; actual wealth pays one fee. Ordinary 15:n mixtures and scores
cover all five targets, n=0..5 and k=0/.0025/.005.

Strict keep hurdle, maximum-anchored epsilon ties, active/defensive/central
priority, adjacent floating-point threshold values, actual tiny-transfer state
and invalid final observations (also suspended) were checked. The real tiny
fixture has T=1.165084386991724e-12, positive fee=2.9127109674793099e-15,
action=target_change, active_after=growth_tilt,
is_trade=False, executed_target_change=True.
Reporting epsilon does not cancel execution or active-state transition.

Normative gamma=4, prior strength=15, window=5, first alternatives at n=5,
buffer=2, epsilon=1e-12, transfer-reporting epsilon=1e-10, review threshold=25%,
targets and fee rates .0025/.005 remain unchanged. No parameter review or tuning.

verify.py --create uses exclusive creation. --check recomputes read-only,
binds exact task/source/import hashes and artifacts, permits HEAD to advance,
and never repairs evidence. Integrity self-tests and preserved trial records
are separate artifacts. Historical SOL-013 remains changes_required.
Trial 001 required exact equality even at the largest subnormal; its 42 failures
were within 8.6e-14 relative error and did not establish a source defect. That
overstrict audit trial is preserved under history/ with its diagnosis. The
subsequent K2 midpoint failures persist at the appropriate comparisons.

Limitations: Synthetic kernel review only; no competition CSVs or outcomes read. No production loader, writer, calibration, selector or final-run certification. SOL-013 design approval is inherited, not a new parameter or performance review. Finite fixtures cannot prove correctly rounded CE for every binary64 input; numerical tolerances are explicit. Injected scores exercise strict hurdle/tie mechanics; the tiny transfer uses the actual CE gate. Chief tests are provisional provenance, not independent acceptance; chief accepts exact delivered evidence.
