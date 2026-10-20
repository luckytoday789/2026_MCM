# SafeInvest competition research

The repository implements the supplied 2026 MCM Senior Group Problem A using annual simple returns, exact inflation deflation and the disclosed one-way transfer fee convention. Python 3.12 and `requirements.txt` define the numerical environment. Three assets and 5,400 annual rows fit comfortably on CPU.

The authoritative project requirements are in `specs/PROBLEM_LOCK.md` and `specs/ACCOUNTING.md`. Use development scenarios 1–120 for research. Reserved scenarios 121–180 are evaluated only after the recorded complete freeze and separate freeze audit. No policy tuning follows that evaluation. The supplied scenarios are synthetic competition inputs; preserve the attribution in `data/README.md`.

Chief alone integrates main and defines immutable tasks. Existing remote Sol implements/reviews assigned work; HY3 executes reviewed fixed commands. The current user-authorized chief + HY3 takeover is recorded in `ops/TWO_NODE_TAKEOVER.md`. Current accepted commits and pending work are in `ops/queue.json`; the latest bounded checkpoint is `ops/TAKEOVER_PROGRESS.md`. Status branches contain operational metadata and are never merged. Do not start duplicate role workers or coordinator loops.

Accepted development evidence includes the baseline, primary and doubled-fee experiments, fresh independent doubled verification, and HY3-009 analysis. The frozen development promotion criteria retain fixed-prior Balanced; they do not support contextual or automatic-target complexity. This selection is not universal customer suitability. Own-horizon personalized rescreens, all-development refit, final freeze/evaluation and manuscript acceptance are distinct gates recorded in the current queue. A successful worker push alone is not acceptance.

`report/submission-draft.md` and `report/build_submission.py` assemble evidence-bound English content. Until every required gate passes, the output remains explicitly incomplete. The final report must be at most ten A4 pages with minimum 11-point text, three member names and an AI-use disclosure. The source supplement must be at most 50 MB. Private names and IDs remain in the local delivery copy; they are never pushed to GitHub.

The human team leader reviews and submits the final deliverables by 2026-10-20 23:59 Beijing. The automation deadline is 23:30 Beijing. No automatic submission is authorized.
