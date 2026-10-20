"""One-shot SOL-035 evidence construction; never called by --check."""
import base64,copy,hashlib,importlib.util,json,os,pathlib,subprocess,sys,time,traceback
R=pathlib.Path(__file__).resolve().parents[2]; H=R/'audit/SOL-035'
sys.dont_write_bytecode=True
s=importlib.util.spec_from_file_location('portable',H/'verify.py'); v=importlib.util.module_from_spec(s); s.loader.exec_module(v)
def save(p,x): (H/p).write_text(json.dumps(x,indent=2,sort_keys=True)+'\n',encoding='utf8',newline='\n')
def snapshot(root):
 return {p.relative_to(root).as_posix():v.sha(p.read_bytes()) for d in v.PROTECTED for p in (root/d).rglob('*') if p.is_file()}
def read(p): return (R/p).read_bytes()
facts,mismatch=v.inventory_facts(read); save('canonical-inventory.json',facts)
identity=v.bindings(read)
save('verification.json',dict(identity=identity,canonical_inventory_sha256=v.sha(v.canonical(facts)),verifier_sha256=v.sha((H/'verify.py').read_bytes()),inventory_count=len(facts),historical_diagnosis_verified=111))
env={k:x for k,x in os.environ.items() if k.upper()!='PYTHONPATH'}; env['PYTHONDONTWRITEBYTECODE']='1'
checks=[]
def command(label,args,cwd=R):
 before=snapshot(cwd); started=time.time(); r=subprocess.run(args,cwd=cwd,env=env,capture_output=True)
 after=snapshot(cwd); (H/(label+'.stdout.txt')).write_bytes(r.stdout); (H/(label+'.stderr.txt')).write_bytes(r.stderr)
 record=dict(label=label,argv=[str(x) for x in args],cwd=str(cwd),exit_code=r.returncode,runtime_seconds=time.time()-started,PYTHONPATH_keys=[k for k in env if k.upper()=='PYTHONPATH'],stdout=label+'.stdout.txt',stderr=label+'.stderr.txt',before=before,after=after,unchanged=before==after)
 try: record['result']=json.loads(r.stdout)
 except (ValueError,UnicodeDecodeError): pass
 checks.append(record); save('clean-environment-checks.json',checks)
 return r
r=command('prescribed',[sys.executable,'-B','audit/SOL-035/verify.py','--check'])
if r.returncode: raise RuntimeError('initial prescribed replay failed: '+r.stderr.decode(errors='replace'))
# In-memory overlays keep originals untouched. Direct core calls also test that
# rejection is semantic rather than solely the outer evidence hash.
negative=[]
def reject(label,fn):
 try: fn()
 except (AssertionError,KeyError,ValueError,FileNotFoundError) as e: negative.append(dict(case=label,rejected=True,exception=type(e).__name__,diagnosis=str(e)))
 else: raise AssertionError('negative accepted: '+label)
def overlay(values): return lambda p: values[p] if p in values else read(p)
p='audit/SOL-002/review.md'; bad=read(p)+b'CONTENT CORRUPTION\n'
reject('content_corruption',lambda:v.check(overlay({p:bad})))
old=json.loads(read('audit/SOL-032/unchanged-inventory.json')); old[p]=v.sha(bad)
reject('content_corruption_rehashed_historical_metadata_core',lambda:v.inventory_facts(overlay({p:bad}),old))
new=copy.deepcopy(facts); new[p]['historical_raw_sha256']=v.sha(bad); new[p]['canonical_git_blob_sha256']=v.sha(bad)
reject('content_corruption_rehashed_new_metadata',lambda:v.check(overlay({p:bad,'audit/SOL-035/canonical-inventory.json':v.canonical(new)})))
def missing(p):
 if p=='audit/SOL-002/review.md': raise FileNotFoundError(p)
 return read(p)
reject('missing_path',lambda:v.check(missing))
old=copy.deepcopy(json.loads(read('audit/SOL-032/unchanged-inventory.json'))); old['audit/extra.txt']='a'*64
reject('extra_inventory_path',lambda:v.inventory_facts(read,old))
p='specs/ACCOUNTING.md'; raw=v.blob(v.BASE,p); lines=raw.splitlines(keepends=True); mixed=lines[0].replace(b'\n',b'\r\n')+b''.join(lines[1:])
reject('arbitrary_mixed_line_conversion',lambda:v.check_spelling(p,mixed,raw))
p='audit/chief/baseline-figures-history/trial-002-exports/baseline-h30-severe-path.png'; raw=read(p)
reject('binary_newline_conversion',lambda:v.check_spelling(p,raw.replace(b'\n',b'\r\n'),raw))
old=v.load_old(); runtime=json.loads(read('audit/SOL-032/runtime.json'))
bad=copy.deepcopy(runtime); bad['expected_file_deliverables']=43
reject('runtime_changed44_count_core',lambda:old.replay_runtime(bad))
bad=copy.deepcopy(runtime); e=bad['complete']; p=e['task']['deliverables'][0]; payload=b'fixture32 999\n'; e['blobs'][p]=base64.b64encode(payload).decode(); e['receipt']['artifacts_sha256'][p]=v.sha(payload)
reject('real_fixture_payload_rehashed_receipt_core',lambda:old.replay_runtime(bad))
bad=copy.deepcopy(runtime); e=bad['complete']; objects=e['git_proof']['objects']; oid=next(k for k,x in objects.items() if x['type']=='commit'); item=objects.pop(oid); payload=base64.b64decode(item['data'])+b'altered proof\n'; newoid=hashlib.sha1(b'commit '+str(len(payload)).encode()+b'\0'+payload).hexdigest(); item['data']=base64.b64encode(payload).decode(); objects[newoid]=item
# Rehash commit object and every explicit commit identity: original immutable
# runtime pin must still reject this otherwise internally consistent proof.
e['result_commit']=newoid; e['completed_entry']['commit']=newoid; e['commit_after_second']=newoid
reject('altered_rehashed_real_commit_proof_bound_to_original',lambda:v.check(overlay({'audit/SOL-032/runtime.json':v.canonical(bad)})))
# Demonstrate the structural old replay permits changed commit message proof;
# the new canonical pin above supplies the necessary exact-history binding.
try:
 old.replay_runtime(bad); negative.append(dict(case='old_semantic_replay_rehashed_commit_message',accepted_by_old_structural_replay=True,new_checker_rejected=True))
except Exception as e: negative.append(dict(case='old_semantic_replay_rehashed_commit_message',old_rejection=str(e),new_checker_rejected=True))
save('negative-checks.json',negative)
# Actual local sparse Git clones at both existing commits. No competition
# data/problem paths are checked out; no remote/network operation is used.
scratch=R/'.runtime/sol035-fixtures'; scratch.mkdir(parents=True,exist_ok=True)
setup=[]
def setupcmd(args,cwd):
 started=time.time(); r=subprocess.run(args,cwd=cwd,env=env,capture_output=True); setup.append(dict(argv=[str(a) for a in args],cwd=str(cwd),exit_code=r.returncode,runtime_seconds=time.time()-started,stdout=r.stdout.decode(errors='replace'),stderr=r.stderr.decode(errors='replace'))); save('checkout-construction.json',setup)
 if r.returncode: raise RuntimeError('fixture setup failed '+repr(args))
for ending in ('false','true'):
 dest=scratch/('autocrlf-'+ending)
 setupcmd(['git','clone','--shared','--no-checkout','--local',str(R),str(dest)],R)
 setupcmd(['git','config','core.autocrlf',ending],dest)
 setupcmd(['git','sparse-checkout','init','--cone'],dest)
 setupcmd(['git','sparse-checkout','set',*v.PROTECTED,'ops'],dest)
 for name,commit in [('accepted',v.ACCEPTED),('later-main',v.BASE)]:
  setupcmd(['git','checkout','--detach',commit],dest)
  # The successor audit did not exist at historical commits. Copy only its
  # compact task/verifier/metadata, each exact hash recorded below.
  target=dest/'audit/SOL-035'; target.mkdir(parents=True,exist_ok=True)
  copied={}
  for name2 in ('.gitattributes','task.json','task-runtime.json','verify.py','canonical-inventory.json','verification.json'):
   data=(H/name2).read_bytes(); (target/name2).write_bytes(data); copied[name2]=v.sha(data)
  # Accepted checkout predates new task base evidence. Do not spoof those
  # files: exercise the inventory core there; full --check runs at later main.
  if name=='accepted':
   code="import importlib.util,json,pathlib,sys; sys.dont_write_bytecode=True; s=importlib.util.spec_from_file_location('v','audit/SOL-035/verify.py'); v=importlib.util.module_from_spec(s); s.loader.exec_module(v); f,n=v.inventory_facts(lambda p:(v.ROOT/p).read_bytes()); assert f==json.loads((v.HOME/'canonical-inventory.json').read_bytes()); print(json.dumps(dict(status='passed',head=v.git('rev-parse','HEAD').decode().strip(),inventory_count=len(f),current_raw_spelling_mismatches=n,live_task=(v.ROOT/'.runtime/task.json').exists())))"
   args=[sys.executable,'-B','-c',code]
  else: args=[sys.executable,'-B','audit/SOL-035/verify.py','--check']
  require_live=not (dest/'.runtime/task.json').exists()
  if not require_live: raise AssertionError('fixture unexpectedly has live task')
  r=command(ending+'-'+name,args,dest); checks[-1]['copied_minimal_audit_sha256']=copied; checks[-1]['core_autocrlf']=ending; checks[-1]['actual_commit']=commit; checks[-1]['runtime_task_absent']=require_live; save('clean-environment-checks.json',checks)
  if r.returncode: raise RuntimeError('actual checkout verification failed '+ending+' '+name+': '+r.stderr.decode(errors='replace'))
save('construction-summary.json',dict(inventory_count=len(facts),current_mismatches=mismatch,negative_cases=len(negative),actual_checkouts=4,full_prescribed_checks=3,python=sys.version,executable=sys.executable))
