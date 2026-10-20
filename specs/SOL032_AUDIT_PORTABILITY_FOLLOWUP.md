# Follow-up for SOL-032 audit checkout portability

The exact SOL-032 delivered checkout passed all prescribed checks and its source
review/22 boundary cases/real44-file runner proof remain valid. Chief accepted
only its narrow writer compatibility scope at d168757efbc70e4641deacc911976f1fa3bd7a7c.
A later additional check on main failed at the old-evidence inventory comparison.
The original failure and all evidence remain unchanged; no check is relabelled.

Diagnosis found111 differing raw checkout hashes, exclusively LF/CRLF differences
in historical text/spec/test files. Every differing file has exactly the same
normalized bytes as both its original pinned Git blob and the passing delivered
checkout. There is no policy, computational source, parameter, input or outcome
change. Source C, fixed configs E and immutable HY3-004/005 tasks stay unchanged;
there is no justification to rerun, cancel or retune those computations.

A new independent audit-only task must bind the exact original task/digest/base,
reviewed SHA and original evidence, then distinguish canonical Git identity from
allowed checkout transport bytes. Preserve old SOL-032 verifier and every hash;
never rewrite its inventory, broaden production source guards or normalize binary
assets. The new checker may reuse unchanged source_facts, boundaries and runtime
proof replay, but must independently compare canonical inventory against original
pinned blobs and actual checkout bytes. Accept only explicitly demonstrated text
LF/full-CRLF spellings; reject changed content, arbitrary mixed conversion,
missing/extra paths, changed count/runtime payload and modified/rehashed proof.
Use actual isolated Git checkouts with autocrlf=false and true, then later HEAD
without a live task. No original CSV, simulations, production config execution,
writer changes or remote process restart. New evidence lives only in its new
audit directory, with read-only --check and preserved failures.

This is an audit replay portability limitation, not evidence of a numerical
failure. Chief acceptance addendum records its scope; actual case results still
need targeted independent numerical review before acceptance or policy claims.
