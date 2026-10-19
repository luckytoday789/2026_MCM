# Narrow writer Git-portability correction after SOL-029

The exact predecessor is a24128200c849567cb6f7dba2d6f0e85a79f3713.
Its worker receipt says completed, but it is NOT accepted. Chief verified all
226 paths/46 source pins and ran both prescribed commands on a clean checkout:
15 tests pass; the required verifier fails with fixture byte inventory changed.
Chief independently recomputed 12427 persisted arithmetic facts successfully.
No production or final outcomes were opened. Original receipts and failed trials
remain immutable; the exact drafts are under audit/chief/quarantine/SOL-029.

## Reproduced W-LF-1 and smallest correction

Three failure.json files were written using Windows default text newlines and
recorded with CRLF byte hashes. Git stores JSON as LF. A generated partial.txt
was recorded as LF but a Windows checkout expands it to CRLF. Four hash/size
mismatches therefore occur after publication. Reconstructing precisely the four
recorded raw forms in a separate diagnostic worktree allows the full verifier
to pass, including seven artifact and twelve identity corruptions. This is
causal diagnosis, not permission to accept or silently repair old evidence.
The previous portable probe copied raw worktree bytes; changing HEAD alone did
not test transport through Git's clean/smudge and checkout behavior.

The successor SOL-031 has one objective: make this same writer and its NEW audit
reproducible from actual published Git bytes without weakening any guard.

1. Copy the three exact quarantined implementation/CLI/test drafts to their
   declared original paths. Keep accepted core code and mathematical parameters
   unchanged. Write failed staging JSON deterministically as explicit UTF-8 LF
   bytes, using the existing serialization convention. Ensure the new audit's
   generated text markers retain their exact bytes after Git checkout; a narrow
   audit/SOL-031/.gitattributes rule is permitted. Do not change root attributes,
   raw input, published historical fixtures, or global Git configuration.
2. Require positive SOL-031 approval alongside SOL-021/SOL-022/SOL-025. Both
   SOL-026 and SOL-029 remain cancelled; replacing or adding either as an approval
   must fail. Include this correction specification in the complete source
   closure. Retain every C/E/P/task/queue/module/source/config/input guard.
3. Adapt the quarantined verifier and recorder only into audit/SOL-031, binding
   the new immutable task/base/publication and final actual source. Exclusively
   create new fixtures/evidence after final code/docs. Do not rehash, repair,
   relabel or regenerate historical SOL-029 evidence. Keep strict byte hashes
   for success artifacts, input CSV, schemas and source proof. Do not hide W-LF-1
   by omitting failure fixtures, relaxing all hashes, ignoring mismatch counts,
   skipping required checks, or accepting arbitrary newline changes in data.
4. Add a REAL Git clean/index/checkout roundtrip of fresh audit fixtures and
   required source, using the actual pinned root attributes and new audit rule.
   Exercise core.autocrlf=true and false in isolated ignored scratch repositories
   or indexes only. Copying raw files into another directory is insufficient.
   Record actual Git commands, return codes, filtered blob and checkout hashes,
   sizes and attribute decisions, then run both prescribed Python3.12 commands
   in those exported views without any case-insensitive PYTHONPATH key or live
   .runtime/task.json. Verify later HEAD/publication identities as before.
   Existing Git objects may be supplied by alternates; no fetch, commit, push,
   checkout, ref/index changes in the assigned or main repository are allowed.
   git init/add/write-tree/checkout-index/config are permitted ONLY inside those
   isolated temporary repositories; no commits or model calls are needed.
5. Preserve meaningful failures and use fresh exclusive creation trials. All
   seven artifact corruptions (including a rehashed numeric cell), twelve source
   binding corruptions, typed signed-zero/adjacent-float/null/bool persistence,
   exact imports without baseline simulation, tiny-fee checks, output refusal,
   partial/oversize/timeout fixtures and unchanged-byte checks remain required.
   Add focused tests for deterministic failure JSON and real Git roundtrip.

## Bounded scope and gates

Only source writer, CLI, writer tests and audit/SOL-031 may change. No package,
helper, task, queue, existing audit, policy, personalized or analysis edits.
Use the prepared Python3.12 CPU environment and a <=1200-second task. This is a
small repair, not a rewrite or generalization. Preserve partial work and report
any actual blocker honestly; do not restart workers or probe model quotas.

No executable production configuration, competition input CSV, policy result,
freeze or final access is authorized. After chief acceptance, separately publish
accepted code C, fixed configuration E, then immutable HY3 commands tasks at E.
Actual result review and downstream research remain separate. A successfully
reconstructed old raw fixture or green local test alone never satisfies this gate.
