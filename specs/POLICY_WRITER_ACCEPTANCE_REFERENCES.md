# Prepared writer acceptance references

These chief references were prepared after accepted SOL-022 and before a writer
implementation exists. They are expected import/compatibility values, not writer
acceptance, a production implementation, or a new experimental result. The
contracts in POLICY_RESULT_WRITER.md and POLICY_WRITER_COMPATIBILITY.md remain
authoritative. Do not publish the writer task until the case-engine repair successor SOL-025
is independently accepted and its code is on a pushed main commit. SOL-023
remains a preserved failed attempt and cannot satisfy this gate.

Pin audit/chief/writer_reference.py and audit/chief/writer-reference.json in the
future writer task. The script uses only standard-library code and exact accepted
HY3-003 Git blobs, without importing the baseline engine or reading competition
input CSVs. It verifies the receipt and acceptance hashes and complete row keys
for 10,800 ledger rows, 1,800 metric rows and 15 summaries. Every source cell is
preserved through an explicitly invertible mapping:

- policy -> mode, year -> period, action -> engine_action;
- growth_units: the inherited literal percentage points per year -> percent/year;
- no numerical rescaling, rounding or reinterpretation.

Saved per-table/per-mode hashes describe ordered lists of source or normalized
string-cell records, serialized as compact ASCII JSON with sorted object keys.
They are expected derivatives, never replacements for original artifact hashes.
The future writer may add fee/fold and declared inapplicable diagnostic columns;
compare its inherited columns to this reference with original declared types and
exact floating values. Do not compare unrelated added columns or assume that a
different CSV display spelling changes a binary64 value. Original source blobs
and the accepted receipts must remain untouched.

The separate synthetic boundary fixture includes 0.01 percent/year, signed zero,
the two immediate neighbors of 0.1, null, false and true. It records float.hex and
exact types. Map the outward growth label back only in a detached analysis-input
copy. The precomputed subtraction is the actual binary64 0.11 - 0.01, not a
rounded decimal replacement. Preserve threshold comparisons at that exact value.
Paired growth difference units are unchanged. Unknown unit strings must fail.

The prepared script checks JSON round-trip semantics only. The actual writer
must declare and test its CSV column types, especially empty nullable cells and
booleans. It still needs all missing-file/numeric/source/config/key/count/status
corruption cases, read-only replay, production source/input authentication and
failure preservation required by the writer contract. These remain untested
until the implementation is delivered; three successful oracle-corruption
rejections in writer-reference-validation.json are not a substitute.

Reproduce the prepared reference read-only:

    python -B audit/chief/writer_reference.py --check

Default creation refuses existing evidence. Scratch corruption copies and exact
original hashes were used without modifying baseline or accepted audit files.
No baseline rerun, policy computation, final access, source refactor or new
policy parameter was introduced.
