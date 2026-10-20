# Generated all-development refit reference

Scope: future implementation/review support only. No competition CSV, refit,
policy evaluation, final result, freeze, task acceptance or customer assignment.

Run `python -B audit/chief/final_refit_reference.py --check` from the repository.
The checker reconstructs fixture.csv and expected.json and compares exact bytes.
It imports no project module. The full 120-by-30 shape is generated in memory;
fixture.csv is a separate twelve-row generated example. See
specs/FINAL_REFIT_HANDOFF.md for the later implementation and independent gates.

The 18 scalar values use exact Fraction inverse-cube moments and 90-digit Decimal
roots. Rational mathematical expectations and binary64 identity hashes have
separate purposes. The seven invariants check this reference construction only;
no future implementation is claimed tested. No independent acceptance is claimed.
