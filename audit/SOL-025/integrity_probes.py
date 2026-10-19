"""Compact scratch corruption probes for the SOL-025 read-only verifier."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT/'audit/SOL-025'
ORIGINAL = HERE/'verification.json'
def sha(data): return hashlib.sha256(data).hexdigest()
def run(argv):
    env = dict(os.environ)
    removed = [k for k in env if k.upper() == 'PYTHONPATH']
    for key in removed: env.pop(key)
    start = time.monotonic()
    p = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    return dict(argv=argv, returncode=p.returncode, stdout=p.stdout, stderr=p.stderr,
                seconds=time.monotonic()-start, pythonpath_present=any(k.upper()=='PYTHONPATH' for k in env))
def main():
    before = ORIGINAL.read_bytes()
    original = json.loads(before)
    mutations = [
      ('number', ['numeric','forced_scalar_facts','terminal_real_wealth'], 'replace', original['numeric']['forced_scalar_facts']['terminal_real_wealth']+1.0),
      ('source_hash', ['identity','source_sha256_lf','src/safeinvest/accounting.py'], 'replace', '0'*64),
      ('tiny_fee_zero', ['numeric','tiny_fee_facts','fee'], 'replace', 0.0),
      ('missing_key', ['numeric','forced_scalar_facts','fee_sum'], 'delete', None),
      ('nonfinite', ['numeric','forced_scalar_facts','fee_sum'], 'nonfinite', 'Infinity'),
      ('wrong_type', ['regression','tests_run'], 'replace', True),
      ('extra_key', ['unexpected'], 'replace', 1),
    ]
    def probe(spec):
        label, keys, operation, value = spec
        doc = deepcopy(original)
        parent = doc
        for key in keys[:-1]: parent = parent[key]
        old = parent.get(keys[-1])
        if operation == 'delete': del parent[keys[-1]]
        else: parent[keys[-1]] = float('inf') if operation == 'nonfinite' else value
        scratch_bytes = (json.dumps(doc, indent=2, allow_nan=True)+'\n').encode()
        with tempfile.TemporaryDirectory(prefix='sol025-'+label+'-') as folder:
            path = Path(folder)/'corrupt.json'
            with path.open('xb') as file: file.write(scratch_bytes)
            result = run([sys.executable, '-B', 'audit/SOL-025/verify.py', '--check', '--evidence', str(path)])
            after = path.read_bytes()
            record = dict(label=label, mutation=dict(path=keys, operation=operation, old=old, new=value),
                scratch_before_sha256=sha(scratch_bytes), scratch_after_sha256=sha(after),
                original_before_sha256=sha(before), original_after_sha256=sha(ORIGINAL.read_bytes()),
                scratch_unchanged=(scratch_bytes==after), original_unchanged=(before==ORIGINAL.read_bytes()),
                command=result,
                reconstruction='Deep copy verification.json; apply mutation; json.dumps(indent=2, allow_nan=True) plus LF; nonfinite replaces value with float(inf).')
            if not (result['returncode'] != 0 and record['scratch_unchanged'] and record['original_unchanged']):
                raise AssertionError(record)
            return record
    with ThreadPoolExecutor(max_workers=2) as executor:
        records = list(executor.map(probe, mutations))
    exclusive = run([sys.executable, '-B', 'audit/SOL-025/verify.py', '--create'])
    if not (exclusive['returncode'] != 0 and ORIGINAL.read_bytes() == before):
        raise AssertionError(exclusive)
    evidence = dict(schema_version=1, task_id='SOL-025', python_version=sys.version,
        selftest_source_sha256=sha(Path(__file__).read_bytes()), original_sha256=sha(before),
        probes=records, exclusive_create_rejection=exclusive,
        original_bytes_unchanged=ORIGINAL.read_bytes()==before,
        scratch_policy='Temporary scratch deleted only after before/after equality; exact scratch reconstructable from preserved original and minimal mutation.')
    with (HERE/'integrity-self-tests.json').open('x', encoding='utf-8', newline='\n') as file:
        json.dump(evidence, file, indent=2, allow_nan=False); file.write('\n')
    print(json.dumps(dict(probes=len(records), rejected=sum(r['command']['returncode']!=0 for r in records),
                         original_bytes_unchanged=evidence['original_bytes_unchanged'])))
if __name__=='__main__': main()
