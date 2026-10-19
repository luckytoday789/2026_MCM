SOL-016 implementation (pending independent chief acceptance)

The upstream implementation base is dd60066010f6904565fb51e99be8088285102e57.
All twelve task-pinned source hashes match after CRLF-to-LF normalization.
The imported package initializer is also bound. task-binding.json records exact
Git blob IDs, the immutable task, and release metadata from explicit commit
e018e2a70f9d1191d86e897df5f943228956139f. No newer main was fetched or merged.

Delivered API: safeinvest.policy_analysis.build_analysis_tables(metrics, *,
config, split) -> AnalysisTables. The frozen container holds ordinary list/dict
records in paired_differences, comparison_gates, selection, profile_screen and
profile_recommendations. No exports, core code, policy/kernel, configuration,
runtime helpers or queue were edited. No commit, push or watcher was started.

The API reads no files and performs no simulation or fitting. Config is checked
against the fixed v2 semantic JSON digest; this is a parameter check, not source
authentication. Inputs are exactly the 34 typed canonical fields derived from the
accepted metric_row plus mode/fee/fold and published policy diagnostics. Exact
field lists and output schemas are saved in verification.json and findings.json.
Reference policy diagnostics must all be null; cost-aware counts/share and
initial-allocation flag are required, with prefix years either valid or null.
Counts, shares, drawdown locations and units are validated. Validation numeric
tolerances reconcile shares with counts only; policy decisions use no tolerance.

For N scenarios there are 80*N input records, 100*N paired rows, 100 gate rows,
30 class screens and 10 recommendations. The rational audit uses N=8; the unit
suite also constructs N=120 with a development label to check the 12000-row
paired shape. Every number is generated in code. No original/raw/development/
final CSV or strategy result was opened. A label validates shape only.

All ten declared contrasts occur at both fees and all five horizons. Each row
keeps six accepted paired metric differences and applicable review diagnostics.
Marginal p10 growth and p90 loss differences are computed from separate scenario
marginals, never quantiles of paired differences. All four fold medians, strictly
positive counts, signed statistics, individual gate flags and failures survive.
Context uses balanced_cost; adaptive always uses BOTH balanced_context and
balanced_cost. H30/.0025 alone selects the primary. Doubled-cost support cannot
replace it. Fixed balanced_cost has no added-complexity support claim.

Each customer screen uses its own H and the fixed conservative/balanced/growth
mode. Horizon, declared eligibility/willingness, reserve/liquidity, risk and
purchasing-power flags are retained even if earlier flags fail. Severe cases use
exact loss then smallest scenario ID. Exceedances are strict loss>tolerance;
p90 equality and p10 zero pass. Among qualifying classes, inclusive .10 pp/year
indifference chooses the least growth-oriented. All assignments remain
provisional/personalized_overlay_pending. The exact own-tolerance/own-H fixed
class follow-up must rescreen risk AND purchasing power; failure causes referral
without automatic reselection. Pending initial referrals stay in original bills;
existing clients keep component dollars.

Units: differences are pp/year, pp for losses/shares, and original nominal/CPI_0
money units. The input accepts the existing metric_row COMMON_UNITS literals,
including its legacy growth_units text 'percentage points per year' on CAGR
levels; the case prose calls levels percent/year. This inherited wording is
reported for chief integration review, not silently changed in existing core.
Profile growth levels are explicitly percent/year. No metric values are rescaled.

Executed checks: Python 3.12.14, 19 focused unittest tests passed in 1.337 seconds
on the first run (history/trial-001-tests.json). The audit uses independent exact
Fraction interpolation and scalar subtraction on delivered output, checking all
800 paired rows, all 100 gates and all 30 profile screens. It also reruns the
focused suite and retains positive/negative behavioral facts, including nextafter
threshold probes, both one-control adaptive failures, context-fails/adaptive-passes,
sensitivity failure, all-referral, zero-fold exclusion, tolerance exceedance and
indifference. These establish behavior, not development performance or production
timing. No statistical significance or investment benefit is inferred.

Verification: python -B audit/SOL-016/verify.py exclusively creates
verification.json with xb mode. --check recomputes and compares read-only. The
verifier binds upstream explicit Git commits/blobs and SHA256 LF bytes, and
hashes implementation, tests, verifier, findings, this document and fixed audit
history. It does not require a worker HEAD or branch. Keys, types, hashes,
integers, flags and decision-driving numbers compare exactly; other recomputed
numbers use abs=1e-11 / rel=1e-12. Independent rational checks use those numeric
tolerances, never to enlarge policy gates. Duplicate evidence keys/nonfinite
JSON are rejected. Verification cannot hash itself; later execution/integrity
logs are separate to avoid circular evidence dependencies. Scratch corruptions,
exclusive-creation refusal and original-byte preservation are recorded in
integrity-self-tests.json; scratch evidence remains under history/.

Infrastructure/metadata probes are recorded in history/infrastructure-001.json.
The first audit initialization also failed: the Fraction oracle expected ideal
p90-loss difference 1 to pass, whereas binary64 marginal interpolation produced
1.0000000000000009 at H15 for two reference contrasts. Per contract the latter
fails; no policy tolerance or implementation change was made. The failed verifier
and execution are preserved. history/diagnosis-001.json retains the actual rows,
exact rational difference and failing stored statistic. The corrected audit uses
independent binary64 scalar interpolation for threshold flags while preserving
rational numeric cross-checks. No unexecuted check is claimed.
The runner owns handoff and delivery; independent chief review is still required.
