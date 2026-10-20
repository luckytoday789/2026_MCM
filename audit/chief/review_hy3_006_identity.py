"""Additional chief provenance/count audit for exact HY3-006 candidate only."""
from collections import Counter
import csv,hashlib,io,json,subprocess
from datetime import datetime,timezone
from pathlib import Path
from verify_canonical_receipt import verify
ROOT=Path(__file__).resolve().parents[2]
S='319781ef3c7fb5d4328a0ae4cea438bcc26a6f18';T='HY3-006'
def git(*a):return subprocess.check_output(['git',*a],cwd=ROOT)
def blob(s,p):return git('show',s+':'+p)
def sha(x):return hashlib.sha256(x).hexdigest()
def obj(s,p):return json.loads(blob(s,p))
def ancestor(a,b):subprocess.run(['git','merge-base','--is-ancestor',a,b],cwd=ROOT,check=True)

def main():
 structural=verify(T,S)
 task=obj('HEAD','ops/tasks/'+T+'.json');par=task['parameters'];E=task['base_commit'];C=par['source_commit']
 receipt=obj(S,'handoff/'+T+'/result.json');root='results/development/'+T+'/'
 m=obj(S,root+'run_manifest.json');binding=m['provenance']['binding'];P=binding['publication_commit']
 assert P=='fb0fcfa6caeee8eb2768c623952003bd82675191'
 for a,b in [(C,E),(E,P),(P,'origin/main')]:ancestor(a,b)
 assert git('rev-list','--count',E+'..'+P).strip()==b'1'
 assert json.loads(blob(P,'ops/tasks/'+T+'.json'))==task==binding['task']
 assert sha(blob(P,'ops/tasks/'+T+'.json'))==binding['task_blob_sha256']
 assert structural['task_sha256']==binding['task_digest']
 for path,digest in par['source_sha256'].items():
  assert sha(blob(C,path))==sha(blob(E,path))==sha(blob(S,path))==digest,path
 config=blob(E,par['config_path']);assert sha(config)==par['config_sha256']
 assert json.loads(config)==m['configuration']
 assert sha(blob(E,'scripts/check_worker_env.py'))==par['environment_check_sha256']
 queue=obj(E,'ops/queue.json')['tasks']
 for id,commit in par['acceptance'].items():
  row=next(r for r in queue if r['id']==id)
  assert row['state']=='accepted' and row['reviewed_commit']==commit
 names=git('ls-tree','-r','--name-only',S,'--',root).decode().splitlines()
 assert set(names)==set(task['deliverables']) and len(names)==44
 counts=Counter();inventory={}
 for path in names:
  raw=blob(S,path);assert len(raw)<=10485760
  inventory[path]=dict(sha256=sha(raw),bytes=len(raw))
  if path.endswith('.csv'):
   rows=list(csv.DictReader(io.StringIO(raw.decode(),newline='')))
   key=path.rsplit('/',1)[1][:-4];counts[key]+=len(rows)
   desc=m['artifacts'][path[len(root):]]
   assert desc['rows']==len(rows) and desc['bytes']==len(raw) and desc['sha256']==sha(raw)
 assert dict(counts)==dict(annual_ledgers=28800,scenario_metrics=4800,summary=40,decisions=18000,target_scores=17585)
 assert obj(S,root+'checks.json')['counts']==dict(counts)
 assert obj(S,root+'reference_imports.json')==dict(modes=[],status='no_imports')
 assert 0<m['elapsed_seconds']<=1200 and m['max_seconds']==1200 and task['max_seconds']==1500
 assert (m['group'],m['fee_rate'],m['split'],m['python'],m['status'])==('doubled',.005,'development','3.12.10','completed')
 primary='6aa2ccdce80834c8beb52a827993f1f587d1d8a6'
 assert blob(primary,'results/development/HY3-004/calibrations.json')==blob(S,root+'calibrations.json')
 previous='665e14502405ca560fe1f78876a189ae5f688f23'
 oldroot='results/development/HY3-005/partial-557463b8f9d845ed9fd2277728be72cb/cases/'
 unchanged=[]
 for path in git('ls-tree','-r','--name-only',previous,'--',oldroot).decode().splitlines():
  equivalent=root+'cases/'+path[len(oldroot):]
  assert blob(previous,path)==blob(S,equivalent)
  unchanged.append(dict(failed_path=path,new_path=equivalent,sha256=sha(blob(S,equivalent))))
 assert len(unchanged)==15
 oldcfg=obj(E,'specs/execution/HY3-005-file44.json');newcfg=json.loads(config)
 oldcfg['run_id']='HY3-006';assert oldcfg==newcfg
 record=dict(schema_version=1,checked_at=datetime.now(timezone.utc).isoformat(),task_id=T,
  reviewed_commit=S,status='passed',structural=structural,source_C=C,configuration_E=E,publication_P=P,
  source_pins_checked=len(par['source_sha256']),output_count=44,counts=dict(counts),inventory=inventory,
  writer_generation_seconds=m['elapsed_seconds'],writer_limit_seconds=1200,parent_task_limit_seconds=1500,
  same_calibration_as_unaccepted_primary=True,identical_preserved_failed_case_artifacts=unchanged,
  scientific_configuration_difference='run_id only',result_accepted=False,independent_review_required=True,
  limitation='Receipt has four command exits, not individual command wall times; generation time is from saved manifest. Chief read-only subprocess timing is recorded separately. No strategy recommendation or final-data permission.')
 path=ROOT/'audit/chief/HY3-006-provenance-review.json';assert not path.exists()
 path.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
 print(json.dumps(dict(status='passed',source_pins=record['source_pins_checked'],outputs=44,counts=dict(counts),generation_seconds=m['elapsed_seconds'],result_accepted=False)))
if __name__=='__main__':main()
