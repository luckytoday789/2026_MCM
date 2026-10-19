# Sol machine onboarding

Checked at: 2026-10-19 20:07 Asia/Shanghai.

## State

**等待主控发布启动包 / Waiting for the chief's startup package.**

Role: sol (engineering and independent verification). Chief: Astra. Compute role: hy3.

This is an onboarding record only. No project task has been claimed, executed, or accepted. No worker loop is running, and no persistent monitor has been installed.

## Repository and storage

- Remote: https://github.com/luckytoday789/2026_MCM
- Local checkout: `E:\2026_MCM\sol-coop`
- Observed `origin/main`: `c7adae903dd29ba053b809e7a0d37e08430f9377`.
- The checkout was newly cloned. Existing non-Git project copies were left unchanged.
- This record is published on `status/sol`; the formal status path and schema await the chief's protocol. It does not define a queue or a replacement protocol.
- No packages, skills, or system configuration changes were installed.

## Tool checks

| Check | Observed result |
|---|---|
| Git | 2.54.0.windows.1 |
| GitHub read access | `git ls-remote` and clone succeeded with authorized network access |
| GitHub write access | To be verified by pushing this branch and checking its remote ref; do not infer success from this text |
| Python | Bundled Python 3.12.14 runs; PATH `python.exe` is an unusable WindowsApps alias |
| Codex | CLI 0.162.1 runs; `codex login status` reports logged in using ChatGPT |
| CLI sandbox caveat | Codex reported access-denied warnings for its existing profile temporary PATH-alias directory; login status still exited 0 |
| GitHub CLI | `gh` is not installed; no installation attempted |
| Model configuration | Existing local model is `gpt-6.1-sol`; existing reasoning effort is `high` |
| Required worker settings | `gpt-6.1-sol`, `xhigh`; not yet launched or validated, no model substitution |
| Current task | None: authoritative queue unavailable |

## Missing authoritative startup files

All of the following are absent from the observed `origin/main`:

- `AGENTS.md`
- `ops/PROTOCOL.md`
- `ops/control.json`
- `ops/queue.json`
- `scripts/coop.py`
- `specs/PROBLEM_LOCK.md`
- `specs/ACCOUNTING.md`

The tree contains only `README.md`, three `audit/` documents, and `docs/PROBLEM_A_ZH.md`. The old README roles and branch workflow were not adopted. No mathematical parameters or accounting convention were invented, and no final-evaluation scenarios were opened.

## Required next event

The chief must publish the startup protocol, control state, queue, worker script, and locked problem/accounting specifications to `origin/main`. After fetching those files, Sol can follow the actual bootstrap procedure, select an eligible `owner=sol` task, and verify one real execution and receipt before reporting the worker as started.

There is no actual task-process or task-receipt validation yet. This onboarding record is not evidence that the collaboration loop has started.
