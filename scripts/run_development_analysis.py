"""Fixed CLI. Successful writer children precede every assembly import.

Only stdlib imports are allowed above main's boundary. --check replays saved
analysis read-only and never launches writer generation/check subprocesses.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback
import tempfile
import uuid

WRITER_SHA256 = 'feca1b69de00cb5677337796c32ab91cd7262351bfed9c9ee5ac1ff5fab46226'
SCRIPT_SHA256 = 'b2ea4ac19ece30fd2bb535c2dcee5cdf48d26d0cba934a3b35cb6e08338ee19b'
LIMIT = 10485760


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def _json(raw):
    def pairs(items):
        d={}
        for k,v in items:
            if k in d: raise ValueError('duplicate JSON key')
            d[k]=v
        return d
    return json.loads(raw,object_pairs_hook=pairs,
        parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite JSON')))


def _relative(root,rel):
    if type(rel) is not str or not rel or '\\' in rel or Path(rel).is_absolute() or '..' in Path(rel).parts:
        raise ValueError('relative POSIX path required')
    p=root/rel
    if p.resolve()!=p or any(q.is_symlink() for q in (p,*p.parents)):
        raise ValueError('symlink path refused')
    return p


def _preflight(root,c,raw,config_path,output):
    """Authenticate authorization using stdlib/Git before any input-capable child."""
    def need(ok,message):
        if not ok: raise ValueError(message)
    def blob(commit,name):
        need(type(commit) is str and len(commit)==40 and all(k in '0123456789abcdef' for k in commit),'full Git commit required')
        return subprocess.check_output(['git','show',commit+':'+name],cwd=root,stderr=subprocess.PIPE)
    def ancestor(older,newer):
        need(subprocess.run(['git','merge-base','--is-ancestor',older,newer],cwd=root,capture_output=True).returncode==0,'C/E/P ancestry mismatch')
    def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
    need(c.get('split')=='development' and c.get('execution_authorized') is True,'no production authorization')
    task=_json((root/'.runtime/task.json').read_bytes())
    need(task.get('owner') in ('hy3','chief') and task.get('kind')=='commands' and task.get('split')=='development','assembly requires published fixed commands task')
    P=subprocess.check_output(['git','rev-parse','origin/main'],cwd=root).decode().strip()
    E=task['base_commit'];C=c['source_commit'];ancestor(C,E);ancestor(E,P)
    need(C!=E and E!=P,'distinct C/E/P publication sequence')
    published=_json(blob(P,'ops/tasks/'+task['id']+'.json'))
    need(canonical(published)==canonical(task),'runtime/published task mismatch')
    matches=[q for q in _json(blob(P,'ops/queue.json'))['tasks'] if q['id']==task['id']]
    need(len(matches)==1,'published task missing/duplicate')
    q=matches[0]
    need(q['state']=='ready' and q['owner']==task['owner'] and type(q['attempt']) is int and q['attempt']==task['attempt'] and
         q['branch']=='work/'+task['owner']+'/'+task['id']+'-a'+str(task['attempt']) and q['task_sha256']==_sha(canonical(task)), 'published task queue binding')
    pinned=blob(E,config_path)
    need(raw in (pinned,pinned.replace(b'\n',b'\r\n')) and task['parameters']['config_path']==config_path and
         task['parameters']['config_sha256']==_sha(pinned), 'pinned configuration mismatch')
    need(set(task['parameters'])==set(c)|{'config_path','config_sha256'} and all(canonical(task['parameters'][k])==canonical(v) for k,v in c.items()), 'fixed task parameters')
    expected={output+'/'+f for f in ('paired_differences.csv','comparison_gates.json','selection.json','profile_screen.json','profile_recommendations.json','run_manifest.json')}
    need(task['allowed_paths']==[output] and len(task['deliverables'])==6 and set(task['deliverables'])==expected,'assigned six files only')
    command=['{python}','-B','scripts/run_development_analysis.py','--config',config_path,'--output',output]
    need(task['commands']==[command] and task['validation_commands']==[command+['--check']],'fixed command contract')
    need(type(task['max_seconds']) is int and 1<=task['max_seconds']<=1500 and
         type(c['execution']['max_seconds']) is int and 1<=c['execution']['max_seconds']<=task['max_seconds'] and
         c['execution']['required_python']=='3.12' and c['execution']['cpu_only'] is True and
         type(c['execution']['max_artifact_bytes']) is int and c['execution']['max_artifact_bytes']==LIMIT,'fixed runtime contract')
    queue=_json(blob(E,'ops/queue.json'))['tasks']
    def approved(ident,commit,verdict,path=None,digest=None):
        if type(ident) is str and ident.startswith('CHIEF-'):
            import re
            need(re.fullmatch(r'CHIEF-[A-Z0-9_-]+',ident) is not None,'chief approval identity')
            expected_path='audit/chief/'+ident+'-review.json'
            review_raw=blob(E,expected_path);r=_json(review_raw)
            need((path is None or path==expected_path) and (digest is None or digest==_sha(review_raw)) and
                 r.get('task_id')==ident and r.get('kind')=='chief_takeover_approval' and
                 r.get('authorization')=='user-directed-two-node-takeover-20261020' and
                 r.get('reviewed_commit')==commit and r.get(verdict)=='approve','exact positive chief takeover approval required')
            if ident!='CHIEF-ANALYSIS-20261020':
                execution=r.get('oracle_execution')
                need(type(execution) is dict and type(execution.get('exit_code')) is int and execution['exit_code']==0 and
                     type(execution.get('argv')) is list and execution['argv'] and
                     type(execution.get('log_path')) is str and
                     _sha(blob(E,execution['log_path']))==execution.get('log_sha256'),'chief numerical approval oracle execution')
            if ident=='CHIEF-ANALYSIS-20261020':
                need(verdict=='code_verdict' and type(r.get('source_sha256')) is dict and
                     set(r['source_sha256'])==set(c['source_sha256']),'chief approval full source closure')
                for name,h in r['source_sha256'].items():
                    need(_sha(blob(commit,name))==h and h==c['source_sha256'][name],'chief approval source digest mismatch')
            return r
        matches=[q for q in queue if q['id']==ident]
        need(len(matches)==1,'missing approval')
        q=matches[0]
        need(q['state']=='accepted' and q['reviewed_commit']==commit and q.get(verdict)=='approve','exact positive approval required')
        review_raw=blob(E,q['acceptance_evidence']);r=_json(review_raw)
        need((path is None or path==q['acceptance_evidence']) and (digest is None or digest==_sha(review_raw)) and
             r.get('task_id')==ident and r.get('reviewed_commit')==commit and r.get(verdict)=='approve','chief approval binding')
        return r
    for ident,commit in c['acceptance'].items():approved(ident,commit,'code_verdict')
    for p in c['producers']:
        approved(p['task_id'],p['result_commit'],'result_verdict',p['acceptance_path'],p['acceptance_sha256'])
        nr=p['numerical_review'];review=approved(nr['task_id'],nr['reviewed_commit'],'code_verdict',nr['acceptance_path'],nr['acceptance_sha256'])
        need(review.get('producer_task_id')==p['task_id'] and review.get('reviewed_result_commit')==p['result_commit'] and
             review.get('result_verdict')=='approve','independent numerical approval required')
    for name,h in c['source_sha256'].items():
        need(_sha(blob(C,name))==h,'source Git blob mismatch')
        current=_relative(root,name).read_bytes()
        need(current in (blob(C,name),blob(C,name).replace(b'\n',b'\r\n')),'current source mismatch')
    # New implementation source must be the positively reviewed version.
    for name in ('src/safeinvest/policy_analysis_writer.py','scripts/run_development_analysis.py','audit/chief/takeover-analysis/schema.json'):
        need(blob(C,name)==blob(c['acceptance']['CHIEF-ANALYSIS-20261020'],name),'unaccepted assembly source')


def _writer_children(root,c,stage,started,*,_synthetic_script=None):
    """Private generated script seam is not a CLI/config option."""
    if sys.version_info[:2]!=(3,12): raise ValueError('Python 3.12 required')
    env={k:v for k,v in os.environ.items() if k.upper()!='PYTHONPATH'}
    if _synthetic_script is None:
        for name,h in (('src/safeinvest/policy_writer.py',WRITER_SHA256),
                       ('scripts/run_development_policy.py',SCRIPT_SHA256)):
            if _sha(_relative(root,name).read_bytes().replace(b'\r\n',b'\n'))!=h:
                raise ValueError('accepted writer source differs')
    if [p.get('group') for p in c['producers']]!=['primary','doubled']:
        raise ValueError('exactly primary then doubled required')
    records=[]
    for p in c['producers']:
        _relative(root,p['config_path']);_relative(root,p['root'])
        script='scripts/run_development_policy.py' if _synthetic_script is None else _synthetic_script
        argv=[sys.executable,'-B',script,'--config',p['config_path'],'--output',p['root'],'--check']
        before=time.monotonic(); remaining=c['execution']['max_seconds']-(before-started)
        if remaining<=0: raise TimeoutError('writer checks exceed task budget')
        try:
            if _synthetic_script is not None:
                child=subprocess.run(argv,cwd=root,env=env,capture_output=True,timeout=remaining)
            else:
                # Producer outputs and source retain their original immutable Git identity.
                # Current assembly may have reviewed private math extensions; they are
                # never substituted into the original writer checker import closure.
                with tempfile.TemporaryDirectory(prefix='safeinvest-producer-check-') as tmp:
                    checkout=Path(tmp)/'producer'
                    subprocess.run(['git','clone','--quiet','--shared','--no-checkout',str(root),str(checkout)],
                                   check=True,capture_output=True,timeout=remaining)
                    # Materialize only original checker inputs; raw/final datasets
                    # are absent even from this disposable historical checkout.
                    subprocess.run(['git','config','core.sparseCheckout','true'],cwd=checkout,
                                   check=True,capture_output=True,timeout=remaining)
                    sparse=checkout/'.git/info/sparse-checkout';sparse.parent.mkdir(parents=True,exist_ok=True)
                    sparse.write_text('\n'.join(('/src/','/specs/','/scripts/run_development_policy.py',
                        '/data/development/scenarios_001_120.csv','/'+p['root']+'/',
                        '/'+p['config_path']))+'\n',encoding='utf8')
                    remaining=c['execution']['max_seconds']-(time.monotonic()-started)
                    if remaining<=0: raise TimeoutError('checkout exceeds task budget')
                    subprocess.run(['git','-c','core.autocrlf=false','checkout','--quiet',p['result_commit']],
                                   cwd=checkout,check=True,capture_output=True,timeout=remaining)
                    remaining=c['execution']['max_seconds']-(time.monotonic()-started)
                    if remaining<=0: raise TimeoutError('checkout exceeds task budget')
                    child=subprocess.run(argv,cwd=checkout,env=env,capture_output=True,timeout=remaining)
            out=child.stdout.decode('utf-8',errors='strict');err=child.stderr.decode('utf-8',errors='strict')
            record=dict(group=p['group'],argv=argv,returncode=child.returncode,
                elapsed_seconds=time.monotonic()-before,stdout=out,stderr=err,
                stdout_sha256=_sha(child.stdout),stderr_sha256=_sha(child.stderr),
                python=platform.python_version(),pythonpath_absent=not any(k.upper()=='PYTHONPATH' for k in env),
                script_sha256=SCRIPT_SHA256 if _synthetic_script is None else _sha((root/script).read_bytes()))
        except subprocess.TimeoutExpired as exc:
            record=dict(group=p['group'],argv=argv,returncode=None,elapsed_seconds=time.monotonic()-before,
                stdout=(exc.stdout or b'').decode(errors='replace'),stderr=(exc.stderr or b'').decode(errors='replace'),status='timeout')
            with (stage/('checker-'+p['group']+'.json')).open('x',encoding='utf-8',newline='\n') as f: json.dump(record,f,indent=2)
            raise
        # Actual child logs survive both success and failure until exclusive completion.
        with (stage/('checker-'+p['group']+'.json')).open('x',encoding='utf-8',newline='\n') as f: json.dump(record,f,indent=2)
        records.append(record)
        if child.returncode!=0: raise ValueError('writer checker authentication failure: '+p['group'])
    return records


def _create(root,config_path,output,*,_synthetic_script=None,_after_checks=None):
    output_path=_relative(root,output)
    if output_path.exists() or output_path.is_symlink():
        raise ValueError('existing output root refused before config/check/analysis')
    output_path.mkdir(parents=True,exist_ok=False)
    stage=output_path/('partial-'+uuid.uuid4().hex);stage.mkdir()
    started=time.monotonic()
    try:
        raw=_relative(root,config_path).read_bytes();c=_json(raw)
        if _synthetic_script is None: _preflight(root,c,raw,config_path,output)
        records=_writer_children(root,c,stage,started,_synthetic_script=_synthetic_script)
        if _after_checks is not None:
            return _after_checks(records,stage)
        # No safeinvest module has been imported by this entry point before here.
        sys.path.insert(0,str(root/'src'))
        from safeinvest.policy_analysis_writer import produce_authenticated
        result=produce_authenticated(root,config_path,output,stage,started,records)
        if time.monotonic()-started>c['execution']['max_seconds']: raise TimeoutError('immutable task budget exceeded')
        for p in stage.rglob('*'):
            if p.is_file() and p.stat().st_size>LIMIT: raise ValueError('actual artifact byte limit exceeded')
        # Checker logs are embedded verbatim in the manifest. Do not add output files.
        for p in stage.glob('checker-*.json'): p.unlink()
        # Publish each file exclusively; publish the completion marker last.
        for p in list(stage.iterdir()):
            if p.name!='run_manifest.json': p.rename(output_path/p.name)
        # The completed manifest is the final atomic publication marker.
        (stage/'run_manifest.json').rename(output_path/'run_manifest.json')
        stage.rmdir()
        return result
    except BaseException as exc:
        failure=dict(status='failed',exception=type(exc).__name__,diagnosis=str(exc),
                     elapsed_seconds=time.monotonic()-started,traceback=traceback.format_exc())
        with (stage/'failure.json').open('x',encoding='utf-8',newline='\n') as f: json.dump(failure,f,indent=2)
        raise


def main(argv=None):
    parser=argparse.ArgumentParser(allow_abbrev=False,description='Authenticated fixed development analysis; no experiment options.')
    parser.add_argument('--config',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args(argv)
    root=Path(__file__).resolve().parents[1]
    sys.dont_write_bytecode=True
    if args.check:
        sys.path.insert(0,str(root/'src'))
        from safeinvest.policy_analysis_writer import check_production
        result=check_production(root,args.config,args.output)
    else:
        result=_create(root,args.config,args.output)
    print(json.dumps(dict(status='passed',read_only=args.check,result=result.get('status'))))


if __name__=='__main__': main()
