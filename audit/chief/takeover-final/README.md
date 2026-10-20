# Chief takeover: generated final components

Scope: generated supplied observations only. No competition refit, final file,
freeze, production loader, task publication or policy decision was executed.
The user's two-node takeover authorizes this local chief implementation; it is
not a replacement remote Sol role or a historical acceptance of new source.

API example (all variables below are explicit generated fixtures):

```python
from safeinvest.final_refit import build_generated_refit
from safeinvest.final_paths import simulate_generated_final_path, final_prefix_metrics

refit = build_generated_refit(generated_csv_bytes, scenario_count=120, periods=30)
path = simulate_generated_final_path(
    generated_one_scenario_30_rows, mode="balanced_context", prior=refit.prior,
    horizon=30, fee_rate=.0025, review_drawdown_pct=25.0, split="final",
)
assert path.result.split == path.result.metrics.split == "final"
assert not path.metadata()["production_execution_authorized"]
own_horizon_metrics = final_prefix_metrics(path, 15)
```

`GeneratedRefit` consumes all ordered supplied rows exactly once and constructs
one immutable `EmpiricalPrior`. Its detached manifest uses the existing nominal
and gross hash payload schemas. No OOF fold is fabricated. Path wrappers create
fresh policy state each call and use that prior by object identity. Metadata
truthfully identifies generated, unverified, unauthorized inputs. The strict
30-row adapter rejects malformed unused suffixes after requested decisions;
current outcomes are accessed only after their decision, tested by a Mapping
access trace. Prefix metrics are calculated with a true final label.

Two old files have only a private arithmetic extraction: `backtest.py` retains
public split, shape, fee and ID guards before `_simulate_policy_arithmetic`;
`metrics.py` retains public split guards before `_compute_metrics_arithmetic`.
The accounting loop, scalar arithmetic order and metrics formulas are unchanged.
No old calibration/case/personalized/writer module was modified by this work.

Verified commands used project Python3.12 and generated inputs:

- `python -B -m unittest discover -s tests -p test_final*.py -v`: 13 passed.
- Separate fresh processes for test_accounting.py (28),
  test_policy_calibration.py (10), test_policy_cases.py (14),
  test_policy_pilot.py (19), test_policy_personalized.py (10),
  test_policy_writer.py (17): all 98 passed.
- `python -B audit/chief/takeover-final/scalar_checks.py`: three generated
  rational facts independently recomputed without project/reference imports.

The focused suite checks all18 saved scalar CE references (tolerance2e-14), six
fresh rational inverse-cube calculations, exact3600-row generated hashes,
all60 final-shaped IDs/eight modes/both fees, own horizons/thresholds, baseline
ledger/metric rational references (tolerance2e-11), actual ordering/future
perturbation isolation, prior immutability, H1 nulls, and review latching.

Broad combined policy discovery additionally encountered isolated source-closure
test contamination and sandbox temporary Git/rename permission errors. No
computational code was changed to suppress them; existing suites passed in
fresh processes with normal temporary-file permissions. Concurrent new analysis
writer tests are outside this component's acceptance and remain separately owned.

Before production the chief must bind exact new source commit/blob hashes,
review the narrow extractions against their old accepted versions, accept actual
development choices and all ten own-tolerance rescreens, independently validate
the fixed authenticated development loader/refit artifact, and obtain a separate
final persistence/table/authentication implementation. A complete reviewed freeze,
external exact-byte attestation and recorded gate opening remain mandatory before
any final file read. Actual HY3 outputs require independent exact-commit review;
this generated arithmetic lane grants no original input or production authority.
