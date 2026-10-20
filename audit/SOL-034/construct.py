"""Create new small generated evidence, refusing every existing target."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[2]
DIR=ROOT/'audit/SOL-034'
sys.path.insert(0,str(ROOT/'src'))
from safeinvest import policy_analysis_writer as a
w=a.w
spec=importlib.util.spec_from_file_location('generated034',DIR/'generated.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)

def main():
    started=time.monotonic();target=DIR/'fixture'
    w.require(not target.exists(),'existing fixture refused');target.mkdir()
    with tempfile.TemporaryDirectory() as temporary:
        temp=Path(temporary);repo=temp/'repo';binding=g.create(repo)
        groups,hashes=g.authenticate(repo,binding)
        before=g.inventory(repo)
        check=temp/'checkout';g.checkout(repo,check)
        w.require(before==g.inventory(check),'Git checkout bytes changed')
        g.authenticate(check,binding)
        # Store one small Git bundle and exact checkout bytes; no historical bundles.
        g.git(repo,'bundle','create',str(target/'objects.bundle'),'--all')
        shutil.copytree(repo,target/'bytes',ignore=shutil.ignore_patterns('.git'))
        (target/'binding.json').write_bytes(w._json_bytes(binding))
        m=a._synthetic_persist(target/'analysis',ROOT,groups,hashes)
        inventory=g.inventory(target/'analysis')
        tables=a._synthetic_check(target/'analysis',ROOT,groups,hashes)
        w.require(inventory==g.inventory(target/'analysis'),'read-only analysis changed output')
        facts=g.scalar_facts(tables)
        # Actual fresh-child writer guard boundary, including nonzero exit 9.
        test_spec=importlib.util.spec_from_file_location('test034',ROOT/'tests/test_policy_analysis_writer.py')
        testmod=importlib.util.module_from_spec(test_spec);test_spec.loader.exec_module(testmod)
        boundary=temp/'boundary';boundary.mkdir();(boundary/'scripts').mkdir()
        source=dict(source_commit='2ea73da59d393893f06a8169432c5d9e0b168c50',source_sha256={n:a.sha(w.blob(ROOT,'2ea73da59d393893f06a8169432c5d9e0b168c50',n)) for n in w.CLOSURE})
        (boundary/'scripts/check.py').write_text(testmod.StringChild(ROOT,source),encoding='utf8')
        (target/'checker-source.txt').write_bytes((boundary/'scripts/check.py').read_bytes())
        c=dict(producers=[dict(group=v,config_path=v+'.json',root=v) for v in ('primary','doubled')],execution=dict(max_seconds=30))
        (boundary/'config.json').write_bytes(w._json_bytes(c))
        for group in ('primary','doubled'):(boundary/(group+'.json')).write_text('0')
        calls=[]
        testmod.cli._create(boundary,'config.json','success',_synthetic_script='scripts/check.py',_after_checks=lambda records,stage:calls.append(records))
        (boundary/'primary.json').write_text('9')
        try:testmod.cli._create(boundary,'config.json','failure',_synthetic_script='scripts/check.py',_after_checks=lambda *x:(_ for _ in ()).throw(AssertionError('analysis after failed child')))
        except ValueError:pass
        failed=w.strict_json(next((boundary/'failure').glob('partial-*/checker-primary.json')).read_bytes())
        w.require(failed['returncode']==9,'actual nonzero child not observed')
        facts.update(boundary=dict(success=calls[0],failure=failed,analysis_called_after_failure=False),
            git=dict(binding=binding,later_HEAD=g.git(repo,'rev-parse','HEAD').decode().strip(),
                checked_out_bytes_unchanged=True,source_files=len(before),no_runtime_task=True),
            measured=dict(elapsed_seconds=time.monotonic()-started,metric_rows=320,
                output_bytes=sum((target/'analysis'/n).stat().st_size for n in a.FILES+('run_manifest.json',)),
                output_files={n:(target/'analysis'/n).stat().st_size for n in a.FILES+('run_manifest.json',)}))
        (DIR/'scalar-facts.json').write_bytes(w._json_bytes(facts))
    print(json.dumps(dict(status='created',elapsed_seconds=time.monotonic()-started)))

if __name__=='__main__':main()
