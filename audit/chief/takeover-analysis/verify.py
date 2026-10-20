"""Portable generated-only replay; does not read competition inputs or write evidence."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from safeinvest import policy_analysis_writer as a


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify():
    before = {p.relative_to(HERE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    generated = load('takeover_generated', HERE / 'generated.py')
    with tempfile.TemporaryDirectory(prefix='safeinvest-analysis-fixture-') as tmp:
        repo = Path(tmp) / 'fixture'
        binding = generated.create(repo)
        groups, hashes = generated.authenticate(repo, binding)
        output = Path(tmp) / 'analysis'
        a._synthetic_persist(output, ROOT, groups, hashes)
        tables = a._synthetic_check(output, ROOT, groups, hashes)
        generated.scalar_facts(tables)
        for name in a.FILES:
            assert (output / name).read_bytes() == (HERE / 'fixture/analysis' / name).read_bytes(), name
    # Preserve the original independently authored scalar oracle. Only its byte
    # retrieval is redirected to the unchanged copied generated fixture blobs.
    oracle_source = (ROOT / 'audit/chief/review_analysis_generated_scalars.py').read_text(encoding='utf8')
    old = "raw=subprocess.check_output(['git','show',commit+':'+p],cwd=ROOT)"
    new = "raw=(fixture_root/name).read_bytes()"
    assert old in oracle_source
    namespace = dict(__name__='takeover_scalar_oracle', __file__=str(ROOT / 'audit/chief/review_analysis_generated_scalars.py'),
                     fixture_root=HERE / 'fixture')
    exec(compile(oracle_source.replace(old, new), str(ROOT / 'audit/chief/review_analysis_generated_scalars.py'), 'exec'), namespace)
    scalar = namespace['audit']('e1783a918122d8eaa507e42ca15a9c0a5f5b9339', fixture_task='SOL-038')
    assert scalar['independent_checks'] == 2820 and scalar['max_absolute_difference'] == 0.0
    original = json.loads((ROOT / 'audit/chief/SOL-038-chief-generated-scalar-review.json').read_text(encoding='utf8'))
    assert scalar['original_git_blob_sha256'] == original['original_git_blob_sha256']
    after = {p.relative_to(HERE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    assert before == after, 'fixture/source evidence changed during read-only verification'
    return dict(status='passed', read_only=True, generated_only=True, scalar_checks=2820,
                source_identity='CHIEF-ANALYSIS-20261020', production_authorized=False)


if __name__ == '__main__':
    assert sys.argv[1:] == ['--check'], 'only --check is supported'
    print(json.dumps(verify(), sort_keys=True))
