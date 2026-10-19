# SOL-020 targeted personalized handoff review

**Design verdict: approve. Implementation verdict: not reviewed.** There are no blocking contradictions in the new handoff or companion JSON relative to the accepted corrected v2 design. No specification change or production run is authorized by this review. SOL-013's corrected-design approval and historical kernel **changes_required** verdict remain intact; K1 is reviewed elsewhere.

Reviewed source is base commit **a2205fb7edd2527253664efad601f0da290f3661**. The exact eleven source SHA256 values are in findings.json and are checked against pinned Git blobs and local checkout bytes. The task is independently bound to ops/tasks/SOL-020.json at **84144ff2eca205e8575e8d206cd03bb9751835b4** (raw Git SHA256 e2c0985b6c862afb568ed383a06d3aa4440bb86ef260c2356b7743f8bad044c7). The task was published after its base, so it is verified at that task publication commit, not invented at the earlier base. The accepted prior review commit is **1908813ef2627ca6e15591278ec15ccf2f9e9cff**. The target is specs/PERSONALIZED_REVIEW.md and specs/personalized_review_v1.json; POLICY_ANALYSIS, POLICY_CASE_ENGINE, POLICY_RESULT_WRITER, the v2 contract/config and locked accounting/problem supply context. This does not repeat the accepted whole-design/kernel review.

## Mapping and referral decision

The ten unique upstream keys are five profiles times two fees. A null class stays null, retains its upstream reasons and produces no policy case. Bills for a new client and existing component dollars for an existing investor are pending-holding instructions, not simulated fallback results or proof of purchasing-power eligibility. A missing, mismatched, unknown/adaptive or hash-invalid assignment is an input error with preserved failure evidence, not an ordinary referral.

A selected class maps only to its fixed conservative_cost, balanced_cost or growth_cost mode. Preserve its fee, matching immutable fold prior, central target, score/fee conventions and all other v2 parameters. Replace only the generic 25% suspension threshold with the profile's own tolerance. Evaluate 120 fresh paths through that profile's own H; do not inherit later latch/deployment diagnostics. Other-fold full training rows remain the declared OOF prior and do not constitute evaluated-path future access. No adaptive substitution, altered class menu, threshold tuning, re-ranking or fallback search is authorized.

| Profile | H | Own threshold | Liquidity | Eligible fixed classes before outcome screens |
| --- | ---: | ---: | --- | --- |
| A | 5 | 10% | high | Conservative |
| B | 15 | 25% | medium | Conservative, Balanced |
| C | 30 | 40% | low | Conservative, Balanced, Growth |
| D | 25 | 15% | medium | Conservative, Balanced |
| E | 6 | 35% | high | Conservative |

Recheck fixed horizon and target reserve as well as BOTH p90 real loss <= tolerance and p10 real CAGR >= 0, inclusively and without display rounding. Any failed screen preserves proposed_class and saved outcomes but nulls recommended_class, with every reason reported. A computation failure remains a failed computation. A passing empirical p90 is not a maximum-loss cap.

## Separate cost questions

Primary .0025 assignments and .005 assignments are separate upstream profile/fee records. A different .005 class is a reportable hypothetical. It cannot replace the primary assignment automatically and cannot certify robustness of the same policy. For example, B can be hypothetically Conservative at primary cost and Balanced at doubled cost; the two personalized results would answer different fixed-policy questions.

Independently preserve the generic Balanced H30/25% research robustness test in POLICY_ANALYSIS/v2. At .005 retain the mode selected at .0025 and its original direct controls: contextual versus fixed cost; adaptive versus BOTH contextual and fixed cost. A doubled-fee winner must not be substituted. The scalar reference deliberately makes primary context qualify at .0025, fail gain at .005, and adaptive qualify at .005: context remains primary and its robustness verdict fails. If the primary is balanced_cost, report no added complexity selected; that fact does not pass absolute customer screens. Personalized fixed-class follow-up does not replace this generic comparison.

## Independent reference evidence

verify.py imports only Python standard-library modules. It contains small Fraction/scalar accounting and event observations, screening arithmetic and table-key/cardinality fixtures, without importing or executing policy, calibration, simulation, analysis or production writer helpers. These are reference expectations, not observed implementation or investment outcomes.

- A completed year-end real value of 75 from initial peak 100 gives exactly 25% loss. At a 25% threshold, review 1 stays unlatched and review 2 latches permanently. If this crossing is first observed at year H=2 end, first_latch_year is null and only two reviews exist.
- An illustrative all-equity 100 transfer at .0025 costs exactly 1/4 before returns, leaving 399/4. This reaches a deliberately tiny 1/4% threshold at the post-fee observation. Recovery to 133 at year end cannot erase the running maximum loss; review 2 still latches. This accounting-only fixture does not add an all-equity policy target.
- Pure inflation with nominal wealth 100 and CPI 4/3 yields real wealth 75 and the same next-review latch. Pending holdings (20,30,50) keep those exact component dollars, transfer/fee zero; gross factors (1/2,6/5,1) then yield (10,36,50). End real wealth at CPI 5/4 is 384/5. Pending exposure can lose or recover.
- Of 120 loss values, 110 equal 10 and ten equal 20. Linear p90 is exactly 10, so a 10% risk screen passes despite ten strict exceedances. p10 growth exactly zero passes. Constant loss 11 with growth zero fails only risk; loss 10 with growth -1 fails only purchasing power; both failures are retained and neither causes reselection.
- B retains 25% at H15. Fourteen flat years followed by 75 real wealth give prefix loss 25, null prefix latch and a first latch only at full-path review 16. Prefix scalar CAGR is 100*(.75^(1/15)-1); annual-return sample variance is exactly 125/3 square percentage points (ddof=1). Matching production mode/fee/prior/threshold must reproduce the exact generic H15 ledger, decisions, scores and metrics. This review checks the scalar expectation, not absent code.

| Assignment fixture | Root summaries | Executed cases | Ledgers | Decisions | Scenario metrics | Score maximum |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| None | 10 | 0 | 0 | 0 | 0 | 0 |
| A-primary, B-doubled, D-primary | 10 | 3 | 5,400 | 5,400 | 360 | 5,400 |
| All | 10 | 10 | 19,440 | 19,440 | 1,200 | 19,440 |

Counts are conditional: each executed case has H*120 ledger and decision keys, 120 own-H metrics and one case summary. Every fixed mode scores its one target only before suspension; score rows equal non-human-review decisions, with no fabricated suspended scores. The explicit one-final-suspended-review shape fixture gives 5,040 partial and 18,240 all-assigned score rows. Keys include profile, fee, scenario and period (or own horizon for metrics); scores add target. Every score links to one decision. Every summary, including referrals, requires upstream result/assignment hashes. Referral metrics/flags/classes/mode/case path are null, scenario_count=0, and simulation_status=not_run_upstream_referral. Executed cases require all metrics and source paths. The illustrative shape values and hash strings are generated placeholders, not upstream evidence or performance.

## Clarifications and scope

No chief correction is needed for design approval. Three schema/report details must remain explicit in later work: drafting SHA is historical, not an execution pin; generic same-primary-mode Balanced robustness remains separately reported; and not-run personalized denominators need a declared count convention. The fixture uses denominator 0 alongside null outcome statistics and never computes 0/0. Upstream generic statistics retain their original provenance/denominator. These choices add no investment parameter. A future immutable task still must pin real accepted generic assignments, code, calibrations and sources, which are intentionally absent from this design-only review.

verification.json is exclusive-created. --check recomputes independently, verifies pinned Git and artifact hashes, accepts HEAD advancement, and writes nothing. Artifact hashes allow only LF/CRLF normalization for Git portability. Rational boundary tests are exact; floating numerical checks use abs 1e-9 and rel 1e-10, never a relaxed policy screen. The executed scratch suite rejected eleven corrupted/missing-evidence copies and a second initialization, accepted the valid and numerical-roundtrip copies, and confirmed every --check left bytes unchanged. A pinned-source run also forbade any mutable HEAD query without changing refs. integrity-self-tests.json records all sixteen actual trial results. execution_history.json preserves the infrastructure and source-path probe failures.

No competition CSV, actual policy run, final outcomes or trading is authorized or evaluated. No implementation, adapter, writer, changed K1 code, strategy benefit, personalized loss guarantee, freeze, final validation or submission is certified. Chief acceptance of exact evidence and later independent implementation/result reviews remain required.
