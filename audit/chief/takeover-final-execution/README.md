# Local chief final execution component

Generated-only implementation/testing. No actual development refit, final file
read, freeze, gate opening, task execution, commit or push was performed here.
The parent chief owns source acceptance, configuration/evidence and publication.

`final_execution.CONFIG_KEYS` and `CLOSURE` are the executable schema/closure.
`run_final_evaluation.py --config <POSIX-path> --output <POSIX-output>` executes
exactly the stage fixed by that immutable configuration. `--check` is read-only
saved hash/count verification, explicitly not independent numerical acceptance.

Required published commands contain exactly one array
`["{python}","-B","scripts/run_final_evaluation.py","--config",CONFIG,"--output",OUTPUT]`
followed later by that array plus `"--check"`. Task parameters are `config_path`,
`config_sha256` (canonical JSON SHA256), `output_path`, `execution_stage`.
Owner is truthfully chief or HY3; normal published queue/branch/receipt protocol
applies. The runner itself produces no fabricated receipt or remote identity.

Config fields: schema_version=1, run_id, stage=refit/final, source_commit,
source_sha256 (exact CLOSURE), source_review and development_review Git references,
primary_mode, ten ordered profile_choices, refit/freeze/freeze_attestation,
execution. References are {commit,path,sha256} of exact canonical Git blobs.
Execution contains cpu_only=true, required_python="3.12", max_seconds<=1800,
max_artifact_bytes=10485760 and fixed output. Profile order is A..E, each .0025
then .005; rows contain profile_id, fee_rate, proposed_class, eligible, reason.
Historical proposed classes may remain on referrals; they are never simulated.

Source review JSON requires status=accepted, source_commit and source_sha256.
Development review requires status=accepted, primary_mode, profile_choices,
all_ten_rescreens_accepted=true, and evidence with at least two exact actual
result/acceptance references. These review commits must precede task base.
Source review authority includes the user's explicit chief/HY3 takeover; this
component does not misdescribe chief numerical checks as remote Sol review.

Refit stage requires all three final references null, recorded running state,
no local STOP, and final_data_open=false. It authenticates original fixed
development bytes, fits all3600 once, and writes a new truthful production
manifest rather than changing the generated component's provenance labels.
The actual refit must subsequently be independently checked and accepted.

Final stage binds that exact committed refit manifest and a complete freeze
at ops/freeze.json. Freeze fields consumed by this component are source_commit,
source_sha256, effective_configuration_sha256, primary_mode, profile_choices,
refit, input_path, input_sha256. Effective configuration excludes only freeze
and freeze_attestation, preventing a circular future digest. Root must add all
other narrative/parameter/command/count/disclosure bindings required by the
locked full freeze contract; this minimal component is not a freeze author.

External freeze attestation requires accepted status, freeze_blob_sha256,
freeze_runner_sha256, exact refit reference, plus refit_acceptance reference.
That external refit review requires status=accepted and exact refit reference.
The attestation commit follows the freeze commit. Valid UTF8 is checked before
runner digest sha256(utf8(text.strip())); literal blob hash remains distinct.
Gate requires running control and final_data_open=true, then the single fixed
final file is opened and exact original bytes verified before parsing/evaluation.

Outputs retain generic16 cases/960paths/28800ledgers/4800metrics,100 descriptive
comparisons/6000 paired rows,10 profile summaries. Each case has separate CSVs
under10MiB. Final fold/support/promotion values are null and inapplicable.
No development selection function is called. Referrals have zero denominator,
null outcome/screens and absent cases. Executed profiles use frozen own horizons
and tolerances, strict exceedance, failed final screens retained without fallback.
Prior is shared; fresh state, fee kernels, severe exact-float/tie/earliest-location
rules are reused. A post-access failure keeps staging, exposure and failure files.

Generated tests cover both honest task owners with actual temporary Git
publications, exact Git reference corruption, freeze text/blob/refit/control
gates, failure before any input-open, full60x30 input shape, fixed fee arithmetic,
future perturbations, ten referrals and ten eligible profile/fee own-horizon
outcomes, and descriptive contrasts without promotion. No original input is used.
