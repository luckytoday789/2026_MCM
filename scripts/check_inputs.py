"""Validate structure and hashes without inspecting final-split performance."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ['scenario_id', 'period', 'equity_return', 'bond_return', 'bill_proxy_return', 'inflation']

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def validate(root=ROOT):
    manifest = json.loads((root / 'data/manifest.json').read_text(encoding='utf-8'))
    for item in manifest['files']:
        assert sha(root / item['path']) == item['sha256'], f"Input changed: {item['path']}"
    with (root / 'data/raw/SafeInvest_Synthetic_Data.csv').open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == FIELDS, reader.fieldnames
        rows = list(reader)
    assert len(rows) == 5400
    keys = {(int(r['scenario_id']), int(r['period'])) for r in rows}
    assert keys == {(s,t) for s in range(1,181) for t in range(1,31)}
    for row in rows:
        for field in FIELDS[2:]:
            assert math.isfinite(float(row[field])) and float(row[field]) > -1, field
    for split, lo, hi in [('development',1,120), ('final_holdout',121,180)]:
        name = 'scenarios_001_120.csv' if split == 'development' else 'scenarios_121_180.csv'
        with (root / 'data' / split / name).open(newline='', encoding='utf-8') as f:
            split_rows = list(csv.DictReader(f))
        assert split_rows == [r for r in rows if lo <= int(r['scenario_id']) <= hi]
    return {'status':'passed','rows':5400,'scenarios':180,'periods_per_scenario':30,
            'development_rows':3600,'final_rows':1800,
            'checks':['source hashes','schema','unique complete keys','finite valid gross returns','exact split'],
            'final_outcomes_computed':False}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output')
    args = parser.parse_args()
    report = validate()
    if args.output:
        output = ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
