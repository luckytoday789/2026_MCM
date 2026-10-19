# Development policy pilot v1 — chief design awaiting independent review

This is a new development design, not an execution authorization, accepted policy,
final freeze or customer recommendation. The original problem/accounting contracts
prevail. SOL-007 must review this design before implementation; a separate task
must implement it, chief must independently check its code/fixtures, and only then
may HY3 run fixed commands. Preserve the three existing pilot baselines unchanged.

## Questions, candidates and scope

We compare simple suitability targets with a transparent estimated-benefit gate,
then test whether changing Balanced targets adds enough value to justify complexity.
No optimizer, external market data, extra fees or daily returns are needed.
The eight declared modes, in equity/bond/bill order, are:

| Mode | Target(s) | Rule |
| --- | --- | --- |
| bills_keep | (0,0,1) | Existing reference |
| equal_weight_annual | exact thirds | Required unchanged annual reference |
| equal_weight_buy_hold | exact thirds initially | Existing reference |
| conservative_cost | (0.15,0.20,0.65) | Fixed target, fixed development calibration |
| balanced_cost | exact thirds | Fixed target, fixed development calibration |
| growth_cost | (0.60,0.30,0.10) | Fixed target, fixed development calibration |
| balanced_context | exact thirds | Fixed target, prefix-updated calibration |
| balanced_adaptive | (0.20,0.25,0.55), exact thirds, (0.45,0.30,0.25) | Prefix-updated calibration; restricted target changes |

Targets are chief's normative, deliberately coarse design assumptions. They are
not estimated optima, and have not been selected by searching candidate returns.
The broad three classes express more equity / less liquidity reserve as growth
emphasis rises. Their actual loss ordering must be measured, not asserted.
Use gamma=4 for all five new modes: a common moderate risk-aversion assumption
keeps differences attributable to targets and updating. Do not tune gamma.
All new modes initially have their stated central target as active target.
A target is an intention: if its estimated benefit cannot pay for the initial
transfer from bills, keep bills, record initial_allocation_deferred, and retry
at the next annual review. Never waive the cost test to manufacture deployment.

Existing all-development baseline summaries were viewed before this specification,
but numerical acceptance is pending SOL-006. There are no new-policy outcomes yet.
Any later internal development results are validation for model development, not
an untouched final test. Record all eight modes, both fee rates and every failed
attempt; report all comparisons rather than only the selected mode.

## Calibration and information boundary

Use development IDs 1..120 only. Four fixed folds: fold(s)=(s-1) mod 4. For each
evaluation scenario, fit its annual reference distribution using only the other
90 scenarios, all their 30 annual observations with equal weight. This pooling is
an empirical one-year marginal model, not concatenation into a fictitious path;
serial dependence is retained in each evaluated 30-year scenario. No optimizer,
feature standardization, threshold selection or other fitted quantity may use
the evaluated fold. Save training/evaluation IDs and hashes per calibration.

For each training observation j, form g_ji=(1+r_ji)/(1+inflation_j). All g_ji>0.
Fixed-calibration modes use this empirical distribution P_train unchanged.
The two contextual Balanced modes at time t use the last n=min(5,t-1) completed
observations of this SAME scenario, converted to real gross factors, and
P_t=[15 P_train + sum(last n point masses)]/(15+n). At t=1, P_t=P_train.
The prior strength 15 is an equivalent observation count, not 15 selected rows.
Both contextual modes use exactly the same information and updating schedule.
Adaptive alternatives are disabled until n=5 (first eligible review is year 6).
No decision sees current returns/inflation, later years, or another evaluation
scenario's outcomes. Each scenario has fresh policy state. Static parameters
fitted only on development are allowed before final evaluation; a later freeze
will refit the selected rule once on all 120 development scenarios.

## Estimated benefit, actual fee and action selection

Let u=h/sum(h), desired target w, tau=0.5 sum_i |w_i-u_i|, actual cost fraction
f=k*tau, and gamma=4. For distribution P define the annual real certainty equivalent

    CE_P(x) = [ E_P (sum_i x_i*g_i)^(1-gamma) ]^(1/(1-gamma)).

Weights are nonnegative and sum to one. CE is a real gross factor. Higher is
preferred; this is a CRRA expected-utility model, not expected arithmetic return,
a guaranteed gain, or an estimate of drawdown. Use stable arithmetic and reject
nonfinite/nonpositive gross factors. There is no fitting of gamma or fee buffer.
Homogeneity gives CE_P((1-f) w)=(1-f) CE_P(w), so actual estimated fee loss in CE
units is f*CE_P(w). The estimated pre-cost benefit is CE_P(w)-CE_P(u).
A conservative score uses twice that estimated fee loss:

    S_keep = CE_P(u)
    S_w = (1-2*f)*CE_P(w).

Trade only when S_w > S_keep + 1e-12. The factor 2 is a decision buffer; charge
ONLY the original actual fee k*T, with T=W*tau, under ACCOUNTING.md. It is not an
extra fee. Thus each executed trade's modeled pre-cost benefit exceeds twice
its modeled fee impact. Record CE_keep, CE_target, tau, f, pre_cost_benefit,
modeled_fee_impact, conservative_score and true net CE. Estimated utility is
one-year/myopic and model-dependent; no claim of a 30-year optimum is permitted.

For fixed modes consider only their central target. Adaptive mode considers only
its active target before year 6; afterwards consider all three Balanced targets.
Choose the highest score among keep and allowed targets. If targets tie within
1e-12, prefer the active target, then defensive, then central, then growth-tilted.
The tolerance governs decision ties only, never severe-case metric ties. If no
target beats keep by strictly more than 1e-12, keep exact dollars and charge zero.
If a winning target equals active target, action=rebalance; otherwise action=
target_change and replace active target only on execution. A proposal that fails
the gate does not change active target. T<=1e-10 is a nontrade review even if a
nominal rebalance request is logged. Numerical accounting remains authoritative.

## Human review and holdings while pending

All five new modes latch human_review at the first review where the maximum real
drawdown observed through t-1 is at least 25%. This common research threshold
isolates other policy differences; it is not a personalized loss guarantee.
Include initial wealth, all earlier post-fee values and year ends when computing
that observed drawdown. Never use the current year's yet-unseen loss. A review
at year t acts before its returns. Once latched, keep each asset's dollar holdings
at every remaining review: no transfer, no fee, no automatic target update or
simulated human restart. Assets still earn returns; losses can deepen and recover.
This suspension stops automation, not market exposure. Baseline references are
unchanged and do not receive this overlay. Report review frequency and its effect.

Missing/invalid inputs, nonfinite scores or broken accounting cause a failed run
with preserved diagnosis, not imputed investment outcomes. The operational
recommendation is human review with existing holdings unchanged; no completed
simulation may silently skip an invalid observation. A customer's changed horizon,
loss tolerance or liquidity need also requires human reassessment before trading.
No withdrawal or liquidity event is simulated because none is supplied.

## Customer suitability: separate horizon, willingness and liquidity checks

Profiles A/B/C/D/E retain H=5/15/30/25/6, tolerance 10/25/40/15/35 percent,
and liquidity high/medium/low/medium/high. In the first pilot score the three
fixed-target cost modes at each profile's own H, never at common H=30.
Use these disclosed service rules, not claimed financial laws:

- H<=6 permits Conservative only; 7<=H<20 permits Conservative/Balanced;
  H>=20 permits all three. Long horizon alone does not override low tolerance.
- Required target bill reserve is 0.60 / 0.25 / 0.10 for high / medium / low
  liquidity. This is a target reserve, not an invariant bill weight after drift.
  It does not model guaranteed immediate cash availability or actual withdrawals.
- Candidate passes risk screen only if its development p90 maximum REAL drawdown
  at H is <= stated tolerance. Also report the empirical exceedance fraction,
  median loss and severe maximum; p90 is not a worst-case bound or guarantee.
- Among passing targets whose p10 real CAGR is nonnegative, maximize median real
  CAGR at the customer horizon. Of targets within 0.10 pp/year of that maximum,
  choose the least growth-oriented class (Conservative, then Balanced, then
  Growth). This is a declared three-menu selection, not a broad search. If none
  has nonnegative p10 growth, or none passes risk/liquidity/horizon, request
  human review. Do not silently relax a constraint or assert bills solve it.

This intentionally cautious rule may assign multiple profiles the same class or
request review. Show the complete candidate screen so the result is explainable.
Targets are illustrative menus, not a mandate to deploy. Before final freeze,
any provisionally assigned rule must be rerun at the profile's OWN loss tolerance
as its suspension threshold, and risk screen rerun; if that fails, human review.
This personalized overlay is a separate small follow-up job, not an assumed
improvement. An initially referred customer retains the original bills pending
human review; an existing investor retains current dollars. Neither is risk-free
in purchasing-power terms. Generic Balanced comparison remains H=30/25% threshold.

## Comparison, selection and cost sensitivity

Produce the existing locked metrics for every mode at H=5,6,15,25,30 and the
required paired comparisons against annual equal weights. Additionally pair
balanced_context minus balanced_cost and balanced_adaptive minus balanced_context.
Keep scenario-level OOF results and fold identifiers. Aggregate scenario results
only after evaluating each independent path. Use existing linear quantiles and
exact severe selection. Retain full severe path and both trade shares.

The default is the simplest fixed-calibration balanced_cost rule. Permit the
contextual variant only if, at H=30 and k=.0025, all these predeclared conditions
hold relative to balanced_cost: median paired CAGR gain >=0.10 percentage points
per year; p10 CAGR decline <=0.10 pp/year; p90 drawdown increase <=1.00 pp; median
paired CAGR gain positive in at least three of four folds. Permit adaptive target
changes only if the same conditions hold versus BOTH contextual fixed target and
the simplest currently eligible mode. Equality at numeric thresholds passes;
these are practical selection tolerances, not significance levels or guarantees.
Always disclose negative findings and review/trade differences. No extra target
search or threshold adjustment after seeing results. If evidence cannot establish
material benefit, retain the simpler rule and explicitly reject added complexity.
A poor result for every rule may justify human review rather than an endorsement.

Repeat all eight modes at k=.005 with the same folds/parameters, calibrations,
actual fee conventions and score formula updated only for k. Original reference
results at k=.0025 are reused after audit, not overwritten. Report whether the
same predeclared selection conditions still hold; doubled-fee results do not
retune the primary rule. There are 8 modes x 2 fee rates; fold calibrations are
validation partitions, not hidden strategy variants. No final outcomes are read.

## Implementation and output handoff after design acceptance

Keep the accepted accounting/metric functions and untouched fixed baseline CLI.
A new driver may call the generic simulate_policy and use a callback sidecar for
four action labels, active/proposed targets, scores and review state; map keep/
human_review to engine keep, rebalance/target_change to engine rebalance. Derive
prior real drawdown using only already completed ledger observations and any
previous post-fee state. Test fresh-state and prefix equivalence explicitly.

Write separate directories per fee/mode so no artifact exceeds runner's 10MB cap.
Each must retain annual ledger, decision diagnostics, per-scenario/horizon metrics,
summary and paired differences; the run manifest binds all files and calibration
IDs/hashes, code/config/input hashes, runtime, commands and environment. Add
calibrations.json, profile_screen.csv and selection.json with explicit units,
parameters, full candidate facts and reasons. Record human_review first year and
share, target-change count and initial-allocation-deferred flag. No completed
artifact is overwritten; --check is strictly read-only. Production data remain
only data/development/scenarios_001_120.csv and its locked hash. Synthetic testing
has its own explicit seam and never masquerades as original data.

Independent validation before HY3: exact deterministic CE fixture; homogeneity
and actual-vs-buffer fee distinction; positive/negative/no-trade/tied scores;
first-five-year update gate; 15:n mixture weights; changing evaluation-fold
outcomes cannot change its prior calibration; future perturbation invariance;
review starts one year after observed threshold crossing and then preserves
dollars; all prefix horizons; state isolation; initial/post-fee loss; complete
units/keys/counts; source/hash/split guards; corruption is rejected read-only.
No implementation task is authorized by this prose alone. The next independent
review should challenge formulas, scope/runtime, normative assumptions, screening
logic and possible outcome-selection bias before the coordinator publishes code work.
