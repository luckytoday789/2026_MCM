# All-development refit implementation handoff after SOL-024

Status: chief preparation only. This is neither an immutable implementation task
nor permission to fit competition observations, create a freeze, or open holdout.
The approved mathematical authorities remain FINAL_EVALUATION.md,
FINAL_OUTPUT_NOTES.md and SOL-024 at
b1de55ec16f7b67884415637f562fcdf446034c7, accepted in
`audit/chief/SOL-024-review.json`. No policy parameter or existing approval changes.

## Exact missing seam

`policy_calibration.build_synthetic_calibrations` builds four OOF priors;
`policy_writer.calibration_attestation` verifies that same four-fold identity.
Neither implements the all-development refit. `policy_cases.build_case_tables`,
`backtest.simulate_policy`, and the development writer reject the final split.
Do not relabel their outputs or select one OOF prior as a final prior. Existing
source docstrings are historical; exact queue acceptances govern their status.

The future pure refit component should accept explicit generated CSV bytes for
review, validate complete ordered scenario/year keys and return an immutable
single prior plus a detached manifest. Its generated entry remains labelled
synthetic, source_verified=false and production_execution_authorized=false.
It has no default path, imports no final loader and cannot assert original-data
identity. A separate fixed production loader may authenticate only
`data/development/scenarios_001_120.csv` against the original locked hash, require
exact IDs 1..120 and years 1..30, then invoke the reviewed pure component. Its
actual execution additionally waits for accepted generic selection and all ten
personalized development rescreens. A generated implementation review may be
prepared earlier; no actual competition refit is run by this handoff.

The refit uses all 3600 annual rows exactly once, sorted by (scenario_id, period),
with probability 1/3600 per row. For each row g_i=(1+r_i)/(1+inflation), preserving
the accepted binary64 operation order and positive-finite-factor checks. There
is no fold exclusion, evaluation_ids partition, shortened client training horizon,
fee-specific fit, rolling refit, bootstrap, optimization or prior parameter search.
All generic and eligible personalized final paths at both fixed fees consume
this same immutable support. Each new path starts in bills with fresh policy
state; its past observations cannot mutate the common support or another path.

Record exact consumed input byte hash/length, asset order, all 120 training IDs,
all 3600 ordered keys, row count and annual weight. Preserve the existing canonical
nominal and real-gross row hash payload schemas from
POLICY_CALIBRATION_PROTOTYPE.md: sorted compact ASCII JSON, float.hex, no newline.
A new refit manifest explicitly identifies calibration_kind=all_development_refit
and keeps its own source/task/acceptance identity separate from those row hashes.
Its schema and exact field names need independent implementation review; this
note is not an executable production configuration or a signed manifest schema.
Do not invent evaluation folds for the refit. An applicable field with no value
must not be disguised as a successful zero-count OOF evaluation.

The contextual distribution still has prior mass 15/(15+n), n=min(5,t-1).
Each training row then has mass 15/((15+n)*3600), and each of n recent same-path
rows has mass 1/(15+n). At n=0 the row mass is exactly 1/3600. Fixed-prior modes
use no recent mixture. The value 15 is prior mass, not 15 sampled observations.
Use the existing accepted EmpiricalPrior and target/fee kernel unchanged unless
an independently reviewed minimal source change is explicitly assigned.

## Generated reference supplied now

`audit/chief/final_refit_reference.py` imports only the standard library and
constructs its observations in code. It reads no competition input and imports
no safeinvest module. `--check` reconstructs the two saved files in
`audit/chief/final-refit-reference/` without writing them. The 4-by-3 CSV has twelve
equally weighted rows. A separate 120-by-30 generated shape is constructed only
in memory to specify the full-refit 3600-key identity. Neither fixture is a
competition calibration or policy outcome.

The saved eighteen scalar references use six rational targets and n=0,1,5.
For support G and recent rows R they compute the exact rational inverse-cube
moment M=[15*mean((w.G)^(-3))+sum((w.R)^(-3))]/(15+n), then its inverse cube root
at Decimal precision 90. They distinguish all-training support from a fold
subset, nominal/source identity from derived gross identity, signed zero and
input line-ending identity. Mathematical rational weights/gross factors are
separate from the binary64 identity payload. Future kernel comparison must state
its tolerance and examine rounding; exact equality to the decimal root is not
required. These expected values do not test or approve a nonexistent refit API.
The reviewer must independently recompute selected expectations as well.

Reproduce using the selected project Python 3.12 interpreter:

```
python -B audit/chief/final_refit_reference.py --check
```

A future implementation task must pin the exact reference script and artifact
blobs along with the approved source closure. Chief-authored reference arithmetic
is supporting evidence; Sol's independent implementation review remains required.

## Granular later work and independent acceptance

1. **Pure refit, generated inputs only (Sol, <=1200 s).** Assign only a new refit
   module, focused tests and its audit directory. Pin accepted kernel/calibration
   APIs and this note on an already pushed base. Exercise complete/missing/extra/
   duplicate/reordered keys, nonfinite or nonpositive gross factors, immutable
   support, detached manifests, canonical nominal/gross hashes, the 18 scalar
   references and generated 120-by-30 shape. Demonstrate all-support weighting;
   do not weaken the old OOF functions. Chief independently checks exact code,
   representative rational facts and negative fixtures before acceptance.
2. **Fixed development loader and refit artifact (Sol code review, then HY3 fixed
   commands, each <=1500 s).** Only after the development decision/rescreen gates
   exist, pin their actual exact accepted commits/receipts, the fixed original
   development hash and accepted pure refit. Separate source C, complete run
   configuration E and task publication P. Require a fresh read-only checker,
   real input/source/artifact hashes, exact support equality and independent Sol
   recomputation of the actual artifact. No final input is needed for this job.
3. **Final path engine (Sol, generated data only, <=1500 s).** Use a new reviewed
   entry point with explicit true final identity. Preserve rejection in existing
   public synthetic/development entry points. If a shared private arithmetic
   seam is necessary, assign those exact changed paths explicitly, preserve old
   behavior and run relevant existing accounting/prefix tests. Review generated
   121..180-shaped fixtures without opening the actual final CSV. Reuse accepted
   accounting, metrics and decisions; never execute through a mislabeled
   synthetic split and then rewrite provenance. Demonstrate same-prior identity,
   fresh state, own-path prefix timing and future-path perturbation isolation.
4. **Final persistence/authentication (separate Sol attempt <=1500 s).** Pin the
   actual accepted refit, path engine, analysis assembly and personalized bridge
   APIs when they exist. Before opening the actual final file require
   source/config/task hashes, external independent freeze attestation, valid
   UTF-8 freeze bytes, exact runner digest, recorded control gate and locked
   expected input path/hash. After an authorized byte read, match the consumed
   file hash and validate complete final keys before simulation. Use
   generated accepted/rejected gate fixtures and record actual file-open order.
   A successful runner gate alone is not artifact/source authentication. Never
   invoke development selection on final statistics; final fold/support/promotion
   fields are null with not-applicable status. Preserve the SOL-024 conventions
   for the ten profile/fee rows and all execution failures.
5. **Actual freeze and final evaluation (chief gate, HY3 fixed commands).** Only
   after all exact development, refit, source and independent review gates pass,
   publish complete configuration and freeze, then independent external freeze
   review, then gate opening and immutable final tasks in a later commit. Keep
   any disjoint shards predeclared and each attempt <=1800 s. No automatic
   submission, placeholder freeze, outcome-driven reselection or silent gate reset.

These are scope and acceptance instructions for later task construction, not
published task identities or permission to start any listed step now. Commands,
allowed paths and exact source pins become immutable only in those future tasks.
Use the existing remote Sol and HY3 roles; do not create local replacements.

## Completion evidence required from later production

Preserve 16 generic cases, 960 paths, 28800 annual ledger rows, 4800 horizon metrics,
100 descriptive comparison rows and 6000 paired rows. Profile root has ten rows;
for executed pairs E, metrics=60*|E| and ledger/decision counts=60*sum(H for E).
All ten eligible implies 9720 ledgers/decisions and 600 metrics; all referred means
no personalized cases and ten null-valued no-run rows with denominator zero.
Keep fees, own horizons, strict exceedance, initial/post-fee drawdown and exact
severe selection unchanged. These are expected counts, not observed outcomes.

Independent Sol acceptance of actual HY3 refit/final commits, chief exact-commit
checks, source/byte inventories and the original exposure/correction disclosure
are mandatory. Wrong policy outcomes are reported honestly; they are not a reason
to rerun a selection. Follow FINAL_OUTPUT_NOTES.md for corrections with explicit
old-freeze/new-source binding. The report must separate development and final
results, preserve negative findings, and retain local-only private identities.

The already pinned quality-assurance-auditor skill (yushui2022/MathModel-Skill,
b13a23e2ccae39a1f13ceb5dbd41fa74ed61eac0) informed evidence/hash separation.
No external code, template, new skill or generic CUMCM workflow was installed.
The SafeInvest protocol, paths and original annual problem remain authoritative.
