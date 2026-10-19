# Reviewed policy menus and profile screens - working text

These tables reproduce the independently approved v2 design. The percentages are target allocations and service rules, not observed returns, guaranteed holdings, accepted customer assignments or authorization to invest. No competition outcome file is used to generate this note.

| Target | Equity (%) | Bonds (%) | Bills (%) | Role |
| --- | ---: | ---: | ---: | --- |
| Conservative | 15 | 20 | 65 | Fixed menu |
| Balanced | 33 1/3 | 33 1/3 | 33 1/3 | Fixed menu |
| Growth | 60 | 30 | 10 | Fixed menu |
| Balanced defensive alternative | 20 | 25 | 55 | Adaptive Balanced alternative from year six |
| Balanced growth alternative | 45 | 30 | 25 | Adaptive Balanced alternative from year six |

Balanced keeps the central target in fixed-prior and contextual modes. The contextual mode changes its return estimate without changing the menu. The adaptive mode may consider its two alternatives after five completed annual observations. All new modes apply the same benefit gate to initial allocation and subsequent trades; a target is not a promise of immediate deployment. Actual weights can drift between accepted trades.

| Profile | Own horizon (years) | Stated temporary loss tolerance (%) | Liquidity | Required target bills (%) | Classes before outcome screens |
| --- | ---: | ---: | --- | ---: | --- |
| A | 5 | 10 | high | 60 | Conservative |
| B | 15 | 25 | medium | 25 | Conservative, Balanced |
| C | 30 | 40 | low | 10 | Conservative, Balanced, Growth |
| D | 25 | 15 | medium | 25 | Conservative, Balanced |
| E | 6 | 35 | high | 60 | Conservative |

Horizon caps are Conservative for at most six years, Conservative or Balanced for seven to nineteen years, and all three for at least twenty years. The target bill reserve is a liquidity proxy: it neither models withdrawals nor guarantees a minimum realized bill weight after drift. Profile D illustrates why a long horizon alone does not admit Growth; its medium-liquidity reserve removes that menu.

Each listed class still needs p90 real drawdown at the own horizon no greater than the stated tolerance and p10 real CAGR no less than zero. Among qualifying classes, use the highest median real CAGR; classes within 0.10 percentage points/year of that maximum prefer the least growth-oriented menu. These comparisons are inclusive. If none qualifies, refer to a human. Record loss exceedances as well as the quantile; passing a p90 screen is not a loss guarantee.

A provisional class must then be evaluated at the profile's own tolerance and horizon, with the target and benefit rule unchanged. Both risk and purchasing-power screens must pass again. Failure refers to a human without trying a replacement class. The entries above are therefore eligibility sets, not recommendations.

## Predeclared test of additional Balanced complexity

The primary comparison uses 30 years and a 0.25% one-way transfer fee. All four gates below must hold for each required direct comparison. Numeric equality passes the thresholds; a zero fold median is not a positive gain.

| Gate | Statistic and threshold |
| --- | --- |
| Typical gain | Median of scenario-paired real CAGR differences >= 0.10 pp/year |
| Lower growth tail | Candidate marginal p10 growth minus reference marginal p10 growth >= -0.10 pp/year |
| Upper loss tail | Candidate marginal p90 loss minus reference marginal p90 loss <= 1.00 percentage points |
| Fold support | Strictly positive paired median growth gain in at least 3 of 4 folds |

Contextual fixed targeting is compared directly with fixed-prior Balanced. Adaptive targeting must pass directly against both of those controls, even if the contextual rule does not itself qualify. Choose qualifying adaptive first, then qualifying contextual, otherwise retain fixed-prior Balanced as the comparison default. A comparison default is not a customer endorsement. These practical thresholds are not significance tests.

The sensitivity fee is 0.50%, with identical priors, targets and rule parameters; both actual fees and the cost gate use that rate, so actions may differ. Assess the primary rule at the higher cost without choosing a new primary rule. Fee-specific profile assignments remain a separate suitability question.

Source: specs/development_policy_pilot_v2.json at 1908813ef2627ca6e15591278ec15ccf2f9e9cff, SHA256 d7b20f38196831befc80dfdcc69c6653d1ae8352d1c87c79e19bcc09d5c84df3. Corrected design acceptance: audit/chief/SOL-013-review.json. Its historical negative kernel verdict remains preserved; subsequent kernel and calibration approvals do not supply policy outcome evidence. Reproduce read-only with `python -B report/build_policy_catalogue.py --check`.
