# Generated final-shaped path references

These are diagnostic accounting fixtures, not competition evidence or an
investment candidate. The stdlib-only generator reads no competition file.
It saves 24 toy rows, 32 rational paths, 192 ledger rows and 96 horizon metrics.
A full 60-by-30 fixture is constructed only in memory and hash-bound in the JSON.
The prefix callback is a deliberately simple timing witness. Three other modes
are the accepted fixed baselines, evaluated here on newly generated observations.

Run `python -B audit/chief/final_path_reference.py --check` to reconstruct both
saved files without writing. Re-creation refuses overwrite. Fractions are exact
p/q strings; CAGR and sample volatility use Decimal precision80. Binary64
implementation comparisons require documented tolerances. Rational locations
are not a substitute for final exact-float severe-case selection; separate
one-ULP and exact-tie witnesses retain that distinction.

The source hash, independent comparison against accepted synthetic arithmetic
and preparation limits are recorded in ../final-path-preparation-validation.json.
No final-capable implementation is approved by those checks. See
../../../specs/FINAL_PATH_ENGINE_HANDOFF.md for the later bounded review scope.
