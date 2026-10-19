# K2 exact rounding near binary64 underflow

SOL-017 at 90f5c8d3fe9b76861f9e302ce23d2e5cd6f2e839 closed the original K1
constant-support rejection but found a second numerical defect. With u=2^-1074,
weights (1/4,1/4,1/2), and support (u,u,4u), the exact constant-support CE is
5u/2. Ties-to-even yields 2u; the log/exp path returned 3u for every n=0..5.
Chief reproduced the defect and accepted the negative evidence in
`audit/chief/SOL-017-review.json`. All historical verdicts and failed audit trials
remain unchanged. Neither review used competition outcomes.

Keep the ordinary log-domain algorithm unchanged. When its log CE lies below
log(minimum normal binary64)+1, evaluate the same inverse-cube moment using exact
rational arithmetic. The one-unit margin ensures values near the normal/subnormal
boundary take the robust route; it is not an input restriction or a policy
threshold. The inputs remain any positive finite binary64 support.

After the existing validate_target admits a long-only target, convert those
validated binary64 weights to fractions and normalize their exact sum to one.
This implements unit-sum weights without a second floating-point normalization.
Compute q_j=sum_i(w_i*g_ji), then
M=(15*mean_prior(q_j^-3)+sum_recent(q_j^-3))/(15+n).
All of this arithmetic is exact. The CE is the positive cube root of 1/M.

Positive finite binary64 bit encodings are monotone. Bisect this finite set to
find adjacent floats bracketing the root using the exact comparison x^3*M<=1.
Compare the rational midpoint cubed times M with one to choose the nearest float;
on equality choose the even significand. The rational normalization and positive
finite support keep the exact CE between the finite support extrema. This path
needs at most 63 bisection comparisons and runs only near underflow. It uses the
Python standard library and no clipping, imputation or new dependency.

This changes numeric evaluation only. Gamma=4, prior mass=15, window=5, targets,
fees, the twice-fee decision buffer, actual one-fee accounting, epsilon gates,
action/state semantics, all research-selection rules and final-data gate remain
unchanged. The source has not run on competition outcomes. A new positive remote
kernel review is required; chief synthetic tests are provisional evidence.

Independent review should challenge upward/downward exact midpoint ties, the
2048-case rational subnormal grid, n=0..5 heterogeneous prior/recent mixtures,
normal/subnormal route boundary, zero/tiny weights and accepted roundoff-sized
unit-sum discrepancies, minimum positive through maximum finite support,
ordinary scalar fixtures and genuine tiny-transfer state transitions. Reuse
unchanged scalar oracle helpers explicitly; never override historical task/hash
boundaries or relabel old results as new approval. Calibration and production
component review gates remain separate.
