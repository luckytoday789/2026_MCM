# Exact doubled-fee development result: independent review contract

This is the handoff for SOL-041. It is an independent review, not an upstream
result acceptance or final-data permission. Source accounting and policy code
already have their separate narrow reviews. Keep their approved bytes fixed.

The sole candidate is HY3-006 attempt 1 on work/hy3/HY3-006-a1, exact commit
319781ef3c7fb5d4328a0ae4cea438bcc26a6f18. Its canonical JSON task digest is
dcdf31a5ce502b4c5115d9a21a29b6649ea107b8e0c8b671b1e17d44812962b6.
Source C is bc04d428425a9afbea799e036213632dc6568c73; configuration/base E is
eae30c8edff452807694b9c8f42db6d1d01464f7; publication P is
fb0fcfa6caeee8eb2768c623952003bd82675191. E precedes P on origin/main.
Task identity, all source/config/input hashes and all candidate artifact hashes
are repeated in the immutable task. Task Git-blob hash means complete raw Git
bytes; it is separate from the sorted compact JSON digest.

Read specs/DEVELOPMENT_CASE_RESULTS_REVIEW.md in full. Independently inspect
this candidate before consuming any chief PASS labels. Useful existing chief
helpers read exact Git blobs without importing SafeInvest arithmetic. They may
support a review but do not replace fresh independent expectations. State the
scope of all reused oracles and all samples.

Review scope:

- Exactly 44 result files plus four parent check logs and one parent receipt,
  only the assigned development input, Python 3.12, CPU and k=0.005. Eight cases,
  28,800 ledger rows, 4,800 metric rows, 40 summaries, 18,000 decisions and
  17,585 actual score rows. There are no imported baselines in this group.
- Rebuild the four 90-scenario/2,700-row training complements and their ordered
  nominal/real-gross digests; no evaluation scenario may enter its own prior.
- Recompute all saved scenario metrics and summaries independently; inspect
  representative complete paths, severe paths, initial deferral, target changes,
  human-review latches and the 1e-10 reporting threshold without cancelling fees.
- Recompute representative CRRA/CE values and action boundaries independently
  across all four folds and five policy modes. Context uses completed years
  only, prior mass 15 and min(5,t-1), gamma 4; alternatives start in year 6.
  Preserve tie-order and global-max rules. Double the cost hurdle, charge the
  actual fee once, and never assume cross-fee holdings/actions are identical.
- Generate compact isolated future-perturbation and at least 12 meaningful
  corruption cases, including numerical changes with updated hashes, missing
  file, source/config/task mismatch, duplicate key, false count and incomplete
  status. Save expected/observed facts and before/after protected inventories.
- Perform exactly one new read-only writer --check in a fresh actual Git
  checkout at the exact candidate SHA, with Python 3.12 and every
  case-insensitive PYTHONPATH variable removed. No .runtime/task.json. Persist
  inventories and direct stdout/stderr files before launch, allow at most 600
  seconds, and retain real exit/timing/log hashes. A failed check stays failed:
  return the complete negative finding without another check or regeneration.

The saved generation runtime is 370.672 seconds under the unchanged 1,200-second
writer limit. The parent task limit is 1,500 seconds. The receipt records four
command exits but no per-command wall durations; disclose this precise evidence
limit. The chief's separately measured read-only run does not establish the
remote review result. Do not call an observed generation time a measured total
parent duration.

HY3-005 failed at 665e14502405ca560fe1f78876a189ae5f688f23 with a timeout,
partial outputs and a status-push error. Preserve it. The rerun changes run_id
only; the 15 saved files of its three partial cases match the new candidate
byte for byte. This is reproducibility evidence, never retroactive acceptance
of the failed task. HY3-004 primary remains a separate unaccepted candidate at
6aa2ccdce80834c8beb52a827993f1f587d1d8a6; SOL-040 reviews it. Shared calibration
bytes may be authenticated without comparing outcome rankings or choosing a
policy. SOL-036's interrupted/quota-failed review remains failed.

Only a real accepted SOL-037 response releases this task's resource hold. No
model/account changes, extra probes, purchases, worker restarts or new producer
run. No final outcomes or customer assignments. Do not edit production source,
source data, old evidence or prior task definitions. Only new audit/SOL-041
files are deliverables. Aim model work complete by 1,100 seconds, leaving the
parent's validation time within 1,500 seconds. Save partials/failures honestly.

The portable audit/SOL-041/verify.py --check must bind this new task/base and
exact producer bytes, replay meaningful arithmetic and corruption checks after
HEAD advances, and work without runtime task metadata. The chief reviews its
exact commit before accepting either review or producer. Even positive numerical
acceptance does not select a policy, approve analysis assembly, freeze a final
protocol or open the holdout.
