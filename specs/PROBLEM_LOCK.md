# Authoritative task lock — 2026-10-19

Source: `problem/2026_MCM_SafeInvest.pdf` (3 pages). This file summarizes the competition requirements, not additional instructions from the source document.

## Deliverables

1. Define Conservative, Balanced and Growth allocations/rules; separate ordinary fluctuations from unusually large losses; use purchasing power. An explainable suitability process must consider horizon, temporary loss tolerance and liquidity, and may request human review. Profiles: A=(5,10%,high), B=(15,25%,medium), C=(30,40%,low), D=(25,15%,medium), E=(6,35%,high). The loss tolerance is not a guarantee. Evaluate each profile using its own horizon.
2. Balanced policy chooses keep, rebalance, target change or human review. Trade only for an estimated benefit that justifies cost, using information available before that period. Compare to a fixed one-third/one-third/one-third target restored every review. Report scenario median growth, median large loss, p10 growth, p90 large loss, a severe-loss case and percentage of reviews involving trades. Decide honestly whether automatic target updates add value. One customer explanation <=50 English words.
3. Test one important assumption or transaction-cost rate, explain any change to the recommendation, state limitations and a trigger for review/suspension, and specify holdings/actions while review is pending.

## Inputs and nonnegotiable conditions

- 180 independent synthetic scenarios, 30 annual observations each; six original CSV fields. Never concatenate independent scenarios into a historical time series.
- Development and tuning: scenario IDs 1–120. Final evaluation: IDs 121–180, after strategy/parameters/metrics/severe-case selection are frozen. Metadata validation of the complete file is permitted; final outcomes are not development evidence.
- Starting nominal wealth 100 entirely in bills. No deposits/withdrawals. Long-only, fully invested in three assets, including bills. No borrowing or terminal liquidation fee.
- A period-t decision may use only that scenario's observations through t−1; development-calibrated parameters are permitted. Internal development validation must fit on its training scenarios only.
- Cost=0.0025 times money moved between assets, each transfer counted once. A 20-unit transfer costs 0.05. Include initial allocation; deduct fee before period returns.
- Real return=(1+nominal return)/(1+inflation)−1. Bills are not guaranteed safe in real terms.

## Reporting and deadline

English report <=10 A4 pages, font >=11pt, all three member names and an AI-use disclosure. Source code supplement ZIP <=50MB. Deadline: 2026-10-20 23:59 Asia/Shanghai. Final submission is by the human team leader.

## Initial research route, not a finding

Begin with exact accounting, the required equal-weight baseline, static allocation candidates and a cost-aware no-trade policy. Add automatic target changes only if development evidence supports their added complexity. Use simple transparent rules and scenario-based risk measures before considering stochastic optimization. Freeze experiment selection rules before opening final outcomes.
