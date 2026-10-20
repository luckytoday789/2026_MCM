"""Fixed chief/HY3 personalized CLI; prerequisites checked before bridge import."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
import traceback
import uuid

LIMIT=10485760


def _sha(raw):return hashlib.sha256(raw).hexdigest()


def _json(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('duplicate JSON key')
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,
        parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite JSON')))


def _path(root,name):
    if type(name) is not str or not name or '\\' in name or Path(name).is_absolute() or '..' in Path(name).parts:
        raise ValueError('relative POSIX path required')
    path=root/name
    if path.resolve()!=path or any(p.is_symlink() for p in (path,*path.parents)):
        raise ValueError('symlink or path escape refused')
    return path


def _blob(root,commit,name):
    if type(commit) is not str or re.fullmatch('[0-9a-f]{40}',commit) is None:
        raise ValueError('full Git commit required')
    return subprocess.check_output(['git','show',commit+':'+name],cwd=root,stderr=subprocess.PIPE)


def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()


def _preflight(root,c,raw,config_path,output):
    """Stdlib/Git only; no safeinvest import, fit, simulation or output creation."""
    def need(ok,message):
        if not ok:raise ValueError(message)
    need(c.get('split')=='development' and c.get('execution_authorized') is True,'fixed development authorization required')
    need(c.get('input')=={'path':'data/development/scenarios_001_120.csv',
        'sha256':'9c4ad83f5dda86251a754e126528a71dd930ae88ed7cdb8a0663a327b6bfb7c7'},'fixed original input')
    task=_json((root/'.runtime/task.json').read_bytes());owner=task.get('owner')
    need(owner in ('chief','hy3') and task.get('kind')=='commands' and task.get('split')=='development', 'real chief/HY3 task required')
    P=subprocess.check_output(['git','rev-parse','origin/main'],cwd=root).decode().strip()
    E=task['base_commit'];C=c['source_commit']
    for old,new in ((C,E),(E,P)):
        need(subprocess.run(['git','merge-base','--is-ancestor',old,new],cwd=root,capture_output=True).returncode==0,'C/E/P ancestry mismatch')
    need(C!=E and E!=P,'distinct C/E/P publication sequence required')
    need(_canonical(task)==_canonical(_json(_blob(root,P,'ops/tasks/'+task['id']+'.json'))),'published immutable task mismatch')
    queue=[q for q in _json(_blob(root,P,'ops/queue.json'))['tasks'] if q['id']==task['id']]
    need(len(queue)==1 and queue[0]['state']=='ready' and queue[0]['owner']==owner and
         queue[0]['attempt']==task['attempt'] and queue[0]['task_sha256']==_sha(_canonical(task)) and
         queue[0]['branch']=='work/'+owner+'/'+task['id']+'-a'+str(task['attempt']),'task queue binding')
    pinned=_blob(root,E,config_path)
    need(raw in (pinned,pinned.replace(b'\n',b'\r\n')) and
         task['parameters']==dict(c,config_path=config_path,config_sha256=_sha(pinned)),'fixed configuration/task mismatch')
    cmd=['{python}','-B','scripts/run_personalized_development.py','--config',config_path,'--output',output]
    need(task['commands']==[cmd] and task['validation_commands']==[cmd+['--check']] and
        task['allowed_paths']==[output],'fixed command scope')
    e=c['execution'];need(e['required_python']=='3.12' and e['cpu_only'] is True and
        type(e['max_seconds']) is int and 1<=e['max_seconds']<=task['max_seconds']<=1500 and
        e['max_artifact_bytes']==LIMIT,'bounded execution')
    ident='CHIEF-PERSONALIZED-V2-20261020';need(c['acceptance']=={ident:C},'personalized source acceptance required')
    review=_json(_blob(root,E,'audit/chief/'+ident+'-review.json'))
    need(review.get('task_id')==ident and review.get('kind')=='chief_takeover_approval' and
        review.get('authorization')=='user-directed-two-node-takeover-20261020' and
        review.get('reviewed_commit')==C and review.get('code_verdict')=='approve' and
        review.get('source_sha256')==c['source_sha256'],'positive source closure approval required')
    for name,digest in c['source_sha256'].items():
        original=_blob(root,C,name);current=_path(root,name).read_bytes()
        need(_sha(original)==digest and current in (original,original.replace(b'\n',b'\r\n')),'source digest/checkout mismatch')
    a=c['analysis'];expected={a['root']+'/'+f for f in ('paired_differences.csv','comparison_gates.json',
        'selection.json','profile_screen.json','profile_recommendations.json','run_manifest.json')}
    need(set(a['artifacts_sha256'])==expected,'complete six-file analysis inventory required')
    approved=_blob(root,E,a['acceptance_path']);approval=_json(approved)
    need(_sha(approved)==a['acceptance_sha256'] and approval.get('task_id')==a['task_id'] and
        approval.get('reviewed_commit')==a['result_commit'] and approval.get('result_verdict')=='approve',
        'positive exact analysis result approval required')
    if a['task_id'].startswith('CHIEF-'):
        need(approval.get('kind')=='chief_takeover_approval' and
            approval.get('authorization')=='user-directed-two-node-takeover-20261020','chief result authorization')
    else:
        accepted=[q for q in _json(_blob(root,E,'ops/queue.json'))['tasks'] if q['id']==a['task_id']]
        need(len(accepted)==1 and accepted[0]['state']=='accepted' and
            accepted[0]['reviewed_commit']==a['result_commit'],'analysis task not accepted')
    for name,digest in a['artifacts_sha256'].items():
        original=_blob(root,a['result_commit'],name)
        need(_sha(original)==digest and _path(root,name).read_bytes() in
             (original,original.replace(b'\n',b'\r\n')),'analysis bytes/commit mismatch')
    if a['receipt'] is None:
        need(a['task_id'].startswith('CHIEF-'),'worker result requires real receipt')
    else:
        rr=_blob(root,a['result_commit'],a['receipt']['path']);receipt=_json(rr)
        need(_sha(rr)==a['receipt']['sha256'] and receipt['status']=='completed' and
            receipt['task_id']==a['task_id'] and all(receipt['artifacts_sha256'].get(k)==v
                for k,v in a['artifacts_sha256'].items()),'real original receipt mismatch')
    return task


def _inventory(root,paths):
    result={}
    for name in paths:
        path=_path(root,name)
        files=list(path.rglob('*')) if path.is_dir() else [path]
        for f in files:
            if f.is_symlink():raise ValueError('inventory symlink refused')
            if f.is_file():result[f.relative_to(root).as_posix()]=_sha(f.read_bytes())
    return result


def _children(root,c,logdir,started):
    """Actual original producer checks, then actual accepted assembly check."""
    raw=(root/c['analysis']['root']/'run_manifest.json').read_bytes(); m=_json(raw)
    ac=m['configuration']; records=[]
    spec=importlib.util.spec_from_file_location('original_analysis_cli',root/'scripts/run_development_analysis.py')
    cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
    # This script has stdlib-only imports; loading it cannot fit or simulate.
    for producer in ac['producers']:
        group=producer['group']; inventory_paths=[producer['root'],producer['config_path'],*c['source_sha256']]
        before=_inventory(root,inventory_paths)
        # Existing helper insists on both producers; execute its original pair once below.
        records.append(dict(group=group,before_inventory=before))
    original=cli._writer_children(root,ac,logdir,started)
    for saved,record,producer in zip(records,original,ac['producers']):
        saved.update(record);saved['after_inventory']=_inventory(root,
            [producer['root'],producer['config_path'],*c['source_sha256']])
    paths=[c['analysis']['root'],c['analysis']['config_path'],*c['source_sha256']]
    before=_inventory(root,paths)
    argv=[sys.executable,'-B','scripts/run_development_analysis.py','--config',c['analysis']['config_path'],
          '--output',c['analysis']['root'],'--check']
    env={k:v for k,v in os.environ.items() if k.upper()!='PYTHONPATH'}
    remaining=c['execution']['max_seconds']-(time.monotonic()-started)
    if remaining<=0:raise TimeoutError('prerequisite check budget exhausted')
    began=time.monotonic(); child=subprocess.run(argv,cwd=root,env=env,capture_output=True,timeout=remaining)
    r=dict(group='analysis',argv=argv,returncode=child.returncode,
        elapsed_seconds=time.monotonic()-began,stdout=child.stdout.decode('utf-8'),stderr=child.stderr.decode('utf-8'),
        stdout_sha256=_sha(child.stdout),stderr_sha256=_sha(child.stderr),
        python=platform.python_version(),pythonpath_absent=not any(k.upper()=='PYTHONPATH' for k in env),
        before_inventory=before,after_inventory=_inventory(root,paths))
    (logdir/'checker-analysis.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
    records.append(r)
    if child.returncode!=0:raise ValueError('upstream analysis checker failed')
    if any(r['before_inventory']!=r['after_inventory'] for r in records):raise ValueError('prerequisite checker changed evidence')
    return records


def _create(root,config_path,output):
    output_path=_path(root,output)
    if output_path.exists() or output_path.is_symlink():raise ValueError('existing output root refused')
    raw=_path(root,config_path).read_bytes();c=_json(raw)
    _preflight(root,c,raw,config_path,output)
    started=time.monotonic();logdir=root/'.runtime'/'personalized-preflight'/uuid.uuid4().hex
    logdir.mkdir(parents=True,exist_ok=False)
    try:
        records=_children(root,c,logdir,started)
        # This is the first import of the new bridge or personalization modules.
        sys.path.insert(0,str(root/'src'))
        from safeinvest.personalized_writer import produce_authenticated
        result=produce_authenticated(root,config_path,output,records,started=started)
        return result
    except BaseException as exc:
        (logdir/'failure.json').write_text(json.dumps(dict(status='failed',exception=type(exc).__name__,
            diagnosis=str(exc),traceback=traceback.format_exc()),indent=2)+'\n',encoding='utf-8')
        raise


def main(argv=None):
    parser=argparse.ArgumentParser(allow_abbrev=False,description=__doc__)
    parser.add_argument('--config',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--check',action='store_true');args=parser.parse_args(argv)
    if sys.version_info[:2]!=(3,12):raise ValueError('Python 3.12 required')
    sys.dont_write_bytecode=True;root=Path(__file__).resolve().parents[1]
    if args.check:
        sys.path.insert(0,str(root/'src'))
        from safeinvest.personalized_writer import check_production
        result=check_production(root,args.config,args.output)
    else:result=_create(root,args.config,args.output)
    print(json.dumps(dict(status='passed',read_only=args.check,result=result.get('status'))))


if __name__=='__main__':main()
