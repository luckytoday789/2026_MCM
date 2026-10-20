# Chief analysis recovery interface

This recovers only the exact SOL-038 draft at
`e1783a918122d8eaa507e42ca15a9c0a5f5b9339`. The failed SOL-034/SOL-038
receipts remain failures. Generated fixture values are software fixtures;
they are not competition outcomes, producer approval, or execution authority.

The public commands remain:

```
python -B scripts/run_development_analysis.py --config <E-config> --output <assigned-root>
python -B scripts/run_development_analysis.py --config <E-config> --output <assigned-root> --check
```

Source C, later approved configuration E, and a later immutable HY3 command
task publication P must remain distinct and ordered. The six exact output
files, two authenticated 44-file producer bundles, typed 9,600-row bridge,
12,000 paired rows, 100 gates, 30 screens, ten provisional recommendations,
unchanged primary-only selection and closed final-data gate are retained.

The new required acceptance identity is `CHIEF-ANALYSIS-20261020`, whose value
is the exact source C commit. At execution base E the canonical Git file
`audit/chief/CHIEF-ANALYSIS-20261020-review.json` must contain:

- `task_id`: `CHIEF-ANALYSIS-20261020`
- `kind`: `chief_takeover_approval`
- `authorization`: `user-directed-two-node-takeover-20261020`
- `reviewed_commit`: the exact reviewed source commit
- `code_verdict`: `approve`
- `source_sha256`: the complete `policy_analysis_writer.CLOSURE` dictionary,
  hashing canonical Git bytes at that exact commit, including this recovery's
  `audit/chief/takeover-analysis/schema.json`.

This is an explicit chief review record, not a worker execution receipt.
The queue can register accepted chief approvals for scheduler dependency
resolution. Existing SOL/HY3 approvals still require their original exact
accepted queue records and canonical chief evidence.

A producer numerical review may retain its accepted SOL identity, or use an
explicit `CHIEF-*` identity under the same chief approval convention. A chief
numerical review additionally requires `producer_task_id`,
`reviewed_result_commit`, `result_verdict=approve` and `oracle_execution` with
actual `argv`, integer `exit_code=0`, tracked `log_path` and canonical Git
`log_sha256`. The producer's original receipt and accepted exact result remain
mandatory; no failed or unaccepted producer becomes usable through this seam.

Historical producer source hashes remain pinned to the unchanged accepted
closure at `b75389aefeb06ed750c9b7aa891ecc383af9ce1a`. Each fresh writer
`--check` executes before assembly import inside a disposable shared local Git
clone checked out at the exact producer result. Sparse checkout materializes
the checker source, contracts, assigned saved producer output, its config and
the permitted development input; raw/final datasets are absent. No remote
fetch, producer generation, parameter fitting or final access occurs. The
current assembly closure has its own exact chief-reviewed identity, permitting
reviewed private arithmetic helpers without substituting them into historical
writer checks. The unchanged writer's structural `bind_task` is also replayed
against original immutable Git C/E/P objects in the analysis authentication.

Generated verification:

```
python -B -m unittest discover -s tests -p test_policy_analysis_writer.py -v
python -B audit/chief/takeover-analysis/verify.py --check
```

The verifier reconstructs only the saved generated Git bundle, checks the five
persisted analysis outputs against unchanged fixture bytes, invokes the original
independent scalar oracle for 2,820 checks and proves fixture immutability. It
does not require the failed worker's checkout or access competition data.

During the authorized takeover the assembly task may truthfully have owner `chief`
or `hy3`, always kind `commands`, and uses the matching `work/<actual-owner>/...`
branch. Publication, source C/config E/task P, all approvals and producer checks
remain mandatory. The original historical writer publication API is unchanged.
