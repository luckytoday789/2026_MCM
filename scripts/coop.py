"""Git-backed, single-owner task runner. Python stdlib only; no embedded secrets."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / '.runtime'
REMOTE = 'origin'
ROLES = {'chief', 'sol', 'hy3'}
CHIEF_CHECKPOINT_VERSION = 2
NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,70}$')

def now():
    return dt.datetime.now(dt.timezone.utc)

def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)

def git(*args, cwd=ROOT, stdin=None, check=True):
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0')
    # Binary pipes prevent Windows from changing mktree's filename delimiter LF to CRLF.
    p = subprocess.run(['git', *args], cwd=cwd,
                       input=stdin.encode('utf-8') if stdin is not None else None,
                       capture_output=True, env=env, timeout=120)
    if check and p.returncode:
        raise RuntimeError(f"git {args[0]} failed: {p.stderr.decode('utf-8',errors='replace').strip()}")
    return p.stdout.decode('utf-8',errors='replace').strip() if p.returncode == 0 else None

def remote_json(path, branch='main'):
    result = git('show', f'{REMOTE}/{branch}:{path}', check=False)
    return json.loads(result) if result else None

def fetch():
    git('fetch', '--prune', REMOTE)

def control():
    c = remote_json('ops/control.json')
    if not c:
        raise RuntimeError('Coordinator bootstrap is not published yet.')
    return c

def stopped(c):
    return (c['state'] != 'running' or (RUNTIME / 'STOP').exists()
            or now() >= dt.datetime.fromisoformat(c['deadline']))

def clean_main():
    if git('branch', '--show-current') != 'main':
        raise RuntimeError('Runner root must be a dedicated checkout on main.')
    if git('status', '--porcelain'):
        raise RuntimeError('Runner root contains uncommitted work; preserve it and resolve before running.')
    git('merge', '--ff-only', f'{REMOTE}/main')

def identity(role):
    path = RUNTIME / f'{role}-identity.json'
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))['machine_id']
    value = uuid.uuid4().hex
    dump(path, {'machine_id': value})
    return value

def publish_status(role, state, **extra):
    """A role has one writer. Push rejection prevents racing writers overwriting status."""
    branch = f'status/{role}'
    git('fetch', REMOTE, f'refs/heads/{branch}:refs/remotes/{REMOTE}/{branch}', check=False)
    previous = remote_json('status.json', branch)
    machine = identity(role)
    if previous and previous.get('machine_id') != machine:
        lease = dt.datetime.fromisoformat(previous.get('lease_until','2000-01-01T00:00:00+00:00'))
        if lease > now() and previous.get('state') not in {'stopped','error'}:
            raise RuntimeError(f'Another machine holds the active {role} lease; do not start a duplicate worker.')
    value = {'role':role,'machine_id':machine,'state':state,'python':sys.version.split()[0],'updated_at':now().isoformat(),
             'lease_until':(now()+dt.timedelta(minutes=10)).isoformat(),**extra}
    body = json.dumps(value, ensure_ascii=False, indent=2)+'\n'
    blob = git('hash-object','-w','--stdin',stdin=body)
    tree = git('mktree',stdin=f'100644 blob {blob}\tstatus.json\n')
    parent = git('rev-parse','--verify',f'{REMOTE}/{branch}',check=False)
    args = ['commit-tree',tree]
    if parent:
        args += ['-p',parent]
    commit = git(*args,stdin=f'{role}: {state}\n')
    git('push',REMOTE,f'{commit}:refs/heads/{branch}')
    git('update-ref',f'refs/remotes/{REMOTE}/{branch}',commit)
    dump(RUNTIME / f'{role}-status.json',value)
    return value

def task_digest(task):
    return hashlib.sha256(json.dumps(task, sort_keys=True, separators=(',',':')).encode()).hexdigest()

def validate_task(task):
    assert task['owner'] in {'sol','hy3'}
    assert NAME.fullmatch(task['id'])
    assert type(task['attempt']) is int and task['attempt'] >= 1
    assert re.fullmatch(r'[0-9a-f]{40}',task['base_commit'])
    assert task['kind'] in {'agent','commands'}
    assert task['instructions'].strip()
    assert task['allowed_paths'] and task['deliverables']
    for key in ['allowed_paths','deliverables']:
        for value in task[key]:
            assert value and not value.startswith(('/', '\\')) and ':' not in value
            assert '..' not in Path(value).parts and '\\' not in value
    for key in ['commands','validation_commands']:
        for command in task.get(key,[]):
            assert isinstance(command,list) and command and all(isinstance(s,str) for s in command)
    assert task['max_seconds'] > 0 and task['max_seconds'] <= 7200
    if task['owner'] == 'hy3':
        assert task['kind'] == 'commands', 'HY3 runner executes only explicit reviewed commands.'
    if task.get('split') == 'final':
        assert task.get('freeze_sha256'), 'Final task requires a recorded freeze.'

def allowed(path, prefixes):
    return any(path == p.rstrip('/') or path.startswith(p.rstrip('/')+'/') for p in prefixes)

def changed_files(work, base):
    tracked = git('diff','--name-only',base,cwd=work).splitlines()
    untracked = git('ls-files','--others','--exclude-standard',cwd=work).splitlines()
    return sorted(set(tracked+untracked))

def scope_check(task, work):
    permitted = task['allowed_paths'] + [f"handoff/{task['id']}"]
    changed = changed_files(work,task['base_commit'])
    for name in changed:
        assert allowed(name,permitted), f'Outside assigned paths: {name}'
        p = work / name
        assert not p.is_symlink(), f'Symlink not allowed in handoff: {name}'
        assert not any(part in {'.git','.venv','.runtime','node_modules'} for part in Path(name).parts)
        assert not Path(name).name.startswith('.env')
        if p.exists():
            assert p.stat().st_size <= 10*1024*1024, f'Artifact >10MB: {name}; split or ask coordinator.'
    return changed

def select_task(role):
    q = remote_json('ops/queue.json') or {'tasks':[]}
    accepted = {x['id'] for x in q['tasks'] if x['state']=='accepted'}
    state_path = RUNTIME / f'{role}-completed.json'
    done = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {}
    for item in q['tasks']:
        if item['state']!='ready':
            continue
        task = remote_json(f"ops/tasks/{item['id']}.json")
        if task['owner'] != role or not set(task.get('depends_on',[])) <= accepted:
            continue
        validate_task(task)
        key = f"{task['id']}-a{task['attempt']}"
        if key in done:
            if done[key].get('task_sha256') != task_digest(task):
                raise RuntimeError('A finished task changed without a new attempt.')
            continue
        branch = f"work/{role}/{key}"
        prior = remote_json(f"handoff/{task['id']}/result.json",branch)
        if prior:
            if prior.get('task_sha256') != task_digest(task):
                raise RuntimeError('Published task was changed without a new attempt.')
            continue
        return task
    return None

def execute_process(command, cwd, log, deadline, role, task_id):
    command = [sys.executable if x=='{python}' else x for x in command]
    env = dict(os.environ, PYTHONUTF8='1', MPLBACKEND='Agg')
    env['MPLCONFIGDIR'] = str(RUNTIME / 'matplotlib')
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('w',encoding='utf-8') as out:
        p = subprocess.Popen(command,cwd=cwd,stdout=out,stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL,env=env,shell=False)
        # Persist the child PID so a supervisor cannot overlap an orphaned turn.
        child_path = RUNTIME / f'{role}-active-child.json'
        dump(child_path, {'pid':p.pid, 'parent_pid':os.getpid(), 'task_id':task_id,
                         'started_at':now().isoformat(),
                         'deadline':(now()+dt.timedelta(seconds=max(0,deadline-time.monotonic()))).isoformat()})
        last_heartbeat = time.monotonic()
        while p.poll() is None:
            if time.monotonic() >= deadline or (RUNTIME/'STOP').exists():
                if os.name=='nt':
                    subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True)
                else:
                    p.terminate()
                try:
                    p.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    p.kill()
                raise RuntimeError('Task timeout or local stop requested; partial work preserved.')
            if time.monotonic()-last_heartbeat >= 240:
                try:
                    publish_status(role,'running',task_id=task_id)
                except Exception as error:
                    # Losing network during a heartbeat must not abandon a live
                    # child and let the watcher launch an overlapping retry.
                    dump(RUNTIME/f'{role}-heartbeat-error.json',
                         {'at':now().isoformat(),'error':str(error),'child_pid':p.pid,
                          'note':'Task monitoring continues; retry heartbeat after 240 seconds.'})
                last_heartbeat = time.monotonic()
            time.sleep(2)
        child_path.unlink(missing_ok=True)
    return {'argv':command,'exit_code':p.returncode,'log':str(log.relative_to(ROOT))}

def deliver(task,work,branch,report):
    role=task['owner']
    key=f"{task['id']}-a{task['attempt']}"
    commit=git('rev-parse','HEAD',cwd=work)
    git('push',REMOTE,f'HEAD:refs/heads/{branch}',cwd=work)
    completed=RUNTIME/f'{role}-completed.json'
    done=json.loads(completed.read_text(encoding='utf-8')) if completed.exists() else {}
    done[key]={'status':report['status'],'commit':commit,'task_sha256':task_digest(task)}
    dump(completed,done)
    publish_status(role,'submitted',task_id=task['id'],result_status=report['status'],commit=commit,branch=branch)
    return report

def run_task(task, backend):
    role = task['owner']
    key = f"{task['id']}-a{task['attempt']}"
    work = RUNTIME/'worktrees'/key
    branch = f'work/{role}/{key}'
    if work.exists():
        receipt=work/'handoff'/task['id']/'result.json'
        if receipt.exists() and not git('status','--porcelain',cwd=work):
            report=json.loads(receipt.read_text(encoding='utf-8'))
            if report['task_sha256']==task_digest(task) and git('branch','--show-current',cwd=work)==branch:
                scope_check(task,work)
                return deliver(task,work,branch,report)
        raise RuntimeError(f'Incomplete attempt exists at {work}; inspect it before issuing a new attempt.')
    if task.get('split') == 'final':
        c = control()
        frozen = git('show',f"{REMOTE}/main:ops/freeze.json",check=False)
        if not c.get('final_data_open') or not frozen or hashlib.sha256(frozen.encode()).hexdigest()!=task['freeze_sha256']:
            raise RuntimeError('Final data gate is closed or freeze hash mismatches.')
    work.parent.mkdir(parents=True, exist_ok=True)
    git('worktree','add','-b',branch,str(work),task['base_commit'])
    dump(work/'.runtime/task.json',task)
    publish_status(role,'running',task_id=task['id'],branch=branch)
    deadline = time.monotonic()+task['max_seconds']
    checks=[]
    failure=None
    try:
        if task['kind']=='agent':
            if backend!='codex':
                raise RuntimeError('Agent task needs Codex backend.')
            prompt=(f"You are role={role} in the authorized SafeInvest team. Read AGENTS.md and .runtime/task.json. "
                    "Complete only that task in this worktree. Do not commit, push, change branches, edit the task, "
                    "or start another watcher; the parent runner handles delivery. Respect allowed_paths and base version. "
                    "Write real deliverables and perform checks. Report blockers rather than inventing parameters. "
                    "The task is authorized; continue through routine fixes.\n"+task['instructions'])
            binary = shutil.which('codex')
            if not binary:
                raise RuntimeError('Codex executable not found.')
            command=[binary,'exec','--approve-for-me','--model','gpt-6.1-sol','-c','model_reasoning_effort="xhigh"',
                     '--cd',str(work),'--output-last-message',str(work/'.runtime/agent-last.txt'),prompt]
            check=execute_process(command,work,RUNTIME/'logs'/f'{key}-agent.log',deadline,role,task['id'])
            checks.append(check)
            assert check['exit_code']==0, 'Codex task exited unsuccessfully.'
        else:
            for i,command in enumerate(task.get('commands',[])):
                check=execute_process(command,work,RUNTIME/'logs'/f'{key}-run-{i}.log',deadline,role,task['id'])
                checks.append(check)
                assert check['exit_code']==0, f'Computation command {i} failed.'
        scope_check(task,work)
        for i,command in enumerate(task.get('validation_commands',[])):
            check=execute_process(command,work,RUNTIME/'logs'/f'{key}-check-{i}.log',deadline,role,task['id'])
            checks.append(check)
            assert check['exit_code']==0, f'Validation command {i} failed.'
        for name in task['deliverables']:
            assert (work/name).is_file(), f'Missing deliverable: {name}'
    except Exception as e:
        failure=str(e)
    handoff=work/'handoff'/task['id']
    handoff.mkdir(parents=True,exist_ok=True)
    # Small log tails are shared for diagnosis; full logs stay on the machine.
    for i,check in enumerate(checks):
        log=ROOT/check['log']
        if log.exists():
            (handoff/f'check-{i}.txt').write_text(log.read_text(encoding='utf-8',errors='replace')[-12000:],encoding='utf-8')
    files=scope_check(task,work)
    # Hash the staged Git representation, after text/EOL normalization, so
    # receipts verify against the exact published blobs on every machine.
    git('add','--',*files,cwd=work)
    artifacts={name:hashlib.sha256(subprocess.run(
                   ['git','show',f':{name}'],cwd=work,capture_output=True,check=True
               ).stdout).hexdigest()
               for name in files if (work/name).is_file()}
    report={'schema_version':1,'task_id':task['id'],'attempt':task['attempt'],'role':role,
            'task_sha256':task_digest(task),'base_commit':task['base_commit'],
            'status':'failed' if failure else 'completed','failure':failure,
            'artifact_hash_basis':'canonical_git_blob',
            'started_from_pinned_source':True,'checks':checks,'artifacts_sha256':artifacts,
            'python':sys.version,'finished_at':now().isoformat(),
            'note':'Completed means worker self-check only; coordinator acceptance is separate.'}
    if (work/'data/manifest.json').exists():
        report['input_manifest']=json.loads((work/'data/manifest.json').read_text(encoding='utf-8'))
    report['task_parameters']=task.get('parameters',{})
    dump(handoff/'result.json',report)
    files=scope_check(task,work)
    git('add','--',*files,cwd=work)
    git('commit','-m',f"{role}: {task['id']} {report['status']}",cwd=work)
    return deliver(task,work,branch,report)

def chief_fingerprint():
    queue=remote_json('ops/queue.json')
    branches=git('for-each-ref','--format=%(refname) %(objectname)',f'refs/remotes/{REMOTE}/work/')
    readiness=[]
    for role in ['sol','hy3']:
        status=remote_json('status.json',f'status/{role}')
        readiness.append((role,status.get('machine_id') if status else None,
                          status.get('state')=='error' if status else False,
                          status.get('python') if status else None))
    return hashlib.sha256(json.dumps([queue,branches,readiness],sort_keys=True).encode()).hexdigest()

def chief_schedule():
    """Explicit, one-shot timed wakeups; idle heartbeat changes remain free."""
    path = ROOT / 'ops/chief-workplan.json'
    if not path.exists():
        return None
    plan = json.loads(path.read_text(encoding='utf-8'))
    if plan.get('state') != 'active' or not plan.get('next_wake_at'):
        return None
    wake = dt.datetime.fromisoformat(plan['next_wake_at'])
    if wake.tzinfo is None:
        raise ValueError('Chief wake time must include a timezone.')
    if now() < wake:
        return None
    return hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest()

def chief_budget_gate():
    # Configuration is deliberately host-local; other roles keep their own limits.
    if not (RUNTIME/'chief-quota-config.json').exists() and not (RUNTIME/'chief-budget-drain.json').exists():
        return 'disabled'
    from quota_guard import gate
    return gate(RUNTIME)

def chief_tick(force=False):
    if chief_budget_gate() not in {'allow','disabled'}:
        return False
    path=RUNTIME/'chief-seen.json'
    fingerprint=chief_fingerprint()
    old=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    scheduled_key=chief_schedule()
    scheduled_due=bool(scheduled_key and scheduled_key != old.get('scheduled_key'))
    if (old.get('schema_version')==CHIEF_CHECKPOINT_VERSION
            and old.get('fingerprint')==fingerprint and not scheduled_due and not force):
        return False
    # On first launch, don't duplicate the active coordinator's bootstrap turn.
    if not old and not scheduled_due and not force:
        dump(path,{'schema_version':CHIEF_CHECKPOINT_VERSION,'fingerprint':fingerprint})
        return False
    binary=shutil.which('codex')
    if not binary:
        raise RuntimeError('Codex not found for coordinator.')
    prompt=(ROOT/'ops/prompts/CHIEF_TICK.txt').read_text(encoding='utf-8')
    command=[binary,'exec','--approve-for-me','--model','gpt-6-astra','-c','model_reasoning_effort="xhigh"',
             '--cd',str(ROOT),'--output-last-message',str(RUNTIME/'chief-last.txt'),prompt]
    publish_status('chief','running',task_id='integrate-and-dispatch')
    check=execute_process(command,ROOT,RUNTIME/'logs'/f'chief-{int(time.time())}.log',
                          time.monotonic()+1800,'chief','integrate-and-dispatch')
    if check['exit_code']:
        raise RuntimeError('Coordinator turn failed; inspect local log.')
    if git('status','--porcelain'):
        raise RuntimeError('Coordinator left uncommitted work; inspect before retry.')
    fetch()
    # A turn can receive a worker result after its last inspection. Acknowledge
    # only the state that triggered that turn, so such a result wakes the next
    # turn. Saving the post-turn snapshot silently lost these notifications.
    # Versioning also revisits one legacy checkpoint that may have lost a result.
    dump(path,{'schema_version':CHIEF_CHECKPOINT_VERSION,'fingerprint':fingerprint,
               'scheduled_key':scheduled_key or old.get('scheduled_key')})
    return True

def doctor(role, recover=False):
    assert role in ROLES
    fetch()
    c=control()
    if not git('config','user.name'):
        git('config','user.name',f'SafeInvest {role} Agent')
    if not git('config','user.email'):
        git('config','user.email',f'safeinvest-{role}@localhost')
    if recover and role=='chief' and not stopped(c):
        if git('branch','--show-current') != 'main':
            raise RuntimeError('Recovery requires the dedicated main checkout; preserve other branches.')
        dirty=git('status','--porcelain')
        ahead=int(git('rev-list','--count',f'{REMOTE}/main..HEAD'))
        if dirty or ahead:
            saved=RUNTIME/'recovery'/f'chief-{int(time.time())}'
            saved.mkdir(parents=True,exist_ok=False)
            (saved/'tracked.patch').write_text(git('diff','--binary','HEAD'),encoding='utf-8')
            dump(saved/'state.json',{'status':dirty,'unpushed_commits':ahead,
                                    'head':git('rev-parse','HEAD'),'at':now().isoformat()})
            chief_tick(force=True)
    clean_main()
    publish_status(role,'ready',python=sys.version.split()[0],codex_available=bool(shutil.which('codex')))
    print(json.dumps({'role':role,'root':str(ROOT),'remote':git('remote','get-url',REMOTE),
                      'python':sys.version.split()[0],'state':c['state'],'write_access':'verified'},ensure_ascii=False))

def watch(role,backend,once=False):
    RUNTIME.mkdir(exist_ok=True)
    lock=RUNTIME/f'{role}.lock'
    try:
        fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:
        raise RuntimeError(f'{lock} exists. Check its PID before clearing a stale lock.')
    os.write(fd,str(os.getpid()).encode())
    os.close(fd)
    failures=0
    last_heartbeat=0
    try:
        if (RUNTIME/'STOP').exists():
            return
        doctor(role,recover=(role=='chief'))
        while True:
            try:
                fetch()
                c=control()
                if stopped(c):
                    publish_status(role,'stopped')
                    return
                if role=='chief':
                    budget=chief_budget_gate()
                    if budget=='drain':
                        publish_status(role,'stopped',reason='local_weekly_allowance_threshold',
                                       note='Current bounded turn ended. Local budget stop is sticky; global state unchanged.')
                        return
                    if budget=='wait':
                        if time.monotonic()-last_heartbeat>240:
                            publish_status(role,'waiting_quota',reason='Awaiting a verified local allowance reading.')
                            last_heartbeat=time.monotonic()
                        if once:
                            return
                        time.sleep(60)
                        continue
                clean_main()
                if role=='chief':
                    changed=chief_tick()
                else:
                    task=select_task(role)
                    changed=bool(task)
                    if task:
                        report=run_task(task,backend)
                        print(json.dumps({'task':task['id'],'status':report['status']},ensure_ascii=False),flush=True)
                failures=0
                if time.monotonic()-last_heartbeat>240:
                    publish_status(role,'idle' if not changed else 'ready')
                    last_heartbeat=time.monotonic()
                if once:
                    return
            except Exception as e:
                failures+=1
                dump(RUNTIME/f'{role}-error.json',{'error':str(e),'at':now().isoformat(),'failures':failures})
                print(f'{role}: {e}',file=sys.stderr,flush=True)
                try:
                    publish_status(role,'error',error=str(e),failures=failures)
                except Exception:
                    pass
                if failures>=2 or once:
                    raise
            time.sleep(60)
    finally:
        lock.unlink(missing_ok=True)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['doctor','watch','once','status','stop'])
    parser.add_argument('--role',choices=sorted(ROLES),default='chief')
    parser.add_argument('--backend',choices=['codex','commands'],default='commands')
    args=parser.parse_args()
    if args.action=='stop':
        RUNTIME.mkdir(exist_ok=True)
        (RUNTIME/'STOP').touch()
        print('Local STOP set. All local task runners will stop; inspect it before restarting.')
    elif args.action=='doctor':
        doctor(args.role)
    elif args.action=='status':
        fetch()
        print(json.dumps({r:remote_json('status.json',f'status/{r}') for r in sorted(ROLES)},ensure_ascii=False,indent=2))
    else:
        watch(args.role,args.backend,once=args.action=='once')

if __name__=='__main__':
    main()
