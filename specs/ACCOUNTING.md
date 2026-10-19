# Accounting and metric contract v1

This fixes a disclosed modeling convention where the problem leaves fee payment details unspecified. Sol must review this convention before reporting a correct implementation; disagreements go to the coordinator rather than silent changes.

Let pre-trade holdings h>=0, W=sum(h), current weights u=h/W, and desired target w>=0 with sum(w)=1. For a target rebalance, measure the intended transfer on pre-fee wealth: T=(W/2)*sum(abs(w-u)), c=k*T. Charge c before returns and allocate remaining wealth proportionally to target: h_plus=(W-c)*w. This is a pre-fee transfer convention with pro-rata fee funding. The tiny fee-funding adjustment is not charged again. It keeps the target exact after fees and avoids double counting. Record intended transferred amount, fee, post-fee holdings and wealth explicitly.

Examples at k=0.0025 and h=(0,0,100):
- Keep bills: T=0, c=0, W_plus=100.
- Target (0.2,0,0.8): T=20, c=0.05, h_plus=(19.99,0,79.96).
- Equal weight: T=200/3, c=1/6, W_plus=599/6; each holding=599/18.
- All equity: T=100, c=0.25, h_plus=(99.75,0,0).

If action=keep, preserve dollar holdings exactly and charge zero. The equal-weight baseline requests target (1/3,1/3,1/3) in every period including period 1. Even a review can produce T=0 if holdings already match.

Then h_end,i=h_plus,i*(1+r_t,i). CPI_t=CPI_(t−1)*(1+inflation_t), CPI_0=1. Real wealth at trade is sum(h_plus)/CPI_(t−1), at year end=sum(h_end)/CPI_t. A decision object must be created before accessing r_t or inflation_t.

For horizon H, growth=100*((real_W_H/100)^(1/H)−1), in percentage points per year. Ordinary fluctuation=sample standard deviation of annual net real wealth returns in percentage points (ddof=1; H>=2). Large loss=100*max_t(1−real_W_t/running_peak), including initial wealth and both post-fee and year-end wealth observations. Larger means worse; minimum zero. Quantiles across independent scenarios use linear interpolation. Never confuse p90 loss with a guaranteed bound or CVaR.

Trade share=100*number(T>1e−10)/number(review periods), including the initial review; additionally report the share excluding initial allocation. Every result records horizon, units and split. Profile horizons are 5,15,30,25,6 respectively. Initial policy comparison uses the common 30-year market horizon; report this explicitly.

Mandatory invariants: nonnegative finite holdings, fully invested after fees, W=W_plus+c, no fee on keep, fees precede returns, exact compounded inflation, initial wealth in drawdown peak, and future-data perturbations leave earlier decisions unchanged. Solver tolerance must be documented; accounting comparisons use abs tolerance 1e−9 on toy fixtures and relative tolerance 1e−10 on ordinary-sized ledgers.
