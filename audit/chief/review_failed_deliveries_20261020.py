"""Read-only structural authentication of failed SOL-034/035/036 deliveries.
Does not promote failed code, findings, or positive verdicts.
"""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
COMMITS={'SOL-034':'632c95f03d3bbfeed1f847598eed3e6cfc5be264','SOL-035':'f33da50c4e16e85f7ca831e0a03d17c05c91cc79','SOL-036':'8a39da30e551f6e4fd54cfef6ec7b070b43d4d8d'}
def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT)
def sha(b): return hashlib.sha256(b).hexdigest()
def verify(tid,commit):
 task=json.loads((ROOT/'ops/tasks'/f'{tid}.json').read_bytes())
 queue=json.loads((ROOT/'ops/queue.json').read_bytes())['tasks']
 q=next(x for x in queue if x['id']==tid)
 raw=git('show',commit+':handoff/'+tid+'/result.json'); r=json.loads(raw)
 canonical=sha(json.dumps(task,sort_keys=True,separators=(',',':')).encode())
 assert canonical==q['task_sha256']==r['task_sha256']
 assert git('rev-parse','origin/work/sol/'+tid+'-a1').decode().strip()==commit
 assert git('rev-parse',commit+'^').decode().strip()==task['base_commit']
 subprocess.run(['git','merge-base','--is-ancestor',task['base_commit'],'origin/main'],cwd=ROOT,check=True)
 assert (r['task_id'],r['attempt'],r['role'],r['base_commit'])==(tid,task['attempt'],task['owner'],task['base_commit'])
 assert r['status']=='failed' and r['failure']
 assert r['artifact_hash_basis']=='canonical_git_blob' and r['started_from_pinned_source'] is True
 assert r['task_parameters']==task['parameters'] and r['python'].startswith('3.12.')
 assert r['input_manifest']==json.loads(git('show',task['base_commit']+':data/manifest.json'))
 changed=git('diff','--name-only',task['base_commit'],commit).decode().splitlines()
 assert set(changed)==set(r['artifacts_sha256'])|{'handoff/'+tid+'/result.json'}
 allowed=task['allowed_paths']+['handoff/'+tid]
 assert all(any(p==a or p.startswith(a+'/') for a in allowed) for p in changed)
 inv={}
 for p in changed:
  b=git('show',commit+':'+p); mode=git('ls-tree',commit,'--',p).decode().split()[0]
  assert mode in ('100644','100755') and len(b)<=10485760
  if p in r['artifacts_sha256']: assert sha(b)==r['artifacts_sha256'][p],p
  inv[p]={'sha256':sha(b),'bytes':len(b)}
 for p,h in task['parameters']['source_sha256'].items(): assert sha(git('show',task['base_commit']+':'+p))==h,p
 return {'task_id':tid,'reviewed_commit':commit,'task_sha256':canonical,'base_commit':task['base_commit'],'receipt_status':r['status'],'failure':r['failure'],'python':r['python'],'structural_authentication':'passed','source_pin_count':len(task['parameters']['source_sha256']),'changed_paths':len(changed),'missing_deliverables':sorted(set(task['deliverables'])-set(changed)),'check_exits':[c['exit_code'] for c in r['checks']],'prescribed_validation_count':len(task['validation_commands']),'inventory':inv,'decision':'not_accepted_failed_attempt','production_acceptance':False}
if __name__=='__main__':
 out=ROOT/'audit/chief/failed-deliveries-20261020-authentication.json'
 assert not out.exists()
 results={tid:verify(tid,c) for tid,c in COMMITS.items()}
 with out.open('x',encoding='utf8',newline='\n') as s: json.dump(results,s,indent=2);s.write('\n')
 print(json.dumps({k:{x:v[x] for x in ('structural_authentication','changed_paths','source_pin_count','missing_deliverables','check_exits','decision')} for k,v in results.items()},indent=2))
