# SOL-004 implementation and evidence

Status: implemented and self-checked; chief acceptance remains pending. findings.json
independently reviews chief's v1.1 contract only, not this later implementation.

## API

- simulate_policy(rows, *, horizon, split, callback, fee_rate=0.0025) extracts the
  accepted loop behind the existing immutable prefix boundary. Only H outcomes
  are consumed. Decisions exist before access to current returns/inflation.
- simulate_equal_weight retains its signature, uses the prior exact-thirds
  callback, and returns the generic engine's result. accounting.py and metrics.py
  are unchanged. The generic simulator is exported by the package.
- baselines.py contains exactly bills_keep, equal_weight_annual and
  equal_weight_buy_hold. Keep preserves component dollars; buy-hold trades only
  on its initial review. No parameter or horizon is fitted.
- build_tables(rows, config, split=...) returns four ordered tables and an executed
  check report. It computes one 30-year ledger per policy/scenario and five prefixes.
  metric_row supports H=1: volatility and ex-initial share are None; later counts
  are zero. The pilot itself accepts only 5,6,15,25,30.
- produce_bundle(LoadedInput, config, output, provenance, command=...) refuses a
  nonempty directory. Failure after creating it leaves a failed manifest/diagnosis
  and any written files. check_bundle only reads saved files, verifies metadata
  and hashes, recomputes from supplied input in memory, and compares exact tables
  and checks. It never repairs or overwrites evidence.

The CLI has only --config, --output and --check, plus help. It requires Python 3.12.
A new run resolves HEAD once to a full source SHA. A check uses the saved SHA;
no worker branch identity or pre-edit HEAD equality is required. Task identity
and delivery receipt are supplied by the parent runner.

## Input and source boundaries

The fixed config path/canonical LF SHA256 freeze every config byte. A separate
canonical JSON digest freezes every effective field for computation API callers.
The production loader accepts only data/development/scenarios_001_120.csv and
its fixed raw-byte hash. Alternate paths/splits/hashes fail before opening;
symlink escapes fail. Bytes are hashed before parsing. The exact six fields,
3600 ordered complete keys (IDs 1..120, years 1..30), finite values and positive
gross factors are required. check_inputs.py is never imported or called.

source_snapshot compares an explicit Git commit's canonical blobs with every
package module, CLI, config, problem/accounting contracts, baseline contracts and
toy oracle. Uniform LF and CRLF checkouts are supported. Other changes fail.
It records actual consumed-byte SHA256 separately from canonical blob SHA256/SHA1
and the reconstructible CRLF checkout digest. Imported package files are checked
too. The CLI rechecks source after creating a run, recording failure if it changed.
Saved checks reject consumed hashes inconsistent with those Git bytes. Output
files, branch identity and runner receipt are not production source.

The manifest binds effective config, profile horizons, H=30 comparison horizon,
input hash/origin, explicit synthetic marker and generator hash where relevant,
creation argv, Python/stdlib versions, UTC start/end, elapsed/CPU seconds, status,
counts and hashes of the other five files. It excludes itself from the hash map.
The current uncommitted implementation cannot pass production source checks until
it is delivered in a source commit. Chief and HY3-002 acceptance remain procedural
prerequisites for any later actual-data task.

## Exact schemas and units

schemas.json lists every ordered CSV column, type, nullability, key and count,
plus the JSON record fields. synthetic-bundle/ contains all six saved files.
UTF-8 LF, deterministic key order and Python round-trip float precision apply.
All detached CSVs carry split and units. Keep targets are empty; zeros are explicit.

- annual_ledgers.csv, 10800 policy/scenario/year rows: action; target, pre/post-fee/
  end component holdings and returns, each expanded in equity,bond,bill_proxy order;
  pre/post-fee/end nominal and real wealth; CPI before/end; transfer, fee, inflation
  and decimal annual_net_real_return. CPI_0=1.
- scenario_metrics.csv, 1800 policy/scenario/horizon rows: real CAGR, sample annual
  fluctuation, maximum real drawdown, terminal real wealth, nominal fee sum, both
  trade/review counts and shares, peak/trough year/kind, split and units.
- summary.csv, 15 policy/horizon rows: 120 scenarios, median/p10 growth, median/p90
  loss, median fluctuation/terminal real wealth/nominal fees, pooled counts and
  shares, severe ID and its growth/loss/terminal real wealth, both shares and
  peak/trough locations.
- paired_differences.csv, 1200 alternative/scenario/horizon rows: explicit annual
  reference identity, split, six alternative-minus-reference differences (growth,
  loss, terminal real wealth, nominal fees, both trade shares) and units.
- checks.json: executed names, counts, thresholds, failures, largest absolute and
  scaled residuals, split, plan ID and output counts.
- run_manifest.json: provenance/metadata above. Failure adds diagnosis and does
  not fabricate missing outputs or counts.

Growth uses percentage points/year; volatility uses percentage points of annual
net real returns (sample ddof=1); loss and trade shares use percent; monetary
values use nominal units except named real wealth in CPI_0 purchasing power.
Paired percentage differences use percentage points; positive loss difference
is worse. Nominal fee sums are descriptive, not real welfare losses.

Initial, post-fee and end observations enter drawdown. Strict peak/loss increases
select earliest maximizing locations; zero loss uses (0,initial). Severe selection
uses exact float loss then smallest ID. Tolerances never change selection ties
or the 1e-10 trade threshold. Toy absolute tolerance is 1e-9; ledger comparisons
use math.isclose(abs_tol=1e-9, rel_tol=1e-10).

## What actually ran

Python 3.12.14 ran the environment check, CLI help and full unittest suite. The
latest full run passed 59 tests: 28 prior accounting, four prior protocol and
27 new driver tests. tests.txt and execution_log.json retain commands, exits and
stdout/stderr. test_evidence.json and verification.json retain numeric comparisons
and negative-probe diagnoses. The saved generated 120x30 fixture produced all
six files and exact row counts. Its checks contain 232957 executed
comparisons/assertions with zero failures.

IDs 1,60,120 were rerun for every policy/horizon and checked with independent
scalar metric arithmetic. Rational two-year paths for all policies and the chief
oracle cover fee timing/real accounting. Guarded rows, year-10 perturbations,
a history-dependent test callback, prefixes and single-scenario/batch comparisons
cover timing. Small scalar fixtures check linear quantiles, earliest/zero locations,
exact severe ties including adjacent floats, paired signs and pooled denominators.

In-process CLI tests replace only the input-loader boundary with an explicitly
synthetic LoadedInput in an isolated Git repository. All source/config checks
remain active. Separate loader tests use an explicit unit fixture hash seam,
reject the real frozen hash on generated bytes, reject malformed keys/schema/
domains, and install builtins.open/io.open guards against raw/final access. These
seams are test code, with no production override flag.

A valid saved --check passes with write methods blocked. Corrupt hash, missing
file/row, rehashed numeric corruption, invalid/incomplete manifest and forged
consumed hashes fail without changing evidence. A failed new fixture run preserves
its failed manifest. Saved checking passes after the isolated fixture HEAD advances;
changed source/config fails. Actual repository refs are untouched.

Two failed test trials remain visible in failure-001.json (synthetic staging
retained CRLF spec blobs) and failure-002.json (quantile expectation incorrectly
required exact equality to rational 3). Fixes affected fixture staging and the toy
assertion; accounting, metrics and chief rules were unchanged. The second trial's
evidence is separately retained. Two initial shell-tool startup failures and one
audit-writer parse error are retained in tests.txt. The first final structural preflight also ran before verification.json existed;
failure-003.json retains that audit sequencing failure and its corrected passing
rerun. No process ran for the tool
startup/parse failures; Node local file/process APIs completed the work. No package was installed.

## Portable saved verification

synthetic-input.csv matches the saved input hash. synthetic-source.bundle is an
isolated synthetic source snapshot including separate generator source. Its commit
is d2c783ff9cf14415d1e8309d75a890646b45f117; this is not the runner's future delivery commit.
All six saved outputs are byte-for-byte copies of the successful synthetic run.

    python -B audit/SOL-004/verify_saved_synthetic.py

This command already passed. It clones the local source bundle to a new ignored
scratch directory, uses the saved explicit source SHA and input bytes, checks the
generator/input hashes, and compares saved files without regenerating input/output
or modifying saved evidence. It requires Python 3.12 and Git, no numeric packages,
network, current branch identity or pre-edit HEAD. The generator is not rerun.

## Later HY3 commands, not executed here

Only after chief independently reviews the exact delivered commit/fixtures,
accepts HY3-002 and publishes a distinct immutable task, run in a clean checkout
of the chief-published accepted source SHA:

    python -B scripts/check_worker_env.py
    python -B scripts/run_development_baselines.py --config specs/development_baselines_v1_1.json --output results/development/HY3-003
    python -B scripts/run_development_baselines.py --config specs/development_baselines_v1_1.json --output results/development/HY3-003 --check

HY3-003 is only the reserved directory name. This implementation dispatches no
such task. No production output directory, actual-data run, competition performance
table, raw/final access, freeze edit, fitting, tuning, recommendation, package/runtime
helper change, actual repository commit/push/branch change or watcher occurred.
Git object/ref writes were confined to the isolated synthetic/protocol test
repositories allowed by the task. There are no known unresolved blockers from
these self-checks. Chief independent acceptance and later separate Sol review of
exact HY3 outputs remain outstanding.
