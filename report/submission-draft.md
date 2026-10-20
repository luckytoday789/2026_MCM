# SafeInvest: Cost-aware decisions in purchasing power

**MANUSCRIPT FOR INDEPENDENT REVIEW**

{{LOCAL_TEAM}}

## Executive summary

SafeInvest must connect a customer's horizon, liquidity needs and willingness to bear temporary loss to an explainable investment service. We compare transparent allocations in stocks, government bonds and bills, account for trading costs before returns, and judge outcomes in purchasing power. Our decision rule trades only when its estimated utility benefit exceeds a buffered transaction-cost hurdle. Four annual actions are available: keep holdings, rebalance to the active target, change the target, or suspend automation for human review. [E0, E2]

On the accepted development comparison, using 120 scenarios, a 30-year horizon and a 0.25% one-way fee, fixed-prior Balanced has median real growth 4.53% per year, p10 growth 1.10%, median maximum real drawdown 26.84%, and p90 drawdown 41.94%. Annual equal thirds gives 3.58%, 1.28%, 20.10% and 34.84%, respectively. Balanced trades at 9.72% of reviews, versus 100.00% for annual equal thirds. These separate marginal summaries describe a growth/loss trade-off; they neither establish a paired performance improvement nor make Balanced suitable for every customer. [E1]

Development gates rejected additional contextual and adaptive complexity, so we froze fixed-prior Balanced before opening the reserved scenarios. Its role in a research comparison is separate from a client recommendation. [E3, E6]

<!-- SLOT:EXECUTIVE_RECOMMENDATION -->
On the 60 reserved scenarios, fixed Balanced has 30-year median real growth 4.03%/year and p90 drawdown 46.60%, versus 3.38%/year and 39.53% for annual thirds. It trades at 10.50% of reviews. Crucially, the Conservative rules provisionally qualified for B and C fail their own-horizon loss screens: p90 drawdowns are 26.46% against B's 25% tolerance and 40.52% against C's 40%. Both failures persist at the doubled fee. A, D and E retain their development referrals. We therefore refer all five profiles for human review, without selecting replacement classes or changing frozen rules after validation. [E8]
<!-- END_SLOT:EXECUTIVE_RECOMMENDATION -->

## 1. Problem, data and evaluation discipline

The competition provides 180 independent synthetic scenarios with 30 annual observations each. We use scenario IDs 1-120 for development and reserve 121-180 for evaluation after a recorded freeze. Independent scenarios are never concatenated into one market history. Each path starts with nominal wealth 100 entirely in bills, without deposits, withdrawals, borrowing or terminal liquidation. The three assets remain long-only and fully invested after fees. The scenarios are supplied competition inputs, not historical observations or estimated real-world probabilities. [E0]

At the start of year t, the decision sees only that scenario's completed observations through t-1 and legitimately calibrated training information. Returns and inflation for year t are applied after the decision. Four development folds are defined by scenario index modulo four; each prior uses the other 90 scenarios and their 2,700 annual rows. This pools a one-year marginal distribution while retaining each evaluation path intact. Training folds overlap, and earlier descriptive baseline findings informed the design, so cross-fitting is development validation rather than an untouched final test. [E2]

The five client horizons are A: 5 years, B: 15 years, C: 30 years, D: 25 years and E: 6 years. We evaluate each profile on its own prefix. General Balanced policy comparisons use the common 30-year horizon. Long-horizon results must not substitute for short-horizon suitability evidence. [E0]

## 2. Exact accounting and meaningful risk measures

Let h be pre-trade component holdings, W their sum, u=h/W the current weights and w the requested nonnegative target with sum one. The one-way transfer T, fee c and post-trade holdings h+ follow the disclosed pre-fee transfer convention: [E0]

T = (W/2) sum_i |w_i-u_i|; c = kT; h+ = (W-c)w.

At the primary fee k=0.0025, moving 20 monetary units costs 0.05. The factor one-half counts a transfer between two assets once. Fees are deducted before returns, including the initial allocation, and funded proportionally. The fee-funding adjustment is not charged again. A keep action preserves component dollar holdings and charges zero; it does not restore weights. Every trade must conserve W = sum_i h+_i + c. [E0]

Let CPI_0=1 and CPI_t=CPI_(t-1)(1+inflation_t). End-of-year holdings are h_end_i=h+_i(1+r_ti), and real wealth V_t=sum_i h_end_i/CPI_t. Real wealth immediately after trading uses CPI_(t-1), because the trade precedes current inflation. We use the exact real gross return (1+r)/(1+inflation), without subtracting inflation approximately. Bills can therefore lose purchasing power. [E0]

For horizon H, annualized real growth is G_H=100[(V_H/100)^(1/H)-1]. Ordinary fluctuation is the sample standard deviation of annual net real returns q_t=V_t/V_(t-1)-1, using denominator H-1. Large loss L_H is the largest percentage decline from the running real wealth peak across initial, post-fee and year-end observations. Post-fee observations capture fee-induced losses but are not additional annual return intervals. Annual data cannot identify intra-year drawdowns. [E0]

We first calculate each scenario's metrics, then report median and p10 growth and median and p90 loss, using linear scenario quantiles. The p90 is a descriptive upper quantile, neither a worst-case bound nor CVaR. A severe case maximizes observed drawdown at the stated horizon; exact ties use the smallest scenario ID, and the path scan retains the earliest maximizing peak/trough pair. The trade share is the percentage of annual reviews with transfer greater than 1e-10; we also report the share excluding initial allocation. [E0]

## 3. Menus, suitability and the four annual actions

The service has three fixed menus and two alternatives available only to the adaptive Balanced variant. Targets are service intentions; actual weights drift between trades, and initial deployment can be deferred by the same benefit hurdle as later trades. [E2]

{{MENU_TABLE}}

Horizon and liquidity first restrict the available classes. A target bill reserve is a liquidity proxy rather than a guarantee about future drifted weights or a simulation of emergency withdrawals. A short horizon admits Conservative; intermediate horizons admit Conservative or Balanced; long horizons may admit all classes subject to liquidity. The specified profiles give the following eligibility sets before outcome screens. [E2]

{{PROFILE_TABLE}}

Every eligible class must have own-horizon p90 real drawdown no greater than the stated loss tolerance and p10 real growth no less than zero. Among qualifying classes, choose the highest median growth; classes within 0.10 percentage points/year of that maximum prefer the least growth-oriented class. Record the loss-exceedance numerator and denominator alongside the quantile. An empty feasible set requires human review. A provisional class must then be rerun at its client's own suspension threshold and horizon and pass both screens again; failure refers to a human without trying a replacement class. A stated tolerance is not a guaranteed loss cap. [E2]

<!-- SLOT:PERSONALIZED_RESULTS -->
The accepted own-tolerance development rescreens support Conservative for B and C at both fees. Each row uses 120 scenarios, the stated client horizon and that client's review threshold. Growth is real percent/year; loss and trade shares are percentages. The exceedance column counts scenario losses strictly greater than the client's tolerance. [E7]

{{PERSONALIZED_TABLE}}

A, D and E have no qualifying class at either fee and remain human referrals, with zero personalized simulations and no invented outcome. High liquidity and a short horizon do not justify treating bills as safe in purchasing power. The four executed B/C cases each contain five losses beyond tolerance despite passing the p90 screen. These are development-qualified rules for reserved validation, not guarantees or unconditional investment instructions. [E6, E7]
<!-- END_SLOT:PERSONALIZED_RESULTS -->

For a distribution P of real gross-return vectors g, the one-year certainty equivalent under constant relative risk aversion four is C_P(x)=[E_P(sum_i x_i g_i)^(-3)]^(-1/3). It is homogeneous: C_P(ax)=a C_P(x) for positive a. For transfer fraction tau=(1/2)sum_i|w_i-u_i| and actual fee fraction f=k tau, a proposed target qualifies only if (1-2f)C_P(w)>C_P(u)+1e-12. The account pays f once; the factor two is a conservative decision margin. A passing target has a positive modeled net benefit under P, not a guaranteed realized gain or a multi-period optimum. [E2]

Among eligible targets, choose the greatest buffered score, with ties within 1e-12 favoring the active target, then defensive, central and growth-tilted alternatives. An ineligible target cannot inherit another target's score. Fixed-prior modes retain their fitted prior. Contextual modes combine a prior weight of 15 with up to five completed observations from the same path; adaptive alternatives become available in year six. The contextual control changes the estimate while keeping the central target, allowing the incremental effect of changing targets to be evaluated separately. [E2]

Each annual review has an explicit action. Keep preserves holdings when no target passes. Rebalance trades to the active target when it passes. Target change selects another eligible target and executes its trade. Human review overrides further automated trading once the applicable observed-loss threshold is reached. Suspension is latched: existing component holdings remain invested, subsequent returns accrue, and no further transfer or transaction fee occurs while review is pending. This retains market and inflation exposure. A loss first observed at year end can affect only a later review, including no further review within the horizon after its final year. [E2]

The generic development and final comparisons use a 25% observed-drawdown suspension threshold. This service trigger is separate from the own-tolerance follow-up required for individual clients; it does not cap losses at 25%. [E2]

## 4. Accepted development evidence

The common comparison below uses the same 120 development scenarios, 30-year horizon and 0.25% one-way fee. All rows use exact inflation deflation and include the initial allocation fee. The cost-aware rows use cross-fitted priors and the generic review trigger; the three reference policies have no human-review overlay. Growth is percent/year, loss is percent of the running real peak, and trade shares are percent of annual reviews. Display values are rounded to two decimals; full precision remains in authenticated source tables. [E1]

{{PRIMARY_H30_TABLE}}

The table shows why trading less is insufficient as a recommendation criterion. Fixed-prior Balanced has a higher marginal median growth than annual equal thirds, while its lower-growth tail is smaller and its upper-loss tail is larger. Initial-thirds buy-and-hold changes both drift and fees, so its comparison with annual rebalancing cannot isolate the causal effect of costs. The accepted descriptive levels must not be confused with medians of paired scenario differences. [E1]

For bills held, 30-year p90 real drawdown is 22.16% and the severe loss is 29.86%. Even the nominally stable reference can lose substantial purchasing power. The annual equal-thirds severe loss is 50.88%, selected in scenario 5. These finite-sample severe cases are illustrations, not bounds on future losses. [E4]

{{BALANCED_SEVERE}}

The own-horizon annual equal-thirds references below make the time-horizon distinction explicit. They are comparisons, not proposed assignments to A-E. [E4]

{{BASELINE_HORIZON_TABLE}}

Additional Balanced complexity has predeclared practical gates: median paired real-growth improvement of at least 0.10 percentage points/year; marginal p10 growth deterioration no worse than 0.10 percentage points/year; marginal p90 loss deterioration no greater than 1.00 percentage point; and a strictly positive paired median gain in at least three of four folds. Adaptive targeting must pass directly against both contextual fixed targeting and fixed-prior targeting. The contextual control's own failure does not remove it as an adaptive comparator. A zero fold gain does not count as support. These gates are decision thresholds, not significance tests. [E2]

<!-- SLOT:PROMOTION_RESULTS -->
The accepted primary analysis retains fixed-prior Balanced. Contextual estimation has zero median paired growth gain and only one positive fold. Adaptive targeting gains only 0.047 percentage points/year over its contextual control while worsening p90 loss by 2.538 points; it also has zero median paired gain over fixed-prior Balanced. Automatic target updates therefore fail the predeclared development test for added value. Fixed Balanced's 0.838-point median paired gain over annual thirds still accompanies worse marginal tails; retaining it within the research menu does not establish universal suitability. [E6]

{{PROMOTION_TABLE}}

The table uses development H=30 and k=0.0025. Growth differences are percentage points/year; loss differences are percentage points, positive meaning worse. The final three rows test added complexity. All modes and failed comparisons remain visible, and the higher-fee results cannot reselect the primary mode. [E6]
<!-- END_SLOT:PROMOTION_RESULTS -->

## 5. Transaction-cost sensitivity and customer explanation

The predeclared sensitivity doubles the one-way fee from 0.25% to 0.50% without changing calibration, targets or rule parameters. Both accounting and the cost hurdle use the changed fee, so actions can differ. Evaluate the originally selected rule at the higher fee rather than selecting a new primary rule from the sensitivity. Fee-specific suitability changes are a separate counterfactual and do not by themselves establish robustness of one fixed strategy. [E2]

<!-- SLOT:SENSITIVITY_RESULTS -->
The accepted same-mode sensitivity uses 120 development scenarios and the common 30-year horizon. Calibration and all non-fee parameters are unchanged, while actual fees and the decision hurdle both use the stated rate. The table shows the annual reference and every Balanced variant at both fees, without selecting a different primary rule. Growth is real percent/year; loss and the two action frequencies are percentages. A dash means that human-review actions are not defined for the unoverlaid annual reference. [E1, E5]

{{SENSITIVITY_H30_TABLE}}

For fixed-prior Balanced, median growth rounds to 4.53% per year at both fee rates, while the trade share falls from 9.72% to 8.33%. Median drawdown rises from 26.84% to 28.26%, and p90 drawdown rises from 41.94% to 42.02%. Fewer transactions therefore do not establish lower realized loss. Changing the cost hurdle changes decisions and holdings paths, so these summaries are not a mechanical fee subtraction from one unchanged portfolio path. [E1, E5]
<!-- END_SLOT:SENSITIVITY_RESULTS -->

<!-- SLOT:SENSITIVITY_RECOMMENDATION_IMPACT -->
The accepted choice is fixed-prior Balanced, so its two fee rows above are the relevant same-mode robustness comparison. Doubling the fee gives no evidence for promoting contextual estimation or automatic target changes and does not remove the loss-tail concern. We retained the simpler rule for reserved evaluation. The completed reserved validation below fails the client loss screens at both fees, so neither fee supports an automatic allocation for these profiles; a changed fee requires renewed suitability review. [E1, E5, E6, E8]
<!-- END_SLOT:SENSITIVITY_RECOMMENDATION_IMPACT -->

<!-- SLOT:CUSTOMER_EXPLANATION -->
We keep your holdings unless a rebalance offers an estimated benefit above our cost buffer. Losses can exceed your tolerance. Once observed loss triggers review, automatic trades stop; your existing assets remain invested while a person reviews your situation. [E2, E6]
<!-- END_SLOT:CUSTOMER_EXPLANATION -->

## 6. Freeze and reserved final evaluation

After development selection and personalized rescreens, we fitted the prior to all 3,600 development rows. An independent binary64 check verified all 10,800 real-gross support values and the nominal, gross and support hashes. The accepted freeze binds the reviewed execution source, full parameters, input hashes, metrics, contrasts, severe-case rules and the complete 121-180 evaluation shard. A separately executed closed-gate audit passed before external attestation and gate opening. Earlier pre-access metadata failures remain preserved; neither read final inputs nor changed policy. This final run was accepted once, with no final policy tuning or reranking. [E8]

<!-- SLOT:FINAL_EVALUATION -->
The following common-horizon comparison uses 60 reserved scenarios, H=30 and the primary 0.25% one-way fee. All-development calibration replaces development cross-fitting as specified before access. Growth is real percent/year; loss is percentage of the running real peak; fluctuation is annual sample standard deviation in percentage points; trade shares are percentages of reviews. [E8]

{{FINAL_H30_TABLE}}

{{FINAL_PAIRED}}

The frozen B/C Conservative follow-ups use their own horizons and loss triggers. Each row is a completed 60-scenario validation, with growth in real percent/year and losses in percent. [E8]

{{FINAL_CLIENT_TABLE}}

All four rows fail the unchanged loss screen despite positive p10 real growth, each with 7/60 losses strictly beyond tolerance. A, D and E retain upstream referrals and have no personalized final simulations. No fallback class is tried. All A-E require human review. For a prospective allocation, keep the initial bills pending review and disclose their inflation risk. For an already invested customer, suspend further automatic trades and preserve component holdings while returns and inflation continue. These are pending-review instructions, not a risk-free replacement portfolio. [E8]

The frozen same-mode Balanced fee comparison below changes the fee and corresponding cost hurdle only. The primary mode remains fixed, and both fees retain the same all-client review conclusion. Growth is percent/year; other columns are percentages. The higher fee lowers p10 growth and trading frequency without removing the loss-tail concern. [E8]

{{FINAL_SENSITIVITY_TABLE}}

{{FINAL_SEVERE}}

An independently expressed stdlib audit passed 997,883 saved-ledger, metric, paired, tail and referral checks, with maximum absolute residual 9.095e-13; three fee/CPI/real-wealth corruptions were rejected. It did not reread original final observations or independently reselect utility actions. The latter rely on separately reviewed source and authenticated production provenance. Supplemental remote review and full manuscript acceptance remain separate gates. [E8]
<!-- END_SLOT:FINAL_EVALUATION -->

## 7. Limitations, reproducibility and conclusion

The scenario design, annual sampling and empirical calibration constrain interpretation. Four-fold training overlaps; marginal pooling assumes useful common information; recent context need not predict future returns. The one-year utility criterion is not a long-horizon optimum. Liquidity screening does not simulate withdrawals or guarantee a bill reserve after drift. The p90 screen allows worse losses in some scenarios. Review occurs only at annual decision times and does not remove retained holdings' risk. These limitations must accompany any recommendation. [E0, E2]

Numerical conclusions come from executable Python outputs identified by exact producer and review commits. Fees, wealth conservation, metrics, timing boundaries and displayed values have separate checks; a worker's successful push is not result acceptance. Failed attempts and negative findings remain in the research record. The separate code supplement preserves reproducible instructions, source/data attribution, the locked configuration and exact research history; its archive size and integrity are checked separately. Private credentials, member identities and local environments are excluded. The human team leader submits the package. [E3]

<!-- SLOT:CONCLUSION -->
The cost-aware service provides explicit, auditable decisions and sharply reduces trading relative to annual rebalancing. That economy does not establish adequate downside protection. Development evidence rejected automatic target updates, and reserved evidence overturns the provisional B/C suitability qualification. We retain the frozen research result and refer all A-E for human assessment. Annual suspension freezes trading rather than wealth; inflation and market losses can continue. Deployment requires a reviewed response to the failed suitability screens, rather than a better-looking rule chosen from the exposed final scenarios. [E6, E7, E8]
<!-- END_SLOT:CONCLUSION -->

## Sources and AI-use disclosure

[E8] Accepted frozen HY3-010 final evidence: producer 4b8ac5d6822ac39ff1189c13d34ed3f84f699319; freeze 06086aed327aa626ddc91472f943c2c9fba1259a; source 7053b41ce81b1e04100d56a24a321e51b3465459. report/final-evaluation-provenance.json binds the exact summary, client, paired and same-path rows. audit/chief/HY3-010-review.json records the actual independent saved-ledger audit; refit acceptance and closed-gate attestation are preserved in the linked freeze history. No source result was rerun for writing.

[E7] Exact accepted CHIEF-PERSONALIZED-RUN-002 outcomes: producer b334b27a2f9fb8df99a6dee611e298bd0dc867d3; chief acceptance audit/chief/CHIEF-PERSONALIZED-RUN-002-review.json records 197524 independent scalar comparisons and 1200 prefix checks. Four own-horizon cases and six upstream referrals are preserved; utility choices rely on the separately accepted implementation.

[E6] Exact accepted HY3-009 development analysis: producer 680c2faaf603df975c35e828aeebdadd8ce242cb; chief acceptance audit/chief/HY3-009-review.json independently checks all 100 gates, 30 screens and 10 provisional choices with 790 scalar comparisons. No final outcomes enter this selection.

[E0] Competition problem and locked conventions: specs/PROBLEM_LOCK.md and specs/ACCOUNTING.md; methods-draft.md. The supplied scenarios are synthetic competition inputs. The project source manifest records CC BY-NC-SA 4.0 attribution based on JST Macrohistory release 6; preserve the supplied attribution in the code supplement.

[E1] Accepted HY3-004 primary development summaries: producer 6aa2ccdce80834c8beb52a827993f1f587d1d8a6, independent review a9073e1d0ab5aadea639daf34ba76fab728d636f; report/primary-development-provenance.json binds each mode/horizon row and chief acceptances.

[E2] Reviewed menu, benefit gate and evaluation design: report/policy-catalogue.md, report/policy-methods-draft.md and specs/development_policy_pilot_v2.json. These sources define methods and thresholds; empirical claims require accepted result evidence.

[E3] Writing coverage, independent acceptance and completion gates: report/evidence-map.json, ops/PROTOCOL.md and chief acceptance records. report/submission-status.json records the draft's actual unresolved slots and source mappings.

[E4] Accepted HY3-003 baseline summaries: producer 7652410d73425371110784ef5fa97c03470a074e, independent review 818af5d65bd8a271962d848dd552bd39ca561f68; report/baseline-development-provenance.json preserves source rows and display provenance.

[E5] Accepted HY3-006 doubled-fee results: producer 319781ef3c7fb5d4328a0ae4cea438bcc26a6f18; fresh HY3-007 verification at 194a45ac5fced5dfab02903e4e732b1cac1c6e67. Chief acceptance is recorded in audit/chief/HY3-006-review.json and audit/chief/CHIEF-HY3-006-20261020-review.json. The latter records actual execution of earlier Sol and chief numerical checks, with their sampling limitations; the failed original Sol task is not accepted retrospectively.

GPT-6 Astra xhigh, followed by GPT-6.1 Sol xhigh in Codex, coordinated specifications, integration, numerical checks and drafting. GPT-6.1 Sol xhigh on a separate computer implemented and independently reviewed assigned components. HY3 in WorkBuddy supervised fixed Python computations on a third computer. AI text and task completion labels were not treated as numerical verification. Human team members are responsible for the submitted work, interpretation and final checks.
