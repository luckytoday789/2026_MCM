# Personalized development bridge - chief takeover preparation

This is implementation evidence, not production acceptance, a recommendation,
freeze, final-data permission or an experiment result. No original competition
CSV was read by these implementation checks. The original pure component and
generic writer remain unchanged.

## Published configuration and task contract

Use Python 3.12. Publish reviewed source commit **C**, then a fixed configuration
at a distinct descendant **E**, then an immutable command task on **E** at **P**.
The task owner may be `chief` or `hy3`, with its genuine owner branch and receipt.
Do not invent a worker receipt for a chief computation.

The configuration has exactly the keys exported as
`safeinvest.personalized_writer.CONFIG_KEYS`:

- `schema_version`: integer 1; `run_id`: uppercase identifier;
  `split`: `development`; `execution_authorized`: true.
- `source_commit`: real reviewed C; `source_sha256`: every exact canonical Git
  blob digest in `personalized_writer.CLOSURE`, with no missing/extra entries.
- `acceptance`: exactly `{"CHIEF-PERSONALIZED-20261020": C}`. The real chief source
  approval at `audit/chief/CHIEF-PERSONALIZED-20261020-review.json` must be present
  in E, with `task_id`, `kind=chief_takeover_approval`,
  `authorization=user-directed-two-node-takeover-20261020`, `reviewed_commit=C`,
  `code_verdict=approve`, and the exact `source_sha256` map. A proposed source
  is not approved by this document or the tests.
- `input`: the unchanged `policy_writer.INPUT_PATH` and `INPUT_HASH` under keys
  `path` and `sha256`; no input override exists.
- `policy_config`: `path=specs/development_policy_pilot_v2.json` and SHA256
  `d7b20f38196831befc80dfdcc69c6653d1ae8352d1c87c79e19bcc09d5c84df3`.
- `analysis`: exactly `task_id`, `result_commit`, `root`, `config_path`,
  `artifacts_sha256`, `acceptance_path`, `acceptance_sha256`, and `receipt`.
  Pin the actual accepted analysis producer commit and all six complete artifacts
  (five analysis outputs plus run_manifest.json), keyed by full repository paths.
  The positive exact chief result approval must exist at E. For worker/command
  receipts set `receipt={"path": real_receipt_path, "sha256": exact_git_blob_sha}`.
  A genuinely chief-origin result may use null only with an explicit CHIEF
  result approval of the prescribed takeover kind/authorization; this is never
  translated into a fictitious Sol or HY3 receipt.
- `execution`: exactly `required_python="3.12"`, `cpu_only=true`, integer
  `max_seconds` in 1..1500, and `max_artifact_bytes=10485760`.

The immutable task's parameters equal this configuration plus `config_path` and
the exact canonical configuration `config_sha256`. Its only allowed path is the
fixed output root. Its command is:

```
{python} -B scripts/run_personalized_development.py --config CONFIG_PATH --output OUTPUT_ROOT
```

The validation command appends `--check`. Set task `max_seconds` between the
configuration budget and 1500. The queue entry binds the actual task digest,
owner, attempt and `work/<owner>/<task>-a<attempt>` branch. Required deliverables
are exactly `personalized_writer.expected_deliverables(OUTPUT_ROOT, mapped)`,
where `mapped=map_assignments(recommendations, screens, split="development",n=120)`
uses the actual accepted upstream JSON. This function performs no simulation and
does not infer a class. It returns three root files plus six files for every
assigned profile/fee pair; referred pairs create no case directory.

## Authentication and completion

The CLI imports only standard-library modules until it has authenticated source,
configuration, immutable task, real upstream approval/receipt and all six exact
analysis artifact blobs. It then runs both original producer read-only checkers
in historical sparse checkouts and the actual accepted analysis read-only
checker in fresh Python 3.12 children with PYTHONPATH removed. Their genuine
exit status, complete logs, log digests and before/after inventories are saved.
Only after successful children does it import the new bridge or personalization
module. Checker failure cannot become a client referral.

The bridge repeats authentication, translates the actual ten recommendation and
thirty screen records, preserves upstream reasons, qualifying/indifference lists
and ordered metric keys, and authenticates the original fixed development input.
If any profile is assigned it reconstructs the same four full-horizon
calibrations and requires exact equality with both accepted generic producers:
each fold has 90 other scenarios by 30 years. Evaluation alone stops at own H.

For upstream referrals, the pure seam receives `rows=None, calibrations=None` and
original reasons; no simulator runs and outcomes/screens/exceedances stay null.
For assignments, each actual fee's fixed upstream class runs once at its own H
and tolerance. Failed personalized screens keep the proposed class and all
observed outcomes; no alternate class, bills proxy or new threshold is tried.

Every executed case has the existing five typed CSVs plus unchanged pure
`component_payload.json`. The ten-row root JSON retains each original payload
with its `source_verified=false` untouched. A separate bridge authentication
object and upstream hashes establish precisely the authenticated provenance.
The typed root CSV is a projection, not a replacement of the complete payload.
All nulls, booleans, signed zeros and adjacent binary64 values survive the codecs.

Output creation is exclusive. Partial files and a failed diagnosis survive any
execution failure; the successful manifest is published last. Every file is
limited to 10 MiB. The later-HEAD `--check` uses the saved immutable task/P binding,
authenticates original identities and historical LF/CRLF consumed-byte proofs,
recomputes only these authorized personalized cases, and rejects missing/extra,
wrong or rehashed-wrong outputs without writing repairs. It does not require a
live runtime task and never runs the original baseline experiment.

## Generated checks and practical limits

Run the focused suite with:

```
python -B -m unittest discover -s tests -p test_personalized_writer.py -v
```

Generated scenarios exercise all-referral, all-assigned, mixed fees/classes,
failed rescreens, invalid upstream assignments, complete full-period priors,
typed serialization, corrupted/rehashed outputs, failed staging, checker failure
before importing the bridge, and a real temporary Git checkout/later-HEAD replay.
The fixture arithmetic has 4 scenarios, not the original 120. On the all-assigned
fixture it has 648 ledgers and 40 metrics; these are test counts, not real client
assignments or observed production outcomes.

These checks are preparation and do not assert a complete genuine production
fixture with accepted original analysis evidence. The chief must review the real
C/E/P/receipt boundary, source closure, actual result acceptance and independent
own-horizon arithmetic before dispatch/acceptance. A raw production run has not
been performed by this helper. No final split API exists.

Validation history: the first attempted suite had a multiline-with syntax error,
which was corrected. Sandboxed Windows Temp rename operations then failed with
WinError 5; the same generated-only checks were rerun under the already-authorized
external execution path. One initial assertion incorrectly interpreted
`prior_mass` as training-row count; the field is the prior mixture weight, so the
test was corrected to check 1.0 and separately inspect all 90 actual training rows
in each generated fold. These failed checks are not positive evidence. A later
attempt to redirect logs before creating this audit directory did not execute
the suite; only an actual completed run with its real exit status is counted.
