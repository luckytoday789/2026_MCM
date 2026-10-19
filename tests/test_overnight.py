import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

SCRIPTS = Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0, str(SCRIPTS))
import coop
import supervise_chief as supervisor
import probe_sol_availability as probe


class OvernightTests(unittest.TestCase):
    def test_due_schedule_is_consumed_once_and_future_plan_waits(self):
        root = coop.ROOT/'.runtime/protocol-tests'
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as temp:
            top=Path(temp)
            (top/'ops/prompts').mkdir(parents=True)
            (top/'ops/prompts/CHIEF_TICK.txt').write_text('Fixture only.')
            runtime=top/'.runtime'
            coop.dump(runtime/'chief-seen.json',{'schema_version':2,'fingerprint':'unchanged'})
            fixed=dt.datetime(2026,10,19,17,0,tzinfo=dt.timezone.utc)
            plan={'state':'active','next_wake_at':'2026-10-20T01:05:00+08:00'}
            coop.dump(top/'ops/chief-workplan.json',plan)
            with (patch.object(coop,'ROOT',top),patch.object(coop,'RUNTIME',runtime),
                  patch.object(coop,'now',return_value=fixed) as clock,
                  patch.object(coop,'chief_fingerprint',return_value='unchanged'),
                  patch.object(coop.shutil,'which',return_value='codex'),
                  patch.object(coop,'publish_status'), patch.object(coop,'git',return_value=''),
                  patch.object(coop,'fetch'),
                  patch.object(coop,'execute_process',return_value={'exit_code':0}) as run):
                self.assertFalse(coop.chief_tick())
                clock.return_value=fixed+dt.timedelta(minutes=5)
                self.assertTrue(coop.chief_tick())
                self.assertFalse(coop.chief_tick())
                self.assertEqual(run.call_count,1)
                plan['next_wake_at']='2026-10-20T01:10:00+08:00'
                coop.dump(top/'ops/chief-workplan.json',plan)
                self.assertFalse(coop.chief_tick())
                clock.return_value=fixed+dt.timedelta(minutes=10)
                self.assertTrue(coop.chief_tick())

    def test_supervisor_respects_stop_pause_deadline_and_existing_processes(self):
        current=dt.datetime(2026,10,19,17,tzinfo=dt.timezone.utc)
        config={'state':'running','deadline':'2026-10-20T23:30:00+08:00'}
        def decide(**changes):
            values=dict(config=config,stop_exists=False,lock_live=False,child_live=False,
                        workers=[],agents=[],current=current)
            values.update(changes)
            return supervisor.restart_decision(**values)
        self.assertEqual(decide(),'start_worker')
        self.assertEqual(decide(stop_exists=True),'stopping')
        self.assertEqual(decide(config={**config,'state':'paused'}),'stopping')
        self.assertEqual(decide(current=current+dt.timedelta(days=1)),'stopping')
        self.assertEqual(decide(lock_live=True),'worker_running')
        self.assertEqual(decide(workers=[123]),'worker_running')
        self.assertEqual(decide(child_live=True),'waiting_for_existing_child')
        self.assertEqual(decide(agents=[456]),'waiting_for_existing_child')

    def test_process_inventory_distinguishes_worker_and_orphan(self):
        rows=[{'ProcessId':10,'CommandLine':'python scripts/coop.py watch --role chief --backend codex'},
              {'ProcessId':20,'CommandLine':f'codex exec --model gpt-6-astra --cd {coop.ROOT}'},
              {'ProcessId':30,'CommandLine':'python scripts/coop.py watch --role hy3'},
              {'ProcessId':40,'CommandLine':'codex exec --model gpt-6.1-sol --cd elsewhere'}]
        self.assertEqual(supervisor.related_processes(rows),([10],[20]))

    def test_quota_probe_requires_success_and_exact_real_reply(self):
        self.assertTrue(probe.response_is_usable(0,probe.TOKEN+'\n'))
        self.assertFalse(probe.response_is_usable(1,probe.TOKEN))
        self.assertFalse(probe.response_is_usable(0,''))
        self.assertFalse(probe.response_is_usable(0,'usage limit'))

    def test_real_process_exit_is_required_before_restart(self):
        process=subprocess.Popen([sys.executable,'-c','import time; time.sleep(1)'])
        self.assertTrue(supervisor.pid_alive(process.pid))
        process.wait(timeout=10)
        self.assertFalse(supervisor.pid_alive(process.pid))

    def test_network_heartbeat_failure_does_not_abandon_live_child(self):
        root=coop.ROOT/'.runtime/protocol-tests'
        root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as temp:
            top=Path(temp)
            process=MagicMock(pid=os.getpid(),returncode=0)
            process.poll.side_effect=[None,0]
            clock=[0]
            def monotonic():
                clock[0]+=300
                return clock[0]
            with (patch.object(coop,'ROOT',top),patch.object(coop,'RUNTIME',top),
                  patch.object(coop.subprocess,'Popen',return_value=process),
                  patch.object(coop.time,'monotonic',side_effect=monotonic),
                  patch.object(coop.time,'sleep'),
                  patch.object(coop,'publish_status',side_effect=RuntimeError('temporary network outage'))):
                result=coop.execute_process(['fixture'],top,top/'child.log',999999,'chief','fixture')
            self.assertEqual(result['exit_code'],0)
            self.assertTrue((top/'chief-heartbeat-error.json').exists())
            self.assertFalse((top/'chief-active-child.json').exists())
            process.terminate.assert_not_called()


if __name__=='__main__':
    unittest.main()
