"""Audit-only evidence corruption probes; never alters the original evidence."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
AUDIT = Path(__file__).resolve().parent


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    original = AUDIT / "verification.json"
    data = original.read_bytes()
    facts = json.loads(data)
    output = AUDIT / "integrity-self-tests.json"
    if output.exists():
        raise FileExistsError("integrity log already exists")
    scratch = AUDIT / "history/corruption-python"
    scratch.mkdir(exist_ok=True)
    probes = []
    for name, field, expected in (
            ("wrong-number", "number", "number mismatch: root.generated_tables.paired_differences[0].net_real_cagr_pct_difference"),
            ("wrong-hash", "hash", "exact mismatch: root.binding.delivered_sha256_lf.src/safeinvest/policy_analysis.py"),
            ("threshold-neighbor", "threshold", "number mismatch: root.behavior_fixtures.thresholds[1].comparison.median_paired_growth_gain_pp"),
            ("extra-key", "extra", "keys mismatch: root"),
            ("missing-key", "missing", "keys mismatch: root"),
            ("nonfinite", "nonfinite", "nonfinite saved evidence: NaN")):
        altered = deepcopy(facts)
        if field == "number":
            altered["generated_tables"]["paired_differences"][0]["net_real_cagr_pct_difference"] += 1.
        elif field == "hash":
            altered["binding"]["delivered_sha256_lf"]["src/safeinvest/policy_analysis.py"] = "0" * 64
        elif field == "threshold":
            import math
            altered["behavior_fixtures"]["thresholds"][1]["comparison"]["median_paired_growth_gain_pp"] = math.nextafter(.1,-math.inf)
        elif field == "extra":
            altered["unregistered"] = True
        elif field == "missing":
            del altered["checks"]
        else:
            altered["checks"]["max_absolute_residual"] = float("nan")
        path = scratch / (name + ".json")
        with path.open("x",encoding="utf8",newline="\n") as stream:
            json.dump(altered,stream,indent=2,sort_keys=True,allow_nan=field=="nonfinite")
            stream.write("\n")
        probes.append((name,path,expected))
    duplicate = scratch / "duplicate-key.json"
    with duplicate.open("xb") as stream:
        stream.write(b'{"status":"duplicate",' + data[1:])
    probes.append(("duplicate-key",duplicate,"duplicate saved evidence key: status"))
    results = []
    commands = [("valid",original,0,None,True),("exclusive",original,1,"verification already exists",False)]
    commands += [(name,path,1,expected,True) for name,path,expected in probes]
    for name,path,expected_exit,expected_message,check in commands:
        before = path.read_bytes()
        args = [sys.executable,"-B",str(AUDIT / "verify.py")]
        if check:
            args += ["--check","--evidence",str(path)]
        start = time.perf_counter()
        run = subprocess.run(args,cwd=ROOT,capture_output=True,text=True)
        after = path.read_bytes()
        matched = run.returncode == expected_exit and (expected_message is None or expected_message in run.stderr)
        record = {"name":name,"expected_exit":expected_exit,"actual_exit":run.returncode,
                  "expected_diagnostic":expected_message,"matched_intended_check":matched,
                  "seconds":time.perf_counter()-start,"stdout":run.stdout,"stderr":run.stderr,
                  "sha256_before":sha(before),"sha256_after":sha(after),"bytes_unchanged":before==after}
        results.append(record)
        if not matched or before != after:
            # Retain an unexpected probe result exclusively rather than hide it.
            with (AUDIT / "history/integrity-unexpected.json").open("x",encoding="utf8") as stream:
                json.dump(record,stream,indent=2)
            raise AssertionError("integrity probe failed: " + name)
    after = original.read_bytes()
    if data != after:
        raise AssertionError("original evidence changed")
    summary={"schema_version":1,"original_sha256_before":sha(data),"original_sha256_after":sha(after),
             "all_intended_checks_matched":True,"original_bytes_preserved":True,"runs":results,
             "preserved_prior_probe_issue":"history/integrity-diagnosis-001.json",
             "preserved_prior_verification_sha256":"2f991051edb333f5f59cc0e9ff9053795376d957f35b7cce8784fe28a4ca7347"}
    with output.open("x",encoding="utf8",newline="\n") as stream:
        json.dump(summary,stream,indent=2,sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status":"passed","probes":len(results),"original_bytes_preserved":True}))


if __name__ == "__main__":
    main()
