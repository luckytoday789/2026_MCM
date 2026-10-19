"""Fixed pilot CLI. No data is read on import; --check never writes evidence."""

import argparse
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from safeinvest.experiments import (
    check_bundle, json_bytes, load_config, load_development, produce_bundle,
    read_manifest, source_snapshot,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--check", action="store_true")
    supplied = list(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(supplied)
    try:
        if sys.version_info[:2] != (3, 12):
            raise ValueError("this pilot requires Python 3.12")
        config = load_config(ROOT, args.config)
        output = Path(args.output)
        output = output if output.is_absolute() else ROOT / output
        # Checking uses the saved explicit SHA, never current branch/HEAD identity.
        source_sha = read_manifest(output)["source_commit"] if args.check else None
        provenance = source_snapshot(ROOT, source_sha)
        loaded = load_development(ROOT, config)
        if args.check:
            result = check_bundle(loaded, config, output, provenance)
            print(json_bytes({"status": result["status"], "read_only": True,
                              "output_counts": result["output_counts"]}).decode(), end="")
        else:
            result = produce_bundle(loaded, config, output, provenance,
                command=["python", "scripts/run_development_baselines.py", *supplied])
            try:
                source_snapshot(ROOT, provenance["source_commit"])
                if result["elapsed_seconds"] > config["execution"]["max_seconds"]:
                    raise ValueError("fixed execution time limit exceeded")
            except Exception as exc:
                result["status"] = "failed"
                result["diagnosis"] = {"exception": type(exc).__name__, "message": str(exc)}
                (output / "run_manifest.json").write_bytes(json_bytes(result))
                raise
            print(json_bytes({"status": result["status"], "split": result["split"],
                              "output_counts": result["output_counts"]}).decode(), end="")
        return 0
    except Exception as exc:
        print(type(exc).__name__ + ": " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
