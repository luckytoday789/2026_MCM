"""Independent SOL-003 metadata/evidence audit; Python 3.12 stdlib only.

Default: create fresh test evidence once. --check: read-only recomputation and
verification of saved evidence. Never imports or runs HY3 worker code, and never
computes performance from the input scenarios. Test Git repositories are local
fixtures below this audit directory, not the project repository or its origin.
"""
import argparse
import ast
import collections
import csv
import datetime as dt
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
BASE = "c651c67c30db1131c25641ac94631238cba0dd8d"
PARENT = "a287f214aece303d6dcd08f05a462cabf61258f2"
HY3 = "2a0263c5822988c0385d32fe084b794f8d644bc5"
SOL = "b25c6b5589d07e767f463f54f053f08bb0085157"
HYBASE = "f5e67b1f53568b94379ea631659d53d90db14f7b"
TASK_HASH = "758b29442ab6f6c7ba984a8d7a38a063d35ce80995df52f4266654133b89a4dd"
FIELDS = ["scenario_id", "period", "equity_return", "bond_return", "bill_proxy_return", "inflation"]
COMMANDS = []


def require(value, message):
    if not value:
        raise AssertionError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def execute(argv, *, cwd=ROOT, expected=0):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", GIT_TERMINAL_PROMPT="0")
    p = subprocess.run([str(x) for x in argv], cwd=cwd, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    record = {"argv": [str(x) for x in argv], "cwd": str(cwd),
              "exit_code": p.returncode, "expected_exit_code": expected,
              "stdout_sha256": sha(p.stdout), "stderr_sha256": sha(p.stderr)}
    if p.returncode != expected:
        record["failure_stdout"] = p.stdout.decode("utf-8", "replace")
        record["failure_stderr"] = p.stderr.decode("utf-8", "replace")
    COMMANDS.append(record)
    require(p.returncode == expected, str(record) + "\n" + p.stderr.decode("utf-8", "replace"))
    return p


def git(*args, cwd=ROOT):
    return execute(["git", *args], cwd=cwd).stdout


def blob(commit, name):
    # Binary output deliberately preserves all bytes, including trailing newlines.
    return git("show", commit + ":" + name)


def load_blob(commit, name):
    return json.loads(blob(commit, name))


def load_module(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def control_check():
    c = load_blob("origin/main", "ops/control.json")
    require(c["state"] == "running", "Project is paused/completed")
    require(dt.datetime.now(dt.timezone.utc) < dt.datetime.fromisoformat(c["deadline"]), "Project deadline")
    for stop in (ROOT / "STOP", ROOT / ".runtime/STOP", ROOT.parents[1] / "STOP", ROOT.parents[2] / "STOP"):
        require(not stop.exists(), "STOP requested: " + str(stop))


def source_snapshot():
    # Hash tracked working files without touching runtime, index, branches or refs.
    names = git("ls-files", "-z").decode("utf-8").split("\0")
    return {n: sha((ROOT / n).read_bytes()) for n in names if n and not n.startswith("audit/SOL-003/")}


def metadata():
    control_check()
    require(sys.version_info[:2] == (3, 12), "This audit requires Python 3.12")
    require(git("rev-parse", "HEAD").decode().strip() == BASE, "Wrong pinned base")
    require(git("rev-parse", BASE + "^").decode().strip() == PARENT, "Wrong chief parent")
    require(git("branch", "--show-current").decode().strip() == "work/sol/SOL-003-a1", "Wrong assigned branch")
    own = json.loads((ROOT / ".runtime/task.json").read_text(encoding="utf-8"))
    require(sha(canonical(own)) == TASK_HASH, "Immutable SOL-003 task changed")
    require(own["allowed_paths"] == ["audit/SOL-003"] and own["base_commit"] == BASE, "SOL-003 scope/base")
    require(own["parameters"]["final_outcomes_allowed"] is False, "Final-outcome gate")
    contract_raw = blob(BASE, "ops/tasks/HY3-001.json")
    contract = json.loads(contract_raw)
    receipt_raw = blob(HY3, "handoff/HY3-001/result.json")
    receipt = json.loads(receipt_raw)
    report_raw = blob(HY3, "results/development/HY3-001/input-check.json")
    report = json.loads(report_raw)
    chief_raw = blob(BASE, "audit/chief/HY3-001-review.json")
    chief = json.loads(chief_raw)
    require(contract["base_commit"] == HYBASE, "HY3 contract source")
    for field, expected in (("task_id", contract["id"]), ("attempt", contract["attempt"]),
                            ("role", contract["owner"]), ("base_commit", HYBASE),
                            ("task_sha256", sha(canonical(contract))), ("task_parameters", contract["parameters"])):
        require(receipt[field] == expected, "HY3 identity mismatch: " + field)
    require(receipt["status"] == "completed" and receipt["failure"] is None and receipt["started_from_pinned_source"] is True,
            "HY3 self-check status")
    require(git("rev-parse", HY3 + "^").decode().strip() == HYBASE, "HY3 actual parent/base")
    scope = git("diff", "--name-only", HYBASE, HY3).decode().splitlines()
    allowed = contract["allowed_paths"] + ["handoff/HY3-001"]
    require(all(any(n == p or n.startswith(p + "/") for p in allowed) for n in scope), "HY3 scope escape")
    require(set(scope) == set(receipt["artifacts_sha256"]) | {"handoff/HY3-001/result.json"}, "HY3 unhashed extra path")
    require(set(contract["deliverables"]) <= set(receipt["artifacts_sha256"]), "HY3 deliverables")
    expected_commands = contract["commands"] + contract["validation_commands"]
    require(len(receipt["checks"]) == len(expected_commands), "HY3 command count")
    for check, expected in zip(receipt["checks"], expected_commands):
        require(check["exit_code"] == 0 and check["argv"][1:] == expected[1:], "HY3 command/check mismatch")
    manifest = load_blob(BASE, "data/manifest.json")
    require(receipt["input_manifest"] == manifest == load_blob(HYBASE, "data/manifest.json"), "HY3 source manifest")
    sources = {}
    for item in manifest["files"]:
        raw = (ROOT / item["path"]).read_bytes()
        require(sha(raw) == item["sha256"] and len(raw) == item["bytes"], "Source hash/size: " + item["path"])
        require(raw == blob(BASE, item["path"]) == blob(HYBASE, item["path"]), "Source version: " + item["path"])
        sources[item["path"]] = {"sha256": sha(raw), "bytes": len(raw)}
    artifacts = {}
    for name, digest in receipt["artifacts_sha256"].items():
        raw = blob(HY3, name)
        # Legacy receipts hashed Windows checkout bytes. Retain both digests and
        # explicitly classify the reconstruction; never relabel it canonical.
        crlf = raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        basis = "canonical_git_blob" if sha(raw) == digest else "exact_crlf_checkout" if sha(crlf) == digest else "unverified"
        require(basis != "unverified", "HY3 artifact mismatch: " + name)
        require(chief["hash_checks"][name]["git_blob_sha256"] == sha(raw) and
                chief["hash_checks"][name]["receipt_match"] == basis, "Chief HY3 hash finding: " + name)
        artifacts[name] = {"git_blob_sha256": sha(raw), "receipt_sha256": digest,
                           "reconstructed_crlf_sha256": sha(crlf), "receipt_match": basis,
                           "git_blob_bytes": len(raw), "trailing_lf_count": len(raw) - len(raw.rstrip(b"\n"))}
        if name.endswith(".txt"):
            require(json.loads(raw) == report, "HY3 retained check differs from output")
    require(receipt["python"].split()[0] == chief["worker_python"] == "3.13.14", "HY3 runtime evidence")
    require(chief["reviewed_commit"] == HY3 and chief["task_sha256"] == receipt["task_sha256"] and
            chief["status"] == "not_accepted_python_version" and chief["required_python"] == "3.12", "Chief rejection")
    queue = load_blob(BASE, "ops/queue.json")
    item = next(x for x in queue["tasks"] if x["id"] == "HY3-001")
    require(item["state"] == "cancelled" and item["reviewed_commit"] == HY3, "HY3 must remain unaccepted")

    datasets = {}
    parsed = {}
    for name in ("data/raw/SafeInvest_Synthetic_Data.csv", "data/development/scenarios_001_120.csv", "data/final_holdout/scenarios_121_180.csv"):
        raw = (ROOT / name).read_bytes()
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
        require(reader.fieldnames == FIELDS, "Six-field schema: " + name)
        rows = list(reader)
        require(all(set(r) == set(FIELDS) and all(v is not None for v in r.values()) for r in rows), "Ragged CSV: " + name)
        keys = [(int(r["scenario_id"]), int(r["period"])) for r in rows]
        counts = collections.Counter(keys)
        lo, hi = (1, 120) if "/development/" in name else (121, 180) if "/final_holdout/" in name else (1, 180)
        expected = {(s, t) for s in range(lo, hi + 1) for t in range(1, 31)}
        duplicate = sum(n - 1 for n in counts.values())
        missing, unexpected = len(expected - set(keys)), len(set(keys) - expected)
        invalid = sum(not math.isfinite(x) or x <= -1 or not math.isfinite(1 + x)
                      for r in rows for x in (float(r[f]) for f in FIELDS[2:]))
        require(duplicate == missing == unexpected == invalid == 0, "Invalid keys/gross domains: " + name)
        require(len(rows) == (hi - lo + 1) * 30, "Row count: " + name)
        parsed[name] = rows
        datasets[name] = {"rows": len(rows), "scenarios": hi-lo+1, "periods_per_scenario": 30,
                          "unique_keys": len(counts), "duplicate_keys": duplicate, "missing_keys": missing,
                          "unexpected_keys": unexpected, "finite_positive_gross_cells": len(rows)*4,
                          "invalid_gross_cells": invalid, "schema": FIELDS}
    original = parsed["data/raw/SafeInvest_Synthetic_Data.csv"]
    for name, lo, hi in (("data/development/scenarios_001_120.csv", 1, 120), ("data/final_holdout/scenarios_121_180.csv", 121, 180)):
        require(parsed[name] == [r for r in original if lo <= int(r["scenario_id"]) <= hi], "Exact ordered split: " + name)
        datasets[name]["row_content_mismatches"] = 0
    numerical = {"status": "passed", "rows": 5400, "scenarios": 180, "periods_per_scenario": 30,
                 "development_rows": 3600, "final_rows": 1800,
                 "checks": ["source hashes", "schema", "unique complete keys", "finite valid gross returns", "exact split"],
                 "final_outcomes_computed": False}
    require(report == numerical == chief["chief_metadata_rerun"], "Independent HY3/chief metadata mismatch")

    sol_receipt = load_blob(SOL, "handoff/SOL-001/result.json")
    sol_review = load_blob(BASE, "audit/chief/SOL-001-review.json")
    old = blob(SOL, "audit/SOL-001/validation.txt")
    old_sha = sha(old)
    old_receipt_sha = sol_receipt["artifacts_sha256"]["audit/SOL-001/validation.txt"]
    require(old_sha != old_receipt_sha and sha(old.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")) != old_receipt_sha,
            "Historical log exclusion unexpectedly changed")
    require(sol_review["hash_checks"]["audit/SOL-001/validation.txt"]["status"] == "unverified_excluded" and
            "audit/SOL-001/validation.txt" in sol_review["excluded_paths"], "Historical exclusion")
    mandatory = {}
    for name in sol_review["mandatory_deliverables_verified"]:
        raw = blob(BASE, name)
        require(raw == blob(SOL, name), "Accepted Sol source changed: " + name)
        require(sha(raw) == sol_receipt["artifacts_sha256"][name], "Mandatory Sol digest: " + name)
        mandatory[name] = sha(raw)
    pinned_inputs = {}
    paths = ["AGENTS.md", "ops/PROTOCOL.md", "specs/PROBLEM_LOCK.md", "specs/ACCOUNTING.md", "data/manifest.json",
             "ops/tasks/HY3-001.json", "scripts/coop.py", "tests/test_coop.py", "scripts/check_worker_env.py",
             "tests/test_accounting.py", "src/safeinvest/__init__.py", "src/safeinvest/accounting.py",
             "src/safeinvest/backtest.py", "src/safeinvest/metrics.py", "audit/chief/HY3-001-review.json",
             "audit/chief/SOL-001-review.json", "audit/chief/runtime_receipt_verification.json"]
    for name in paths:
        raw = blob(BASE, name)
        local = (ROOT/name).read_bytes()
        # Read-only Windows checkouts can use CRLF; source semantics still bind to Git.
        require(local.replace(b"\r\n", b"\n") == raw.replace(b"\r\n", b"\n"), "Local source changed: " + name)
        pinned_inputs[name] = {"git_blob_sha256": sha(raw), "working_file_sha256": sha(local)}
    patch_raw = git("diff", PARENT, BASE, "--", "scripts/coop.py", "tests/test_coop.py", "scripts/check_worker_env.py")
    return {"reviewed_shas": {"base": BASE, "chief_parent": PARENT, "hy3_result": HY3, "hy3_base": HYBASE, "sol_core": SOL},
            "task_sha256": TASK_HASH, "hy3_contract_sha256": sha(canonical(contract)),
            "hy3_contract_blob_sha256": sha(contract_raw), "hy3_receipt_blob_sha256": sha(receipt_raw),
            "hy3_output_blob_sha256": sha(report_raw), "chief_hy3_review_blob_sha256": sha(chief_raw),
            "sources": sources, "pinned_inputs": pinned_inputs, "hy3_changed_paths": scope,
            "hy3_artifacts": artifacts, "metadata": numerical, "datasets": datasets,
            "chief_patch_sha256": sha(patch_raw), "mandatory_sol_outputs": mandatory,
            "hy3_acceptance": {"accepted": False, "worker_python": "3.13.14", "required_python": "3.12", "rerun_required": True},
            "historical_log": {"status": "unverified_excluded", "commit": SOL, "git_blob_sha256": old_sha,
                               "receipt_sha256": old_receipt_sha, "reused": False},
            "residuals": {"source_hash_mismatches": 0, "key_errors": 0, "invalid_gross_cells": 0, "split_row_mismatches": 0},
            "final_outcomes_computed": False}


def protocol_suite():
    mod = load_module("sol003_protocol_suite", ROOT / "tests/test_coop.py")
    # The original suite chooses coop.ROOT/.runtime/protocol-tests. Redirect its
    # fixture root so the real .runtime directory remains entirely read-only.
    mod.coop.ROOT = OUT / "fixtures"
    mod.coop.RUNTIME = mod.coop.ROOT / ".runtime"
    suite = unittest.defaultTestLoader.loadTestsFromModule(mod)
    require(suite.countTestCases() == 4, "Expected four accepted protocol tests")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def supplemental():
    coop = load_module("sol003_coop", ROOT / "scripts/coop.py")
    checks = []
    with tempfile.TemporaryDirectory(dir=OUT, prefix="blob-fixture-") as temp:
        top = Path(temp)
        git("init", "-b", "main", cwd=top)
        git("config", "core.autocrlf", "true", cwd=top)
        (top/".gitattributes").write_bytes(b"*.txt text eol=lf\n")
        fixtures = {"mixed.txt": b"first\r\nsecond\n\n", "no-newline.txt": b"tail",
                    "trailing.txt": b"one\r\n\r\n", "utf8.txt": "证据\r\nend\n".encode("utf-8")}
        expected = {n: b.replace(b"\r\n", b"\n") for n, b in fixtures.items()}
        for name, raw in fixtures.items():
            (top/name).write_bytes(raw)
        git("add", "--", ".gitattributes", *fixtures, cwd=top)
        for name, raw in fixtures.items():
            staged = git("show", ":"+name, cwd=top)
            require(staged == expected[name], "Staged exact bytes: " + name)
            # The implementation's binary subprocess expression is reproduced.
            p = subprocess.run(["git", "show", ":"+name], cwd=top, capture_output=True, check=True)
            require(p.stdout == staged and sha(p.stdout) == sha(staged), "Hash preserves bytes: " + name)
            require(len(staged)-len(staged.rstrip(b"\n")) == len(expected[name])-len(expected[name].rstrip(b"\n")), "Trailing LF")
            checks.append({"name": name, "working_sha256": sha(raw), "git_blob_sha256": sha(staged),
                           "exact_bytes_match": True, "trailing_lf_count": len(staged)-len(staged.rstrip(b"\n"))})
        require(not coop.allowed("audit/SOL-003-other/x", ["audit/SOL-003"]), "Sibling prefix escaped")
        require(coop.allowed("audit/SOL-003/x", ["audit/SOL-003"]), "Allowed child")
        task = {"allowed_paths": ["results/development"], "id": "T", "base_commit": "a"*40}
        outside = top/"outside.txt"
        outside.write_bytes(b"unchanged\n")
        with patch.object(coop, "changed_files", return_value=["outside.txt"]):
            try:
                coop.scope_check(task, top)
            except AssertionError:
                pass
            else:
                raise AssertionError("scope_check accepted a forbidden file")
        for name in ("results/development/.env.secret", "results/development/.runtime/x"):
            with patch.object(coop, "changed_files", return_value=[name]):
                try:
                    coop.scope_check(task, top)
                except AssertionError:
                    pass
                else:
                    raise AssertionError("scope_check accepted excluded metadata")
    # Identify whether the chief's new mixed-EOL fixture really contains EOLs.
    tree = ast.parse((ROOT/"tests/test_coop.py").read_text(encoding="utf-8"))
    fragments = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
                 and "mixed.txt" in n.value and "write_bytes" in n.value]
    require(len(fragments) == 1, "Locate mixed-EOL fixture source")
    generated = ast.parse(fragments[0])
    payloads = [n.value for n in ast.walk(generated) if isinstance(n, ast.Constant) and isinstance(n.value, bytes)]
    require(len(payloads) == 1, "Locate generated fixture bytes")
    payload = payloads[0]
    require(payload == b"first\r\nsecond\n", "Chief fixture must contain real CRLF/LF")
    return {"status": "passed", "canonical_blob_cases": checks,
            "scope_checks": "child allowed; sibling, forbidden file, .env and .runtime rejected",
            "chief_fixture_payload_hex": payload.hex(), "chief_fixture_has_actual_crlf": b"\r\n" in payload,
            "chief_fixture_verified": "Generated fixture contains actual CRLF/LF; independent cases additionally cover multiple and absent trailing newlines.",
            "project_runtime_modified": False}


def normalized_log(raw):
    return raw.decode("utf-8", "strict").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def write_log(name, raw):
    data = normalized_log(raw)
    (OUT/name).write_bytes(data)
    return {"path": "audit/SOL-003/"+name, "sha256": sha(data), "bytes": len(data), "encoding": "UTF-8", "newlines": "LF"}


def new_evidence():
    require(not (OUT/"verification.json").exists(), "Evidence already exists; --check will verify without replacing it")
    before = source_snapshot()
    data = metadata()
    suites = {}
    p = execute([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_accounting.py", "-v"])
    log = write_log("accounting-tests.txt", p.stdout+p.stderr)
    require(b"Ran 28 tests" in p.stderr and re.search(rb"\nOK\r?\n?$", p.stderr), "28 accounting tests not proved")
    suites["accounting"] = {"tests": 28, "exit_code": 0, "log": log}
    p = execute([sys.executable, "-B", "audit/SOL-003/verify.py", "--protocol-suite"])
    log = write_log("protocol-tests.txt", p.stdout+p.stderr)
    require(b"Ran 4 tests" in p.stderr and re.search(rb"\nOK\r?\n?$", p.stderr), "Four protocol tests not proved")
    suites["protocol"] = {"tests": 4, "exit_code": 0, "log": log, "fixture_root": "audit/SOL-003/fixtures"}
    p = execute([sys.executable, "-B", "scripts/check_worker_env.py"])
    good = json.loads(p.stdout)
    require(good["status"] == "passed" and good["python"].startswith("3.12."), "3.12 preflight")
    good_log = write_log("env-312.txt", p.stdout+p.stderr)
    simulated = ("import runpy,sys; from unittest.mock import patch; "
                 "sys.argv=['scripts/check_worker_env.py']; "
                 "a=patch.object(sys,'version_info',(3,13,14,'final',0)); "
                 "b=patch.object(sys,'version','3.13.14 (SIMULATED ONLY)'); "
                 "a.start(); b.start(); runpy.run_path('scripts/check_worker_env.py',run_name='__main__')")
    p = execute([sys.executable, "-B", "-c", simulated], expected=1)
    bad = json.loads(p.stdout)
    require(bad["status"] == "failed" and bad["python"] == "3.13.14", "Simulated 3.13 preflight must fail")
    bad_log = write_log("env-313-simulated.txt", p.stdout+p.stderr)
    extra = supplemental()
    require(source_snapshot() == before, "Tracked source changed during audit")
    data.update({"schema_version": 1, "status": "passed", "validation_exit_code": 0,
                 "python": sys.version, "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                 "suites": suites, "environment_checks": {
                     "real_312": {"exit_code": 0, "report": good, "log": good_log},
                     "simulated_313": {"exit_code": 1, "expected_rejection": True, "report": bad, "log": bad_log}},
                 "supplemental": extra, "commands_executed": COMMANDS,
                 "source_files_unchanged": True, "project_runtime_read_only": True})
    # No self-hash: verification.json hashes all other durable deliverables and logs.
    outputs = ["review.md", "findings.json", "verify.py", "accounting-tests.txt", "protocol-tests.txt", "env-312.txt", "env-313-simulated.txt", "investigation.json"]
    data["output_hashes"] = {"audit/SOL-003/"+name: sha((OUT/name).read_bytes()) for name in outputs}
    (OUT/"verification.json").write_bytes((json.dumps(data, indent=2, ensure_ascii=False)+"\n").encode("utf-8"))
    print(json.dumps({"status": "passed", "accounting_tests": 28, "protocol_tests": 4,
                      "metadata_rows": 5400, "final_outcomes_computed": False, "supplemental": extra}, indent=2))


def check_evidence():
    saved_path = OUT/"verification.json"
    saved_raw = saved_path.read_bytes()
    saved = json.loads(saved_raw)
    actual = metadata()
    for key, value in actual.items():
        require(saved.get(key) == value, "Saved metadata differs: " + key)
    require(saved["status"] == "passed" and saved["validation_exit_code"] == 0, "Saved validation failed")
    require(saved["python"].startswith("3.12."), "Saved audit interpreter")
    findings = json.loads((OUT/"findings.json").read_text(encoding="utf-8"))
    require(findings["pass"] is True and findings["blockers"] == [], "Unresolved material finding")
    require(findings["reviewed_shas"] == actual["reviewed_shas"], "Review SHAs")
    required_outputs = {"audit/SOL-003/" + n for n in ("review.md", "findings.json", "verify.py", "accounting-tests.txt", "protocol-tests.txt", "env-312.txt", "env-313-simulated.txt", "investigation.json")}
    require(set(saved["output_hashes"]) == required_outputs, "Incomplete output evidence manifest")
    for name, digest in saved["output_hashes"].items():
        require(name.startswith("audit/SOL-003/") and ".." not in Path(name).parts, "Evidence path scope")
        require(sha((ROOT/name).read_bytes()) == digest, "Saved output hash differs: " + name)
    for kind, expected in (("accounting", 28), ("protocol", 4)):
        suite = saved["suites"][kind]
        raw = (ROOT/suite["log"]["path"]).read_bytes()
        require(suite["tests"] == expected and suite["exit_code"] == 0 and sha(raw) == suite["log"]["sha256"], "Suite evidence: " + kind)
        require(raw == normalized_log(raw) and not raw.startswith(b"\xef\xbb\xbf"), "UTF-8 LF log: " + kind)
        require(("Ran %d tests" % expected).encode() in raw and re.search(rb"\nOK\n?$", raw), "Test completion: " + kind)
    require(saved["environment_checks"]["real_312"]["exit_code"] == 0 and
            saved["environment_checks"]["simulated_313"]["exit_code"] == 1 and
            saved["environment_checks"]["simulated_313"]["expected_rejection"] is True, "Preflight evidence")
    for key in ("real_312", "simulated_313"):
        evidence = saved["environment_checks"][key]
        raw = (ROOT/evidence["log"]["path"]).read_bytes()
        require(sha(raw) == evidence["log"]["sha256"] and raw == normalized_log(raw), "Environment log hash/encoding")
        require(json.loads(raw) == evidence["report"], "Environment report evidence")
    require(saved["supplemental"]["status"] == "passed" and saved["supplemental"]["chief_fixture_has_actual_crlf"] is True, "Mixed line-ending evidence")
    for record in saved["commands_executed"]:
        require(record["exit_code"] == record["expected_exit_code"], "Unresolved failed command")
    require(saved_path.read_bytes() == saved_raw, "--check modified verification.json")
    print(json.dumps({"status": "passed", "mode": "check", "verification_sha256": sha(saved_raw),
                      "metadata_recomputed": True, "saved_evidence_replaced": False,
                      "accounting_tests_evidenced": 28, "protocol_tests_evidenced": 4,
                      "final_outcomes_computed": False}, indent=2))


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true")
    group.add_argument("--protocol-suite", action="store_true")
    args = parser.parse_args()
    require(sys.version_info[:2] == (3, 12), "Python 3.12 required")
    if args.protocol_suite:
        return protocol_suite()
    if args.check:
        check_evidence()
    else:
        new_evidence()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        # A failing --check is read-only and nonzero; never repairs evidence.
        print("SOL-003 validation failed: " + str(exc), file=sys.stderr)
        if "--check" not in sys.argv and "--protocol-suite" not in sys.argv:
            failure = {"status": "failed", "validation_exit_code": 1, "error": str(exc), "commands_executed": COMMANDS}
            stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            (OUT/("validation-failure-"+stamp+".json")).write_bytes((json.dumps(failure, indent=2)+"\n").encode("utf-8"))
        raise SystemExit(1)
