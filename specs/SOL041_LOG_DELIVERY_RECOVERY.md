# SOL-041 delivery recovery: original logs only

The exact candidate 1f7f328313a5976aa9ff60375432d61457f7d811 has a completed
worker receipt but is NOT accepted. Chief authenticated 29 changed paths,
28 canonical artifact hashes and 42 source pins. A fresh actual Git clone at
that exact SHA, Python 3.12.0, no PYTHONPATH and no runtime task exits 1 in
clean_record(): writer.stdout.log is absent. All four named writer/portable
stdout/stderr logs are absent from Git. Root *.log ignore rules are the likely
delivery cause; audit/SOL-041/.gitignore contains no exception. The original
receipt, local passes, numerical files and missing-log failure remain immutable.
HY3-006 is still pending independent acceptance. No numerical discrepancy has
been established by this delivery failure.

A NEW audit-only Sol task may recover the FOUR original files from the preserved
SOL-041 worktree/isolated clone. Copy exact bytes into new audit files ending
.txt (or explicit task-local ignore exceptions), and require each original
recorded SHA256. Preserve a local-source inventory and provenance without
publishing credentials or unnecessary machine paths. Do not recreate expected
stdout from known JSON, regenerate metrics, rerun the writer, edit old audit
files, or infer success from a parent exit. If any original log cannot be
recovered with its exact hash, return a precise failed finding. No writer retry
is authorized by this repair.

Bind the new immutable task/digest/base separately. Authenticate the entire
old canonical receipt/task/source closure and every old artifact against the
exact Git commit, plus old clean and portability records and all four recovered
log hashes. Preserve the chief rejection. Use an ignored NEW isolated actual
Git clone, without network or branch changes, checkout the exact old commit,
strip every case-insensitive PYTHONPATH, and place only the four hash-verified
logs into their original names there. The original verify.py and independent.py
must remain byte-for-byte unchanged. This repaired disposable clone is a review
reconstruction, NOT the original delivered tree and NOT retroactive acceptance.

Run original Python -B audit/SOL-041/verify.py --check once in that isolated
reconstruction, with no .runtime/task.json and a bounded timeout. This invokes
no writer and independently replays the full original arithmetic/fixtures. Save
real argv,Python,exit,duration,stdout/stderr and before/after evidence inventories.
Require original review/source/evidence bytes unchanged; separately identify the
four recovered untracked log files. The new portable verifier must independently
reconstruct and replay that exact audit after HEAD advances without runtime task
metadata, using locally present Git objects and the recovered published bytes.
Do not merely trust saved pass flags or skip clean_record. Keep --check read-only
to source and expected evidence; temporary ignored clones are permitted.

Demonstrate missing recovered log, changed log bytes, rehashed false claimed
log metadata, wrong original source/task, and altered original numerical evidence
are rejected without modifying protected bytes. Use the original17 corruption
and20 future-perturbation checks through the unchanged original verifier.
Avoid duplicating the original large audit bundle in main: use exact Git objects
and only new repair evidence. All four recovered files must survive an actual
Git add/commit local roundtrip with normal ignore rules; no force add concealment.
Run the new --check on that exact local committed tree. Keep original and repair
Git inventories and actual durable logs, not just digests. Parent owns final push.

Scope: only new audit/SOL-043, CPU/Python3.12, <=1200s total. No competition
input selection or producer generation; no source/spec/old-evidence edits,
worker restart,account/package/model changes,fetch,network,push or final access.
Chief must review exact new commit before either review or HY3-006 acceptance.
