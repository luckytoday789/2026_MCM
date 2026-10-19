# Authorized overnight operation, 2026-10-20

The human asked all three existing computers to keep working while they sleep.
Routine repairs, repository updates and task dispatch remain authorized. Do not
wait for a chat reply when the issue can be safely resolved within this scope.
Do not buy credits, bypass quota/security controls, switch the assigned models,
upload private member identities, or submit the competition entry.

## Actual local mechanism

On the chief Windows host, `Start-NightWatch.ps1` starts one independent
`scripts/supervise_chief.py` process. It checks process ownership every 30 seconds,
saves a health snapshot at least every five minutes, and logs a progress/quality
checkpoint every 30 minutes. It uses a reversible process-level sleep prevention
request. A screen may turn off normally. It cannot prevent power loss, manual
sleep, a shutdown, a network outage, or exhaustion of model quota.

Health evidence is in ignored `.runtime/chief-health.json` and
`.runtime/chief-supervisor-events.jsonl`. The supervisor itself makes no model
calls. A healthy heartbeat is not evidence that a mathematical task advanced.
The normal runner still polls GitHub every 60 seconds and publishes its role
heartbeat. Health snapshots include exact recent process IDs, queue counts,
cached role status, most recent log and the chief work plan. Numerical quality
comes from actual task acceptance audits, never from this operational snapshot.

The supervisor adopts an existing chief runner; it does not start a duplicate.
It checks both worker and model child processes before clearing a stale PID lock.
It preserves all results, worktrees, logs and incomplete attempts. Unexpected
runner exits cause bounded exponential backoff (60 seconds through one hour).
An existing orphaned model turn is allowed to finish. A dirty main or unpushed
commit is captured locally and handed to one exclusive recovery chief turn;
the chief must preserve unfinished work and reconcile only authorized changes.
No new model turn starts while an existing child is still present.

Local STOP, global pause/completion and the 23:30 Beijing deadline are respected.
Never remove a human STOP automatically. For a planned restart, humans or an
active authorized coordinator first verify old processes have ended.

Local allowance protection, when explicitly enabled by the user, takes priority
over timed wakeups and automatic restart. See `ops/LOCAL_BUDGET.md`. Its configuration
and actual account readings stay in ignored local runtime files. Other machines
are unaffected; the chief's global project control remains running on a local
budget stop. The supervisor must not clear a budget drain after a quota reset.

## Keep useful work moving

`ops/chief-workplan.json` is a coordinator-owned one-shot timer and action list.
Each bounded chief turn MUST update it before committing/pushing:

- If useful chief work remains, schedule the next wake immediately or within
  five minutes and specify concrete unfinished work. Work in bounded turns.
- If only a remote result is outstanding, schedule a fallback check in 30
  minutes. Incoming receipts still trigger earlier turns without waiting.
- If awaiting a resource reset, set a concrete next check time and bounded retry
  policy. Do not keep invoking a model for unchanged idle heartbeats.
- On completion, set the plan inactive and global control complete after all
  required evidence, report rendering and packaging checks pass.

A consumed timer does not fire repeatedly. A turn must publish a fresh future
timer when further work is intended. Saving the start-of-turn result fingerprint
ensures a receipt arriving during a turn still wakes the following turn.

Use waiting time for a provisional cost-aware policy implementation, synthetic
unit/perturbation checks, report methods, traceability, plotting/formatting
preparation. Mark provisional evidence honestly. Sol independently reviews the
chief design and HY3 outputs before final claims or final-data release. HY3-003
already exists; do not rerun it. Keep the final split closed until the prescribed
freeze and review gates actually pass. Give HY3 a new pinned computation task
as soon as its code and parameters are reviewed and ready.

## Sol quota recovery without waking the humans

Two previous Sol attempts failed on the account's usage limit. Their preserved
logs suggest October 20 at 01:01 as the next retry time, without an explicit
timezone. Use Beijing 01:05 only as a cautious probe time, not guaranteed access.
SOL-010 is a single scripted probe on the actual Sol computer. Until its specified
time the script sleeps and makes no model requests. Then it invokes the assigned
Sol model once with a read-only, no-tools prompt and a five-minute timeout.
It records the real return code and exact expected reply in a hashed receipt.
This uses the existing login and subscription; it does not change account/model.

Only an exact successful SOL-010 receipt and response can establish current
availability. Then release the immutable SOL-008 and SOL-009 resource holds.
The probe does not guarantee enough budget to complete both reviews. If it fails,
retain all evidence, leave those reviews held, and schedule at most two additional
single probes during the night, at least one hour apart and never earlier than
any newly reported reset hint. Use new immutable tasks/attempts for those probes.
Do not resubmit full reviews just to test quota. If model access still fails,
record a concise help request and continue useful work whose gates permit it.

Routine checks stay in files. Surface completion, substantive failure or a real
need for human action. Background CLI work does not automatically post into the
original Desktop chat; never claim it can. The next human message can inspect
the actual GitHub receipts, local health snapshot and completed artifacts.
