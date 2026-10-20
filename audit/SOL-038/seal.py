"""One-time evidence seal creation; verifier never calls this."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from safeinvest import policy_analysis_writer as a
DIR=ROOT/'audit/SOL-038'
PUBLICATION='95eb627ce6536662b8c583dfd2e6046c3aaf0ea9'
raw=a.w.blob(ROOT,PUBLICATION,'ops/tasks/SOL-038.json');task=a.w.strict_json(raw)
paths=[ROOT/'src/safeinvest/policy_analysis_writer.py',ROOT/'scripts/run_development_analysis.py',ROOT/'tests/test_policy_analysis_writer.py']
paths+=[p for p in DIR.rglob('*') if p.is_file() and p!=DIR/'verification.json' and p!=DIR/'clean-environment-checks.json' and not p.name.startswith('local-check-')]
files={}
for p in paths:
    b=p.read_bytes();canonical=b if p.suffix=='.bundle' else b.replace(b'\r\n',b'\n')
    crlf=canonical if p.suffix=='.bundle' else canonical.replace(b'\n',b'\r\n')
    files[p.relative_to(ROOT).as_posix()]=dict(sha256=a.sha(canonical),bytes=len(canonical),crlf_sha256=a.sha(crlf),crlf_bytes=len(crlf))
v=dict(schema_version=1,task_id='SOL-038',base_commit=task['base_commit'],publication_commit=PUBLICATION,
    task_digest=a.sha(a.canonical(task)),task_blob_sha256=a.sha(raw),files=files,accepted_sources=task['parameters']['source_sha256'])
with (DIR/'verification.json').open('x',encoding='utf8',newline='\n') as f:json.dump(v,f,indent=2,sort_keys=True)
print(json.dumps(dict(status='sealed',files=len(files))))
