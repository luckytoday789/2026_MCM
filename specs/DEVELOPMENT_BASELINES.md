# First development baseline experiment, v1

Owner: chief. Specified before any strategy outcomes. Independent review and accepted
core implementation are required before experiment dispatch. Fixed parameters:
specs/development_baselines_v1.json. This is a development design, not the final
freeze or a customer recommendation.

## Question and scope

Measure the required equal-weight annual baseline against two simple references:
keep initial bills, and initially buy equal weights then preserve holdings. This
isolates costs and weight drift from annual rebalancing. Buy-and-hold does not
estimate trade benefit and cannot alone satisfy the full Balanced requirement.

Use only original synthetic scenarios 1--120. Each independently starts with wealth
100 in bills. No fitted parameter, forecast, optimizer, random search, daily
conversion, withdrawal, extra fee or terminal liquidation. Audited scenario
outcomes are valid competition evidence; they are not historical forecasts.

This pilot does not assign Conservative/Balanced/Growth targets, decide suitability
or conclude whether automatic target updates add value. Those require later
development design, a cost-aware rule and profile analysis.

## Actions and timing

Asset order: equity, bond, bill proxy. bills_keep keeps dollar holdings at every
review. equal_weight_annual requests exact thirds every review, including period 1.
equal_weight_buy_hold requests thirds in period 1 and keeps holdings thereafter.
All three have one review each year. Keep costs zero.

Construct and record each action using policy ID, year, pre-return holdings and
available history before obtaining that year's returns or inflation. Use the locked
transfer and pro-rata fee convention, then returns, then exact CPI deflation.

Actions do not depend on horizon. Prefixes of one 30-year ledger per policy/scenario
therefore support H=5,6,15,25,30. Exclude all wealth, fees and reviews after H from
H-year metrics; independently verify prefix reruns. Common policy comparison: H=30.
Profile A/B/C/D/E uses H=5/15/30/25/6. Tolerances are not guaranteed bounds.

## Metrics and aggregation

Apply specs/ACCOUNTING.md: real CAGR; sample standard deviation of annual net real
wealth returns (ddof=1); maximum real drawdown including initial, post-fee and
year-end observations. Calculate scenario metrics before scenario aggregation.

For each policy/horizon report median and p10 growth, median and p90 loss, median
annual fluctuation, median terminal real wealth, median cumulative nominal fees,
and trade percentages including/excluding the initial review. Use linear quantiles.
Growth and fluctuation are percentage points per year; loss and trade share are
percent; wealth and nominal fee sums use initial nominal units, with real wealth
in time-zero purchasing power. Nominal fee sums are descriptive, not real welfare
losses. Summary trade shares use pooled trade counts / pooled review counts:
120*H or 120*(H-1); scenario denominators are H or H-1. Trade means transfer >1e-10.

Severe case: greatest large loss within each policy/horizon; exact ties choose
smallest scenario ID. Report ID, growth, loss, real terminal wealth, drawdown
peak/trough locations (year and initial/post_fee/end kind), and both trade shares.
This finite-sample maximum is not a probabilistic bound.

For each alternative minus equal_weight_annual on the same scenario/horizon,
record paired differences in growth, loss, terminal real wealth, nominal fee sum,
and both trade shares. Positive loss difference means worse. These are descriptive
comparisons with no significance claim or winner-selection threshold.

## Outputs in the future fixed run directory

The future HY3 task will specify an already-pushed source SHA and output directory.

- run_manifest.json: schema/plan ID; source SHA; config/code/input hashes; command;
  Python/package versions; UTC start/end; split and parameters; CPU runtime;
  completed/failed status; hashes of every other output file.
- annual_ledgers.csv: 10,800 rows keyed by policy/scenario/year. Record action,
  pre-trade holdings/wealth, target when applicable, transfer, fee, post-fee
  holdings/wealth, annual returns, inflation, end holdings/wealth, CPI before/after,
  post-fee/end real wealth. Asset components have separate numeric columns.
- scenario_metrics.csv: 1,800 policy/scenario/horizon rows; all defined metrics,
  fee sums, trade counts, review denominators, percentages, split and units.
- summary.csv: 15 policy/horizon rows with the specified aggregates and severe
  case, scenario count 120, horizon, split and metric unit columns.
- paired_differences.csv: 1,200 alternative/scenario/horizon rows with unit columns.
- checks.json: checks actually run, counts, failures and maximum numerical residuals.

CSV: UTF-8, deterministic order, round-trip float precision. Metrics must be finite.
Keep targets may be blank; all monetary zeros are explicit. No H=1 metrics here.

## Acceptance and next handoff

First accept chief's independent review of SOL-001, HY3-001 source/split evidence,
and Sol's independent review of this design. Then publish and review the actual
pilot driver before assigning HY3 fixed commands. HY3 must not invent a missing
driver or infer an API. No task can reference unpushed source.

Required checks:

1. Development hash, schema, complete unique IDs/periods and row counts. Performance
   driver reads neither raw nor final data.
2. Independent toy oracle: 20-unit transfer, initial fee, exact keep, two-year
   path, inflation-only loss and initial-fee drawdown followed by recovery.
3. Every ledger: nonnegative finite holdings, budget balance, fee before returns,
   keep preservation, exact CPI, baseline target. Toy abs=1e-9; ledger rel=1e-10.
4. All policies, horizons, scenarios and required files/counts/hashes.
5. IDs 1,60,120: independently rerun all prefixes and recompute metrics from
   holdings. Perturb returns/inflation at and after year 10; actions through year
   10 and earlier states stay unchanged. Single-scenario and batch outputs agree.
6. A later separate Sol task recomputes representative HY3 ledgers, quantiles,
   paired differences and severe-case selections.

Preserve every failure and candidate. Validation tier: scenario-check.
After audit, pilot supports descriptive baseline comparisons. Recommendations need
later suitability, cost-aware policy development and sensitivity. All later tuning
uses development evidence. Final 121--180 stays closed until a separate freeze.
