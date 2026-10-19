# SOL-026 quota interruption: narrow writer recovery

The exact failed attempt is e8733bbc9f1234e04a5e382046d3c89fc12cae7d.
Chief verified its immutable task, all 111 changed paths, 35 source pins and all
canonical artifact hashes. The actual model log ended on a usage-limit error
before prescribed parent checks. Missing required files are verification.json,
integrity-self-tests.json and clean-environment-checks.json under audit/SOL-026.
Chief replay at the exact commit passed 13 focused tests and failed the verifier
because verification.json is absent. This is not code acceptance. All original
branch contents and failure evidence remain preserved.

## Recovery scope for new immutable SOL-029

Use the pinned quarantine copies of policy_writer.py, run_development_policy.py
and test_policy_writer.py as drafts, copied to their original source paths. They
are not installed/accepted implementations. Review the actual delivered source,
finish the narrow binding/evidence work, and retain all five original writer
contracts. Do not rewrite accepted accounting, policy, calibration, case or
analysis code; do not add policy complexity, assemble analysis, or run competition
inputs. No original HY3-003 baseline is rerun.

1. The old config guard hardcodes SOL-026 as required writer approval. It cannot
   remain so: SOL-026 is failed. For this successor, require positive SOL-029
   approval alongside SOL-021, SOL-022, SOL-025, with exact task-base queue and
   chief evidence. Add a negative fixture where the old failed SOL-026 mapping
   is offered. Do not accept a cancelled/negative task or simply omit writer
   approval. Update boundary fixtures accordingly. The execution contract already
   says eventual writer task; no mathematical specification change is needed.
2. Copy/rework the old verifier only into audit/SOL-029, binding this new task,
   base, publication, source pins and final actual source bytes. Do not revive or
   fabricate old SOL-026 final evidence, copy creation evidence as if current,
   or edit historical handoff/audit files. Draft documentation describes planned
   clean-environment checks which had not been completed: replace such claims
   with actual successor evidence. Preserve old negative history by exact commit
   and hash; do not re-create large historical synthetic bundles unnecessarily.
3. Complete strict provenance guards and verification of saved consumed/imported
   source hashes. Verify checker behavior after HEAD advances and without a live
   .runtime/task.json; verify unchanged inputs/outputs/source after successful and
   rejected checks. Bind all declared modules and columns, typed null/bool/float
   values, exact accepted baseline imports and primary/doubled groups. Existing
   seven corruption categories remain mandatory, including rehashed numeric
   corruption. Use compact reproducible overlays rather than copied bundles.
4. Exclusively create fresh synthetic evidence from the final corrected source,
   final verifier and final audit documents, without self-hashing cycles. Then
   run both prescribed commands in fresh Python 3.12 subprocesses with all
   case-insensitive PYTHONPATH keys absent. Save real argv, return codes, logs,
   timing, module identities and original byte inventories. Preserve failures
   and stop honestly if the quota or another actual blocker recurs.

The new task must explicitly pin these recovery notes, the original contracts,
the quarantine drafts and the failure review. The resource hold is released
only after a successful real probe on the Sol machine. A focused green test
suite alone does not replace this fresh audit or chief independent acceptance.
No executable production JSON may be written until positive writer acceptance.
No final outcome access or change of freeze rules is authorized.
