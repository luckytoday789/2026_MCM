"""Read saved SOL-004 synthetic evidence without regenerating any fixture/output.

Only a scratch clone under ignored .runtime is created. No actual refs, source,
competition CSV or saved evidence is modified. Requires Python 3.12 and local Git.
"""
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
AUDIT = Path(__file__).resolve().parent


def main():
    if sys.version_info[:2] != (3, 12):
        raise ValueError("Python 3.12 required")
    output = AUDIT / "synthetic-bundle"
    before = {p.name: p.read_bytes() for p in output.iterdir() if p.is_file()}
    runtime = ROOT / ".runtime"
    runtime.mkdir(exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="SOL-004-saved-check-", dir=runtime))
    source = scratch / "source"
    subprocess.run(["git", "-c", "core.autocrlf=false", "clone", "--quiet", str(AUDIT / "synthetic-source.bundle"), str(source)],
                   check=True, capture_output=True)
    sys.path.insert(0, str(source / "src"))
    from safeinvest import experiments as ex
    manifest = ex.read_manifest(output)
    if manifest["split"] != "synthetic" or not manifest["input"]["fixture"]:
        raise ValueError("this audit verifier accepts saved synthetic evidence only")
    fixture = (AUDIT / "synthetic-input.csv").read_bytes()
    generator = (source / "tests/test_development_baselines.py").read_bytes()
    if ex.digest(fixture) != manifest["input"]["sha256"]:
        raise ValueError("saved synthetic input hash mismatch")
    if ex.digest(generator) != manifest["input"]["fixture_generator_sha256"]:
        raise ValueError("saved fixture generator hash mismatch")
    rows = tuple(csv.DictReader(io.StringIO(fixture.decode("utf-8"), newline="")))
    loaded = ex.LoadedInput(rows, "synthetic", ex.digest(fixture), manifest["input"]["origin"], ex.digest(generator))
    config = ex.load_config(source, ex.CONFIG_PATH)
    provenance = ex.source_snapshot(source, manifest["source_commit"])
    result = ex.check_bundle(loaded, config, output, provenance)
    if before != {p.name: p.read_bytes() for p in output.iterdir() if p.is_file()}:
        raise AssertionError("saved evidence changed")
    print(json.dumps({"status": result["status"], "split": "synthetic", "read_only": True,
                      "fixture_regenerated": False, "outputs_regenerated": False,
                      "source_commit": manifest["source_commit"],
                      "output_counts": result["output_counts"], "check_count": result["checks"]["count"]}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(type(exc).__name__ + ": " + str(exc), file=sys.stderr)
        raise SystemExit(1)
