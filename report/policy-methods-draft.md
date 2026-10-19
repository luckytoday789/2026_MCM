# Cost-aware policy methods — design and kernel reviewed

This is reusable working text for the corrected v2 design, not a final paper or
an empirical result. SOL-009 supported the utility derivation but required
clarification of action selection and comparison statistics. SOL-013 approved
the corrected design but found a subnormal arithmetic defect in the kernel.
SOL-017 closed that defect but found extreme midpoint rounding error K2. The
K2 correction passed SOL-021 and independent chief replay. SOL-022 accepted
calibration mathematics and SOL-016 accepted the pure analysis component on
synthetic inputs. The case-engine delivery SOL-023 failed its standalone test
entry; its numerical checks do not waive that failure. SOL-025 separately passed
the portable repair and independent case acceptance. Writer acceptance and
production evidence remain separate gates. No customer
recommendation or performance advantage is claimed.

## An explicit estimate of benefit before trading

Let \(g_i=(1+r_i)/(1+\pi)\) be annual real gross returns and \(x\) a portfolio.
Under the declared constant-relative-risk-aversion utility
\(U(z)=-1/(3z^3)\), the annual certainty equivalent is

\[
C_P(x)=\left[E_P\left(\sum_i x_i g_i\right)^{-3}\right]^{-1/3}.
\]

The coefficient of relative risk aversion is four. This is a common modeling
assumption for comparing rules, not an estimate of each customer's preferences.
For positive scale \(a\), \(C_P(ax)=aC_P(x)\). Thus a one-way transfer fraction
\(\tau=\tfrac12\sum_i|w_i-u_i|\) and actual fee fraction \(f=k\tau\) reduce
the target's modeled certainty equivalent from \(C_P(w)\) to \((1-f)C_P(w)\).

We require a buffered score \((1-2f)C_P(w)>C_P(u)+10^{-12}\). The factor two
raises the decision hurdle; the account pays the original fee only once. For a
qualifying request, its actual modeled net advantage equals its buffered advantage
plus \(fC_P(w)\), so it is positive under the same assumed distribution. This
sufficient modeled condition does not guarantee a realized gain or a long-horizon
optimum. No fee is charged when the action is keep.

We first remove targets failing the strict hurdle. Among the remaining scores
within \(10^{-12}\) of the highest eligible score, priority is active target,
defensive, central, then growth-tilted. An ineligible active target cannot inherit
another target's passing score. The accounting executes a selected request even
when its transfer is below the reporting threshold; trade-frequency counting
and execution are distinct records. Initial allocation faces the same cost test.
A deferred investor stays in bills and can be considered again next year.

## Development calibration and the timing boundary

Four fixed evaluation folds use scenario index modulo four. Each fold's empirical
prior uses all annual observations from the other 90 scenarios, equally weighted.
This estimates a one-year marginal distribution without joining scenarios into
a path. Each evaluated path remains intact. Pooling assumes exchangeable marginal
conditions; annual observations within a scenario need not be independent.

Fixed modes retain the prior. Contextual modes mix it with the last
\(n=\min(5,t-1)\) completed observations from the same scenario:

\[
P_t=\frac{15P_{\mathrm{train}}+\sum_{j=1}^{n}\delta_{g_{t-j}}}{15+n}.
\]

The number 15 describes prior weight, not a selection of 15 training rows.
Adaptive target alternatives first become available in year six. Every decision
uses only completed observations; fresh state is created for every scenario.
The context and adaptive controls share the information schedule, while their
holdings and suspension states may differ. These assumptions do not establish
that recent outcomes predict later returns.

## Review and customer screening

The generic comparison suspends automation when the maximum real drawdown already
observed at a review reaches 25%. It includes previous fees and year-end values;
a loss first observed during year t can affect the next review. Suspension is
latched. Holdings remain unchanged at each later review, with no transfer or fee,
and still earn subsequent returns. This stops automatic trading but retains
market and inflation exposure. The threshold is not a loss limit.

Suitability separately checks horizon, target bill reserve, willingness to bear
loss and purchasing-power performance. Every profile uses its own horizon.
A p90-loss screen can pass despite scenarios exceeding the stated tolerance;
we therefore retain the exceedance count and denominator, median and severe loss.
Nonnegative p10 growth screens terminal purchasing power rather than every point
along the path. Targets within 0.10 percentage points/year of the best qualifying
median growth use the least growth-oriented class. Empty feasible sets require
human review. A provisional assignment must be rerun at its own tolerance and
horizon and pass risk and purchasing-power screens again before freeze.

## Testing added complexity without changing the comparator

Development promotion uses the median of scenario-paired growth differences,
but differences of the separate marginal p10 growth and p90 loss quantiles.
Fold support uses strictly positive paired median gains in at least three folds.
Adaptive targeting must pass directly against both contextual fixed targeting
and fixed-prior targeting. The contextual rule's own failure does not remove
it as an adaptive comparator. All cases and negative findings remain visible.

Doubled costs use identical calibration and parameters with both accounting and
the decision score updated for the new fee. The resulting actions may differ.
This is a robustness assessment of the primary choice, not a second opportunity
to choose a primary rule. Overlapping fold training, viewed baseline summaries
and model-design choices mean development evidence is not an untouched test or
a significance guarantee. The reserved final scenarios remain closed until a
recorded freeze and must never be used for subsequent tuning.

## Own-horizon follow-up before a recommendation

For a provisionally assigned fixed class, the follow-up changes only the
suspension threshold to the profile's own stated tolerance and evaluates its own
horizon. The fold prior, target, fee and benefit rule remain fixed. The resulting
paths must pass both loss and purchasing-power screens again. Failure leads to
human review without selecting a different class. An initially referred profile
is not silently simulated under a replacement policy. A last-year loss can occur
without a subsequent review inside the evaluation horizon.

Primary-fee and doubled-fee profile choices remain separate. If their provisional
classes differ, that is a counterfactual change in suitability, not evidence that
one fixed strategy is robust to costs. The primary recommendation cannot be
replaced automatically by this sensitivity result. These follow-up outcomes and
all final evaluations remain unavailable at this drafting stage.
