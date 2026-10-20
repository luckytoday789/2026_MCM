# Accepted primary development summaries

Incomplete report evidence note. All eight predeclared modes and all five horizons are shown; this table does not select a mode, assign a customer, test a promotion rule, or report final outcomes. Comparison assembly and the independent doubled-fee review remain separate gates.

Inputs are the 120 original independent synthetic scenarios 1–120. Each horizon uses its own prefix; the common Balanced comparison horizon is 30 years. Cost-aware priors use the accepted four-fold scenario split with 90 training scenarios and all 2,700 annual training rows per fold. Fixed references are authenticated imports from accepted HY3-003. The actual one-way fee is 0.25%, including initial allocation, before annual simple returns; inflation is compounded exactly.

Growth is net real CAGR (%/year). Loss is maximum real drawdown (%), including initial and post-fee wealth. Fluctuation is the sample standard deviation of annual net real wealth returns (percentage points, ddof=1). Trade shares count reviews with transfer >1e-10. Linear p10/p90 scenario quantiles are descriptive, not guaranteed bounds. Display uses Python binary64 fixed-point rounding to two decimals; full source strings remain in provenance.

| H | Mode | Median growth | p10 growth | Median loss | p90 loss | Median fluctuation | Trades incl. initial (%) | Trades later (%) |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | bills_keep | 1.51 | -1.19 | 3.67 | 10.76 | 3.74 | 0.00 | 0.00 |
| 5 | equal_weight_annual | 3.68 | -1.87 | 7.31 | 19.32 | 7.28 | 100.00 | 100.00 |
| 5 | equal_weight_buy_hold | 3.56 | -1.76 | 7.69 | 20.36 | 7.49 | 20.00 | 0.00 |
| 5 | conservative_cost | 2.70 | -1.03 | 4.78 | 12.81 | 5.03 | 35.67 | 19.58 |
| 5 | balanced_cost | 3.62 | -1.86 | 7.74 | 20.41 | 7.59 | 34.50 | 18.12 |
| 5 | growth_cost | 4.99 | -2.66 | 11.47 | 26.29 | 10.64 | 62.17 | 52.71 |
| 5 | balanced_context | 3.65 | -1.77 | 7.69 | 20.62 | 7.54 | 27.33 | 9.17 |
| 5 | balanced_adaptive | 3.65 | -1.77 | 7.69 | 20.62 | 7.54 | 27.33 | 9.17 |
| 6 | bills_keep | 1.34 | -0.80 | 4.66 | 11.32 | 3.76 | 0.00 | 0.00 |
| 6 | equal_weight_annual | 3.52 | -2.24 | 8.90 | 21.96 | 7.55 | 100.00 | 100.00 |
| 6 | equal_weight_buy_hold | 3.30 | -2.44 | 9.63 | 23.86 | 7.54 | 16.67 | 0.00 |
| 6 | conservative_cost | 2.53 | -0.90 | 6.50 | 14.67 | 5.37 | 30.97 | 17.17 |
| 6 | balanced_cost | 3.34 | -2.42 | 9.66 | 23.83 | 7.74 | 30.00 | 16.00 |
| 6 | growth_cost | 4.84 | -2.74 | 13.42 | 32.06 | 10.76 | 58.47 | 50.17 |
| 6 | balanced_context | 3.34 | -2.44 | 9.66 | 23.65 | 7.60 | 23.33 | 8.00 |
| 6 | balanced_adaptive | 3.37 | -2.45 | 9.76 | 23.65 | 7.64 | 29.72 | 15.67 |
| 15 | bills_keep | 1.07 | -0.36 | 9.26 | 18.03 | 4.06 | 0.00 | 0.00 |
| 15 | equal_weight_annual | 3.61 | 0.15 | 15.20 | 27.67 | 7.87 | 100.00 | 100.00 |
| 15 | equal_weight_buy_hold | 3.91 | -0.04 | 18.37 | 30.34 | 9.11 | 6.67 | 0.00 |
| 15 | conservative_cost | 2.66 | 0.23 | 12.82 | 21.76 | 6.13 | 15.22 | 9.17 |
| 15 | balanced_cost | 4.14 | -0.02 | 17.85 | 30.91 | 9.23 | 14.44 | 8.33 |
| 15 | growth_cost | 5.00 | -0.17 | 21.67 | 37.14 | 11.50 | 47.22 | 43.45 |
| 15 | balanced_context | 3.99 | -0.09 | 18.76 | 30.34 | 9.20 | 11.22 | 4.88 |
| 15 | balanced_adaptive | 4.14 | -0.09 | 19.49 | 30.30 | 9.47 | 17.00 | 11.07 |
| 25 | bills_keep | 1.14 | 0.30 | 11.91 | 22.16 | 4.07 | 0.00 | 0.00 |
| 25 | equal_weight_annual | 3.85 | 1.16 | 19.02 | 33.93 | 7.85 | 100.00 | 100.00 |
| 25 | equal_weight_buy_hold | 4.37 | 0.79 | 24.94 | 38.36 | 9.79 | 4.00 | 0.00 |
| 25 | conservative_cost | 3.31 | 0.83 | 18.23 | 29.54 | 7.19 | 9.63 | 5.87 |
| 25 | balanced_cost | 4.79 | 0.86 | 24.28 | 38.30 | 9.80 | 10.63 | 6.91 |
| 25 | growth_cost | 5.25 | 1.23 | 27.27 | 43.63 | 11.35 | 39.30 | 36.77 |
| 25 | balanced_context | 4.43 | 0.84 | 24.64 | 37.48 | 9.77 | 8.40 | 4.58 |
| 25 | balanced_adaptive | 4.55 | 0.86 | 25.08 | 38.19 | 10.04 | 14.27 | 10.69 |
| 30 | bills_keep | 1.34 | 0.17 | 12.29 | 22.16 | 4.06 | 0.00 | 0.00 |
| 30 | equal_weight_annual | 3.58 | 1.28 | 20.10 | 34.84 | 8.03 | 100.00 | 100.00 |
| 30 | equal_weight_buy_hold | 4.21 | 1.02 | 28.75 | 44.01 | 10.39 | 3.33 | 0.00 |
| 30 | conservative_cost | 3.13 | 0.86 | 20.56 | 33.54 | 7.51 | 8.19 | 5.03 |
| 30 | balanced_cost | 4.53 | 1.10 | 26.84 | 41.94 | 9.92 | 9.72 | 6.61 |
| 30 | growth_cost | 4.83 | 1.51 | 30.04 | 45.86 | 11.63 | 35.81 | 33.59 |
| 30 | balanced_context | 4.15 | 1.22 | 26.51 | 40.15 | 9.78 | 7.64 | 4.45 |
| 30 | balanced_adaptive | 4.14 | 1.12 | 26.86 | 42.69 | 9.97 | 13.22 | 10.23 |

The generic human-review threshold is 25% for all five cost-aware modes in these runs. These generic results cannot establish suitability at a client’s own tolerance. The original failures, sampled independent CRRA rescoring limits and required personalized rescreens remain disclosed in the exact acceptance evidence. No customer recommendation follows from this note.

Producer: `6aa2ccdce80834c8beb52a827993f1f587d1d8a6`; independent review: `a9073e1d0ab5aadea639daf34ba76fab728d636f`. See `audit/chief/HY3-004-review.json` and `audit/chief/SOL-040-review.json`. Source regeneration reads accepted Git summary blobs only; it neither simulates nor reads final data.
