# Accepted implementation source index

Preparation snapshot only. These reviews establish computational behavior within
their stated scope; production results, recommendations and the final report need
their own acceptance. No competition input or outcome table is read by this index.

| Component | Accepted review | Scope |
| --- | --- | --- |
| __init__ | SOL-004 (`69ed125b7fde`) | Package initialization |
| accounting | SOL-001 (`b25c6b5589d0`) | One-way transfers, fee funding and exact inflation |
| backtest | SOL-004 (`69ed125b7fde`) | Annual decisions with prefix-only context |
| baselines | SOL-004 (`69ed125b7fde`) | Three fixed reference callbacks |
| metrics | SOL-001 (`b25c6b5589d0`) | Growth, annual fluctuation and real drawdown |
| experiments | SOL-004 (`69ed125b7fde`) | Fixed baseline tables and prefix metrics |
| policy_pilot | SOL-021 (`d154f90d1c50`) | Corrected cost-aware kernel; K1 and K2 history retained |
| policy_calibration | SOL-022 (`21ad493707d7`) | Generated-byte fold calibration arithmetic |
| policy_analysis | SOL-016 (`ceec2b6d1107`) | Pure analysis on explicit metric grids |
| policy_cases | SOL-025 (`803b7a085284`) | Pure case tables; portable repair separately accepted |

Full source, task, receipt and acceptance hashes are in component-index.json.
The acceptance snapshot is `8d00ca8eafc00fd636273be4125216e981289804`.
Check current source identity with `python -B report/build_component_index.py --check`.

The failed SOL-023 attempt remains preserved. SOL-025 separately passed the
prescribed clean-environment commands and independent replay. No source index
entry authorizes final evaluation or certifies policy performance.
