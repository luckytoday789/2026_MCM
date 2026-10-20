# Limitations and AI-use disclosure -- working text

This draft distinguishes accepted computational checks from pending policy and
final evidence. Reconcile it with the final evidence and independent manuscript
review before delivery. It contains no customer assignment, new parameter or
claim that pending work passed. Private member details remain in the local copy.

## Model limitations and review behavior

The supplied scenarios are synthetic competition inputs. Their empirical spread
measures behavior within that scenario design; it does not estimate historical
market frequencies or establish future probabilities. Annual observations omit
intra-year peaks, troughs and trading opportunities. Our large-loss measure includes
annual post-fee and year-end wealth, but cannot recover losses between observations.
All paths follow the specified no-deposit, no-withdrawal setting. A customer's
liquidity classification screens target bill reserves; it does not simulate an
emergency cash withdrawal or guarantee that the reserve persists as weights drift.

The fee convention is explicit: intended one-way transfers are measured on
pre-fee wealth, the fee is funded proportionally, and returns follow the charge.
The sensitivity comparison will change that rate while retaining the declared
rule parameters. It will not test every fee-funding convention or isolate the
causal fee effect of annual rebalancing versus buy-and-hold, whose allocations
also differ. The doubled-fee outcomes are still pending at this draft's date.

The proposed cost-aware rule uses a one-year certainty equivalent under a fixed
risk-aversion assumption. Passing its buffered hurdle establishes an estimated
advantage under that distribution, not a realized gain or a multi-year optimum.
The empirical prior pools marginal annual observations across training scenarios;
it assumes useful common information despite possible within-scenario dependence.
The contextual extension also assumes recent completed observations are relevant.
Development comparisons and four-fold checks evaluate these choices, but their
training sets overlap and design was informed by viewed development baselines.
They are not an untouched final test or a significance guarantee.

Neither a p90-loss screen nor a stated tolerance is a loss cap. The declared review
rule acts only on information available at a subsequent annual review, so a large
loss may occur before automation suspends or in the final year without a later
review. While review is pending, the rule keeps existing component holdings,
makes no transfer and charges no transaction fee; the holdings still earn returns
and remain exposed to market and inflation risk. It does not liquidate into bills.
Initial unsuitable profiles are referred without simulating a substitute portfolio.
The generic 25% trigger and each profile's own-tolerance follow-up are distinct.
The prescribed personalized rescreen can reject a provisional class without trying
a replacement. Implementation and outcome acceptance remain necessary before
these proposed rules become recommendations.

## AI-use disclosure for the research record

GPT-6 Astra xhigh, followed by GPT-6.1 Sol xhigh in Codex, coordinated the
mathematical specifications, task contracts, code integration, independent
numerical checks and report drafting.
GPT-6.1 Sol xhigh on a separate Codex computer implemented assigned components
and reviewed specified mathematical and computational work. HY3 in WorkBuddy
supervised fixed Python execution on a third computer. Numerical results came
from executable Python code; model prose and a worker's completion label were
not treated as numerical verification.

Accepted work is identified by exact task, source, receipt and reviewed commit.
The record preserves negative numerical reviews, failed test commands, partial
implementations and actual quota failures. These do not disappear when a later
attempt succeeds. Development baseline results are accepted; at this drafting
stage there are no accepted cost-aware policy outcomes, customer assignments or
final results. No claim of final evaluation, complete paper validation or human
approval is made here. Update this status from the final record before submission.

The existing MIT-licensed math-modeling-skill (anticipate218, pinned commit
`e70b85b8a41aeb748789f66860c6bd4d123871cd`) informed organization and evidence
wording. The K-Dense scientific-visualization skill informed the figure workflow;
its pinned source and procedural citation are in baseline-figure-captions.md.
No additional skill was installed. The SafeInvest source requirements govern
format, names, annual returns, fee accounting and data splits.

Internal sources: specs/PROBLEM_LOCK.md; specs/ACCOUNTING.md;
specs/DEVELOPMENT_POLICY_PILOT_V2.md; specs/PERSONALIZED_REVIEW.md;
specs/PERSONALIZED_OUTPUT_NOTES.md; ops/PROTOCOL.md; ops/queue.json;
audit/chief/HY3-003-review.json; audit/chief/SOL-013-review.json;
audit/chief/SOL-020-review.json; audit/chief/SOL-021-review.json.
