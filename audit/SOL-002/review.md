# SOL-002 independent review

**Verdict: passed for the pinned chief design and toy oracle. No material blocker found.**

Reviewed base: 297fc5d846bfc218795238e567875e49b18e7053. This reviews chief's specification and reference mathematics, not the accepted production implementation or strategy performance. Three nonblocking clarifications are proposed for the separate pilot-driver review.

Python 3.12.14 ran **393 passing checks**, including **115 oracle leaf comparisons** (numeric inputs/results, exact rational strings, nulls and metadata). Every numeric oracle leaf is covered. Largest absolute residual: **9.266521423384168e-15**, at the second post-fee real wealth observation, below **1e-9**. Rational representations match exactly. verification.json records each expected/observed value; findings.json records verdict, source hashes and corrections.

## Sources and independence

Read AGENTS.md, the immutable local task, protocol, PROBLEM_LOCK.md, ACCOUNTING.md, DEVELOPMENT_BASELINES.md, development_baselines_v1.json, accounting_oracle.json and accounting_reference.py. Source SHA256 and Git object IDs are computed from **canonical Git blob bytes at the pinned commit**, not Windows checkout bytes. The four chief-source hashes match the task. The verifier also checks the lock/protocol hashes, HEAD, assigned branch, task identity and permitted directory. Checkout source text must match the pin after newline normalization.

Only locally available origin/main control/queue metadata was inspected beyond the pin: running state, unexpired deadline, no local/parent STOP, SOL-001 accepted before this slot. No fetch occurred. The old pinned queue and absent later implementation are intentional, not a dependency failure or permission to import later code.

Chief's reference was reviewed **as text only**. Its scalar Fraction sales, fees, allocations, CPI and JSON derivation agree with the lock. Its second transfer equals the equity sale and half the absolute dollar differences. Float square roots account for harmless residuals in CAGR/dispersion.

Our verifier imports/executes neither chief Python nor production accounting/metrics. Chief JSON is observed comparison data only. Independently calculated expectations use a general exact cash-flow engine: desired purchases determine transfers; fees reduce desired holdings pro rata. Drawdown enumerates all earlier peak/trough pairs; sample variance uses pairwise squared differences; Decimal precision 70 supplies roots. Stored chief results and later production code never supply expected values. No third-party package or scenario file is used.

## Policies, fees and real returns

| Policy | Initial action | Later action | Target |
| --- | --- | --- | --- |
| bills_keep | keep | keep | none |
| equal_weight_annual | rebalance | rebalance | exact thirds |
| equal_weight_buy_hold | rebalance | keep | thirds initially |

Asset order is equity/bond/bill_proxy. Keep preserves current dollars, costs zero and permits weight drift. A target request restores exact **post-fee** weights. A zero-transfer rebalance remains a review with no counted trade. Annual equal weights includes initial allocation. There is no withdrawal, liquidation fee or second fee on fee funding.

For W=sum(h), desired dollars d=Ww, the independent computation is T=sum(max(d_i-h_i,0)), c=T/400, h_plus_i=d_i-c*w_i. Equal desired/pre-trade totals make T half their L1 difference, as locked. Intended transfer differs slightly from realized component changes because fee funding is pro rata.

| Target from (0,0,100) | Transfer | Fee | Post-fee holdings/wealth |
| --- | --- | --- | --- |
| keep | 0 | 0 | (0,0,100) |
| (1/5,0,4/5) | 20 | 1/20 | (1999/100,0,1999/25) |
| thirds | 200/3 | 1/6 | each 599/18; total 599/6 |
| all equity | 100 | 1/4 | (399/4,0,0) |

Fees precede returns. CPI compounds multiplicatively; trade wealth uses CPI before the year, end wealth CPI after it. A separate two-year 10%-inflation/no-return toy gives CPI=121/100 and final real wealth=10000/121, rejecting additive inflation or nominal-minus-inflation approximation.

With year-end real wealth E_t and E_0=100, annual **net** real return is E_t/E_(t-1)-1, including that year's fee. For a target request this is also (1-c/W)*sum(w_i*(1+r_i))/(1+inflation)-1. It is not the post-fee-to-end return. CAGR=100*((E_H/100)^(1/H)-1). Fluctuation is sample standard deviation of annual net real returns times 100, **ddof=1**. H=1 fluctuation is undefined, not zero.

Independent two-year annual-rebalance calculation:

| Quantity | Year 1 | Year 2 |
| --- | --- | --- |
| Intended transfer | 200/3 | 599/216 |
| Fee | 1/6 | 599/86400 |
| Post-fee holding per asset | 599/18 | 8768761/259200 |
| Year-end real wealth | 182695/1836 | 254294069/2643840 |
| Annual net real return | -181/36720 | -14669/439200 |

CAGR=-1.9267582081245814 percentage points/year; fluctuation=2.013144926263849 percentage points/year; loss=10089931/2643840 percent. All end holdings and the complete five-observation real path also match the oracle.

Drawdown includes initial 100, post-fee and year-end observations. Bills with zero nominal return and 10% inflation give terminal real wealth=1000/11, growth=-100/11 percent and loss=100/11 percent. Initial-fee/recovery ends above 100 yet retains loss=1/6 percent. A separate [100,120,119.7,130] path demonstrates a later post-fee trough above initial wealth: loss=1/4 percent. Increasing paths have zero drawdown.

## Timing, horizons and scenario separation

The design constructs decisions before current-year returns/inflation, using only that scenario's observations through t-1. The policies have no fitted parameter and their actions do not depend on horizon. Toy perturbations from year 10 preserve states through year 9, year-10 pre-trade holdings and actions through year 10, while changing year-10 outcomes. Each horizon is independently rerun from initial wealth and compared with its prefix. These checks validate this mathematical interpretation, not an unseen production driver.

Scenarios independently reset holdings, CPI and drawdown peaks. Metrics precede aggregation. A reset toy gives scenario losses 0% and 50%; concatenating its paths would create spurious 75% loss. Single-toy and batched-toy outputs agree.

Profiles A/B/C/D/E correctly use H=5/15/30/25/6. Unique metric horizons are [5,6,15,25,30]; common policy comparison uses H=30. H-year metrics exclude later holdings, fees and reviews. Profile tolerance/liquidity labels remain inputs for later suitability work, not guarantees or recommendations.

| Output | Independent calculation | Rows |
| --- | --- | ---: |
| annual_ledgers | 3 policies * 120 scenarios * 30 years | 10,800 |
| scenario_metrics | 3 * 120 * 5 horizons | 1,800 |
| summary | 3 * 5 | 15 |
| paired_differences | 2 alternatives * 120 * 5 | 1,200 |

Write the annual ledger once per policy/scenario, not once per horizon. H=30 is reused for profile C/common comparison. Config/prose agree on counts, split, input declaration, initial holdings, exact thirds, fees, threshold, profile mapping, quantiles, six output files and execution guards. The declared input hash is verified as a specification value only; actual CSV hashing/schema/split validation is separate HY3 work.

## Quantiles, trades, severe case and paired signs

Quantiles sort **scenario metrics** and interpolate at (n-1)*q. [0,10,20,30] gives p10=3, median=15, p90=27. Median/p10 growth, median/p90 loss, median fluctuation, terminal wealth and nominal fees are specified. Wealth uses time-zero purchasing power; nominal fee sums are descriptive, not real welfare losses. No CVaR, guaranteed bound, significance claim, fitted threshold or winner recommendation is asserted.

A trade is strictly T>1e-10. This classifies activity; it does not waive a small nonzero fee. Scenario denominators are H and H-1; pooled denominators are 120H and 120(H-1). All five horizons are checked. Two-year including/excluding percentages are bills=0/0, annual=100/100, buy/hold=50/0. Every annual review counts in denominators, including keep and zero-transfer reviews.

Select greatest drawdown within each policy/horizon; **exact** ties choose smallest scenario ID. A toy confirms that a 1e-12 larger loss wins even at higher ID: the 1e-9 comparison tolerance is not a tie tolerance. Severe-case growth, terminal wealth and trade shares belong to the selected scenario, not aggregate quantiles. Peak/trough location ties need the minor clarification below.

Paired differences are **alternative minus annual baseline** on matching scenario/horizon keys. Positive loss is worse; positive growth/wealth is better; negative nominal fees or activity alone do not establish better performance. Bills' toy growth/loss/wealth/fee/trade-in/trade-ex signs are (-,+,-,-,-,-). Buy/hold has terminal difference=-1563989/2643840, fee difference=-599/86400 and trade differences=-50/-100 percentage points. Both reference policies save fees while having worse net toy growth; this supports no customer recommendation.

## Minor corrections, separate from blockers

**S1: deterministic drawdown locations.** Repeated peaks/troughs and zero loss do not determine unique location fields. [100,120,120,90,90] has four maximizing pairs and identical 25% loss. Proposed text: “Scan initial (year 0), then each year's post_fee and end; update peak only on strict increase, and selected drawdown only on strict increase. Initialize both selected locations to (0,initial).” This picks earliest maximizing locations and a zero-loss sentinel, without changing metrics or severe scenario. Resolve at the already-required driver review.

**S2: explicit schema.** Add annual_net_real_return=E_t/E_(t-1)-1 (decimal; E_0=100), optionally its percentage form. Explicitly include split, alternative_policy, reference_policy=equal_weight_annual, horizon and difference units in paired_differences.csv; include profile_horizons in the manifest. These make detached evidence auditable. The quantities/identities are already recoverable from the specified holdings, CPI, keys and manifest, so this is not a missing mathematical parameter or a blocker.

**S3: future H=1 consumers.** Excluding initial review has denominator zero. Explicitly return null for this trade share and ddof=1 volatility, keep later counts 0/0 and never coerce undefined values to zero. The present pilot expressly excludes H=1 metrics, so all actual denominators are positive.

No missing mathematical parameter, uncomputable required output or unsupported recommendation was found within this pilot's scope. These suggestions authorize neither fee changes nor invented policies. Full Balanced cost-benefit logic, Conservative/Growth allocations, suitability, sensitivity, customer explanation and final evaluation correctly remain later work.

## Executed validation and limitations

Executed initializer and then {python} audit/SOL-002/verify.py --check. **393 checks passed, exit 0.** Deliberately corrupted saved evidence was rejected with exit 1 and a separate diagnosis; the checker preserved the corrupted evidence/findings bytes rather than regenerating them. Restored original bytes, reran --check and confirmed verification.json/findings.json remained byte-identical. In-memory faults also demonstrate rejection of incorrect chief fee, zero H=1 volatility and wrong profile horizon.

The first verifier run failed before evidence initialization: an intentional fault-injection test mixed Decimal and float. This reviewer-code error was corrected using Decimal; it was not a chief defect. execution_log.json preserves the failure. The initial 354-check passing evidence is archived in history/; the intentional corruption input/diagnosis is separately preserved. No negative trial is represented as a pass.

This audit opens no scenario/raw/final data, measures no scenario performance, does not inspect accepted SOL-001 implementation and cannot certify a future driver. Acceptance still needs chief's exact-commit implementation review, accepted input evidence, reviewed driver and specified checks on actual development outputs. All edits are under audit/SOL-002. No chief source, task, branch, commit, push, watcher, package environment or final-data gate was changed.
