# SOL-021 independent K2 review

Code verdict: **approve**. Evidence integrity: passed.
3720 checks; all 2048 retained rational grid cases; 0 failed comparisons.

Production base: 79a9a63d939c14d4af242d86ceeaa42c044803c4. Immutable task: cc080c884d63e6dcf4100c50758042e4120db120.
Exact SHA256 and imported Git blob IDs are in findings.json and verification.json.
Unchanged named SOL-017 decimal_ce and SOL-013 ordinary helpers are isolated in
oracle.py, with per-function pinned-source provenance. No historical boundary is
invoked, overridden or relabeled. Historical negative verdicts remain unchanged.

The exact route normalizes the fractions of floats returned by validate_target.
Positive unit-sum weights make each q a convex combination of finite positive
support. Their inverse-cube mean is bounded by inverse cubes of support extrema,
so its inverse cube root lies within those extrema. The 15:n mixture preserves
these bounds.

Positive finite binary64 encodings increase with value. Starting at zero and
maximum finite, x^3*M<=1 is monotone and halves an integer interval below 2^63,
requiring at most 63 comparisons. Adjacent endpoints bracket the root; if it
equals maximum finite, the upper endpoint still returns correctly. Comparing
the rational midpoint cubed times M with one selects the nearest endpoint.
Encoding parity equals significand parity, including subnormal/normal transitions;
the equality branch therefore implements ties-to-even.

The exact 5u/2 midpoint returns 2u; the opposite 7u/2 midpoint returns 4u.
All n=0..5, heterogeneous prior/recent support, duplicates, zero/tiny weights,
residual validated unit sums, minimum positive through maximum finite, invalid
support and both sides of log(minimum normal)+1 are checked. Adjacent boundary
probes record the actual route: preliminary log roundoff may map neighboring
values to the same route, within the one-log-unit margin and ordinary tolerance.

Ordinary 15:n mixtures, strict hurdle/ties and real tiny positive transfer state
transitions use unchanged independent oracles. Initial rational fixtures:
T=200/3, fee=1/6, each post-fee holding=599/18, buffered score=3887/3750,
true net CE=7787/7500, terminal wealth=7787/75. The twice-fee decision buffer
remains separate from actual one-fee accounting. The tiny selected change executes,
charges its positive fee and updates active state below the trade-count epsilon.

AST comparison confirms code outside helper/imports/CE routing is unchanged.
The ordinary log moment is unchanged. No clipping, input bound, strategy threshold,
fee, target or parameter tuning is introduced; the routing margin is numeric only.
Tiny comparisons are exact; larger tolerances are declared with zero absolute
tolerance. Correct rounding is reviewed for the exact route, not the ordinary route.

Read-only --check recomputes observations, verifies pinned imports, oracle
provenance and artifact hashes, and does not require HEAD equality. Scratch tests
challenge numeric observations, source/import hashes, artifacts and exclusive
creation, preserving deliberate corruptions without repair.

Infrastructure issues are in history/infrastructure.json. The first audit trial
wrongly required exact ordinary maximum-support bounds; diagnosis-001.json records
the correction to the declared relative tolerance, and the failed trial and source
are preserved. Two malformed tool-call constructions ran no code. The first
advanced-HEAD scratch view omitted a refs directory; diagnosis-002.json records
the fix and preserves the failed creation. A second clean-control failure came
from JSON lists versus recomputed tuples; diagnosis-003.json records lossless JSON
normalization. That failed suite is preserved and superseded by passing controls.
No verification existed during either failed creation.
The shell helper could not start; Node execFile ran Python 3.12 without a shell.
A missing NumPy probe affected no check: reviewed modules use the standard library.
A task-path probe was corrected to the pinned dispatch commit.
No real CSV reads, installs, source/spec/task edits, workers, commits, pushes,
publication or production/final runs occurred. Production loader, writer,
calibration and final evaluation remain outside this kernel review.
