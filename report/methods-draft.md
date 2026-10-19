# Accounting and evaluation methods — working text

**Editorial status:** reusable methods draft only. The mathematical conventions
below are locked; this is not a completed competition report. Accepted descriptive
baseline tables are in baseline-development.md. Policy selection, suitability
outcomes and final evaluation are pending. References
in parentheses are internal evidence pointers to be converted into report citations.

## Independent annual scenarios and purchasing power

The supplied data contain 180 independent synthetic scenarios, each with 30 annual
observations. They are competition inputs, not a historical market time series.
We allocate scenarios 1--120 to development and reserve 121--180 for a final
evaluation after the policy and evaluation protocol are frozen. We never join
different scenarios into one investment path. Each path starts independently with
nominal wealth 100 held entirely in bills. Holdings are long-only and fully invested;
the problem includes no deposits, withdrawals, borrowing or terminal liquidation.

At the beginning of year \(t\), a policy can use only observations through year
\(t-1\) from that scenario, together with any legitimately development-calibrated
parameters. Current returns and inflation are applied only after the decision.
Internal validation must exclude the evaluation scenarios from calibration.
The final split remains closed until a recorded freeze; final outcomes cannot
determine parameters or selection rules. (Sources: PROBLEM_LOCK; PROTOCOL.)

Let \(r_{t,i}\) be asset \(i\)'s annual simple nominal return and \(\pi_t\)
annual inflation. The consumer-price index follows

\[
C_0=1,\qquad C_t=C_{t-1}(1+\pi_t).
\]

An asset's real gross return is \((1+r_{t,i})/(1+\pi_t)\), rather than the
approximation \(1+r_{t,i}-\pi_t\). All performance judgments use purchasing
power measured in time-zero wealth units. Bills can lose purchasing power.

## One-way transfers and fee funding

Write pre-trade holdings as \(h_t^-\), wealth as
\(W_t^-=\sum_i h_{t,i}^-\), and weights as \(u_t=h_t^-/W_t^-\).
A target \(w_t\) has nonnegative components summing to one. The intended
one-way transfer and actual fee are

\[
T_t=\frac{W_t^-}{2}\sum_i|w_{t,i}-u_{t,i}|,
\qquad c_t=kT_t,\qquad k=0.0025.
\]

The factor one-half counts each intended transfer once. We measure transfers on
pre-fee wealth, pay the fee before returns, and allocate the remaining wealth in
the target proportions:

\[
h_t^+=(W_t^- - c_t)w_t,\qquad
h_{t,i}^{\mathrm{end}}=h_{t,i}^+(1+r_{t,i}).
\]

This explicitly chosen convention funds the fee proportionally and leaves the
target exact after fees. The small fee-funding adjustment is not charged again.
For a keep decision, \(h_t^+=h_t^-\), \(T_t=c_t=0\): we preserve dollar holdings,
not portfolio weights. Every target trade must satisfy
\(W_t^-=\sum_i h_{t,i}^++c_t\). Fees include the initial allocation.
(Source: ACCOUNTING; independent implementation review: SOL-001 and SOL-004.)

Real wealth immediately after trading is
\(V_t^+=\sum_i h_{t,i}^+/C_{t-1}\); real wealth at year end is
\(V_t=\sum_i h_{t,i}^{\mathrm{end}}/C_t\), with \(V_0=100\).
The distinction matters because trading precedes the current year's inflation.
The annual net real return \(q_t=V_t/V_{t-1}-1\) includes fees. Post-fee wealth
is an additional loss observation, not an additional annual return interval.

## Growth, ordinary fluctuation and large loss

For a customer's horizon \(H\), annualized real growth is

\[
G_H=100\left[(V_H/100)^{1/H}-1\right]\quad\text{percent per year}.
\]

Ordinary fluctuation is the sample standard deviation of annual net real returns,

\[
F_H=100\sqrt{\frac{1}{H-1}\sum_{t=1}^{H}(q_t-\bar q)^2},
\qquad \bar q=\frac{1}{H}\sum_{t=1}^{H}q_t.
\]

It is measured in percentage points of annual return. Large loss is maximum real
drawdown. In chronological order, form
\(x=(100,V_1^+,V_1,\ldots,V_H^+,V_H)\), and define

\[
L_H=100\max_j\left(1-\frac{x_j}{\max_{\ell\le j}x_\ell}\right).
\]

Thus ordinary fluctuation measures variability, while large loss measures the
greatest decline from an attained purchasing-power peak. Including initial wealth
and post-fee observations prevents the initial fee or a temporary fee-induced
trough from disappearing. Larger \(L_H\) means worse loss. The sample standard
deviation is undefined at \(H=1\); all five requested profile horizons exceed one.
(Sources: ACCOUNTING; DEVELOPMENT_BASELINE_DRIVER.)

Metrics use only the first \(H\) years. Profiles A, B, C, D and E use horizons
5, 15, 30, 25 and 6 years, respectively. The initial policy comparison uses a
common 30-year horizon and must be labeled accordingly. A customer's temporary
loss tolerance is a screening input, not a guarantee about future drawdown.

## Scenario summaries, severe cases and trade frequency

Calculate metrics for each independent scenario before taking medians or tail
quantiles. For sorted scenario values \(y_{(0)},\ldots,y_{(n-1)}\), the linear
quantile at probability \(p\) interpolates between indices
\(\lfloor(n-1)p\rfloor\) and \(\lceil(n-1)p\rceil\). Required summaries include
median and p10 growth, and median and p90 large loss. These are descriptive
scenario statistics; p90 loss is neither a worst-case bound nor CVaR.

For each policy and horizon, the development baseline contract selects the
scenario with the greatest drawdown; exact ties choose the smallest scenario ID.
Within a path, scanning initial, post-fee and year-end observations updates peaks
and selected losses only on strict increases. This retains the earliest
maximizing peak/trough pair, or the initial sentinel when loss is zero. Numerical
comparison tolerances do not redefine ties. Report the severe scenario's ID,
growth, loss, terminal real wealth and peak/trough locations. This finite-sample
case is not a bound on possible future losses. Its final-evaluation use must be
recorded in the freeze before final outcomes are opened.

A review counts as a trade when \(T_t>10^{-10}\). Across \(n\) scenarios, the
pooled trade share is \(100\sum_{s,t}\mathbf1(T_{s,t}>10^{-10})/(nH)\).
Also report the share excluding year 1, with denominator \(n(H-1)\) and numerator
restricted to years 2 through \(H\). Every policy has an annual review even when
no money moves. (Sources: ACCOUNTING; DEVELOPMENT_BASELINES and its v1.1 addendum.)

## Fixed references and limits of the evidence

The required reference requests equal thirds in equity, bonds and bills at every
annual review, including the initial allocation. Two additional references keep
initial bills throughout, or initially buy equal thirds and keep the resulting
dollar holdings thereafter. They help describe fee and drift effects. Buy-and-hold
does not itself implement an estimated-benefit trade rule.

Pair alternatives with the annual equal-weight reference on the same scenario and
horizon. Growth differences are percentage points per year; positive drawdown
differences indicate worse losses. Nominal fee totals are descriptive currency
sums, not inflation-adjusted welfare losses. No statistical significance or
out-of-sample investment recommendation follows from these descriptive baselines.
The three development references passed independent SOL-008 numerical review
and chief replay; their descriptive tables are in baseline-development.md. New
policy results and final outcomes require separate independent acceptance.

Any future result paragraph must name its split, horizon, scenario count and fee
rate, and identify accepted run evidence. The accepted baseline implementation's
toy checks establish computational behavior; they do not establish that a proposed
policy benefits customers. Suitability, automatic target updates, sensitivity and
the final recommendation require their own accepted evidence.
