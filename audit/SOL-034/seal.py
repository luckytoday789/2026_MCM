"""One-time evidence seal creation; verifier never calls this."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from safeinvest import policy_analysis_writer as a
DIR=ROOT/'audit/SOL-034'
PUBLICATION='fff5331dd62581c56848e165198458d38726d705'
raw=a.w.blob(ROOT,PUBLICATION,'ops/tasks/SOL-034.json');task=a.w.strict_json(raw)
paths=[ROOT/'src/safeinvest/policy_analysis_writer.py',ROOT/'scripts/run_development_analysis.py',ROOT/'tests/test_policy_analysis_writer.py']
paths+=[p for p in DIR.rglob('*') if p.is_file() and p.name!='verification.json' and not p.name.startswith('final-002') and p.name!='clean-environment-checks.json']
files={}
for p in paths:
    b=p.read_bytes();files[p.relative_to(ROOT).as_posix()]=a.sha(b if p.suffix=='.bundle' else b.replace(b'\r\n',b'\n'))
v=dict(schema_version=1,task_id='SOL-034',base_commit=task['base_commit'],publication_commit=PUBLICATION,
    task_digest=a.sha(a.canonical(task)),task_blob_sha256=a.sha(raw),files=files,accepted_sources=task['parameters']['source_sha256'])
with (DIR/'verification.json').open('x',encoding='utf8',newline='\n') as f:json.dump(v,f,indent=2,sort_keys=True)
print(json.dumps(dict(status='sealed',files=len(files))))
