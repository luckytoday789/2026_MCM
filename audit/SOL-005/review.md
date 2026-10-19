# SOL-005 receipt and provenance review

Status: passed. Material blockers: 0.

Reviewed HY3-002 exactly at 9fdd20e09f8c080b7d3381d3d545524084cb3955, chief acceptance/release at da96ea77bcc476f2970a982f037c2679a68522b7, and accepted SOL-003 evidence at bb74c0f25cb18c3e02fef6d51416422514a8f503. SOL-005 dispatch is pinned to fa7856618626b2534524d18ac25fbca6fcc4cdcb.

The binary Git audit checks the immutable task digest, role/attempt, queue branch binding, actual single parent, allowed paths plus the runner handoff exception, seven added files, six canonical artifact hashes, and integrated bytes. It checks all four prescribed argv/exit records and retained logs against both JSON outputs. Receipt Python and environment Python must both be 3.12.10; the preflight must explicitly pass. Exit labels alone are insufficient.

The HY3 task was published after its source base and is read at the chief base, not assumed present in the result tree. The actual result parent is c651c67c30db1131c25641ac94631238cba0dd8d. Source PDF/CSV bytes, manifest and both exact checker scripts match the prior independent review. The input-check JSON has the same canonical hash b6bff43d5ad3ea27a5f103acfcd4ebc425a62788c0f6a70d7bb4d1790deaa3cf and matches SOL-003 metadata and chief saved rerun field for field.

Reused proof: SOL-003 verification.json sources, metadata, zero residuals and its binding to the original HY3-001 metadata output; exact source/checker equality is established here. SOL-003 independently verified source hashes, schema, complete unique keys, valid finite gross cells and exact splits. The old execution remains rejected for Python 3.13.14. Its original receipt/artifacts and rejection remain available at pinned objects; cancellation remains recorded. The corrected environment is new receipt evidence, not a new investment experiment.

The release registration is compared with its pinned status commit, including Python and lease timing. Chief equality and carry-forward scope are supported only for identical deterministic metadata under a corrected interpreter. The final gate is closed at the source/result/review/base/dispatch versions. This audit applied no strategy to any final data.

Limitations:

- Reuses only SOL-003 independent source/split metadata proof at the explicit accepted commit.
- No CSV numeric analysis, strategy run, numerical experiment or prior 32-test suite was rerun.
- Python 3.12.10 is supported by receipt, both retained preflight logs and environment JSON; these are retained evidence, not remote process attestation.
- Chief metadata-rerun equality is verified against its saved report; its separate process was not rerun or independently attested here.
- Git commits have no intrinsic branch: immutable queue branch/commit binding is checked; no current checkout branch is used.
- Cancelled HY3-001 receipts remain in their original Git objects; no old Python 3.13 execution is accepted.
- This review certifies neither investment performance, SOL-004 future driver nor any future HY3 result; it does not open the final gate.
- Final input bytes are hashed only; no strategy is applied to final inputs.

Validation: python -B audit/SOL-005/verify.py --check. Initializer writes each evidence file only if absent; check recomputes all facts from explicit Git objects, compares saved evidence and review text, and never rewrites them. Local review text/code hashes use UTF-8 LF normalization to permit ordinary Git CRLF checkouts; all source/receipt/output provenance hashes use exact binary git show bytes.

Blockers and concrete fixes:

- None.
