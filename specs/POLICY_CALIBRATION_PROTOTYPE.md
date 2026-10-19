# Provisional calibration seam, 2026-10-20

Chief preparation under the authorized overnight plan; independent SOL-009
design and SOL-011 kernel reviews are still pending. This does not change either
immutable task, authorize a competition-data policy run, or freeze a policy.

`src/safeinvest/policy_calibration.py` accepts explicit generated CSV bytes only
through `build_synthetic_calibrations(data, scenario_count=..., periods=...)`.
There is no path loader, command-line entry point, final split, or all-development
refit API. It is not exported from the package. Its result manifest always says
synthetic and production_execution_authorized=false. This is a software seam,
not a sandbox that can prove what a caller's supplied bytes represent. Tests
construct all their own rows and never open competition CSVs.

The input must have the six original fields in order, complete unique sorted
scenario/year keys, and finite returns/inflation greater than -1. Synthetic
scenario counts must be a positive multiple of four. Fold assignment is
(scenario_id-1) mod 4; each prior uses every annual observation of the other
three folds equally. The real gross transformation is exactly (1+r)/(1+inflation).
The empirical prior is the existing provisional kernel's immutable container.
There is no optimization, time-series concatenation, new parameter, or policy
outcome computation.

## Provenance contract

Each frozen bundle records the SHA256 and length of the exact supplied input
bytes. Each frozen fold records sorted training/evaluation IDs, every training
(scenario_id, period) key, its immutable real gross rows, and two distinct hashes:

- `training_rows_sha256`: the compact ASCII JSON object with schema
  training-annual-simple-v1, fields in the original six-field order, and rows
  [integer scenario, integer period, four float.hex strings in return/inflation
  order]. Object keys are sorted, separators are comma and colon, and there is
  no whitespace or trailing newline.
- `real_gross_sha256`: the same canonical JSON rules with schema
  training-real-gross-v1, asset_order containing the three return field names,
  and rows [integer scenario, integer period, three float.hex gross strings].

Digest schemas deliberately distinguish source nominal observations from derived
real vectors. Two different nominal/inflation inputs can produce identical real
vectors; those training source hashes must differ even if the gross hash agrees.
LF and CRLF inputs have different file hashes but the same selected-row hashes
when their parsed values agree. Exact source bytes and consumed source bytes are
still the future driver's responsibility; a calibration manifest does not bind
code provenance by itself. `manifest()` returns fresh JSON containers so changing
one cannot alter the frozen calibration.

All rows are checked for valid numerical factors before calibration. Detecting
an invalid evaluation row is input validation, not use of its outcome to fit its
own prior. Changing valid outcomes in evaluation fold f must leave all of fold
f's training IDs, keys, row/gross digests and prior unchanged. The global input
digest and the other folds' legitimately affected training digests must change.

## Executed evidence and review gates

Ten chief-authored synthetic tests passed on Python 3.12.0; the timestamped log
and exact source hashes are in audit/chief/policy-calibration/. They include an
independent rational real-gross/CE fixture, exclusion under fold perturbations,
complete keys, deterministic serialization, distinct source/gross provenance,
invalid input rejection, immutable state, and a generated 120-by-30 shape with
four sets of 90 training scenarios/2700 training rows. These are computational
fixtures, not strategy performance or independent acceptance. No failed run was
observed in this initial focused test execution.

A separate narrow Sol review must independently challenge exclusion, weighting,
parsing, numerical conversion, canonical digests and mutation boundaries. Release
only after the design and dependent kernel are accepted unchanged; otherwise
preserve this draft and issue a corrected task against pushed sources. The future
production driver needs the fixed development path/hash, a new reviewed production
entry point, source and artifact manifests, result/check writers, and the existing
selection/suitability checks. Neither this file nor its review authorizes HY3 to
run a policy experiment. Do not rerun the submitted HY3-003 baseline job.

The existing backtesting-frameworks skill (wshobson/agents,
0874a27b17a22e2b7c2e2bcd725768e0803cad06) and backtest-validation skill
(artheras/skills, 825040f3cc7eb4179a8ee86e0158d9828f427f7b) informed isolation,
provenance and trial-record discipline. Both were already pinned in
ops/skills-lock.json. No external code or new skill was installed. The problem's
independent synthetic annual scenarios, exact fees and split override generic
historical, daily, or Sharpe-based validation suggestions.
