"""Independent local supervisor. No model calls for ordinary health checks."""
import ctypes
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import coop
import quota_guard

ROOT, RUNTIME = coop.ROOT, coop.RUNTIME


def pid_alive(pid):
    if not pid or int(pid) <= 0:
        return False
    if os.name == 'nt':
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x100000, False, int(pid))
        if not handle:
            # Access denied is not proof that a process has exited.
            return ctypes.get_last_error() != 87
        try:
            return kernel.WaitForSingleObject(handle, 0) != 0
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def read_json(path, default=None):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else default


def read_pid(path):
    return int(path.read_text(encoding='utf-8-sig').strip()) if path.exists() else None


def process_inventory():
    if os.name != 'nt':
        raise RuntimeError('This supervisor currently supports the Windows chief host only.')
    command = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -match "
               "'^(python|pythonw|codex|node)(\\.exe)?$' } | "
               "Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress")
    p = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
                       capture_output=True, text=True, encoding='utf-8', errors='replace',
                       timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    if p.returncode:
        raise RuntimeError('Cannot verify process inventory; no restart attempted.')
    rows = json.loads(p.stdout) if p.stdout.strip() else []
    return rows if isinstance(rows, list) else [rows]


def related_processes(rows):
    workers, agents = [], []
    root_text = str(ROOT).replace('\\', '/').lower()
    for row in rows:
        command = (row.get('CommandLine') or '').replace('\\', '/').lower()
        if 'coop.py' in command and '--role chief' in command:
            workers.append(row['ProcessId'])
        if root_text in command and 'gpt-6-astra' in command and 'exec' in command:
            agents.append(row['ProcessId'])
    return workers, agents


def restart_decision(config, stop_exists, lock_live, child_live, workers, agents, current, quota_state='disabled'):
    if stop_exists or config['state'] != 'running' or current >= dt.datetime.fromisoformat(config['deadline']):
        return 'stopping'
    if quota_state=='drain':
        return 'budget_draining'
    if lock_live or workers:
        return 'worker_running'
    if child_live or agents:
        return 'waiting_for_existing_child'
    if quota_state=='wait':
        return 'waiting_for_quota'
    return 'start_worker'


def append_event(event):
    with (RUNTIME / 'chief-supervisor-events.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'at':coop.now().isoformat(), **event}, ensure_ascii=False)+'\n')


def snapshot(decision, workers, agents, config, keep_awake):
    queue = read_json(ROOT/'ops/queue.json', {'tasks':[]})
    counts = {}
    for item in queue['tasks']:
        counts[item['state']] = counts.get(item['state'], 0)+1
    statuses = {}
    for role in ('chief', 'sol', 'hy3'):
        try:
            statuses[role] = coop.remote_json('status.json', f'status/{role}')
        except Exception as error:
            statuses[role] = {'inspection_error':str(error)}
    logs = sorted((RUNTIME/'logs').glob('chief-*.log'), key=lambda p:p.stat().st_mtime)
    latest = logs[-1] if logs else None
    value = {'supervisor_pid':os.getpid(), 'checked_at':coop.now().isoformat(),
             'state':decision, 'worker_pids':workers, 'agent_pids':agents,
             'keep_awake':keep_awake, 'queue_counts':counts, 'deadline':config['deadline'],
             'cached_remote_status':statuses, 'remote_status_is_not_quota_evidence':True,
             'local_status':read_json(RUNTIME/'chief-status.json'),
             'last_error':read_json(RUNTIME/'chief-error.json'),
             'quota':read_json(RUNTIME/'chief-quota-status.json'),
             'budget_drain':read_json(RUNTIME/'chief-budget-drain.json'),
             'workplan':read_json(ROOT/'ops/chief-workplan.json'),
             'latest_log':str(latest) if latest else None,
             'latest_log_bytes':latest.stat().st_size if latest else None}
    coop.dump(RUNTIME/'chief-health.json', value)
    return value


def main():
    RUNTIME.mkdir(exist_ok=True)
    lock = RUNTIME/'chief-supervisor.lock'
    if lock.exists():
        if pid_alive(read_pid(lock)):
            raise RuntimeError('A live supervisor already owns this machine.')
        lock.unlink()  # Only this verified stale supervisor lock is removed.
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)
    child = None
    output = None
    failures = 0
    next_start = 0.0
    started = 0.0
    last_health = last_quality = 0.0
    previous = None
    keep_awake = False
    try:
        if os.name == 'nt':
            keep_awake = bool(ctypes.windll.kernel32.SetThreadExecutionState(0x80000001))
        append_event({'event':'supervisor_started', 'pid':os.getpid(), 'keep_awake':keep_awake})
        while True:
            try:
                config = read_json(ROOT/'ops/control.json')
                quota_guard.refresh(RUNTIME)
                quota_state=quota_guard.gate(RUNTIME)
                rows = process_inventory()
                workers, agents = related_processes(rows)
                lock_path = RUNTIME/'chief.lock'
                lock_live = pid_alive(read_pid(lock_path))
                active = read_json(RUNTIME/'chief-active-child.json', {})
                child_live = pid_alive(active.get('pid'))
                if child and child.poll() is None and child.pid not in workers:
                    workers.append(child.pid)
                decision = restart_decision(config, (RUNTIME/'STOP').exists(), lock_live,
                                            child_live, workers, agents, coop.now(),quota_state)
                if child and child.poll() is not None:
                    append_event({'event':'worker_exited', 'pid':child.pid, 'exit_code':child.returncode})
                    output.close()
                    output = None
                    child = None
                    failures += 1
                    next_start = time.monotonic()+min(3600,60*2**min(failures-1,6))
                if decision in {'stopping','budget_draining'}:
                    snapshot(decision, workers, agents, config, keep_awake)
                    if decision=='budget_draining' and agents:
                        quota_guard.notify_current_turn(RUNTIME)
                    # The runner observes the same STOP/control itself. Do not kill its work here.
                    if not workers and not agents and not child_live:
                        if decision=='budget_draining':
                            dirty=coop.git('status','--porcelain')
                            ahead=coop.git('rev-list','--count','origin/main..HEAD')
                            quota_guard.save(RUNTIME/'chief-budget-stop.json',{
                                'stopped_at':coop.now().isoformat(),'worker_pids':workers,'agent_pids':agents,
                                'reason':'local_weekly_allowance_threshold',
                                'quota':read_json(RUNTIME/'chief-quota-status.json'),
                                'git_status':dirty,'unpushed_commits':ahead,
                                'workplan':read_json(ROOT/'ops/chief-workplan.json'),
                                'note':'All local chief processes ended; no global pause or result deletion. Inspect any unfinished work before an explicit resume.'})
                            append_event({'event':'budget_stop_confirmed','dirty_worktree':bool(dirty),'unpushed_commits':ahead})
                        break
                elif decision == 'start_worker' and time.monotonic() >= next_start:
                    if lock_path.exists():
                        # Recheck immediately before removing a stale worker lock.
                        if pid_alive(read_pid(lock_path)):
                            continue
                        lock_path.unlink()
                    output = (RUNTIME/'chief-supervised-worker.log').open('a', encoding='utf-8')
                    child = subprocess.Popen([sys.executable, '-X', 'utf8', str(ROOT/'scripts/coop.py'),
                                              'watch', '--role', 'chief', '--backend', 'codex'],
                                             cwd=ROOT, stdout=output, stderr=subprocess.STDOUT,
                                             stdin=subprocess.DEVNULL,
                                             creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                    started = time.monotonic()
                    append_event({'event':'worker_started', 'pid':child.pid, 'failures':failures})
                    workers.append(child.pid)
                    decision = 'worker_started'
                if child and child.poll() is None and time.monotonic()-started > 1200:
                    failures = 0
                moment = time.monotonic()
                if moment-last_health >= 300 or decision != previous:
                    health = snapshot(decision, workers, agents, config, keep_awake)
                    append_event({'event':'health_check', 'state':decision,
                                  'worker_pids':workers, 'agent_pids':agents})
                    last_health = moment
                if moment-last_quality >= 1800:
                    append_event({'event':'quality_checkpoint',
                                  'note':'Inspect exact task audits for numerical acceptance; heartbeat is availability only.',
                                  'workplan':read_json(ROOT/'ops/chief-workplan.json'),
                                  'queue_counts':health['queue_counts']})
                    last_quality = moment
                previous = decision
            except Exception as error:
                append_event({'event':'inspection_failed', 'error':str(error), 'restart_skipped':True})
            time.sleep(30)
    finally:
        if keep_awake:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
        if output:
            output.close()
        lock.unlink(missing_ok=True)
        append_event({'event':'supervisor_stopped', 'pid':os.getpid()})


if __name__ == '__main__':
    main()
