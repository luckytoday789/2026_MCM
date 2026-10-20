import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path.cwd()/'scripts'))
import quota_guard as guard

TEST_ROOT=Path.cwd()/".runtime/quota-tests"
TEST_ROOT.mkdir(parents=True,exist_ok=True)


class QuotaTests(unittest.TestCase):
    def config(self, runtime):
        guard.save(runtime/'chief-quota-config.json',{'enabled':True,'limit_id':'codex',
                   'window_minutes':10080,'stop_remaining_percent':50})

    def reply(self, used=22):
        return {'rateLimits':{'limitId':'codex','primary':{
            'usedPercent':used,'windowDurationMins':10080,'resetsAt':4102444800}}}

    def test_actual_weekly_bucket_not_token_count_or_short_window(self):
        reply=self.reply()
        bucket=reply['rateLimits']
        bucket['secondary']=bucket['primary']
        bucket['primary']={'usedPercent':95,'windowDurationMins':300,'resetsAt':4102444800}
        self.assertEqual(guard.weekly_snapshot(reply)['remaining_percent'],78)
        bucket['secondary']=None
        with self.assertRaises(ValueError):guard.weekly_snapshot(reply)

    def test_threshold_finishes_current_work_and_is_sticky_after_reset(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as tmp:
            runtime=Path(tmp)
            self.config(runtime)
            with patch.object(guard,'read_server',return_value=self.reply(49)):
                guard.refresh(runtime,force=True)
            self.assertEqual(guard.gate(runtime),'allow')
            with patch.object(guard,'read_server',return_value=self.reply(50)):
                guard.refresh(runtime,force=True)
            self.assertEqual(guard.gate(runtime),'drain')
            # No STOP is created and no active task is killed by crossing 50%.
            self.assertFalse((runtime/'STOP').exists())
            with patch.object(guard,'read_server',return_value=self.reply(0)):
                guard.refresh(runtime,force=True)
            self.assertEqual(guard.gate(runtime),'drain')

    def test_below_threshold_remaining_is_not_missed(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as tmp:
            runtime=Path(tmp)
            self.config(runtime)
            with patch.object(guard,'read_server',return_value=self.reply(51)):
                guard.refresh(runtime,force=True)
            self.assertEqual(guard.gate(runtime),'drain')

    def test_explicit_forty_percent_threshold_allows_fifty_and_drains_at_forty(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as tmp:
            runtime=Path(tmp)
            self.config(runtime)
            config=guard.read(runtime/'chief-quota-config.json')
            config['stop_remaining_percent']=40
            guard.save(runtime/'chief-quota-config.json',config)
            for used in (50,59):
                with patch.object(guard,'read_server',return_value=self.reply(used)):
                    guard.refresh(runtime,force=True)
                self.assertEqual(guard.gate(runtime),'allow')
            with patch.object(guard,'read_server',return_value=self.reply(60)):
                guard.refresh(runtime,force=True)
            self.assertEqual(guard.gate(runtime),'drain')

    def test_unavailable_or_stale_quota_holds_new_work_without_assumed_balance(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as tmp:
            runtime=Path(tmp)
            self.config(runtime)
            with patch.object(guard,'read_server',side_effect=RuntimeError('offline')):
                self.assertEqual(guard.refresh(runtime,force=True)['state'],'unavailable')
            self.assertEqual(guard.gate(runtime),'wait')
            self.assertFalse((runtime/'chief-budget-drain.json').exists())
            with patch.object(guard,'read_server',return_value=self.reply()):
                guard.refresh(runtime,force=True)
            with patch.object(guard,'now',return_value=guard.now()+dt.timedelta(minutes=4)):
                self.assertEqual(guard.gate(runtime),'wait')

    def test_remote_machines_without_local_opt_in_are_unchanged(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as tmp:
            runtime=Path(tmp)
            with patch.object(guard,'read_server') as request:
                self.assertEqual(guard.refresh(runtime),{'state':'disabled'})
                self.assertEqual(guard.gate(runtime),'disabled')
                request.assert_not_called()

    def test_cached_checks_do_not_repeat_metadata_request(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as tmp:
            runtime=Path(tmp)
            self.config(runtime)
            with patch.object(guard,'read_server',return_value=self.reply()) as request:
                guard.refresh(runtime)
                guard.refresh(runtime)
                self.assertEqual(request.call_count,1)

    def test_invalid_percent_or_expired_window_is_not_treated_as_allowance(self):
        for used in (-1,101,float('nan')):
            with self.assertRaises(ValueError):guard.weekly_snapshot(self.reply(used))
        reply=self.reply()
        reply['rateLimits']['primary']['resetsAt']=1
        with self.assertRaises(ValueError):guard.weekly_snapshot(reply)

    def test_worker_finishes_current_turn_then_stops_without_starting_another(self):
        import coop
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as tmp:
            runtime=Path(tmp)
            self.config(runtime)
            with patch.object(guard,'read_server',return_value=self.reply()):
                guard.refresh(runtime,force=True)
            events=[]
            def turn():
                events.append('current_started')
                guard.save(runtime/'chief-budget-drain.json',{'reason':'fixture_threshold'})
                events.append('current_saved_and_finished')
                return True
            def publish(role,state,**extra):
                events.append(state)
            config={'state':'running','deadline':'2099-01-01T00:00:00+00:00'}
            with (patch.object(coop,'RUNTIME',runtime),patch.object(coop,'doctor'),
                  patch.object(coop,'fetch'),patch.object(coop,'control',return_value=config),
                  patch.object(coop,'clean_main'),patch.object(coop,'chief_tick',side_effect=turn) as run,
                  patch.object(coop,'publish_status',side_effect=publish),patch.object(coop.time,'sleep')):
                coop.watch('chief','codex')
            self.assertEqual(run.call_count,1)
            self.assertLess(events.index('current_saved_and_finished'),events.index('stopped'))
            self.assertFalse((runtime/'STOP').exists())
            self.assertEqual(config['state'],'running')

    def test_supervisor_cannot_restart_after_budget_drain(self):
        import supervise_chief as supervisor
        config={'state':'running','deadline':'2099-01-01T00:00:00+00:00'}
        args=dict(config=config,stop_exists=False,lock_live=False,child_live=False,
                  workers=[],agents=[],current=guard.now())
        self.assertEqual(supervisor.restart_decision(**args,quota_state='drain'),'budget_draining')
        self.assertEqual(supervisor.restart_decision(**args,quota_state='wait'),'waiting_for_quota')
        args.update(workers=[123],child_live=True,agents=[456])
        self.assertEqual(supervisor.restart_decision(**args,quota_state='drain'),'budget_draining')


if __name__=='__main__':
    unittest.main()
