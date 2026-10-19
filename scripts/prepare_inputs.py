"""Coordinator bootstrap only: create exact row subsets and provenance hashes."""
import csv
import hashlib
import json
from pathlib import Path

root=Path(__file__).resolve().parents[1]
source=root/'data/raw/SafeInvest_Synthetic_Data.csv'
with source.open(newline='',encoding='utf-8-sig') as f:
    reader=csv.DictReader(f)
    fields=reader.fieldnames
    rows=list(reader)
paths=['problem/2026_MCM_SafeInvest.pdf','data/raw/SafeInvest_Synthetic_Data.csv']
for name,lo,hi in [('development/scenarios_001_120.csv',1,120),('final_holdout/scenarios_121_180.csv',121,180)]:
    path=root/'data'/name
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=fields,lineterminator='\n')
        writer.writeheader()
        writer.writerows(r for r in rows if lo <= int(r['scenario_id']) <= hi)
    paths.append('data/'+name)
manifest={'source':'User-supplied 2026 MCM Senior Group Problem A SafeInvest attachments',
          'license':'CC BY-NC-SA 4.0','transformation':'Originals unchanged; derived CSV files are row subsets only.',
          'files':[{'path':p,'sha256':hashlib.sha256((root/p).read_bytes()).hexdigest(),
                    'bytes':(root/p).stat().st_size} for p in paths]}
(root/'data/manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('Source hashes and exact scenario subsets prepared; no strategy outcomes computed.')
