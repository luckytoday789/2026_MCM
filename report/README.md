# SafeInvest report workbench

This directory contains preparation for the English competition report, not a
finished report or a statement that the research has passed its evidence gates.
The project-specific requirements in `specs/PROBLEM_LOCK.md` govern the format:
at most 10 A4 pages, font at least 11 pt, all three member names, AI-use disclosure,
and a separate source-code ZIP at most 50 MB. Humans submit the deliverables.
Do not apply another competition's page limit, anonymity rule or summary template.

## Current writing boundary

The accounting engine, fixed baseline driver and first development baseline
result are accepted. HY3-003 at `7652410d73425371110784ef5fa97c03470a074e`
passed independent SOL-008 review at `818af5d65bd8a271962d848dd552bd39ca561f68`
and the chief's pinned, read-only replay. Its descriptive tables can be used.
The corrected v2 cost-aware and suitability design was approved by SOL-013.
The corrected numerical kernel passed SOL-021 at
`d154f90d1c50b37990b75ec0a45aa01a38252343` and the chief's independent replay;
historical K1/K2 negative reviews remain preserved. Personalized handoff design
was approved by SOL-020.
No policy selection or customer recommendation follows from these references.
The authoritative current states are in `ops/queue.json`; use the exact worker
SHAs and acceptance records above for citations.

- [component-index.md](component-index.md) links ten accepted source modules to
  exact reviewed commits, task/receipt digests and chief acceptance hashes.
  Reproduce source identity with `python -B report/build_component_index.py --check`;
  this index does not certify outcome claims or final readiness.
- [methods-draft.md](methods-draft.md) contains reusable English text for the
  locked accounting, annual metrics and scenario protocol. It contains no
  competition performance result or new policy parameter.
- [policy-catalogue.md](policy-catalogue.md) derives target weights, profile
  horizon/liquidity eligibility and promotion thresholds from the exact approved
  design. Its provenance keeps the original negative kernel review separate.
  Reproduce with `python -B report/build_policy_catalogue.py --check`; no outcome
  inputs are read and no customer assignment is inferred.
- [Personalized output notes](../specs/PERSONALIZED_OUTPUT_NOTES.md) carry the
  accepted SOL-020 no-run/null/denominator conventions and separate the generic
  same-policy cost test from fee-specific profile assignments. They authorize
  no computation and contain no actual assignment evidence.
- [evidence-map.json](evidence-map.json) maps every required answer to its source,
  evidence status and missing validation. It is a writing map, not an acceptance
  receipt, freeze file or implementation task.
- [baseline-development.md](baseline-development.md) contains all 15 accepted
  reference/horizon rows and their severe cases. The companion provenance JSON
  binds full-precision source rows and display rounding. Reproduce or check it
  with `python -B report/build_baseline_note.py --check`; this does not simulate
  any experiment or access final outcomes.

## Proposed page budget

| Content | Pages | Material needed before final writing |
| --- | ---: | --- |
| Title, local member names and executive summary | 1.0 | Accepted recommendations and quantitative findings; write summary last |
| Data, accounting, metrics and validation method | 2.0 | Locked definitions; final protocol details after freeze |
| Conservative / Balanced / Growth and profiles A--E | 1.5 | Reviewed design, accepted profile evidence and personalized review check |
| Balanced decisions, baseline comparison and severe case | 2.0 | Accepted selected-policy results, ablations and severe-case path |
| Cost sensitivity and recommendation impact | 1.0 | Accepted fixed-parameter sensitivity results |
| Limitations, suspension and holdings pending review | 1.0 | Reviewed operational rule and supported conclusions |
| References, reproducibility and AI-use disclosure | 1.0 | Actual tools, source versions and final supplement inventory |
| Layout reserve within the same 10-page limit | 0.5 | Rendered-page corrections |

This is a layout budget, not a rendered page count. Keep disclosure and references
inside the total. Use compact tables rather than a separate contents page. Do not
shrink text below 11 pt to accommodate missing material.

## Evidence displays to build after acceptance

1. **Profile table:** profile, own horizon, stated tolerance, liquidity, candidate
   eligibility, p90 loss, loss-exceedance fraction, p10 growth, selected rule or
   referral, and reason. Show failed screens as well as passing ones. Report the
   result of the personalized suspension follow-up before confirming an assignment.
2. **Balanced comparison:** the required equal-weight annual baseline and every
   declared candidate; median growth, p10 growth, median loss, p90 loss, ordinary
   fluctuation, both trade shares and human-review frequency where applicable.
   Label horizon, split, scenario count and fee rate. Distinguish contextual
   updating from target changes using the declared same-context comparison.
3. **Severe-case path:** use the predeclared worst-loss selection and show its
   scenario, real wealth, running peak, selected trough, review/trade events and
   horizon. A baseline comparison drawn on the selected policy's scenario must
   not be labeled the baseline's own worst scenario. Keep post-fee observations.
4. **Cost sensitivity:** the unchanged rule at the original and doubled fee,
   required metrics, trade/review changes and whether the recommendation changes.
   The doubled rate is a pending pilot assumption, not an executed experiment.
5. **Customer explanation:** at most 50 English words, written after policy
   selection; include the action, reason, cost awareness and remaining risk.

Do not copy unaccepted CSV values into manuscript tables. Each final value needs
an accepted run/commit, file and row key, units, and a documented rounding rule.
Store full precision in evidence; round only for display. CAGR levels use percent
per year, and differences between CAGR levels use percentage points per year.
Keep development and final results visibly separate. No final evaluation is
authorized by this plan.

## Next dependencies and completion checks

- SOL-013 approved the corrected design and SOL-021 closed K2 after independent
  chief checks. Pure analysis SOL-016 and calibration SOL-022 are accepted.
  SOL-023 failed its prescribed standalone test command and remains unaccepted;
  its exact code and negative evidence are preserved. SOL-025 was separately
  accepted at 803b7a085284405ee5ee4d4f0d5720ebaa2e67f7 after clean-environment
  replay, independent numerical checks and corruption rejection. Writer
  implementation and actual policy outcomes remain pending. Personalized
  design is approved by SOL-020, with implementation/outcomes still unreviewed.
  Preserve old negative verdicts, quota failures and cancelled tasks;
  do not rerun accepted HY3-003 or treat synthetic checks as policy outcomes.
- After review, resolve concrete findings and publish granular implementation
  work against already-pushed prerequisite commits. HY3 runs reviewed code with
  fixed parameters. Review its outputs independently before using the numbers.
- The accepted metric/driver API currently supports synthetic/development runs
  only. Any future final-evaluation support needs an explicit implementation,
  tests and independent review **before** freezing the final code. A plan is not
  permission to relabel development output as final.
- SOL-024 at b1de55ec16f7b67884415637f562fcdf446034c7 approved the final
  contract design; chief replay and independent count/severe/hash checks passed.
  specs/FINAL_OUTPUT_NOTES.md carries its required null/denominator conventions,
  external freeze attestation and explicit correction-source binding into future
  implementation. Final code, development decisions, refit and freeze remain
  unaccepted; the design review creates no freeze or holdout access.
- Freeze code, parameters, metrics, selection and severe-case rules, plus input
  hashes, before opening final outcomes. Keep failed evaluations and disclose
  any bug correction; never erase the gate history or tune on final outcomes.
- Request a targeted Sol mathematical/evidence review of the assembled report
  once the evidence exists. Reconcile abstract, tables, recommendations and code.
  Render the final document and check every page, font size, equation and figure.
- Verify the final code ZIP size and exact inventory. Preserve source/data
  attribution and available licenses. The source manifest records the supplied
  competition material as CC BY-NC-SA 4.0; retain that attribution.
- Insert member names only into a local delivery copy from the ignored private
  record. The recorded GitHub upload restriction still applies; do not put names,
  IDs or that private file into tracked drafts, figures or shared supplements.
- Keep an accurate AI-use record: chief model/specification/writing work, Sol
  implementation/reviews, and HY3 supervision of deterministic Python jobs.
  Disclose actual accepted and checked work, not capabilities or planned tests.
- The human team leader submits the report and code supplement. No automatic
  competition upload is permitted.

Writing aid: the existing `math-modeling-skill`, pinned in `ops/skills-lock.json`
to `anticipate218/math-modeling-skill` commit
`e70b85b8a41aeb748789f66860c6bd4d123871cd` (MIT), informed structure and evidence
discipline. No template/code was copied and no new skill was installed. The
SafeInvest problem and repository protocol override generic competition rules.
