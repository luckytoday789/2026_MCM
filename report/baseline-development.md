# Accepted development baseline evidence

This research note uses 120 original synthetic scenarios (IDs 1–120), with annual simple returns and initial wealth 100 in bills. It reports three predeclared references at five horizons. It is descriptive development evidence, not a final test, a suitability assignment, or evidence that automatic target changes add value.

The one-way transfer fee is 0.25%, including initial allocation, paid before annual returns. Purchasing power uses exact compounded inflation. Each horizon uses its own prefix. A/B/C/D/E have horizons 5/15/30/25/6; the general policy comparison uses 30 years.

Annual thirds restores equal weights at every annual review. Initial thirds held pays for its initial allocation, then keeps component dollars at reviews while returns change their values. Bills held never transfers. No reference has a human-review overlay.

Growth is real CAGR (% per year). Loss is maximum decline from the running real wealth peak (%), including initial wealth and post-fee observations. The p10 and p90 are linear scenario quantiles, not confidence bounds. All display values below are rounded to two decimals; source values retain full precision.

| Horizon | Reference | Median growth | p10 growth | Median loss | p90 loss | Trades incl. initial (%) | Trades later (%) |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | Bills held | 1.51 | -1.19 | 3.67 | 10.76 | 0.00 | 0.00 |
| 5 | Annual thirds | 3.68 | -1.87 | 7.31 | 19.32 | 100.00 | 100.00 |
| 5 | Initial thirds held | 3.56 | -1.76 | 7.69 | 20.36 | 20.00 | 0.00 |
| 6 | Bills held | 1.34 | -0.80 | 4.66 | 11.32 | 0.00 | 0.00 |
| 6 | Annual thirds | 3.52 | -2.24 | 8.90 | 21.96 | 100.00 | 100.00 |
| 6 | Initial thirds held | 3.30 | -2.44 | 9.63 | 23.86 | 16.67 | 0.00 |
| 15 | Bills held | 1.07 | -0.36 | 9.26 | 18.03 | 0.00 | 0.00 |
| 15 | Annual thirds | 3.61 | 0.15 | 15.20 | 27.67 | 100.00 | 100.00 |
| 15 | Initial thirds held | 3.91 | -0.04 | 18.37 | 30.34 | 6.67 | 0.00 |
| 25 | Bills held | 1.14 | 0.30 | 11.91 | 22.16 | 0.00 | 0.00 |
| 25 | Annual thirds | 3.85 | 1.16 | 19.02 | 33.93 | 100.00 | 100.00 |
| 25 | Initial thirds held | 4.37 | 0.79 | 24.94 | 38.36 | 4.00 | 0.00 |
| 30 | Bills held | 1.34 | 0.17 | 12.29 | 22.16 | 0.00 | 0.00 |
| 30 | Annual thirds | 3.58 | 1.28 | 20.10 | 34.84 | 100.00 | 100.00 |
| 30 | Initial thirds held | 4.21 | 1.02 | 28.75 | 44.01 | 3.33 | 0.00 |

Ordinary fluctuation is the sample standard deviation of annual net real wealth returns (percentage points, ddof=1). Each severe case below is that reference’s own largest loss at that horizon, with the prescribed exact tie rule. The same scenario number across references does not imply equal paths or peak/trough locations.

| Horizon | Reference | Median fluctuation | Median fee sum (nominal) | Severe scenario | Severe loss (%) | Real peak (year, stage) | Real trough (year, stage) |
| ---: | --- | ---: | ---: | ---: | ---: | --- | --- |
| 5 | Bills held | 3.74 | 0.00 | 46 | 25.18 | 0, initial | 5, end |
| 5 | Annual thirds | 7.28 | 0.21 | 20 | 30.44 | 2, end | 5, end |
| 5 | Initial thirds held | 7.49 | 0.17 | 109 | 29.23 | 2, end | 4, end |
| 6 | Bills held | 3.76 | 0.00 | 46 | 25.18 | 0, initial | 5, end |
| 6 | Annual thirds | 7.55 | 0.22 | 20 | 30.46 | 2, end | 6, post_fee |
| 6 | Initial thirds held | 7.54 | 0.17 | 109 | 29.23 | 2, end | 4, end |
| 15 | Bills held | 4.06 | 0.00 | 36 | 28.67 | 1, end | 14, end |
| 15 | Annual thirds | 7.87 | 0.38 | 5 | 50.88 | 1, end | 8, post_fee |
| 15 | Initial thirds held | 9.11 | 0.17 | 5 | 45.58 | 1, end | 8, end |
| 25 | Bills held | 4.07 | 0.00 | 19 | 29.03 | 13, end | 18, end |
| 25 | Annual thirds | 7.85 | 0.68 | 5 | 50.88 | 1, end | 8, post_fee |
| 25 | Initial thirds held | 9.79 | 0.17 | 29 | 66.93 | 17, end | 23, end |
| 30 | Bills held | 4.06 | 0.00 | 42 | 29.86 | 20, end | 27, end |
| 30 | Annual thirds | 8.03 | 0.95 | 5 | 50.88 | 1, end | 8, post_fee |
| 30 | Initial thirds held | 10.39 | 0.17 | 29 | 66.93 | 17, end | 23, end |

At 30 years, annual thirds has median real growth 3.58% and p90 loss 34.84%; initial thirds held has 4.21% and 44.01%, respectively. Their comparison changes both allocation drift and fees, so it does not isolate a causal fee effect. Differences of marginal medians are not median paired differences; the accepted paired_differences.csv retains all 1,200 scenario/horizon contrasts.

Bills held has a 30-year p90 real loss of 22.16% and a severe loss of 29.86%. Keeping nominal bills therefore does not eliminate purchasing-power loss in these supplied scenarios. These observations alone do not establish which menu suits any customer.

All-development baseline summaries were viewed before the policy pilot design. Later four-fold policy experiments remain development evidence, even though each fitted prior excludes its evaluated fold. No new policy has yet produced accepted outcomes. Scenarios 121–180 remain closed until the recorded final freeze.

Source: `results/development/HY3-003/summary.csv` at `7652410d73425371110784ef5fa97c03470a074e`, SHA256 `965c3ac513f63de31830603ab968f5c6e99c6ceb763515b99753282d8c3a4994`. Independent review: SOL-008 at `818af5d65bd8a271962d848dd552bd39ca561f68`; chief acceptance: `audit/chief/HY3-003-review.json` and `audit/chief/SOL-008-review.json`. This note imports existing accepted artifacts and does not rerun the experiment.
