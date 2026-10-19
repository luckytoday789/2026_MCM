"""Prepare a source-only report index. No experiment inputs or outcome tables read."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
SNAPSHOT='8d00ca8eafc00fd636273be4125216e981289804'
COMPONENTS=(
 ('__init__','SOL-001','Package initialization'),
 ('accounting','SOL-001','One-way transfers, fee funding and exact inflation'),
 ('backtest','SOL-001','Annual decisions with prefix-only context'),
 ('baselines','SOL-001','Three fixed reference callbacks'),
 ('metrics','SOL-001','Growth, annual fluctuation and real drawdown'),
 ('experiments','SOL-004','Fixed baseline tables and prefix metrics'),
 ('policy_pilot','SOL-021','Corrected cost-aware kernel; K1 and K2 history retained'),
 ('policy_calibration','SOL-022','Generated-byte fold calibration arithmetic'),
 ('policy_analysis','SOL-016','Pure analysis on explicit metric grids'),
 ('policy_cases','SOL-025','Pure case tables; portable repair separately accepted'),
)

def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def blob(commit,path):return git('show',commit+':'+path)
def canonical(raw):return raw.replace(b'\r\n',b'\n')

def calculate():
    assert git('cat-file','-t',SNAPSHOT).strip()==b'commit'
    queue=json.loads(blob(SNAPSHOT,'ops/queue.json'))
    current=json.loads((ROOT/'ops/queue.json').read_bytes())
    locked={t['id']:t for t in queue['tasks']};active={t['id']:t for t in current['tasks']}
    records=[]
    for module,task_id,scope in COMPONENTS:
        entry=locked[task_id];live=active[task_id]
        assert entry['state']==live['state']=='accepted'
        commit=entry['reviewed_commit'];assert live['reviewed_commit']==commit
        if task_id in ('SOL-016','SOL-021','SOL-022','SOL-025'):
            assert entry['code_verdict']==live['code_verdict']=='approve'
        source_path='src/safeinvest/'+module+'.py';source=blob(commit,source_path)
        assert blob(SNAPSHOT,source_path)==source
        assert canonical((ROOT/source_path).read_bytes())==source
        task_path='ops/tasks/'+task_id+'.json';task=json.loads(blob(SNAPSHOT,task_path))
        task_digest=sha(json.dumps(task,sort_keys=True,separators=(',',':')).encode())
        assert entry['task_sha256']==live['task_sha256']==task_digest
        acceptance_path=entry['acceptance_evidence'];acceptance=blob(SNAPSHOT,acceptance_path)
        assert canonical((ROOT/acceptance_path).read_bytes())==acceptance
        receipt_path='handoff/'+task_id+'/result.json';receipt=json.loads(blob(commit,receipt_path))
        assert receipt['task_sha256']==task_digest
        records.append(dict(module=module,path=source_path,scope=scope,task_id=task_id,
            reviewed_commit=commit,canonical_source_sha256=sha(source),
            task_canonical_sha256=task_digest,receipt_path=receipt_path,
            receipt_canonical_sha256=sha(blob(commit,receipt_path)),
            acceptance_evidence=acceptance_path,acceptance_evidence_sha256=sha(acceptance)))
    return dict(schema_version=1,purpose='Accepted implementation source index for report preparation; no performance claim',
        acceptance_snapshot_commit=SNAPSHOT,components=records,
        limitations=['These code acceptances do not accept future run results.',
                    'Writer, production policy outcomes, personalized implementation and final freeze remain separate gates.',
                    'SOL-023 remains failed; SOL-025 separately repairs prescribed test discovery.',
                    'This is a preparation snapshot, not a final supplement inventory or submission artifact.'],
        competition_outcomes_read=False)

def render(index):
    lines=['# Accepted implementation source index','',
           'Preparation snapshot only. These reviews establish computational behavior within',
           'their stated scope; production results, recommendations and the final report need',
           'their own acceptance. No competition input or outcome table is read by this index.','',
           '| Component | Accepted review | Scope |','| --- | --- | --- |']
    for record in index['components']:
        lines.append('| '+record['module']+' | '+record['task_id']+' (`'+record['reviewed_commit'][:12]+'`) | '+record['scope']+' |')
    lines.extend(['','Full source, task, receipt and acceptance hashes are in component-index.json.',
                  'The acceptance snapshot is `'+SNAPSHOT+'`.',
                  'Check current source identity with `python -B report/build_component_index.py --check`.','',
                  'The failed SOL-023 attempt remains preserved. SOL-025 separately passed the',
                  'prescribed clean-environment commands and independent replay. No source index',
                  'entry authorizes final evaluation or certifies policy performance.',''])
    return '\n'.join(lines)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    value=calculate();doc=render(value)
    paths=(ROOT/'report/component-index.json',ROOT/'report/component-index.md')
    if args.check:
        before=[p.read_bytes() for p in paths]
        assert json.loads(before[0])==value
        assert canonical(before[1]).decode()==doc
        assert [p.read_bytes() for p in paths]==before
    else:
        assert all(not p.exists() for p in paths), 'Refuse to overwrite existing snapshot'
        with paths[0].open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
        with paths[1].open('x',encoding='utf-8',newline='\n') as f:f.write(doc)
    print(json.dumps(dict(components=len(value['components']),snapshot=SNAPSHOT,read_only=args.check,competition_outcomes_read=False)))

if __name__=='__main__':main()
