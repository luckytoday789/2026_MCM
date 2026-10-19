# Three-computer protocol v1

## Roles

| Role | Model/client | Responsibility |
| --- | --- | --- |
| chief | GPT-6 Astra xhigh / coordinator Codex | Mathematical decisions, clear task specifications, policy design, integration, evidence selection, final English paper |
| sol | GPT-6.1 Sol xhigh / remote Codex | Accounting/backtest implementation, targeted tests, independent review of chief's policy and HY3's experiments |
| hy3 | HY3 / remote WorkBuddy | Supervise deterministic Python worker, run specified experiments, preserve ledgers and checks, diagnose/report execution failures |

This is a responsibility allocation, not a measured claim about HY3's relative intelligence. Numeric work is done by Python, not model mental arithmetic. Computational volume is tiny (three assets, 5,400 annual observations); all nodes can use CPU. GPU on chief is optional.

## Branches and directories

- `main`: accepted code/specifications/results/report plus coordinator-owned dispatch queue.
- `archive/pre-coordination-20261019`: historical setup before this protocol.
- `work/sol/<task>-a<attempt>` and `work/hy3/<task>-a<attempt>`: one immutable task attempt each; completion receipt is `handoff/<task>/result.json`.
- `status/chief`, `status/sol`, `status/hy3`: lightweight machine status with single-writer leases. These branches contain only `status.json` and are never merged into main.

| Directory | Purpose / authority |
| --- | --- |
| `problem/`, `data/raw/` | Original source files, no worker edits |
| `data/development/` | Scenarios 1–120 |
| `data/final_holdout/` | Scenarios 121–180, final gate required |
| `specs/` | Coordinator's mathematical and experimental contracts |
| `src/safeinvest/`, `tests/` | Implementations and meaningful checks; modified only by assigned tasks |
| `results/development/`, `results/final/` | Machine-readable results with run provenance |
| `audit/` | Independent numerical review and findings |
| `report/` | Final manuscript, figures and evidence-to-claim mapping |
| `ops/tasks/`, `ops/queue.json` | Coordinator dispatches immutable tasks and records acceptance |
| `ops/prompts/` | Forwardable onboarding and coordinator continuation |
| `scripts/` | Common tools; coordinator-maintained |
| `handoff/` | Task result manifests, evidence and diagnosis |
| `.runtime/`, `.venv/` | Ignored local state, logs, worktrees, credentials-free settings and environment |

## Task state and ownership

`waiting -> ready -> worker running -> submitted completed/failed -> coordinator accepted or new attempt`.

Queue state is coordinator-owned: `waiting`, `ready`, `accepted`, `cancelled`. Worker execution states live in status/result manifests, not in a shared mutable queue. Owner is explicit; workers cannot steal work. A local exclusive PID lock plus a remote ten-minute role lease prevents accidental duplicate workers. If a machine crashes, inspect the lock PID before removing a stale local lock; a different machine waits for lease expiry or obtains an explicit handover.

An immutable task has id, attempt, owner, 40-character base_commit, kind, dependencies, instructions, permitted paths, deliverables, explicit commands/checks and timeout. Do not edit a published attempt. A changed task needs an incremented attempt (and new branch); a different objective needs a new id. Queue statuses may change without changing task contents.

The runner uses a separate worktree at the pinned base. It does not merge arbitrary current main into an in-flight experiment. It checks the changed paths, tests and required output files before committing and pushing. No force push is used. The input/source version remains traceable even if main advances while a computation runs.

## Acceptance and self-checks

1. Structural checks: task identity/hash, branch, source commit, permitted paths and required outputs.
2. Deterministic checks: expected fixtures, accounting identities, inflation, weights, no-lookahead perturbation, split guards and input hashes.
3. Independent review: chief reviews Sol implementation; Sol independently recomputes selected chief/HY3 outputs. A model writing both code and tests is not independent validation.
4. Result promotion: chief inspects the exact result commit and actual reports, resolves any required review, integrates only accepted changes, and records the reviewed SHA in the queue. A worker's word “completed” is not enough.
5. Research checks: record every candidate, use only development outcomes to tune, freeze policy/metrics/parameters/selection rules, then final evaluation once with no further tuning. Final bug corrections remain disclosed and do not erase contamination history.

Receipt format note (2026-10-19): new receipts declare
artifact_hash_basis=canonical_git_blob and hash staged Git bytes after line-ending
normalization. Validate against exact published blobs. Older receipts hash local
checkout bytes: document CRLF reconstruction and quarantine any unverifiable
artifact. Never rewrite a historical receipt. Workers load runner changes after
an orderly idle restart; machine status now retains the Python version.


`ops/freeze.json` must bind code SHA, parameters, metrics, severe-case rule and input hashes. A final task supplies SHA256 of its canonical UTF-8 contents (strip outer whitespace, matching the runner's `git show` read), and `ops/control.json.final_data_open` must be true. This is a procedural study gate, not protection against collaborators deliberately opening a tracked file.

## Start the two remote machines

Forward `ops/prompts/START_SOL.txt` or `START_HY3.txt`. Each machine clones this repo, logs in to GitHub with its own account, and has collaborator write access. Git pushes must work without a recurring login dialog before starting a background runner. Do not share credentials.

Create a local Python 3.12 virtual environment and install `requirements.txt` for numeric jobs. Metadata validation and the runner itself need only standard Python. Commands below assume `python` is the selected interpreter:

```text
python scripts/coop.py doctor --role sol
python scripts/coop.py watch --role sol --backend codex
```

For WorkBuddy's machine:

```text
python scripts/coop.py doctor --role hy3
python scripts/coop.py watch --role hy3 --backend commands
```

The HY3 worker is intentionally deterministic: it runs the coordinator's commands. WorkBuddy handles setup and failure explanation. A local WorkBuddy scheduled task can periodically check its `.runtime/hy3-status.json` / `hy3-error.json` and report only a meaningful change; it must not start duplicate workers. Use the actual WorkBuddy scheduler, not an assumed CodeBuddy CLI. Do not use cloud scheduling for files that exist only on this local machine.

Run `python scripts/coop.py once --role ... --backend ...` for a single cycle. `python scripts/coop.py status` reads all machine states. `python scripts/coop.py stop` writes a local STOP file. To resume, inspect unfinished work and remove only that known STOP file, then restart. Do not delete `.runtime/` wholesale: it can contain unfinished task worktrees.

For unattended Windows use, launch the command with a hidden background process and redirect logs to `.runtime/`; keep the computer awake and network connected. On macOS/Linux use the platform's process manager. Login prompts, sleeping computers, model quotas and denied permissions can stop progress; report actual process and remote status rather than claiming “always running.”

## Coordinator loop

`python scripts/coop.py watch --role chief --backend codex` watches task-branch changes and worker registration/error changes. Its first pass records the initial state so it does not duplicate bootstrap work. Meaningful changes invoke GPT-6 Astra xhigh with `CHIEF_TICK.txt`; idle heartbeat changes do not invoke the model. Chief serializes integration and dispatch, then pushes main. The runner stops after two consecutive infrastructure failures, local STOP, project stop state or the configured deadline. A failed task is not automatically rerun; chief creates a corrected attempt.

There is no automatic wakeup of this exact original chat from a background process. During an active chat, the coordinator reports needs here; background work records needs in status/error files and GitHub, and the remote clients can surface them using their own notification mechanisms. Avoid claiming an unattended process can send a chat message unless that integration has actually been configured.

## Research stages

1. Bootstrap, environment registration and data validation.
2. Sol implements and challenges the accounting/baseline contract; chief independently checks fixtures and locks metrics.
3. Chief specifies static candidates, suitability and conservative cost-aware policy; HY3 runs explicit development experiments.
4. Sol independently audits no-lookahead, costs, metrics and representative ledgers; chief chooses the simplest supported strategy and issues sensitivity jobs.
5. Freeze the exact final protocol. HY3 runs one specified final evaluation. Sol verifies evidence and chief decides recommendations without tuning to final outcomes.
6. Chief writes/integrates the English <=10-page report and <=50MB code supplement. Sol checks evidence and mathematical statements; HY3 regenerates specified final tables/figures. Humans supply member names and submit.

## References for execution adapters

- Codex supports scripted `exec`, structured results and saved CLI login: https://learn.chatgpt.com/docs/non-interactive-mode
- WorkBuddy supports local scheduled tasks and model/workspace selection: https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Automation-Guide
- Model assignment rationale: https://developers.openai.com/api/docs/guides/model-selection
