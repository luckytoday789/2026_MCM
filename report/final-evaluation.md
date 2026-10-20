# Accepted frozen final evaluation

One frozen evaluation used scenarios121-180,60 independent paths and a common all3600-development-row prior. Source7053b41ce81b1e04100d56a24a321e51b3465459; accepted freeze06086aed327aa626ddc91472f943c2c9fba1259a. Actual closed-gate audit and external attestation precede the gate opening. Both pre-access metadata failures are preserved; neither opened final data or changed policy. Exact final producer: 4b8ac5d6822ac39ff1189c13d34ed3f84f699319; acceptance: audit/chief/HY3-010-review.json. No final tuning or policy reranking occurred.

## Common30-year primary-fee comparison

Fee0.25%; growth percent/year; loss percentages; fluctuation annual sample standard deviation in percentage points; trades percentage of reviews. All values are from the same60 scenarios. The frozen reporting mode remains Balanced fixed.

| Mode | Median G | p10 G | Median L | p90 L | Fluct. | Trades all | Trades later |
| --- | --- | --- | --- | --- | --- | --- | --- |
| bills_keep | 1.01 | 0.12 | 14.79 | 22.77 | 4.05 | 0.00 | 0.00 |
| equal_weight_annual | 3.38 | 1.50 | 22.30 | 39.53 | 8.24 | 100.00 | 100.00 |
| equal_weight_buy_hold | 3.65 | 1.05 | 29.94 | 52.53 | 10.76 | 3.33 | 0.00 |
| conservative_cost | 2.74 | 0.86 | 22.54 | 39.30 | 7.90 | 7.67 | 4.48 |
| balanced_cost | 4.03 | 1.52 | 27.48 | 46.60 | 10.05 | 10.50 | 7.41 |
| growth_cost | 4.59 | 1.53 | 32.91 | 51.80 | 12.15 | 34.06 | 31.78 |
| balanced_context | 3.59 | 1.05 | 28.53 | 47.13 | 10.17 | 7.11 | 3.91 |
| balanced_adaptive | 3.75 | 1.00 | 28.74 | 44.80 | 10.37 | 12.33 | 9.31 |

The median paired Balanced-minus-annual-thirds growth difference is 0.814 percentage points/year. Marginal p10-growth difference is 0.022 points/year and marginal p90-loss difference is 7.073 points. These are different statistics; final diagnostics do not reopen model selection.

## Own-horizon frozen customer validation

| Profile/H | Fee % | Tolerance | p90 L | p10 G | Loss > tol. | Med L | Severe L |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B/15 | 0.25 | 25 | 26.46 | 0.21 | 7/60 | 12.45 | 46.36 |
| B/15 | 0.50 | 25 | 26.47 | 0.20 | 7/60 | 12.49 | 46.37 |
| C/30 | 0.25 | 40 | 40.52 | 0.86 | 7/60 | 22.54 | 54.71 |
| C/30 | 0.50 | 40 | 40.52 | 0.86 | 7/60 | 22.54 | 54.71 |

All five profiles require human review. A,D,E retain development referrals, with zero personalized simulations. B,C fail the unchanged final loss screen at both fees even though p10 real growth remains positive: their p90 losses exceed25% and40%,respectively. Each executed case exceeds tolerance in7/60 scenarios. No replacement class is selected. The development-qualified recommendation therefore does not survive reserved validation. Existing invested customers retain component dollar holdings with automation suspended; prospective allocations remain in initial bills pending review, with explicit inflation risk.

## Same-mode fee sensitivity

| Fee % | Median G | p10 G | p90 L | Trades all | Trades later |
| --- | --- | --- | --- | --- | --- |
| 0.25 | 4.03 | 1.52 | 46.60 | 10.50 | 7.41 |
| 0.50 | 4.03 | 1.14 | 46.60 | 8.06 | 4.89 |

The higher fee does not rescue suitability or justify a new primary choice. Final customers' p10 growth remains positive but p90 loss fails at both fees; this is a negative robustness finding.

## Severe path and verification limits

Balanced's own severe scenario is172: loss62.44%,real CAGR2.17%/year,terminal real wealth190.50. Its peak is year13(end) and trough year27(end). Annual thirds on that same path loses44.17%,grows2.58%/year and ends at214.83. Annual thirds has its own separate worst scenario155 with loss57.81%; do not confuse these severe-case definitions.

The independent stdlib oracle recomputed997883 saved-ledger,metric,tail,paired and referral checks; maximum absolute residual was9.095e-13. Three fee/CPI/real-wealth corruptions were rejected. It did not reread original final observations or independently reselect utility actions; separate reviewed source and exact producer hashes support those boundaries. Supplemental remote review and full manuscript/layout/package acceptance remain pending. Humans submit.
