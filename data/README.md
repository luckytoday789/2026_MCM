# Input provenance and split

The PDF and original CSV were supplied by the team for the 2026 MCM Senior Group Problem A, SafeInvest. The synthetic dataset is based on selected United States series from the Jordà–Schularick–Taylor Macrohistory Database, Release 6; it does not reproduce historical observations and is not a forecast.

The problem statement and supplied synthetic dataset are distributed under **CC BY-NC-SA 4.0**, for noncommercial use. Their original attribution and license are retained here. The files under `problem/` and `data/raw/` are unmodified copies. Files under `data/development/` and `data/final_holdout/` are row subsets derived from the original CSV; this split is the only transformation, and the same license applies. Checksums are stored in `data/manifest.json`.

Use `data/development/scenarios_001_120.csv` for development. Final outcomes in `data/final_holdout/scenarios_121_180.csv` are gated procedurally by the recorded freeze. Git directories are not an access-control barrier: every collaborator can technically read them, so the loader and task checks must enforce the study protocol.
