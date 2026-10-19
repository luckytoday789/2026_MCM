# Development writer compatibility notes after SOL-016 acceptance

This additive handoff belongs to the future writer task. It changes no published
attempt, existing implementation, policy parameter, prior result or run gate.
SOL-016 is accepted at ceec2b6d1107a4137ee3d24d689ba7ba614703c2. Calibration,
case-engine and writer acceptance remain separate. No computation is authorized
by this note. Pin this file in the eventual immutable writer/assembly task.

## Growth levels, differences and the existing canonical seam

The accepted experiments.metric_row / COMMON_UNITS schema uses the literal
`growth_units = "percentage points per year"` for CAGR levels. SOL-016 deliberately
accepts that exact inherited schema. Its values are already percentage returns:
`100 * ((real_terminal / 100) ** (1/H) - 1)`. The level's correct report label is
`percent/year`; paired level differences are `percentage points per year`.
This is a label correction, never a factor-of-100 numeric conversion.

The case-engine contract requires the correct level meaning. After its exact
receipt is accepted, the writer must bind the delivered case schema explicitly.
For new on-disk case metrics and summaries, use the level literal `percent/year`.
For imported HY3-003 records, preserve the original Git blobs and record their
legacy literal in the import manifest. A normalized derivative may change only
that unit label and the already declared lossless key mapping. For the call into
accepted build_analysis_tables, construct a detached metric copy and map that
single known level literal back to the legacy COMMON_UNITS literal. Do not mutate
case tables, source records, saved artifacts or the analysis implementation.

The mapping must be named in provenance with source schema/version/hash, exact
field, original literal, destination literal and direction. Reject unexpected
unit strings; do not treat arbitrary labels as equivalent or guess units from
values. A pinned source that emits the inherited literal needs only the outward
correction; a source that emits the correct literal needs the analysis-input
bridge. Select the path by the accepted source schema, not by silent per-row
coercion. Paired growth_difference_units already has the correct meaning and
must stay unchanged. Profile growth fields already use percent/year.

Acceptance fixtures must establish that every numerical cell, key, null and
boolean survives normalization exactly, including signed zero and adjacent
binary64 values where representable. Hash untouched source artifacts before and
after. Verify that 0.01 is reported as 0.01 percent/year, never as 1; verify that
subtracting 0.01 from 0.11 yields the original floating subtraction in pp/year,
without rounding a decision threshold. JSON/CSV readers must preserve declared
column types rather than infer null/boolean success from empty strings.

## Reviewed calibration versus production provenance

The approved calibration seam, if SOL-022 approves its current source, takes
explicit CSV bytes and returns immutable folds; its top-level manifest honestly
says synthetic. The writer validates the fixed development path, exact raw bytes
and 120-by-30 grid before using reviewed mathematics. It then creates a distinct
production provenance record from those checks and fold identities; it must not
copy a synthetic manifest and flip its split or authorization flag.

If reusing build_synthetic_calibrations internally, identify it by exact source
and record that it is an arithmetic seam only. Consume its immutable folds,
not its manifest as an origin certificate. Confirm training/evaluation membership,
keys, digests and equally weighted real-gross rows independently. If the accepted
case interface requires a CalibrationBundle, pass the original immutable object;
keep the external production attestation separate. Do not alter source merely
to change a label. Any actual shared-core refactor needs a new scoped review.

## Keep first execution and later analysis independently bounded

The first writer task should produce and verify case bundles only. Its production
path remains closed until chief publishes the accepted source plus a separate
fixed execution configuration and HY3 kind=commands task. Only generated inputs
and temporary output roots are used during implementation acceptance.

Use the existing allowed split: five new primary-fee policy cases, eight new
doubled-fee cases, and three exact primary reference imports. Analysis assembly
may be a separate bounded task consuming all accepted case bundles. Do not build
incomplete comparison grids or provisional selections from only the first group.
A later assembly must verify the precise producer receipts and all sixteen case
identities before invoking the accepted pure analysis API. Generic assignments
remain provisional until their own-horizon/own-tolerance runs and independent
risk and purchasing-power rescreens pass.

All writer and assembly acceptance must demonstrate read-only corruption
rejection. Preserve failure diagnostics; use small copied corruption fixtures
and concise original/altered hashes where possible instead of many repeated full
bundles. Historical SOL-016 full corruption artifacts remain preserved unchanged.
The eventual <=50 MB code supplement should contain the reproducible accepted
code and selected required evidence inventory; repository audit history remains
available separately and must not be deleted to meet the supplement limit.
