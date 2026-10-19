# Fixed development writer execution configuration

This additive interface note resolves execution provenance for the future writer.
It changes no policy, immutable task, accepted source or historical design flag.
It does not authorize computation. Pin it in the writer implementation task only
after SOL-023 is accepted. POLICY_RESULT_WRITER.md and the compatibility/reference
notes remain authoritative. Sol must report contradictions before implementation.

## Separate code, configuration and task commits

Use three ordered publications, so no file has to contain its own Git hash:

1. C is the full existing 40-character main commit containing accepted writer
   code and its complete computational dependency closure.
2. E is a later pushed main commit adding the chief's fixed execution JSON. That
   JSON pins C and hashes of source/specification blobs from C. It cannot pin its
   own bytes or E. A configuration name is not source authentication.
3. The immutable HY3 task has base_commit E (or a later pushed main commit with
   identical required bytes). Its task parameters pin the configuration's path
   and canonical Git-blob SHA256, source commit C, input hash and fixed group.
   Only this separately published kind=commands task authorizes execution.

Validate C as an existing commit and ancestor of the task's real pinned base.
Validate the configuration against that task's pinned bytes before opening input.
Allow HEAD to advance when checking an accepted saved bundle: verify its recorded
exact commits and contents, not equality with the current branch tip. The source
set must explicitly cover the script, every imported computational module,
package initialization, locked mathematical contracts and policy/layout configs.
An unlisted dependency, missing pin or altered module fails. Existing worker
receipt/audit commits are separate evidence identities, not substitutes for C.

The writer CLI still accepts only --config, --output and --check. An execution
JSON is UTF-8 strict JSON: reject duplicate/unknown/missing keys, NaN/infinity,
wrong types, and booleans where an integer or number is required. No ad hoc input,
mode, fee, horizon, split, threshold, policy search or final flag is exposed.
Synthetic fixture execution remains an internal, explicitly synthetic test seam;
it cannot be enabled by a production config or arbitrary caller label.

## Required configuration fields

The future configuration has exactly these top-level fields:

- schema_version: integer 1.
- run_id: the chief-assigned immutable development job ID.
- split: literal development.
- execution_authorized: true only in the later chief-issued execution file.
- source_commit: C as defined above.
- source_sha256: exact path-to-canonical-Git-blob-SHA256 mapping for that closure.
- acceptance: task-ID-to-exact-reviewed-commit mapping for accepted dependencies,
  including SOL-021, SOL-022, SOL-023 and the eventual writer task. Resolve each
  against the pinned base queue and its referenced chief acceptance evidence;
  cancelled attempts and accepted negative code verdicts do not pass.
- input: exactly path, sha256, scenario_ids, periods; fixed respectively to
  data/development/scenarios_001_120.csv,
  9c4ad83f5dda86251a754e126528a71dd930ae88ed7cdb8a0663a327b6bfb7c7,
  [1,120], and 30. The hash is of original raw bytes; do not normalize CSV bytes.
- policy_config: exactly path and sha256, binding the unchanged v2 policy file.
- layout_config: exactly path and sha256, binding policy_driver_layout_v2.json.
- group: primary or doubled, with the exact membership below.
- horizons: exactly [5,6,15,25,30].
- references: an empty list for doubled; for primary exactly one HY3-003 entry
  with task_id, reviewed_commit, receipt_sha256 and artifacts_sha256. Bind the
  exact reviewed receipt and the five inherited files (annual_ledgers.csv,
  scenario_metrics.csv, summary.csv, run_manifest.json and checks.json). The
  receipt independently authenticates those artifact hashes. Other inherited
  evidence may be referenced in provenance, without silently widening the set.
- expected_counts: exactly cases, new_cases, imported_cases, annual_ledgers,
  scenario_metrics, summary, decisions, target_scores_max, with values below.
- execution: exactly cpu_only=true, required_python="3.12", max_seconds (a
  positive integer <=1500 and no greater than the immutable task allowance),
  max_artifact_bytes=10485760.

The chief publishes actual configurations only after positive writer acceptance.
Do not create an executable example with invented hashes, placeholder commits or
execution_authorized=true during implementation. Immutable task parameters must
agree with all configuration fields controlling the run, not merely run_id.
The original design/config production_execution_authorized=false stays intact:
its historical meaning is that the design alone authorizes no production job.

## Exact groups and structural counts

Primary uses fee 0.0025. It computes conservative_cost, balanced_cost, growth_cost,
balanced_context and balanced_adaptive. It imports bills_keep, equal_weight_annual
and equal_weight_buy_hold at their exact accepted primary fee. The imported
reference files are never rerun or modified. Doubled uses fee 0.005 and computes
all eight named modes. A group is a fixed list, not a parameter search.

For each group the expected counts are:

| Field | Primary | Doubled |
| --- | ---: | ---: |
| cases | 8 | 8 |
| new_cases | 5 | 8 |
| imported_cases | 3 | 0 |
| annual_ledgers | 28800 | 28800 |
| scenario_metrics | 4800 | 4800 |
| summary | 40 | 40 |
| decisions | 18000 | 18000 |
| target_scores_max | 24000 | 24000 |

These are structural expectations, not observed runtime, output size or results.
The score count is a bound: four nonadaptive modes allow 3600 each; adaptive
allows 120*(5+25*3)=9600. Review suspension reduces actual scores. Check precise
score/decision links and eligibility instead of requiring the upper bound to be
attained. Each cost-aware case has 3600 decisions even when review is latched.
Each imported/reference case has inapplicable empty sidecars, not zero-success
policy diagnostics. The primary root import index authenticates all three
reference cases. The doubled root index explicitly records no imports.

Store each case under cases/<mode>/; one bundle contains only one fixed fee.
The complete artifact index contains exact relative paths, declared column types,
row counts, bytes and hashes. No analysis/selection or personalized result is
created by this first writer. Those are later independently reviewed jobs.

## Verification order and negative fixtures

Before data access, verify the strict config, task/config relationship, accepted
source closure, and recorded reference identities. Then verify the allowed input
path (including symlink resolution), raw hash, six fields and complete grid.
Only then build the four priors and cases. Production attestations remain
separate from the unchanged synthetic-labelled arithmetic calibration object.

Before any input access or computation, refuse an existing requested output root. Preserve the unique
partial staging path and failure diagnosis if any stage fails; never reuse it.
Measure the fixed budget and actual artifact bytes. Preserve an interrupted or
oversized attempt; do not silently split it into new jobs. A later immutable job
may be narrowed by the chief if measured evidence requires that change.

The writer's read-only --check validates the recorded config, receipt and source
against exact pinned blobs and hashes. The current queue may have advanced: use
its recorded task-base version for dependencies and source C, and separately
record any subsequent chief acceptance when applicable. It cannot regenerate
expected hashes from modified files, repair a manifest or fill missing evidence.
Source/config/input, imported baseline bytes and all existing output bytes must
remain unchanged after checks, including rejected corruptions. Exact source,
config, key, count, numeric, missing-file and incomplete-status corruptions are
required in the implementation evidence. No production or final-outcome run is
needed to test these boundaries on explicit generated fixtures.
