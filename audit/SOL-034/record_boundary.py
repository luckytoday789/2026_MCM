"""Actual fresh-child module-identity records; generated fixtures only."""
import importlib.util,json,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('test034',ROOT/'tests/test_policy_analysis_writer.py');t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
a=t.a;w=a.w
with tempfile.TemporaryDirectory() as scratch:
    root=Path(scratch);(root/'scripts').mkdir()
    source=dict(source_commit='2ea73da59d393893f06a8169432c5d9e0b168c50',source_sha256={n:w.sha(w.blob(ROOT,'2ea73da59d393893f06a8169432c5d9e0b168c50',n)) for n in w.CLOSURE})
    checker=t.StringChild(ROOT,source);(root/'scripts/check.py').write_text(checker,encoding='utf8')
    c=dict(producers=[dict(group=g,config_path=g+'.json',root=g) for g in ('primary','doubled')],execution=dict(max_seconds=30))
    (root/'config.json').write_bytes(w._json_bytes(c))
    for g in ('primary','doubled'):(root/(g+'.json')).write_text('0')
    calls=[];t.cli._create(root,'config.json','success',_synthetic_script='scripts/check.py',_after_checks=lambda records,stage:calls.extend(records))
    (root/'primary.json').write_text('9')
    try:t.cli._create(root,'config.json','failure',_synthetic_script='scripts/check.py',_after_checks=lambda *args:(_ for _ in ()).throw(AssertionError('analysis after child failure')))
    except ValueError:pass
    failed=w.strict_json(next((root/'failure').glob('partial-*/checker-primary.json')).read_bytes())
    output=dict(source_text=checker,source_sha256=w.sha(checker.encode()),records=calls+[failed],analysis_called_after_failure=False)
    with (ROOT/'audit/SOL-034/boundary-module-records.json').open('x',encoding='utf8',newline='\n') as f:json.dump(output,f,indent=2)
print('actual fresh-child module records created')
