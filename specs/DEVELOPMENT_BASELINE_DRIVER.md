# Development baseline driver contract v1.1

Owner: chief. This is the implementation addendum to DEVELOPMENT_BASELINES.md,
accepted through SOL-002 at 54d90abd3d35f6578bab964cd54dcce42e578f53.
The original v1 plan, configuration and published tasks remain historical evidence.
Use specs/development_baselines_v1_1.json for the next run. No policy parameters,
fee convention, metrics or scenario split change. This is not the final freeze.

## Clarifications resolved before implementation

- S1: Scan initial (year 0, kind initial), then each year's post_fee and end real
  wealth. Update the running peak only on a strict increase; update the selected
  maximum drawdown only on a strict increase. Start both selected locations at
  (0, initial). This chooses the earliest maximizing pair and the initial sentinel
  when loss is zero. Select severe scenario by greatest exact float drawdown, then
  smallest scenario ID; numerical comparison tolerances are not tie tolerances.
- S2: Explicitly retain annual_net_real_return as a decimal, equal to
  real_end_t/real_end_(t-1)-1 with real_end_0=100. Each paired row names split,
  alternative_policy, reference_policy, scenario_id, horizon and difference units.
  The manifest contains profile_horizons, the common comparison horizon and the
  entire effective configuration. Add split and units to detached CSVs.
- S3: For H=1 utility calls, sample volatility and trade share excluding initial
  are null, with later trade count and review count both zero. Pilot horizons
  remain 5,6,15,25,30 and all defined pilot metric values must be finite.
- Accepted input verification is HY3-002, the Python 3.12 successor. HY3-001 remains
  cancelled and preserved. Its data agreement does not waive its runtime defect.

## Implementation scope

Provide a small standard-library, CPU-only driver over the accepted accounting
and metric engine. No optimizer, fitting, random candidate search, new policy,
package installation or runtime-helper edit. It is reasonable to extract the
existing simulation loop into simulate_policy with a prefix-only callback and
retain simulate_equal_weight as a backward-compatible wrapper. Do not duplicate
accounting/fee formulas in production code or change the existing public API.
Only three callbacks exist: bills_keep, equal_weight_annual and
initial-equal-weight-then-keep. Callbacks cannot receive current/future outcomes.

Production command interface:

    python scripts/run_development_baselines.py --config specs/development_baselines_v1_1.json --output results/development/HY3-003
    python scripts/run_development_baselines.py --config specs/development_baselines_v1_1.json --output results/development/HY3-003 --check

HY3-003 above reserves a run-directory name, not a published task. Chief will
publish its immutable commands only after code review and prerequisite acceptance.
SOL-004 implementation tests use generated toy data, with synthetic labels. They
must not create competition performance tables. Driver acceptance precedes the
first actual 120-scenario run.

The production loader opens only the exact configured development CSV, after
checking its path and SHA256. It checks six exact fields, 3600 unique ordered
scenario/period rows for IDs 1..120 and years 1..30, finite annual simple values
and positive gross factors. Reject duplicates, missing rows, extra IDs, wrong
input hashes, invalid config and final/raw paths. Do not call check_inputs.py
from the performance driver: that metadata tool also opens raw/final inputs.
The loader may validate numeric domains up front; policies still receive only
completed history and decisions precede current-outcome access in the simulator.

The CLI uses the exact supplied config and rejects unrecognized policy IDs,
unsupported horizons, altered split/initial wealth/fee/rules for this fixed pilot.
Do not silently replace configured values with other defaults. A changed study
requires a separately versioned chief configuration. Unit-level functions may
accept explicit synthetic fixtures; their labels cannot be presented as real runs.

## Output schemas and auditability

Use the six filenames in the configuration. CSVs are UTF-8 LF, deterministically
ordered by policy ID, scenario ID, year/horizon (summary by policy ID/horizon),
with round-trip floats and explicit zero amounts. Empty targets mean keep.
Every CSV includes split and clear unit columns; annual returns/inflation are
simple decimals, monetary fields are nominal units except named real wealth.

annual_ledgers.csv has one row per policy/scenario/year: decision action/target,
pre/post-fee/end component holdings and total wealth, CPI before/end, pre/post-fee/
end real wealth, transfer, fee, asset returns, inflation, annual_net_real_return.

scenario_metrics.csv has one row per policy/scenario/horizon: real CAGR, sample
annual fluctuation, real maximum drawdown, terminal real wealth, nominal fee sum,
trade counts, review counts, trade shares including/excluding initial, and the
selected drawdown peak/trough year/kind. Exclude every observation after horizon.

summary.csv has one row per policy/horizon: scenario count, median/p10 CAGR,
median/p90 loss, median fluctuation, median terminal real wealth, median nominal
fee sum, pooled trade counts and denominators and both pooled trade percentages.
Include severe scenario ID, its growth/loss/terminal real wealth, peak/trough
locations and both trade shares. Quantiles operate on scenario metrics, not rows.

paired_differences.csv contains the two alternatives minus equal_weight_annual
for each scenario/horizon: growth, loss, terminal real wealth, nominal fees and
both trade shares. Use percentage POINTS for differences of percentages. State
that positive loss difference is worse. Do not calculate a winner or p-value.

checks.json records actual check names, status, counts, thresholds, failures and
largest numerical residuals. A status alone is insufficient. Record absolute and
scaled residuals separately; compare fixtures at abs=1e-9 and ordinary ledgers
at abs=1e-9/rel=1e-10 without converting tolerance to a trading/selection threshold.

run_manifest.json binds plan/schema, Git source commit, effective config,
canonical Git source hashes, actual code/config/input bytes consumed, exact
command, Python/package versions (stdlib is sufficient), UTC start/end, elapsed
and CPU time, split, horizons, status and hashes of every other output file.
Exclude the manifest itself from its output hash map. The production run must
reject changed tracked code/config relative to recorded source SHA; output files
are not source. No local credentials, machine identity or private team details.

A new run refuses a nonempty output directory so failed evidence is preserved.
On failure after directory creation, write a failed manifest/diagnosis and exit
nonzero, without fabricating missing outputs. --check never overwrites evidence:
verify hashes, schema/counts/keys, rerun deterministic computations and compare
stored rows, reporting corruption with a nonzero exit. Normalize output hashes
using published LF bytes; never silently repair or regenerate saved files.

## Mandatory checks

1. Preserve all 28 existing accounting and four protocol tests. Check exact
   agreement of the annual equal-weight wrapper and generic engine on toys.
2. All initial fee fixtures, inflation-only loss, initial/post-fee loss followed
   by recovery, zero-transfer reviews, keep-dollar preservation and H=1 nulls.
3. Every ledger reconciles pre wealth = post-fee wealth + fee, intended transfer,
   nonnegative holdings, target weights, return application, compounded CPI,
   exact real deflation and net annual returns. No fee on keep.
4. Generated 120-by-30 synthetic rows produce counts 10800/1800/15/1200, distinct
   keys, finite metrics and all three policies/five horizons. Label these synthetic.
5. For IDs 1,60,120, independently rerun each horizon from initial holdings and
   compare with prefixes. Recompute representative metrics by independent scalar
   arithmetic from rows, not by reusing the production metric function for expected
   values. In the real run these checks use the selected development scenarios.
6. Alter returns/inflation at and after year 10: decisions through year 10,
   year-10 pre-trade holdings and states through year 9 stay unchanged. Compare
   single-scenario versus batch results. Include a guarded-row test for access order.
7. Independent small fixtures check interpolated quantiles, severe exact ties,
   earliest peak/trough/zero-loss locations, paired signs and pooled denominators.
8. File checks: valid generated output passes; corrupted data/hash/missing rows
   fail without rewriting evidence; production loader rejects final/raw paths and
   ID 121. A test guard must fail on attempted opening of raw/final data paths.

Chief reviews exact implementation and independently checks fixtures before HY3
runs it. Sol subsequently receives a separate exact-commit review of HY3 outputs.
No final-data gate, policy freeze, target recommendation or performance claim is
implied by accepting this driver.
