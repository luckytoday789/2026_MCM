"""Require Python 3.12 before project computation."""
import argparse
import json
from pathlib import Path
import sys

def check():
    valid=sys.version_info[:2]==(3,12)
    return {"status":"passed" if valid else "failed","python":sys.version.split()[0],
            "required_python":"3.12","reason":None if valid else
            "Restart this worker under local Python 3.12; preserve worktrees and avoid duplicate watchers."}

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    report=check()
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps(report,indent=2))
    raise SystemExit(0 if report["status"]=="passed" else 1)
