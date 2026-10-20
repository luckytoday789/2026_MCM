"""SOL-032 independent read-only audit replay; no live task or HEAD dependency."""
import ast
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
HOME=Path(__file__).resolve().parent
BASE='e33b748c29d366559706d5272319d9138f0c7aa4'
PREVIOUS='a24dca5d5494455407207e0fd70c06b258d4fd1f'
PUBLICATION='21d235be2ba4cb8eb1baa25deb67ecaf9e2f6445'
MODES=('conservative_cost','balanced_cost','growth_cost','balanced_context','balanced_adaptive','bills_keep','equal_weight_annual','equal_weight_buy_hold')
TABLES=('annual_ledgers','scenario_metrics','summary','decisions','target_scores')
TOP=('run_manifest.json','checks.json','calibrations.json','reference_imports.json')
APPROVALS=('SOL-021','SOL-022','SOL-025','SOL-031','SOL-032')

def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
def require(ok,msg):
    if not ok:raise AssertionError(msg)
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,stderr=subprocess.PIPE)
def blob(commit,name):return git('show',commit+':'+name)
def files(root):return [root+'/'+n for n in TOP]+[root+'/cases/'+m+'/'+t+'.csv' for m in MODES for t in TABLES]
def inventory():
    paths=git('ls-tree','-r','--name-only','-z',PUBLICATION,'--','src','scripts','specs','tests','audit').decode().split('\0')
    return {p:sha((ROOT/p).read_bytes()) for p in paths if p and not p.startswith('audit/SOL-032/')}
def modules():
    return {n:str(Path(m.__file__).resolve()) for n,m in sorted(sys.modules.items()) if n=='safeinvest' or n.startswith('safeinvest.') or n=='audit_coop'}

sys.path.insert(0,str(ROOT/'src'))
from safeinvest import policy_writer as w

def source_facts(read=None):
    read=read or (lambda p:(ROOT/p).read_bytes())
    task=json.loads(read('audit/SOL-032/task.json'))
    require(task==json.loads(blob(PUBLICATION,'ops/tasks/SOL-032.json')),'immutable publication mismatch')
    require(task['base_commit']==BASE and task['id']=='SOL-032' and task['attempt']==1 and task['owner']=='sol','task identity')
    require(task['allowed_paths']==['audit/SOL-032'] and task['parameters']['expected_file_deliverables']==44,'task scope/count')
    for p,h in task['parameters']['source_sha256'].items():
        raw=blob(BASE,p)
        require(sha(raw)==h,'canonical source pin: '+p)
        require(read(p) in (raw,raw.replace(b'\n',b'\r\n')),'changed source/evidence: '+p)
    name='src/safeinvest/policy_writer.py'
    old=blob(PREVIOUS,name).decode(); new=blob(BASE,name).decode()
    replacements=[
      ("'specs/POLICY_WRITER_RECOVERY.md','specs/POLICY_WRITER_GIT_PORTABILITY.md')", "'specs/POLICY_WRITER_RECOVERY.md','specs/POLICY_WRITER_GIT_PORTABILITY.md',\n    'specs/POLICY_WRITER_FILE_DELIVERABLES.md')"),
      ("{'SOL-021','SOL-022','SOL-025','SOL-031'}", "{'SOL-021','SOL-022','SOL-025','SOL-031','SOL-032'}"),
      ("    require(rel in task['deliverables'],'undeclared output root')", "    expected_files={rel+'/'+name for name in ('run_manifest.json','checks.json',\n        'calibrations.json','reference_imports.json')}\n    expected_files.update(rel+'/cases/'+mode+'/'+table+'.csv' for mode in MODES for table in TABLES)\n    require(task.get('allowed_paths')==[rel] and type(task.get('deliverables')) is list and\n            len(task['deliverables'])==len(expected_files) and set(task['deliverables'])==expected_files,\n            'exact assigned output root and 44 distinct file deliverables required')")]
    for a,b in replacements:
        require(old.count(a)==1,'unique expected predecessor text')
        old=old.replace(a,b)
    require(old==new,'source diff exceeds three approved edits')
    unchanged=[]
    for p in w.CLOSURE:
        if p in (name,'specs/POLICY_WRITER_FILE_DELIVERABLES.md'):continue
        require(blob(PREVIOUS,p)==blob(BASE,p),'changed computational closure: '+p);unchanged.append(p)
    def functions(raw):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(raw).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    before=functions(blob(PREVIOUS,'scripts/coop.py'));after=functions(blob(BASE,'scripts/coop.py'))
    runner=('run_task','deliver','execute_process','select_task','scope_check','changed_files','task_digest','validate_task')
    for n in runner:require(before[n]==after[n],'runner behavior changed: '+n)
    return dict(task_digest=sha(canonical(task)),publication=PUBLICATION,base=BASE,predecessor=PREVIOUS,
                expected_file_deliverables=44,unchanged_closure=unchanged,unchanged_runner_functions=list(runner),
                runner_exclusion='Pre-existing chief_model/chief_tick dispatch changes are outside worker runner and writer scope.')

def boundaries():
    C='b'*40;E='e'*40;P='f'*40;h='a'*64;out='results/development/generated32';cfg='specs/generated-memory-only.json'
    c=dict(schema_version=1,run_id='generated32',split='development',execution_authorized=True,source_commit=C,
      source_sha256={p:h for p in w.CLOSURE},acceptance={k:'c'*40 for k in APPROVALS},
      input=dict(path=w.INPUT_PATH,sha256=w.INPUT_HASH,scenario_ids=[1,120],periods=30),
      policy_config=dict(path=w.POLICY,sha256=h),layout_config=dict(path=w.LAYOUT,sha256=h),
      group='doubled',horizons=[5,6,15,25,30],references=[],expected_counts=w.expected_counts('doubled'),
      execution=dict(cpu_only=True,required_python='3.12',max_seconds=1500,max_artifact_bytes=10485760))
    t=dict(id='GENERATED32',attempt=1,owner='hy3',kind='commands',base_commit=E,max_seconds=1500,split='development',
      allowed_paths=[out],deliverables=files(out),parameters={},
      commands=[['{python}','-B','scripts/run_development_policy.py','--config',cfg,'--output',out]])
    require(len(t['deliverables'])==44 and len(set(t['deliverables']))==44,'independent expected file construction')
    results=[]
    def trial(label,change=None,reject=None,queue_change=None,review_change=None):
        cc=copy.deepcopy(c);tt=copy.deepcopy(t)
        if change:change(cc,tt)
        raw=canonical(cc);tt['parameters']=dict(cc,config_path=cfg,config_sha256=sha(raw))
        q={'tasks':[dict(id=k,state='accepted',reviewed_commit=v,code_verdict='approve',acceptance_evidence='audit/chief/'+k+'.json') for k,v in cc['acceptance'].items()]}
        if queue_change:queue_change(q)
        published={'tasks':[dict(id=tt['id'],state='ready',attempt=1,owner='hy3',branch='work/hy3/GENERATED32-a1',task_sha256=sha(canonical(tt)))]}
        def getblob(root,commit,name):
            if (commit,name)==(E,cfg):return raw
            if (commit,name)==(P,'ops/tasks/GENERATED32.json'):return canonical(tt)
            if name=='ops/queue.json' and commit in (P,E):return canonical(published if commit==P else q)
            if commit==E and name.startswith('audit/chief/'):
                ident=Path(name).stem;r=dict(task_id=ident,reviewed_commit=cc['acceptance'][ident],code_verdict='approve')
                if review_change:review_change(ident,r)
                return canonical(r)
            raise AssertionError('unexpected Git boundary '+commit+':'+name)
        edges=[]
        def ancestry(root,a,b):
            require((a,b) in ((E,P),(P,P),(C,E)),'unexpected ancestry');edges.append((a,b))
        def fakegit(root,*args):
            require(args==('rev-parse','origin/main'),'unexpected live Git query');return P.encode()
        with patch.object(w,'blob',getblob),patch.object(w,'ancestor',ancestry),patch.object(w,'git',fakegit),patch.object(w,'load_fixed_input',side_effect=AssertionError('INPUT LOADER BOMB')) as bomb:
            try:b=w.bind_task(ROOT,cc,cfg,raw,out,tt,P)
            except (ValueError,FileNotFoundError) as exc:
                require(reject is not None and reject in str(exc),'unexpected rejection '+label+': '+str(exc))
                results.append(dict(case=label,rejected=True,diagnosis=str(exc)))
            else:
                require(reject is None,'negative accepted: '+label)
                require(b['task_digest']==sha(canonical(tt)) and b['output']==out,'binding identity')
                require(edges==[(E,P),(P,P),(C,E)],'full C/E/P ancestry not traversed')
                results.append(dict(case=label,rejected=False,file_count=len(tt['deliverables']),task_digest=b['task_digest']))
            bomb.assert_not_called()
    trial('complete44')
    trial('reverse_order',lambda c,t:t['deliverables'].reverse())
    for label,vals in [('missing',files(out)[:-1]),('extra',files(out)+[out+'/extra.csv']),('duplicate',files(out)[:-1]+[files(out)[0]]),('root_only',[out]),('sibling_files',files(out+'-sibling'))]:
        trial(label,lambda c,t,v=vals:t.update(deliverables=v),'44 distinct file')
    for label,vals in [('sibling_root',[out+'-sibling']),('additional_prefix',[out,out+'-sibling']),('parent_prefix',['results/development']),('no_prefix',[])]:
        trial(label,lambda c,t,v=vals:t.update(allowed_paths=v),'exact assigned output root')
    for ident in APPROVALS:
        trial('missing_'+ident,lambda c,t,k=ident:c['acceptance'].pop(k),'positive kernel')
    for ident in ('SOL-026','SOL-029'):
        trial('retained_'+ident,lambda c,t,k=ident:c['acceptance'].update({k:'d'*40}),'cancelled writer approval')
    trial('SOL032_queue_not_positive',reject='dependency lacks exact positive approval',queue_change=lambda q:q['tasks'][-1].update(code_verdict='changes_required'))
    trial('SOL032_review_not_positive',reject='chief acceptance mismatch',review_change=lambda k,r:r.update(code_verdict='changes_required') if k=='SOL-032' else None)
    trial('SOL032_queue_missing',reject='dependency missing/duplicate',queue_change=lambda q:q.update(tasks=[x for x in q['tasks'] if x['id']!='SOL-032']))
    def missing_review(k,r):
        if k=='SOL-032':raise FileNotFoundError('generated missing SOL-032 review blob')
    trial('SOL032_review_absent',reject='missing SOL-032 review blob',review_change=missing_review)
    return results

def replay_runtime(evidence):
    require(evidence['expected_file_deliverables']==44,'recorded 44-count changed')
    facts=[]
    for label in ('complete','missing'):
        e=evidence[label];t=e['task'];r=e['receipt'];root=t['allowed_paths'][0]
        declared=files(root)
        require(t['deliverables']==declared and len(declared)==44,'runtime file inventory')
        require(r['task_id']==t['id'] and r['attempt']==t['attempt'] and r['role']==t['owner'] and r['base_commit']==t['base_commit'],'receipt identity')
        require(r['task_sha256']==sha(canonical(t)) and r['artifact_hash_basis']=='canonical_git_blob','receipt canonical identity')
        require(all(x['exit_code']==0 for x in r['checks']) and len(r['checks'])==2,'real fixture commands failed')
        require(r['status']==('completed' if label=='complete' else 'failed'),'runtime status')
        require(r['failure']==(None if label=='complete' else 'Missing deliverable: '+declared[-1]),'missing-file diagnosis')
        blobs={p:base64.b64decode(v) for p,v in e['blobs'].items()}
        require(set(blobs)==set(r['artifacts_sha256']),'exact receipt artifact inventory')
        for p,raw in blobs.items():require(sha(raw)==r['artifacts_sha256'][p],'canonical receipt hash: '+p)
        expected=declared if label=='complete' else declared[:-1]
        require(set(p for p in blobs if p.startswith(root+'/'))==set(expected),'exact output coverage')
        for index,p in enumerate(declared):
            if p in blobs:require(blobs[p]==('fixture32 '+str(index)+'\n').encode(),'fixture payload')
        proof=e['git_proof'];objects={k:(v['type'],base64.b64decode(v['data'])) for k,v in proof['objects'].items()}
        for oid,(typ,raw) in objects.items():require(hashlib.sha1(typ.encode()+b' '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==oid,'Git object hash')
        commit=objects[e['result_commit']];require(commit[0]=='commit','result commit proof')
        require(('parent '+t['base_commit']).encode() in commit[1].splitlines(),'runner did not start at exact task base')
        tree=commit[1].splitlines()[0].split()[1].decode()
        def lookup(name):
            node=tree
            for part in name.split('/'):
                typ,raw=objects[node];require(typ=='tree','Git tree proof')
                entries={};i=0
                while i<len(raw):
                    z=raw.index(b'\0',i);meta=raw[i:z].decode();oid=raw[z+1:z+21].hex();entries[meta.split(' ',1)[1]]=oid;i=z+21
                node=entries[part]
            typ,raw=objects[node];require(typ=='blob','Git blob proof');return raw
        require(lookup('fixture.py').decode()==evidence['fixture_script'] and sha(lookup('fixture.py'))==evidence['fixture_script_sha256'],'actual fixture script binding')
        for p,raw in blobs.items():require(lookup(p)==raw,'published artifact proof')
        require(json.loads(lookup('handoff/'+t['id']+'/result.json'))==r,'published receipt proof')
        require(e['completed_entry']['task_sha256']==r['task_sha256'] and e['completed_entry']['commit']==e['result_commit'],'dedup identity')
        require(e['select_after'] is None,'dedup selection')
        if label=='complete':require(e['second_receipt']==r and e['commit_after_second']==e['result_commit'] and e['outputs_before']==e['outputs_after'],'completed redelivery changed outputs')
        else:
            require(e['outputs_before']==e['outputs_after'] and e['run_task_calls']==1,'failed attempt retried/reset')
            require(e['successful_outputs_before_failed']==e['successful_outputs_after_failed'],'earlier completed outputs changed')
        facts.append(dict(case=label,declared=44,published_outputs=len(expected),canonical_hashes=len(blobs),git_objects=len(objects),status=r['status']))
    return facts

def check(read=None):
    read=read or (lambda p:(ROOT/p).read_bytes())
    get=lambda n:json.loads(read('audit/SOL-032/'+n))
    v=get('verification.json')
    require(sha(read('audit/SOL-032/verify.py'))==v['verifier_sha256'],'changed verifier')
    require(v['expected_file_deliverables']==44,'verification 44-count changed')
    for p,h in v['evidence_sha256'].items():require(sha(read('audit/SOL-032/'+p))==h,'changed evidence: '+p)
    source=source_facts(read)
    require(source==v['source_facts'],'source facts changed')
    boundary=boundaries();require(boundary==get('boundaries.json'),'boundary replay mismatch')
    runtime=replay_runtime(get('runtime.json'));require(runtime==v['runtime_facts'],'runtime replay mismatch')
    require(inventory()==get('unchanged-inventory.json'),'source/old-evidence inventory changed')
    return dict(status='passed',source=source,boundary_cases=len(boundary),runtime=runtime,modules=modules(),read_only=True)

if __name__=='__main__':
    require(sys.argv[1:]==['--check'],'only --check is supported; evidence cannot be repaired')
    require(sys.version_info[:2]==(3,12),'Python 3.12 required')
    print(json.dumps(check(),sort_keys=True))
