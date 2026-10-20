"""Isolated in-memory corruption tests. No originals are modified."""
import copy
import json
from pathlib import Path
import sys
from unittest.mock import patch
sys.dont_write_bytecode=True
HOME=Path(__file__).resolve().parent
sys.path.insert(0,str(HOME))
import verify as v

def main():
    before={p.name:v.sha(p.read_bytes()) for p in HOME.iterdir() if p.is_file()}
    source_before=v.inventory();results=[]
    original=lambda p:(v.ROOT/p).read_bytes()
    def test(label,overrides,expect):
        def read(p):return overrides[p] if p in overrides else original(p)
        try:v.check(read)
        except AssertionError as exc:
            v.require(expect in str(exc),'unexpected corruption diagnosis: '+str(exc));results.append(dict(case=label,rejected=True,diagnosis=str(exc)))
        else:raise AssertionError('corruption accepted '+label)
    target='src/safeinvest/policy_writer.py'
    test('source_modified',{target:original(target)+b'\n# isolated changed source\n'},'changed source/evidence')
    p='audit/SOL-032/verification.json';facts=json.loads(original(p));facts['expected_file_deliverables']=43
    test('recorded_count43',{p:v.canonical(facts)},'44-count changed')
    runtime_path='audit/SOL-032/runtime.json';runtime=json.loads(original(runtime_path));runtime['expected_file_deliverables']=43
    raw=v.canonical(runtime);facts=json.loads(original(p));facts['evidence_sha256']['runtime.json']=v.sha(raw)
    test('runtime_count43_rehashed',{p:v.canonical(facts),runtime_path:raw},'recorded 44-count changed')
    boundary_path='audit/SOL-032/boundaries.json';boundary=json.loads(original(boundary_path));boundary[0]['file_count']=43
    raw=v.canonical(boundary);facts=json.loads(original(p));facts['evidence_sha256']['boundaries.json']=v.sha(raw)
    test('boundary_count43_rehashed',{p:v.canonical(facts),boundary_path:raw},'boundary replay mismatch')
    # Keep all valid hashes but change an actual fixture output: independent replay must reject it.
    runtime=json.loads(original(runtime_path));name=runtime['complete']['task']['deliverables'][0]
    import base64
    changed=b'changed\n';runtime['complete']['blobs'][name]=base64.b64encode(changed).decode()
    runtime['complete']['receipt']['artifacts_sha256'][name]=v.sha(changed)
    raw=v.canonical(runtime);facts=json.loads(original(p));facts['evidence_sha256']['runtime.json']=v.sha(raw)
    test('runtime_payload_rehashed',{p:v.canonical(facts),runtime_path:raw},'fixture payload')
    # Simulate a later tip and an absent runtime task without writing either location.
    oldgit=v.git;oldread=Path.read_bytes;queries=[]
    def query(*args):
        queries.append(args)
        if 'HEAD' in args:return b'd'*40
        return oldgit(*args)
    def guarded_read(path):
        if path==v.ROOT/'.runtime/task.json':raise FileNotFoundError('simulated absent runtime task')
        return oldread(path)
    with patch.object(v,'git',query),patch.object(Path,'read_bytes',guarded_read):
        result=v.check()
    v.require(not any('HEAD' in q for q in queries),'checker used current HEAD')
    results.append(dict(case='later_HEAD_no_runtime_task',status=result['status'],git_queries=len(queries)))
    v.require(source_before==v.inventory(),'original source/evidence changed')
    after={p.name:v.sha(p.read_bytes()) for p in HOME.iterdir() if p.is_file()}
    v.require(before==after,'overlay tests changed originals')
    return dict(status='passed',cases=results,originals_unchanged=True,modules=v.modules())
if __name__=='__main__':print(json.dumps(main(),sort_keys=True))
