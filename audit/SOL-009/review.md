# SOL-009 independent design review

Design verdict: **changes_required**. The gamma=4 CE derivation, actual-fee accounting and buffered sufficient trade condition are mathematically sound. Resolve D1 (tie/gate order) and D2 (selection statistics and explicit adaptive comparators) before issuing implementation work. These are specification blockers, not a failed evidence audit. Detailed section/key edits are in findings.json; verification.json independently records expected and observed arithmetic.

Scope: review exactly specs/DEVELOPMENT_POLICY_PILOT.md and specs/development_policy_pilot_v1.json at a996298fd22b11dc54deb43cb596f143da05bf93, validated unchanged at task base 2561688380d9e2527eb6066100adde70b7d0ea1c. SOL-007 at cf5e70860e7aac615775fe96b0c1696a9fc5226b remains an unsuccessful quota attempt; this does not recreate an accepted review. SOL-008/HY3-003 numerical acceptance is independent. No competition numerical input, strategy outcome, final data, previous broad suite or production policy is needed or used.

| Exact canonical git blob | SHA256 |
| --- | --- |
| specs/DEVELOPMENT_POLICY_PILOT.md | 94e436a979f2c232b729c352d209c83c76ba014a14613852ad447446cb6948e0 |
| specs/development_policy_pilot_v1.json | 39ab8f78f6e4c487d00c1055e6d474c51a2d940e3cad951768a6c75874cc835a |
| audit/chief/policy_design_fixtures.py | c3b4b907cfb9b179faae717a09067ee45862b13bf9e56d06e28a841ab43fff3b |
| audit/chief/policy-design-fixtures.json | 55108ba36593f3f342cff4be6be01fac7c77af6f74baabf787c04b9db684f10c |
| specs/ACCOUNTING.md | a9c3ab8dbba3ad752336642061ead272e2c196de83f73eb410e39bd5b559f71e |
| specs/PROBLEM_LOCK.md | 566c93ad1b5f79c9ec10a42725ab023953c9a02aeb1c91a459e740caf68c0e46 |

Hash checks read original/base git objects and the checkout. Checkout comparison allows CRLF to LF only; no whitespace stripping. The original and new base blobs must match exactly. Chief fixtures are read as evidence, never executed or imported. The independent verifier uses standard-library rational arithmetic, a 70-digit Decimal oracle and a separate log-moment CE computation, with absolute/relative tolerance 1e-12. Chief's recorded floating residuals are informational, not last-bit portability requirements.

## Independent derivation and synthetic facts

For wealth z>0, U(z)=z^(1-gamma)/(1-gamma). At gamma=4, U(z)=-1/(3z^3), U'(z)=z^-4>0 and U''(z)=-4z^-5<0, so relative risk aversion is -zU''/U'=4. If G_x=sum_i x_i g_i, equating U(CE)=E[U(G_x)] gives CE=(E[G_x^-3])^(-1/3). The negative outer exponent is required: reducing the inverse-cube moment increases CE. For any a>0, CE(a*x)=a*CE(x), even though a*x is not a normalized portfolio; it represents scaled wealth exposure. Common starting real wealth factors out of both alternatives.

Let A=CE(w)>0, B=CE(u), f=k*tau. The actual post-fee portfolio factor is (1-f)A; the score is (1-2f)A. If score>B+epsilon, then actual modeled net advantage=(1-f)A-B=(score-B)+f*A>epsilon+f*A>0. Equivalently, the pre-cost benefit A-B exceeds 2fA+epsilon. This is sufficient under the same modeled distribution, not a guarantee about realized returns. At declared costs f<=0.005, fee scaling is positive. The factor two changes the hurdle only; charging two actual fees would violate ACCOUNTING.md.

At initial h=(0,0,100), equal thirds imply tau=2/3, T=200/3, c=1/6, post-fee wealth599/6 and each holding599/18. For deterministic gross factors(11/10,51/50,1), target CE=26/25, buffered score3887/3750, actual net CE7787/7500 and terminal wealth7787/75. With inflation2%, that terminal purchasing power is15574/153. Separately, exact real gross from10% nominal and2% inflation is55/51; subtraction is incorrect. verification.json records these rational expectations and observed calculations, including chief fixture comparisons.

Equal returns make a positive-transfer target strictly worse after fees; the investor remains in bills if initial allocation is rejected. Zero-fee equal scores also keep. Keep preserves dollars and charges zero. Recent five masses receive1/20 each and the prior receives15/20, divided among2700 rows, not15 selected training rows. Positive homogeneity and actual modeled fee loss are checked on a nonconstant two-point prior plus five recent observations.

D1 is a real edge ambiguity: with keep score1, active score1+0.75epsilon and defensive score1+1.5epsilon, priority among approximate target ties can pick active below the keep hurdle, while filtering eligible targets first picks defensive and trades. Approximate equality is also nontransitive. Specify eligible-first, ties within epsilon of the eligible maximum, and a final strict hurdle check. No silent parameter change is proposed.

## Information boundary, actions and suspension

Each evaluation fold has30 scenarios, its prior uses only the other90 and2700 annual observations. No fitted feature/threshold or support may see the held-out fold. Synthetic ID-marker perturbations verify the exclusion arithmetic; this is not a production no-lookahead test. Full other-scenario paths are permitted calibration data under the independence premise, not contemporaneous forecasts. Contextual modes must share the same distribution at the same prefix, while their wealth, active targets and latches can differ.

Use n=min(5,t-1), with adaptive alternatives first available at review6; no current return or inflation is visible. The active target starts central, remains central if deployment is deferred, and changes only on an accepted executed target request. Fixed modes never consider other targets. Adaptive uses defensive/central/growth-tilted only after the history gate. A failed proposal must not update state. Log year1 deferred allocation, per-review reason, first deployment year and before/after active targets, rather than inferring deployment from any later keep. Tiny requests require exact accounting; T<=1e-10 is a reporting threshold, not permission to erase fees. Clarify these schema/state conventions as L7 requests.

The25% threshold is a normative generic research overlay. Observe maximum real drawdown through t-1, including initial100 and previous post-fee and year-end values. If year1 ends at75, year2 latches; recovery to120 cannot undo the observed maximum or latch. A previous fee-induced trough74 followed by recovery110 still means26% drawdown. While pending, keep component dollars at each review, charge zero, retain active target and never simulate a human restart. Dollars then change with asset returns: holdings(10,20,70) become(11,18,71.4) after returns(10%,-10%,2%). Suspension is not de-risking or a loss cap. Missing/nonpositive/nonfinite inputs must preserve a failed run, not create imputed outcomes.

The accepted callback exposes holdings and completed history, not ledger/CPI. An incremental per-scenario observer can reconstruct prior realized states from the last requested accounting trade and next completed observation without exposing future rows. Test it against the completed engine ledger. Do not weaken the accepted baseline CLI's fixed configuration guards to add new modes.

## Suitability and limits of this model

| Profile | Own H | Tolerance | Liquidity | Classes passing horizon and target reserve only |
| --- | ---: | ---: | --- | --- |
| A |5|10%|high|Conservative |
| B |15|25%|medium|Conservative, Balanced |
| C |30|40%|low|Conservative, Balanced, Growth |
| D |25|15%|medium|Conservative, Balanced |
| E |6|35%|high|Conservative |

These are eligibility sets, not computed recommendations. D's long horizon cannot override medium liquidity; all profiles must also pass willingness/risk and purchasing-power screens at their own H. The horizon caps, target reserves0.60/0.25/0.10, gamma4 and generic25% suspension are declared service/model assumptions, not empirical findings. Target reserves drift, no actual liquidity withdrawals are modeled, and bills can lose purchasing power.

A one-year empirical utility rule is explainable and acceptable as a deliberately limited competition model, after the two blockers are resolved. It does not optimize30-year utility or drawdown, estimate personal preferences, establish a causal advantage, model intrayear losses, guarantee liquidity or protect against unobserved shocks. Pooled annual observations need not be independent even though evaluated scenarios are independent. Fixed marginal pooling assumes exchangeability/stationarity; the15-equivalent-year prior and five-year window are unvalidated assumptions about useful information. Negative cubic moments heavily weight adverse one-year outcomes. Reject invalid factors; do not clip them into plausible results.

P90 drawdown<=tolerance is an empirical filter, not a worst-case constraint. A synthetic120-scenario sample with108 zeros and12 losses50% has linear p90=5%, yet10% of scenarios exceed10% tolerance. Report exceedance fraction, denominator, median loss and severe loss alongside the gate. Nonnegative p10 CAGR screens terminal purchasing power, not losses along the path or a guaranteed future90% success rate. Maximizing median growth can overlook severe tails. The three-menu restriction and0.10 pp/year lower-growth indifference rule avoid some false precision but do not validate that tolerance. Use inclusive risk/p10/indifference comparisons and retain failed candidates.

Before freeze, every provisional assignment needs a separate simulation at its OWN suspension threshold and H, followed by all screens again. Threshold changes can improve or worsen outcomes; no improvement is assumed. Current prose refers a failed assignment to human review. State that explicitly, or predeclare any reselection protocol separately. A new customer referred initially stays in bills; an existing investor retains current holdings. This personalized follow-up must not be confused with the common H30/25% Balanced comparison.

## Selection, sensitivity and implementation handoff

D2 requests operational definitions: median of scenario-paired CAGR differences; differences of marginal p10 growth and p90 drawdown quantiles; positive within-fold paired median in at least3/4 folds. Quantile of paired differences is different. Synthetic values A=(0,3,10), B=(1,2,100) have median paired gain-1 versus difference of medians+1, and paired p10-72.2 versus marginal p10 difference-0.6. A faithful implementation must not be left to guess.

Require adaptive to pass against balanced_context AND balanced_cost with identical calibration/prefix rules, and output both direct comparisons. State eligibility if context itself fails promotion. These controls distinguish forecasting updates from target changes; beating annual equal weights alone proves neither. The default balanced_cost is a comparison default, not an automatic customer endorsement. Primary selection thresholds are practical tolerances, not significance levels. Four folds have overlapping training data. Baseline summaries were already viewed; the design's normative choices plus multiple modes/horizons/fees create selection risk despite predeclared promotion rules. OOF development is not the untouched final test. Preserve all16 mode-fee outcomes, failed attempts, fold negatives, review and trade differences.

Doubled costs use the SAME support/parameters and actual fee convention, with k changed in both accounting and score. The resulting states/latches can change; do not hold primary actions fixed. Rerun doubled-cost references at that cost. Reuse original references only at their original fee and exact audited source/input identity. Report robustness separately without choosing a new primary rule by looking at sensitivity results.

implementation-handoff.json proposes five small production modules/CLI responsibilities and three targeted test files; it is not an implementation authorization. It specifies16 fee/mode partitions,57600 ledger rows,9600 horizon-metric rows and20 paired-contrast files totaling12000 rows, including adaptive-cost. Candidate diagnostics are separately bounded. Manifests must bind every file, units, counts, exact sources, configuration, training/evaluation IDs, input hashes, command and measured runtime. No artifact may exceed10MB or overwrite completed evidence. All engineering/compute attempts must fit1800seconds or be split by chief into bounded immutable tasks. Support-evaluation and memory figures are complexity estimates only; production timing has not been measured. Personalized follow-up is a separate outcome-dependent job.

## Reproduction and evidence integrity

Run Python3.12: python -B audit/SOL-009/verify.py --check. Initial generation uses exclusive file creation. --check recomputes source hashes and synthetic facts, compares saved floats with abs/rel1e-12, and writes nothing. It returns nonzero for inconsistent evidence but does not fail solely because design_verdict=changes_required. Audit artifact hashes bind this review, findings, handoff and verifier with explicit LF normalization. Failed generation records are preserved; intentionally corrupt evidence and execution receipts are under this audit directory. execution.json records actual command returns, verification timing and the before/after file hashes used to check read-only behavior. No strategy runtime is inferred from that timing.

The ordinary process tool initially failed to initialize. A local Node subprocess fallback read the same files and invoked the existing Python3.12.14 interpreter; no environment/package change, watcher, branch change, commit or push was made. Only audit/SOL-009 deliverables/evidence are written.
