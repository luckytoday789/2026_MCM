# SOL-001 implementation and independent accounting review

Status: implementation ready for coordinator review, not an accepted modeling
conclusion. Role: sol; task SOL-001 attempt 1; base commit
`f5e67b1f53568b94379ea631659d53d90db14f7b`.

## Scope and provenance

Read AGENTS.md, the immutable `.runtime/task.json`, ops/PROTOCOL.md,
specs/PROBLEM_LOCK.md and specs/ACCOUNTING.md. The worktree HEAD matched the
task base and branch `work/sol/SOL-001-a1`; the local origin/main control was
running and SOL-001 was ready. No branch changes, commits, pushes, task edits,
watchers, strategy fitting or optimization were performed. No source CSV or
final-holdout outcomes were opened. All numeric fixtures are synthetic.

The implementation uses Python 3.12 and only its standard library. No project
requirements or specifications were changed. Tests were executed with Python
3.12.14. The ordinary shell tool failed during process setup before executing
commands; filesystem/process operations then used the available Node execution
tool. This was an infrastructure failure, not a failed quantitative trial.

## Independent assessment of the fee convention

There is no blocking mathematical objection to the locked convention. For a
valid positive-wealth portfolio it is self-financing after the explicit fee:
`sum(h_plus) + c = W`, all holdings remain nonnegative, and the desired target
is attained after fees. It counts a transfer once, includes initial allocation,
and avoids recursively charging for the fee-funding adjustment. Keep preserves
dollars exactly and incurs no fee. The implementation follows this convention
without substituting a post-fee turnover calculation.

My interpretive reservation is that **intended pre-fee turnover is not actual
net asset purchases after paying the fee**. For the required 20-unit example,
transfer 20 from bills into equity first: provisional holdings are (20,0,80).
The 0.05 fee is then funded pro rata: equity contributes 0.01 and bills 0.04,
giving (19.99,0,79.96). Thus equity's observed net increase is 19.99 although
the recorded intended transfer is 20. Likewise, an all-equity target has
intended turnover 100 but net equity holdings 99.75. An implementation that
recomputed turnover from those net holdings would use a different convention.

The original problem does not resolve fee funding this precisely. The
coordinator's disclosed convention is coherent, but the final report should
name it and avoid describing intended turnover as observed post-fee purchases.
Fee funding assumes divisible holdings and implicitly permits proportional
liquidation of all assets without charging the adjustment again. This is a
modeling assumption, not an empirical market-execution claim. No alternative
fee convention was implemented or tested against competition outcomes.

## Public APIs and units

Put `src` on PYTHONPATH, then import from `safeinvest` or its named modules.
Every holdings/weights/returns vector uses `(equity, bond, bill)` order. Dollar
amounts are nominal wealth units, with locked initial holdings `(0,0,100)`.
Returns, inflation, fee rates and ledger annual returns use decimals, not
percentage inputs. Frozen dataclasses and tuples can be exported with
`dataclasses.asdict` and `json.dumps`.

| API | Behavior and result |
| --- | --- |
| `rebalance(holdings, target, fee_rate=0.0025)` | Returns `TradeResult`: pre-trade holdings/wealth, target, intended transfer, fee, post-fee holdings and wealth. Uses the locked pre-fee formula. |
| `keep(holdings)` | Same result shape, exact copied dollar holdings, zero transfer and fee, target `None`. |
| `apply_returns(holdings, returns)` | Applies `h_i*(1+r_i)` after the trade; returns a tuple. |
| `compound_cpi(cpi_before, inflation)` | Applies `CPI_before*(1+inflation)`; initialize CPI at one. |
| `deflate(nominal_wealth, cpi)` | Divides by the compounded CPI exactly. |
| `annual_real_returns(year_end_real_wealth, initial_wealth=100)` | End-to-end annual decimal wealth returns, including the year's trading fee. |
| `compute_metrics(year_end_real_wealth, post_fee_real_wealth, split=..., initial_wealth=100)` | Returns horizon, split, units, net real CAGR, sample annual real volatility (`ddof=1`), and real maximum drawdown. Both series have H entries. |
| `maximum_real_drawdown(observations)` | Percent drawdown on the supplied chronological path; callers supply initial, post-fee and end observations in that order. |
| `linear_quantile(values, probability)` | Sorted linear interpolation at `(n-1)*p`, for one metric per independent scenario. |
| `simulate_equal_weight(rows, horizon=..., split=..., fee_rate=0.0025)` | One-scenario `BacktestResult` with explicit metadata, H ledger records, metrics, and trade percentages including/excluding initial review. |
| `decide_from_history(callback, scenario_id=..., period=..., holdings=..., history=...)` | Validates the exact same-scenario prefix 1..t-1 and invokes the callback with a frozen `DecisionContext`; requires a `Decision` result. |

`horizon`, `split`, and other parameters shown after `...` above are keyword
arguments; simulator horizon/split and metric split are mandatory. The simulator
accepts original six-field CSV-style mappings, including numeric strings:
`scenario_id`, `period`, `equity_return`, `bond_return`, `bill_proxy_return`,
`inflation`. Rows must already be ordered 1..N for exactly one scenario, with
H<=N. It rejects mixed scenarios even beyond H, missing/out-of-order periods,
and development IDs outside 1..120. It reads outcome fields only within H.

Only `synthetic` and `development` split labels are supported at this stage;
`final_holdout` is rejected. This API does not implement the future freeze/data
gate, load a file, or verify provenance/hashes of caller-supplied rows. Labeling
real final data as synthetic would violate the study protocol; the label is
not a security mechanism. No scenario summaries or market results are inferred
from the toy examples.

Each ledger records decision/action/target, before/post-fee/end holdings and
nominal wealth, intended turnover, fee, before/end CPI, before/post-fee/end real
wealth, realized asset returns/inflation, and annual net real return. Post-fee
real wealth uses **previous** CPI; year-end uses compounded **current** CPI.
The metrics path is initial 100 followed by each post-fee/year-end pair. Annual
volatility uses H annual end-to-end returns, not 2H intra-year observations.
Growth and drawdown use percent units; volatility is in percentage points of
annual returns. Trade shares count `T>1e-10`, even if the fee rate is zero.

Minimal synthetic example:

```python
from safeinvest import simulate_equal_weight

rows = [dict(scenario_id=7, period=t, equity_return=0.0,
             bond_return=0.0, bill_proxy_return=0.0, inflation=0.0)
        for t in (1, 2)]
result = simulate_equal_weight(rows, horizon=2, split="synthetic")
# Initial turnover 200/3, fee 1/6; wealth stays 599/6 thereafter.
```

## Independent expected numbers

Expected balances were simplified with `fractions.Fraction`, in a separate
calculation that imports no safeinvest implementation. The numerical output
is preserved in `expected_numbers.json`. This independence is arithmetic/code
separation by the same worker, not a substitute for coordinator acceptance or
independent human/agent review.

At fee rate 1/400 and initial holdings (0,0,100):

| Target | Intended transfer | Fee | Post-fee holdings/wealth |
| --- | ---: | ---: | --- |
| Bills | 0 | 0 | (0,0,100) |
| (0.2,0,0.8) | 20 | 0.05 | (19.99,0,79.96); total 99.95 |
| Equal weight | 200/3 | 1/6 | Each 599/18; total 599/6 |
| Equity | 100 | 0.25 | (99.75,0,0) |

Hand-computable two-year equal-weight fixture: first-year returns (0.20,0,0),
inflation 0.02; second-year returns (-0.10,0.05,0), inflation 0.03.

| Quantity | Independent expected value |
| --- | --- |
| Year 1 end nominal wealth | 4792/45 = 106.488888888889 |
| Year 1 end real wealth | 47920/459 = 104.400871459695 |
| Year 2 intended transfer | 599/135 = 4.437037037037 |
| Year 2 fee | 599/54000 = 0.011092592593 |
| Year 2 post-fee nominal wealth | 5749801/54000 = 106.477796296296 |
| Year 2 CPI | 5253/5000 = 1.0506 |
| Year 2 end nominal wealth | 339238259/3240000 = 104.703166358025 |
| Year 2 end real wealth | 339238259/3403944 = 99.660352520488 |
| Annual net real returns | 101/2295 and -26939/593280 |
| Net real CAGR | -0.169968185677 percent/year |
| Sample annual real volatility | 6.322638071291 percentage points |
| Maximum real drawdown | 4.540689050701 percent |
| Trade share, including/excluding initial | 100% / 100% |

For zero asset returns, zero fees, and inflation 10% then 20%, nominal wealth
stays 100, CPI becomes 33/25 and real wealth becomes 2500/33. Expected CAGR is
-12.961172022151%, sample volatility 5.356869554444 percentage points, and
maximum drawdown 800/33 = 24.242424242424%. This is exact compounded deflation,
not subtraction of inflation rates.

The post-fee drawdown fixture has observations `(100,99,110,88,120)`; expected
maximum loss is 20% from 110 to 88, despite final wealth 120. A one-year path
`(100,99,110)` still has a 1% fee-time drawdown. Zero market returns with the
default initial equal-weight fee produce wealth 599/6 and drawdown 1/6 percent.

## Prefix-only decision demonstration

The baseline creates a `Decision('rebalance', (1/3,1/3,1/3))` through the same
callback boundary before it accesses current return or inflation fields. No
adaptive policy, target updater, suitability logic or human-review workflow
was implemented in this task. For a future callback, the available interface
is illustrated by:

```python
from safeinvest import Decision, Observation, decide_from_history

def keep_example(context):
    assert len(context.history) == context.period - 1
    # Period 2 sees only period 1; no period 2 outcome is in this object.
    return Decision("keep")

decision = decide_from_history(
    keep_example, scenario_id=7, period=2, holdings=(20,30,50),
    history=[Observation(7, 1, (0.1,0.02,0.01), 0.03)],
)
```

The context contains only scenario ID, review period, current holdings and an
immutable completed-history tuple. It rejects cross-scenario or non-prefix
history. A guarded-row test raises on premature current outcome access. A
future-outcome perturbation test compares actual callback contexts and earlier
ledgers. These tests support the access-order contract. Ordinary Python cannot
sandbox a callback that captures external future rows in a closure or global;
future policy code still needs an independent no-lookahead audit.

## Validation and numerical tolerances

All tests are in `tests/test_accounting.py`. The required validation command is:

```text
python -m unittest discover -s tests -p test_accounting.py -v
```

Final execution: **28 tests passed, exit code 0**, with bytecode writing disabled
through `PYTHONDONTWRITEBYTECODE=1`. The full output and earlier successful runs
are preserved in `validation.txt`; no failed numerical/test trial was discarded.

The suite covers the exact four initial examples, keep/no trade, fee-before-
returns, zero fees/returns, compounded inflation and deflation, inflation-only
loss, two-year rational balances/metrics, initial and post-fee drawdown peaks,
trade shares, exact -100% returns and terminal loss, interpolation, CSV strings,
explicit horizon, input/split/scenario
guards, serialization, immutable prefixes and future perturbations. A seeded
200-case toy check verifies conservation, nonnegative finite holdings and full
investment; a separate 30-period synthetic ledger reconciles every period.
No performance claim about competition scenarios follows from these checks.

No numerical solver is used. Targets with unit-sum error <=1e-12 are accepted
and normalized solely for floating-point roundoff; negative weights and larger
sum errors are rejected. No turnover threshold is applied to fee computation.
Assertions use absolute tolerance 1e-9 and relative tolerance 1e-10, as locked.
Holdings and rates must be finite; positivity/domain checks reject invalid
states rather than clipping or silently repairing them.

## Unresolved conventions and limitations for coordinator review

- At H=1, sample standard deviation and trade share excluding the initial
  review have no defined denominator. Both are explicitly `None`, not zero.
  All specified customer horizons are >=5, so this affects toy/utility calls.
- Rebalancing needs positive pre-trade wealth to define current weights. Source
  asset returns are >-1, but `apply_returns` also applies an exact -100% return
  literally. Zero holdings can be kept without fees. A total terminal loss is
  measured as CAGR -100% and drawdown 100%; the baseline rejects a subsequent
  review at zero wealth, and metrics reject a subsequent annual interval with
  zero prior wealth. No bankruptcy recovery/continuation rule is invented.
  Inflation must remain >-1 so compounded CPI is strictly positive.
- An artificial fee rate large enough to consume all wealth is rejected.
  The specified 0.0025 rate leaves positive wealth for valid targets.
- Annual end points and fee-time observations cannot identify losses inside
  a year. Drawdown here is the locked observed-path measure, not continuous-
  time maximum drawdown or a guarantee on future losses.
- The caller supplies the customer horizon; no default 30-year comparison,
  customer profile selection, scenario aggregation or severe-case rule is
  chosen here. Any later common-market comparison must label its 30 years.
- Floating-point overflow/underflow is not a modeled economic state. Ordinary
  finite positive-wealth annual ledgers are the supported range; no currency
  rounding, minimum lot size or terminal liquidation charge is introduced.

No implementation blocker remains for this task. Chief must review the exact
delivered code, these assumptions and executed checks before acceptance.
