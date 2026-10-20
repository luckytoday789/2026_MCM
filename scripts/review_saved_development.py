"""Replay existing independent arithmetic on a published development bundle.

No producer generation. Prior missing logs remain missing historical evidence;
this task records a new, genuine read-only checker invocation and fresh oracles.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
PRODUCER='319781ef3c7fb5d4328a0ae4cea438bcc26a6f18'
REVIEWER='1f7f328313a5976aa9ff60375432d61457f7d811'


def git(*args,cwd=ROOT):
    return subprocess.check_output(['git',*args],cwd=cwd,stderr=subprocess.PIPE)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')


def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    loaded=importlib.util.module_from_spec(spec)
    sys.modules[name]=loaded
    spec.loader.exec_module(loaded)
    return loaded


def replay(output):
    assert sys.version_info[:2]==(3,12)
    task=json.loads((ROOT/'.runtime/task.json').read_bytes())
    assert task['owner']=='hy3' and task['kind']=='commands'
    assert task['parameters']['producer_commit']==PRODUCER
    assert task['parameters']['reviewer_commit']==REVIEWER
    output=output.resolve()
    assert output.is_relative_to(ROOT/'audit') and not output.exists()
    output.mkdir(parents=True)
    started=time.monotonic()
    record={'schema_version':1,'task_id':task['id'],'producer_commit':PRODUCER,
            'reviewer_commit':REVIEWER,'started_at':dt.datetime.now(dt.timezone.utc).isoformat(),
            'status':'started','producer_generations':0,'final_data_read':False,
            'historical_SOL041_acceptance':False,'mathematical_acceptance':'chief_review_required'}
    try:
        temporary=ROOT/'.runtime/reviews'/task['id']
        assert not temporary.exists(),'Preserve previous review; issue a new immutable attempt.'
        legacy=temporary/'original-review'
        legacy.mkdir(parents=True)
        files=git('ls-tree','-r','--name-only',REVIEWER,'audit/SOL-041').decode().splitlines()
        pins=task['parameters']['reviewer_files_sha256']
        assert set(files)==set(pins),'Exact historical source inventory changed.'
        for name in files:
            raw=git('show',REVIEWER+':'+name)
            assert sha(raw)==pins[name],name
            target=legacy/Path(name).name
            target.write_bytes(raw)
        v=module(legacy/'verify.py','hy3_saved_sol041')
        v.ROOT=ROOT
        original,record['structural']=v.authenticate()
        assert v.RESULT==PRODUCER
        # Sol-authored and earlier chief-authored independent algorithms are
        # kept at their exact original bytes. This wrapper adds no policy math.
        oracle=v.oracle('review_development_case_bundle',original)
        record['accounting']=oracle['audit_group']('HY3-006',PRODUCER)
        write(output/'accounting.json',record['accounting'])
        oracle=v.oracle('review_development_decisions',original)
        record['decisions']=oracle['audit']('HY3-006',PRODUCER)
        write(output/'decisions.json',record['decisions'])
        independent=module(legacy/'independent.py','hy3_saved_sol041_independent')
        record['sol_authored_arithmetic']=independent.audit_extra(v,record['decisions'])
        write(output/'independent-arithmetic.json',record['sol_authored_arithmetic'])
        record['corruptions']=independent.fixtures_replay(v,record['sol_authored_arithmetic'],record=False)
        write(output/'corruptions.json',record['corruptions'])
        # New checker logs are genuine and separately labelled. Never create
        # the four missing original logs or report the old delivery accepted.
        checkout=temporary/'producer-checkout'
        subprocess.run(['git','clone','--shared','--no-checkout',str(ROOT),str(checkout)],
                       check=True,capture_output=True,timeout=120)
        subprocess.run(['git','config','core.autocrlf','false'],cwd=checkout,check=True)
        subprocess.run(['git','checkout','--detach',PRODUCER],cwd=checkout,
                       check=True,capture_output=True,timeout=120)
        env={k:value for k,value in os.environ.items() if k.upper()!='PYTHONPATH'}
        env.update(PYTHONUTF8='1',MPLBACKEND='Agg')
        command=[sys.executable,'-B','scripts/run_development_policy.py','--config',
                 'specs/execution/HY3-006-file44.json','--output',
                 'results/development/HY3-006','--check']
        before=git('status','--porcelain',cwd=checkout).decode()
        tick=time.monotonic()
        with (output/'fresh-check.stdout.txt').open('wb') as stdout, (output/'fresh-check.stderr.txt').open('wb') as stderr:
            process=subprocess.run(command,cwd=checkout,env=env,stdin=subprocess.DEVNULL,
                                   stdout=stdout,stderr=stderr,timeout=600)
        record['fresh_writer_check']={'command':command,'exit_code':process.returncode,
            'elapsed_seconds':time.monotonic()-tick,'before_status':before,
            'after_status':git('status','--porcelain',cwd=checkout).decode(),
            'stdout_sha256':sha((output/'fresh-check.stdout.txt').read_bytes()),
            'stderr_sha256':sha((output/'fresh-check.stderr.txt').read_bytes()),
            'checker_only':True,'original_missing_logs_reconstructed':False}
        assert process.returncode==0,record['fresh_writer_check']
        assert record['fresh_writer_check']['after_status']==before,''
        record['status']='passed'
    except BaseException as error:
        record.update(status='failed',error_type=type(error).__name__,error=str(error))
        raise
    finally:
        record['finished_at']=dt.datetime.now(dt.timezone.utc).isoformat()
        record['elapsed_seconds']=time.monotonic()-started
        write(output/'verification.json',record)
    print(json.dumps({'status':record['status'],'producer_commit':PRODUCER,
                      'producer_generations':0,'elapsed_seconds':record['elapsed_seconds']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True,type=Path)
    replay(parser.parse_args().output)
