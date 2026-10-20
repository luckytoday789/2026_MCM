# Writer file deliverables compatibility correction

Chief provisional source, pending independent SOL-032 review. SOL-031 remains
accepted as its exact prior component; its historical evidence is unchanged.
The writer bind_task required the directory itself in task.deliverables, while
scripts/coop.py run_task requires every deliverable to be a file. Chief reproduced
this in the real local Git end-to-end runner fixture; computation and checker
commands succeed but the receipt fails. No HY3-004/HY3-005 task has been issued,
no competition input was read, and no numerical or final run occurred.

Replace only that output-declaration guard. For requested relative output root R,
require allowed_paths exactly [R], and deliverables to be the exact 44 distinct
file paths: R/run_manifest.json, R/checks.json, R/calibrations.json,
R/reference_imports.json, plus R/cases/M/T.csv for each of the eight fixed MODES
and the five fixed TABLES in the accepted writer. The list order is immaterial;
missing/extra/duplicate files, root-only declarations, wrong/sibling roots or
additional allowed prefixes fail before input access. Keep the exact CLI command,
C/E/P/publication/task/config/source/input/approval checks unchanged. The existing
runner remains unchanged and needs no remote restart. No policy/accounting,
fees, imports, numeric checking or output persistence behavior changes.

The complete source closure additionally includes this note. Future executable
configurations require both positive SOL-031 original writer approval and
positive SOL-032 independent compatibility review, alongside SOL-021/022/025;
failed SOL-026/029 remain forbidden. Old HY3-004.json/HY3-005.json configurations
are preserved unused preparation snapshots and do not satisfy the new guard.
After independent acceptance publish new source C, new distinctly named fixed
configurations E, then separate real-base HY3 commands tasks. No task was
previously published for those IDs, so this does not replace an attempt.

The chief change and focused tests require independent Sol review before use.
Test the unchanged real runner against generated files with the exact directory
allowed prefix and file-only deliverables, including canonical receipt hashes,
retry/deduplication and a missing-file failed receipt. Test binding positives and
negative output inventories with input access mocked to fail; use no competition
CSV or production configs. Preserve the initial failing regression and all
new failures. The old SOL-031 verifier remains replayable at its historical
exact source checkout; do not repair old hashes or present that check as evidence
for the modified source. New review evidence binds this exact source and task.
