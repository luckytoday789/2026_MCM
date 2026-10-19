# Chief persisted-writer oracle qualification

This is preparation for independent review of SOL-029. It is not acceptance of
the failed SOL-026, the pending SOL-029, any production run, or a policy benefit.
No competition input or outcome is read. The exact old branch remains failed.

The new `audit/chief/writer_persisted_oracle.py` reads only the exact Git blobs of
a named saved synthetic fixture. It imports no SafeInvest module and does not
invoke an engine or regenerate a bundle. It uses rational arithmetic on the
binary64 inputs and 70-digit Decimal calculations to check fees, budget,
holdings, compounded CPI, deflation, annual returns, own-horizon CAGR/sample
volatility/drawdown, trade counts, quantiles and severe-case tie ordering.
Fee multiplication is checked exactly; other numeric comparisons use the locked
ordinary-ledger tolerances. Policy decisions and writer provenance require the
separate existing reviews and the exact new receipt.

`trial-001.json` and `trial-001-source.py` preserve the actual initial failure:
the chief oracle used `equity` where the generated input column is
`equity_return`. The one-line mapping correction is in the current source.
`trial-002.json` records the successful execution: 12,427 checks, 16 mode/fee
cases, 384 ledger rows, 192 metric rows and 48 summaries. Maximum observed
absolute numeric discrepancy is 1.865174681370263e-14. These are saved synthetic
fixture checks, not new competition experiments. Reproduce read-only:

```text
python -B audit/chief/writer_persisted_oracle.py e8733bbc9f1234e04a5e382046d3c89fc12cae7d audit/SOL-026/synthetic-8c7ac3f4217c4ac490ee4277a92041f6
```

`corruption-checks.json` pins the corrected oracle and records four reconstructable
in-memory CSV overlays, their original/altered hashes, and the real rejection.
They set a positive fee to zero, change CPI to 2, change growth to 500, and set
p90 loss to zero. No original blob was modified. The oracle checks arithmetic
independently of a bundle manifest's
success label or claimed file hashes.

For SOL-029, first validate its immutable task, exact new receipt, final source
and all prescribed evidence. Then run this oracle against that exact commit and
its fresh synthetic fixture, saving a new result. Do not reuse this older
qualification report as if it described the successor. Continue the independent
C/E/P binding, typed-persistence, reference-import and corruption checks before
any writer acceptance. Production execution and final-data gates stay separate.
