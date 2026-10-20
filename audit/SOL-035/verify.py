"""SOL-035 read-only canonical Git / exact checkout spelling replay. Only --check."""
import ast,base64,copy,hashlib,importlib.util,json,os,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
HOME=Path(__file__).resolve().parent
BASE='45e1da032122fca8c69ef508e82c36fd95ffe003'
PUB='c21af611288936474a866c550894dbca9fe14d75'
OLDPUB='21d235be2ba4cb8eb1baa25deb67ecaf9e2f6445'
ACCEPTED='d168757efbc70e4641deacc911976f1fa3bd7a7c'
OLDTASK='776a649d49058b47f71db7fdbb3269452077f2063c5ba313dea574467031c657'
RUNTIME_TASK_SHA256='fbf2b11843f312ee507ded7e176d36fadf202455ba561834d78181e7ed3a314b'
PROTECTED=('src','scripts','specs','tests','audit','handoff')
TEXT={'.md','.json','.py','.txt','.csv','.svg','.patch','.gitattributes'}
def require(ok,msg):
 if not ok: raise AssertionError(msg)
def sha(b): return hashlib.sha256(b).hexdigest()
def canonical(v): return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
def git(*a,input=None): return subprocess.check_output(['git',*a],cwd=ROOT,input=input,stderr=subprocess.PIPE)
def blob(c,p):
 require(not p.startswith(('data/','problem/')),'forbidden original input access')
 return git('show',c+':'+p)
def tree(c,roots):
 result={}
 for entry in git('ls-tree','-rz',c,'--',*roots).split(b'\0'):
  if not entry: continue
  meta,p=entry.split(b'\t',1); mode,typ,oid=meta.decode().split()
  require(typ=='blob' and mode in ('100644','100755'),'nonregular tracked entry')
  result[p.decode()]=oid
 return result

def blobs(entries):
 if not entries: return {}
 names=list(entries); raw=git('cat-file','--batch',input=('\n'.join(entries[p] for p in names)+'\n').encode()); pos=0; result={}
 for p in names:
  end=raw.index(b'\n',pos); header=raw[pos:end].split(); require(header[0].decode()==entries[p] and header[1]==b'blob','batch Git identity')
  n=int(header[2]); data=raw[end+1:end+1+n]; pos=end+n+2
  require(hashlib.sha1(b'blob '+str(n).encode()+b'\0'+data).hexdigest()==entries[p],'Git blob object hash')
  result[p]=data
 require(pos==len(raw),'batch trailing bytes'); return result

def spellings(p,raw):
 # Binary files are accepted only byte-for-byte. Text transports are whole-file
 # LF or whole-file CRLF, never arbitrary per-line substitutions.
 forms={'canonical':raw}
 if Path(p).suffix in TEXT or Path(p).name=='.gitattributes':
  try: raw.decode('utf8')
  except UnicodeDecodeError: return forms
  if b'\0' in raw: return forms
  lf=raw.replace(b'\r\n',b'\n')
  if b'\r' not in lf and raw in (lf,lf.replace(b'\n',b'\r\n')):
   forms.update(LF=lf,fullCRLF=lf.replace(b'\n',b'\r\n'))
 return forms

def check_spelling(p,actual,raw):
 forms=spellings(p,raw)
 require(actual in forms.values(),'changed/mixed checkout bytes: '+p)
 return next(k for k,v in forms.items() if v==actual)

def inventory_facts(read,recorded=None):
 entries=tree(OLDPUB,('src','scripts','specs','tests','audit'))
 entries={p:o for p,o in entries.items() if not p.startswith('audit/SOL-032/')}
 pinned=blobs(entries)
 old=json.loads(blob(ACCEPTED,'audit/SOL-032/unchanged-inventory.json')) if recorded is None else recorded
 require(set(old)==set(entries),'historical inventory exact paths missing/extra')
 facts={}; mismatches=0
 for p,raw in pinned.items():
  forms=spellings(p,raw); hashes={k:sha(v) for k,v in forms.items()}
  require(old[p] in hashes.values(),'historical raw hash is not exact pinned spelling: '+p)
  actual=read(p); spelling=check_spelling(p,actual,raw); mismatches+=sha(actual)!=old[p]
  facts[p]=dict(git_blob_oid=entries[p],canonical_git_blob_sha256=sha(raw),historical_raw_sha256=old[p],permitted_spelling_sha256=hashes)
 # Independently reconstruct all 111 historical diagnosis entries; no pass-label trust.
 diagnosis=json.loads(blob(BASE,'audit/chief/SOL-032-later-main-inventory-diagnosis.json'))
 require(diagnosis['mismatch_count']==111 and len(diagnosis['items'])==111,'diagnosis count')
 require(len({x['path'] for x in diagnosis['items']})==111,'diagnosis duplicate path')
 for item in diagnosis['items']:
  p=item['path']; f=facts[p]; valid=f['permitted_spelling_sha256']
  require(len(set(valid.values()))>1 and item['expected']==old[p] and item['expected']!=item['current'],'diagnosis expected raw identity: '+p)
  historical_forms=dict(spellings(p,pinned[p]))
  # Some chief-host bytes have only the last LF written as CRLF. Bind that
  # exact historical spelling/hash for diagnosis only; it is NEVER a permitted
  # current checkout spelling and check_spelling still rejects arbitrary mixes.
  lf=pinned[p].replace(b'\r\n',b'\n')
  if 'LF' in historical_forms and lf.endswith(b'\n'):
   historical_forms['historical_only_final_CRLF']=lf[:-1]+b'\r\n'
  matches={k:v for k,v in historical_forms.items() if sha(v)==item['current']}
  require(bool(matches),'diagnosis exact historical spelling: '+p)
  current=next(iter(matches.values()))
  require(len(current)==item['current_bytes'],'diagnosis historical byte size: '+p)
  f['chief_historical_diagnosis']=dict(expected_raw_sha256=item['expected'],observed_raw_sha256=item['current'],exact_spelling=next(iter(matches)),byte_count=len(current),permitted_for_current_checkout=item['current'] in valid.values())
 return facts,mismatches

def bindings(read):
 task=json.loads(read('audit/SOL-035/task.json')); published=blob(PUB,'ops/tasks/SOL-035.json')
 require(task==json.loads(published),'new immutable task publication')
 require(task['id']=='SOL-035' and task['attempt']==1 and task['owner']=='sol' and task['base_commit']==BASE and task['allowed_paths']==['audit/SOL-035'],'new task scope/base')
 check_spelling('task.json',read('audit/SOL-035/task.json'),published)
 require(sha(read('audit/SOL-035/task-runtime.json'))==RUNTIME_TASK_SHA256 and json.loads(read('audit/SOL-035/task-runtime.json'))==task,'exact runtime task snapshot')
 for p,h in task['parameters']['source_sha256'].items():
  raw=blob(BASE,p); require(sha(raw)==h,'new base source pin: '+p); check_spelling(p,read(p),raw)
 receipt=json.loads(blob(ACCEPTED,'handoff/SOL-032/result.json'))
 check_spelling('handoff/SOL-032/result.json',read('handoff/SOL-032/result.json'),blob(ACCEPTED,'handoff/SOL-032/result.json'))
 oldtask=json.loads(blob(OLDPUB,'ops/tasks/SOL-032.json'))
 require(receipt['task_sha256']==sha(canonical(oldtask))==OLDTASK,'original canonical task digest')
 require(receipt['base_commit']==oldtask['base_commit']=='e33b748c29d366559706d5272319d9138f0c7aa4' and receipt['artifact_hash_basis']=='canonical_git_blob' and receipt['status']=='completed','original receipt identity')
 for p,h in receipt['artifacts_sha256'].items():
  raw=blob(ACCEPTED,p); require(sha(raw)==h,'original receipt canonical artifact: '+p); check_spelling(p,read(p),raw)
 review=json.loads(read('audit/chief/SOL-032-review.json'))
 require(review['reviewed_commit']==ACCEPTED and review['task_sha256']==OLDTASK and review['code_verdict']=='approve' and review['artifacts_sha256']==receipt['artifacts_sha256'],'exact acceptance')
 return dict(task_canonical_digest_sha256=sha(canonical(task)),runtime_task_snapshot_sha256=RUNTIME_TASK_SHA256,task_publication=PUB,task_publication_blob_sha256=sha(published),task_publication_stripped_git_blob_sha256=sha(published.strip()),task_base=BASE,original_task_canonical_digest_sha256=OLDTASK,original_task_publication=OLDPUB,original_task_publication_blob_sha256=sha(blob(OLDPUB,'ops/tasks/SOL-032.json')),original_task_publication_stripped_git_blob_sha256=sha(blob(OLDPUB,'ops/tasks/SOL-032.json').strip()),accepted_result_commit=ACCEPTED,canonical_receipt_sha256=sha(blob(ACCEPTED,'handoff/SOL-032/result.json')),canonical_artifacts_sha256=receipt['artifacts_sha256'])

def path_guard(read):
 # Later commits may add tracked evidence. Original paths remain pinned above;
 # every additional protected path must match its actual HEAD Git blob exactly
 # or one of the same narrow text checkout spellings. Untracked extras fail.
 head=git('rev-parse','HEAD').decode().strip(); entries=tree(head,PROTECTED)
 entries={p:o for p,o in entries.items() if not p.startswith('audit/SOL-035/')}
 actual=set()
 for d in PROTECTED:
  for p in (ROOT/d).rglob('*'):
   if p.is_file() and not p.relative_to(ROOT).as_posix().startswith('audit/SOL-035/'):
    require(not p.is_symlink(),'symlink checkout path'); actual.add(p.relative_to(ROOT).as_posix())
 require(actual==set(entries),'protected checkout missing/extra paths: '+repr(sorted(actual.symmetric_difference(entries))[:12]))
 for p,raw in blobs(entries).items(): check_spelling(p,read(p),raw)
 return head,len(entries)

def load_old():
 path=ROOT/'audit/SOL-032/verify.py'
 spec=importlib.util.spec_from_file_location('sol032_readonly',path); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def check(read=None):
 read=read or (lambda p:(ROOT/p).read_bytes())
 identity=bindings(read); facts,mismatches=inventory_facts(read)
 expected=json.loads(read('audit/SOL-035/canonical-inventory.json'))
 require(facts==expected,'new reconstructed canonical inventory metadata')
 head,n=path_guard(read)
 old=load_old(); v=json.loads(read('audit/SOL-032/verification.json'))
 source=old.source_facts(read); require(source==v['source_facts'],'original source facts replay')
 boundary=old.boundaries(); require(boundary==json.loads(read('audit/SOL-032/boundaries.json')) and len(boundary)==22,'22 original boundary replay')
 runtime=old.replay_runtime(json.loads(read('audit/SOL-032/runtime.json'))); require(runtime==v['runtime_facts'],'original runtime replay')
 verification=json.loads(read('audit/SOL-035/verification.json'))
 require(verification['identity']==identity and verification['canonical_inventory_sha256']==sha(canonical(facts)) and verification['verifier_sha256']==sha(Path(__file__).read_bytes()),'new verification binding')
 return dict(status='passed',head=head,live_runtime_task_required=False,read_only=True,identity=identity,inventory_count=len(facts),historical_diagnosis_verified=111,current_raw_spelling_mismatches=mismatches,protected_paths=n,boundary_cases=len(boundary),runtime=runtime,python=sys.version,executable=sys.executable,PYTHONPATH_keys=[k for k in os.environ if k.upper()=='PYTHONPATH'],modules=old.modules())

if __name__=='__main__':
 require(sys.argv[1:]==['--check'],'only --check; no writes or repair mode')
 require(sys.version_info[:2]==(3,12),'Python 3.12 required')
 print(json.dumps(check(),sort_keys=True))
