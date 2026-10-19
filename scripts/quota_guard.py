"""Local subscription guard: read-only metadata, never model calls or reset credits."""
import datetime as dt
import json
import math
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import threading
import time
import uuid


def now():
    return dt.datetime.now(dt.timezone.utc)


def read(path, default=None):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else default


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temporary.replace(path)


def settings(runtime):
    config=read(runtime/'chief-quota-config.json', {})
    if not config.get('enabled'):
        return None
    if config.get('window_minutes') != 10080 or config.get('limit_id') != 'codex':
        raise ValueError('Only the explicitly selected Codex weekly allowance is configured.')
    threshold=float(config['stop_remaining_percent'])
    if not math.isfinite(threshold) or not 0 <= threshold <= 100:
        raise ValueError('Invalid remaining allowance threshold.')
    return config


def weekly_snapshot(result):
    buckets=result.get('rateLimitsByLimitId') or {}
    bucket=buckets.get('codex') or result.get('rateLimits') or {}
    if bucket.get('limitId') != 'codex':
        raise ValueError('The server did not identify the Codex quota bucket.')
    windows=[bucket.get(name) for name in ('primary','secondary')]
    windows=[w for w in windows if w and w.get('windowDurationMins')==10080]
    if len(windows)!=1:
        raise ValueError('A unique weekly allowance was not returned; do not infer it.')
    value=windows[0]
    used=float(value['usedPercent'])
    if not math.isfinite(used) or not 0 <= used <= 100:
        raise ValueError('Invalid quota percentage.')
    reset=int(value['resetsAt'])
    if reset <= now().timestamp():
        raise ValueError('Quota snapshot belongs to an expired window.')
    return {'limit_id':'codex','window_minutes':10080,'used_percent':used,
            'remaining_percent':100-used,'resets_at':reset,
            'source':'Codex account/rateLimits/read'}


def read_server():
    binary=shutil.which('codex')
    if not binary:
        raise RuntimeError('Codex executable unavailable for quota inspection.')
    process=subprocess.Popen([binary,'app-server','--stdio'],stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,
                             encoding='utf-8',errors='replace',
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    replies=queue.Queue()
    def reader():
        for line in process.stdout:
            try:
                replies.put(json.loads(line))
            except ValueError:
                continue
    threading.Thread(target=reader,daemon=True).start()
    def send(value):
        process.stdin.write(json.dumps(value)+'\n')
        process.stdin.flush()
    def response(request_id):
        end=time.monotonic()+20
        while time.monotonic()<end:
            try:
                value=replies.get(timeout=max(.1,end-time.monotonic()))
            except queue.Empty:
                break
            if value.get('id')==request_id:
                if 'error' in value:
                    raise RuntimeError('Read-only quota request failed: '+str(value['error'].get('code')))
                return value['result']
        raise RuntimeError('Read-only quota request timed out.')
    try:
        send({'id':1,'method':'initialize','params':{
            'clientInfo':{'name':'safeinvest_quota_monitor','version':'1.0.0'}}})
        response(1)
        send({'method':'initialized','params':{}})
        send({'id':2,'method':'account/rateLimits/read'})
        return response(2)
    finally:
        # This is our metadata-only child, never the worker or an active model.
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        process.stdin.close()
        process.stdout.close()


def refresh(runtime, force=False):
    config=settings(runtime)
    if not config:
        return {'state':'disabled'}
    path=runtime/'chief-quota-status.json'
    previous=read(path, {})
    if not force and previous.get('checked_at'):
        age=(now()-dt.datetime.fromisoformat(previous['checked_at'])).total_seconds()
        if 0 <= age < 60:
            return previous
    try:
        value=weekly_snapshot(read_server())
        value.update(checked_at=now().isoformat(),state='verified',
                     stop_remaining_percent=config['stop_remaining_percent'])
        if value['remaining_percent'] <= float(config['stop_remaining_percent']):
            drain=runtime/'chief-budget-drain.json'
            if not drain.exists():
                save(drain,{'requested_at':now().isoformat(),'reason':'weekly_allowance_threshold',
                            'threshold_remaining_percent':config['stop_remaining_percent'],
                            'observed':value,
                            'instruction':'Finish the current bounded turn, save/push, stop this machine; no new turn or automatic restart.'})
    except Exception as error:
        value={'state':'unavailable','checked_at':now().isoformat(),'error':str(error),
               'note':'No quota is inferred. Hold new model work until a verified reading returns.'}
    save(path,value)
    return value


def gate(runtime):
    # Sticky across quota resets and restarts until an explicitly authorized resume.
    if (runtime/'chief-budget-drain.json').exists():
        return 'drain'
    config=settings(runtime)
    if not config:
        return 'disabled'
    status=read(runtime/'chief-quota-status.json', {})
    if status.get('state')!='verified' or not status.get('checked_at'):
        return 'wait'
    age=(now()-dt.datetime.fromisoformat(status['checked_at'])).total_seconds()
    if not 0 <= age <= 180:
        return 'wait'
    if status['remaining_percent'] <= float(config['stop_remaining_percent']):
        return 'drain'
    return 'allow'


def notify_current_turn(runtime):
    """Steer the existing chief only once; this never starts a model process."""
    notice=runtime/'chief-budget-notice.json'
    if notice.exists() or not (runtime/'chief-budget-drain.json').exists():
        return
    logs=sorted((runtime/'logs').glob('chief-*.log'),key=lambda p:p.stat().st_mtime)
    if not logs:
        return
    with logs[-1].open(encoding='utf-8',errors='replace') as stream:
        match=re.search(r'session id:\s*([0-9a-f-]{36})',stream.read(16384))
    if not match:
        return
    binary=shutil.which('codex')
    if not binary:
        return
    message=('The user-authorized local weekly allowance threshold has been reached. '
             'Do not begin another substantive task. Finish/checkpoint the current bounded task, '
             'perform necessary checks, preserve and push authorized results, and leave recovery notes. '
             'Do not set global control paused/complete, clear the local budget drain, or start/restart workers. '
             'The parent will stop this machine after your process exits. Never set STOP while still working.')
    result=subprocess.run([binary,'queue','--thread',match.group(1),'--message',message],
                          stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20,
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    save(notice,{'at':now().isoformat(),'thread_id':match.group(1),'exit_code':result.returncode,
                 'note':'Existing-turn instruction only. Runner boundary gate independently prevents new turns.'})
