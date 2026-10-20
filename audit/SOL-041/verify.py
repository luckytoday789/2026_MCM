"""Portable read-only SOL-041 replay. Never launches the producer writer.

Only --record writes new audit evidence. --check reads exact Git objects and saved
fixtures without relying on HEAD, remote branch tips or .runtime/task.json.
"""
import argparse,copy,csv,hashlib,io,json,math,os,platform,re,subprocess,sys,time,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
BASE='da37f1cff664c2ba5b475ddd07ae58630004ea3e'
RESULT='319781ef3c7fb5d4328a0ae4cea438bcc26a6f18'
TASK_DIGEST='a68184a570dfeb49ac72a36060b2e3d88ed0d2c45fb7f6f17f3ddced40434dfe'
BUNDLE='results/development/HY3-006/'

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
def digest(x):return hashlib.sha256(x).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,stderr=subprocess.PIPE)
def blob(p,c=RESULT):return git('show',c+':'+p)
def require(ok,msg):
 if not ok:raise AssertionError(msg)
def pairs(xs):
 d={}
 for k,v in xs:
  require(k not in d,'duplicate JSON key');d[k]=v
 return d
def strict(b):return json.loads(b,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite JSON')))
def table(p):
 r=csv.DictReader(io.StringIO(blob(p).decode(),newline=''));require(len(r.fieldnames)==len(set(r.fieldnames)),'duplicate columns')
 rows=list(r);require(all(None not in x for x in rows),'malformed CSV');return rows
def near(a,b,label,rel=1e-10,abs_=1e-9):
 a,b=float(a),float(b);require(math.isfinite(a) and math.isfinite(b) and math.isclose(a,b,rel_tol=rel,abs_tol=abs_),(label,a,b))
def save(p,x):
 with (HERE/p).open('w',encoding='utf8',newline='\n') as f:json.dump(x,f,indent=2,allow_nan=False);f.write('\n')
def ancestor(a,b):require(subprocess.run(['git','merge-base','--is-ancestor',a,b],cwd=ROOT,capture_output=True).returncode==0,'ancestry')
def authenticate():
 pins=strict((HERE/'task-pins.json').read_bytes());require(digest(canonical(pins))==TASK_DIGEST,'SOL-041 immutable task digest')
 require(pins['base_commit']==BASE and pins['id']=='SOL-041' and pins['allowed_paths']==['audit/SOL-041'],'review scope')
 p=pins['parameters']['producer'];require(p['result_commit']==RESULT and p['result_accepted'] is False,'exact unaccepted candidate')
 for name,h in pins['parameters']['source_sha256'].items():require(digest(blob(name,BASE))==h,'review source pin '+name)
 require(git('cat-file','-t',RESULT).strip()==b'commit','producer Git commit')
 require(git('rev-parse',RESULT+'^').decode().strip()==p['base_commit'],'producer parent E')
 ancestor(p['source_commit'],p['base_commit']);ancestor(p['base_commit'],p['publication_commit']);ancestor(p['publication_commit'],BASE)
 pt=strict(blob('ops/tasks/HY3-006.json',p['publication_commit']))
 require(digest(blob('ops/tasks/HY3-006.json',p['publication_commit']))==p['task_blob_sha256'],'producer task Git blob')
 require(digest(canonical(pt))==p['task_sha256'],'producer task canonical digest')
 require((pt['id'],pt['owner'],pt['attempt'],pt['base_commit'])==('HY3-006','hy3',1,p['base_commit']),'producer identity')
 q=next(x for x in strict(blob('ops/queue.json',p['publication_commit']))['tasks'] if x['id']=='HY3-006')
 require((q['state'],q['branch'],q['task_sha256'])==('ready',p['branch'],p['task_sha256']),'publication queue')
 config=strict(blob(p['config_path'],p['base_commit']));require(digest(blob(p['config_path'],p['base_commit']))==p['config_sha256'],'config Git pin')
 require(config['group']=='doubled' and config['references']==[] and config['run_id']=='HY3-006','no doubled imports')
 for name,h in config['source_sha256'].items():require(digest(blob(name,p['source_commit']))==h and digest(blob(name))==h,'producer source pin '+name)
 require(digest(blob(p['input']['path']))==p['input']['sha256'],'development input')
 raw=blob('handoff/HY3-006/result.json');require(digest(raw)==p['receipt_sha256'],'receipt pin');receipt=strict(raw)
 require(receipt['status']=='completed' and receipt['failure'] is None and receipt['artifact_hash_basis']=='canonical_git_blob','completed canonical receipt')
 require(receipt['task_sha256']==p['task_sha256'] and receipt['task_parameters']==pt['parameters'] and receipt['started_from_pinned_source'] is True,'receipt task binding')
 require(receipt['input_manifest']==strict(blob('data/manifest.json',p['base_commit'])),'input metadata binding')
 commands=pt['commands']+pt['validation_commands'];require(len(commands)==len(receipt['checks'])==4,'four parent commands')
 for argv,check in zip(commands,receipt['checks']):require(check['exit_code']==0 and check['argv'][1:]==argv[1:],'parent argv/exit')
 require(receipt['python'].startswith('3.12.'),'receipt Python')
 require(receipt['artifacts_sha256']==p['artifacts_sha256'],'all artifact pins')
 names=set(git('diff','--name-only',p['base_commit'],RESULT).decode().splitlines())
 require(names==set(p['artifacts_sha256'])|{'handoff/HY3-006/result.json'},'producer changed path set')
 inventory={}
 for name,h in p['artifacts_sha256'].items():
  raw=blob(name);require(digest(raw)==h,'artifact pin '+name)
  require(git('ls-tree',RESULT,'--',name).split()[0] in (b'100644',b'100755'),'regular Git file')
  require(len(raw)<=10485760,'file quota');inventory[name]={'bytes':len(raw),'sha256':h}
 require(len([n for n in inventory if n.startswith(BUNDLE)])==44,'44 result files')
 m=strict(blob(BUNDLE+'run_manifest.json'));require(m['status']=='completed' and m['configuration']==config,'manifest configuration/status')
 require(0<=m['elapsed_seconds']<=m['max_seconds']==1200,'generation writer runtime')
 require(m['fee_rate']==.005 and m['scenario_count']==120 and m['periods']==30,'manifest fixed shape')
 require(strict(blob(BUNDLE+'reference_imports.json'))=={'status':'no_imports','modes':[]},'no reference imports')
 require(m['provenance']['binding']['task']==pt and m['provenance']['binding']['publication_commit']==p['publication_commit'],'manifest historical task')
 checks=strict(blob(BUNDLE+'checks.json'));expected={'annual_ledgers':28800,'scenario_metrics':4800,'summary':40,'decisions':18000,'target_scores':17585}
 require(checks['counts']==expected and checks['status']=='passed','saved counts')
 counts={k:0 for k in expected}
 for rel,entry in m['artifacts'].items():
  raw=blob(BUNDLE+rel);require(digest(raw)==entry['sha256'] and len(raw)==entry['bytes'],'manifest file hash/bytes')
  rr=csv.reader(io.StringIO(raw.decode(),newline=''));header=next(rr);schema=entry['schema']
  require(header==[x[0] for x in schema] and len(header)==len(set(header)),'typed schema')
  seen=set();rows=0
  for cells in rr:
   require(len(cells)==len(schema),'CSV width');values={}
   for value,(key,typ,nullable) in zip(cells,schema):
    if value=='':require(nullable,'unexpected null');values[key]=None
    elif typ=='int':require(re.fullmatch(r'-?(0|[1-9][0-9]*)',value) is not None,'typed int');values[key]=int(value)
    elif typ=='float':require(math.isfinite(float(value)),'typed float');values[key]=float(value)
    elif typ=='bool':require(value in ('true','false'),'typed bool');values[key]=value=='true'
    else:values[key]=value
   key=tuple(values[x] for x in entry['keys']);require(key not in seen,'duplicate typed key');seen.add(key);rows+=1
  require(rows==entry['rows'],'actual row count');counts[rel.rsplit('/',1)[-1][:-4]]+=rows
 require(counts==expected,'fresh full table counts')
 notes=strict((HERE/'infrastructure-notes.json').read_bytes());release=next(x for x in strict(blob('ops/queue.json',notes['origin_main_at_start']))['tasks'] if x['id']=='SOL-037')
 require(release==notes['release'] and release['state']=='accepted','resource release exact Git bytes')
 return pins,{'status':'passed','inventory':inventory,'counts':counts,'generation_seconds':m['elapsed_seconds'],'receipt_per_command_wall_times':False,'publication':p['publication_commit'],'resource_release':release['reviewed_commit']}

def oracle(name,pins):
 raw=blob('audit/chief/'+name+'.py',BASE);require(digest(raw)==pins['parameters']['source_sha256']['audit/chief/'+name+'.py'],'oracle authentication')
 require(b'from safeinvest' not in raw and b'import safeinvest' not in raw,'oracle production import')
 ns={'__name__':'sol041_authenticated_'+name,'__file__':str(ROOT/'audit/chief'/ (name+'.py'))};exec(compile(raw,ns['__file__'],'exec'),ns);ns['ROOT']=ROOT
 return ns

def clean_record():
 r=strict((HERE/'clean-environment-checks.json').read_bytes());require(r['status']=='passed' and r['exit_code']==0 and r['launch_count']==1 and r['timeout_seconds']==600 and not r.get('timed_out'),'single fresh writer check')
 require(r['producer_commit']==RESULT and r['python'].startswith('3.12.') and r['duration_seconds']<=601,'writer Python/timing')
 before=strict((HERE/r['before_inventory']).read_bytes());after=strict((HERE/r['after_inventory']).read_bytes());require(before==after and r['unchanged'],'writer unchanged inventories')
 require(before['head']==RESULT and not before['runtime_task_exists'] and not before['git_status'],'writer actual clean Git checkout')
 for key in ('stdout','stderr'):require(digest((HERE/r[key]).read_bytes())==r[key+'_sha256'],'writer log hash')
 require(strict((HERE/r['stdout']).read_bytes())['status']=='passed','writer output')
 return r

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');ap.add_argument('--record',action='store_true');a=ap.parse_args();require(a.check!=a.record,'choose --check or --record')
 require(sys.version_info[:2]==(3,12),'Python3.12 required');start=time.monotonic();record={'status':'started','producer':RESULT,'base':BASE,'task_digest':TASK_DIGEST}
 try:
  pins,record['structural']=authenticate()
  record['writer']=clean_record()
  o=oracle('review_development_case_bundle',pins);record['all_accounting_metrics']=o['audit_group']('HY3-006',RESULT)
  o=oracle('review_development_decisions',pins);record['all_decisions_scores_calibration']=o['audit']('HY3-006',RESULT)
  from independent import audit_extra,fixtures_replay,history
  record['own_arithmetic']=audit_extra(sys.modules[__name__],record['all_decisions_scores_calibration'])
  record['historical_failures']=history(sys.modules[__name__],pins)
  record['fixtures']=fixtures_replay(sys.modules[__name__],record['own_arithmetic'],record=a.record)
  record['status']='passed';record['duration_seconds']=time.monotonic()-start
  if a.record:save('verification.json',record)
  else:
   saved=strict((HERE/'verification.json').read_bytes());require(saved['status']=='passed' and saved['producer']==RESULT and saved['task_digest']==TASK_DIGEST,'saved review evidence identity')
   for key in ('structural','all_accounting_metrics','own_arithmetic','historical_failures','fixtures'):
    require(canonical(saved[key])==canonical(record[key]),'saved expected/observed evidence mismatch '+key)
   left=dict(saved['all_decisions_scores_calibration']);right=dict(record['all_decisions_scores_calibration']);left.pop('checked_at',None);right.pop('checked_at',None)
   require(canonical(left)==canonical(right),'saved decision evidence mismatch')
  print(json.dumps({'status':record['status'],'producer':RESULT,'duration_seconds':record['duration_seconds'],'accounting_checks':record['all_accounting_metrics']['independent_numeric_checks'],'decision_checks':record['all_decisions_scores_calibration']['checks'],'own_checks':record['own_arithmetic']['checks'],'corruptions':record['fixtures']['rejected'],'read_only':a.check}))
 except BaseException as exc:
  record.update(status='failed',error_type=type(exc).__name__,error=str(exc),duration_seconds=time.monotonic()-start)
  if a.record:save('verification-failure-'+str(time.time_ns())+'.json',record)
  raise
if __name__=='__main__':main()
