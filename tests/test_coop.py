import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('coop',Path(__file__).resolve().parents[1]/'scripts/coop.py')
coop=importlib.util.module_from_spec(spec)
spec.loader.exec_module(coop)

class ProtocolTests(unittest.TestCase):
    def test_path_boundary(self):
        self.assertTrue(coop.allowed('results/development/x.csv',['results/development']))
        self.assertFalse(coop.allowed('results/development2/x.csv',['results/development']))
        self.assertFalse(coop.allowed('specs/ACCOUNTING.md',['results']))

    def test_task_path_escape_rejected(self):
        task=self.task('a'*40)
        task['allowed_paths']=['../escape']
        with self.assertRaises(AssertionError):
            coop.validate_task(task)

    def task(self,base):
        return {'id':'HY3-TEST','attempt':1,'owner':'hy3','base_commit':base,'kind':'commands',
                'depends_on':[],'instructions':'Write an exact small fixture.',
                'allowed_paths':['results/development'],
                'deliverables':['results/development/value.json'],
                'commands':[['{python}','fixture.py']],
                'validation_commands':[['{python}','fixture.py','--check']],
                'max_seconds':30,'split':'development'}

    def test_python_registration_changes_wake_chief_but_heartbeats_do_not(self):
        state={"machine_id":"same-machine","state":"ready","python":"3.13.14",
               "updated_at":"first","lease_until":"first"}
        def remote(path,branch="main"):
            return {"tasks":[]} if branch=="main" else dict(state)
        with patch.object(coop,"remote_json",side_effect=remote), patch.object(coop,"git",return_value=""):
            before=coop.chief_fingerprint()
            state.update(updated_at="later",lease_until="later",state="idle")
            self.assertEqual(coop.chief_fingerprint(),before)
            state["python"]="3.12.14"
            self.assertNotEqual(coop.chief_fingerprint(),before)

    def test_end_to_end_local_git_delivery_and_deduplication(self):
        # A real bare Git remote verifies branch publication without network/model calls.
        test_root=coop.ROOT/'.runtime/protocol-tests'
        test_root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=test_root) as temp:
            top=Path(temp)
            assert top.resolve().is_relative_to(test_root.resolve())
            bare=top/'remote.git'
            root=top/'worker'
            subprocess.run(['git','init','--bare',str(bare)],check=True,capture_output=True)
            subprocess.run(['git','init','-b','main',str(root)],check=True,capture_output=True)
            old_root,old_runtime=coop.ROOT,coop.RUNTIME
            coop.ROOT,coop.RUNTIME=root,root/'.runtime'
            # git()'s default cwd is bound at import; pass through a wrapper for this fixture.
            original_git=coop.git
            def local_git(*args,**kwargs):
                kwargs.setdefault('cwd',root)
                return original_git(*args,**kwargs)
            coop.git=local_git
            try:
                coop.git('config','user.name','Protocol Test')
                coop.git('config','user.email','test@localhost')
                coop.git('remote','add','origin',str(bare))
                (root/'ops/tasks').mkdir(parents=True)
                (root/'.gitignore').write_text('.runtime/\n',encoding='utf-8')
                (root/'fixture.py').write_text(
                    "from pathlib import Path\nimport sys\np=Path('results/development/value.json')\n"
                    "if '--check' in sys.argv:\n assert p.read_text()=='{\"value\": 1}'\n"
                    "else:\n p.parent.mkdir(parents=True,exist_ok=True)\n p.write_text('{\"value\": 1}')\n",encoding='utf-8')
                (root/'.gitattributes').write_text('*.txt text eol=lf\n',encoding='utf-8')
                (root/'fixture.py').write_text((root/'fixture.py').read_text()+"\nif '--check' not in sys.argv:\n (p.parent/'mixed.txt').write_bytes(b'first\\r\\nsecond\\n')\n",encoding='utf-8')
                coop.dump(root/'ops/control.json',{'state':'running','deadline':'2099-01-01T00:00:00+00:00'})
                coop.dump(root/'ops/queue.json',{'tasks':[]})
                coop.git('add','.')
                coop.git('commit','-m','fixture')
                base=coop.git('rev-parse','HEAD')
                task=self.task(base)
                coop.dump(root/'ops/tasks/HY3-TEST.json',task)
                coop.dump(root/'ops/queue.json',{'tasks':[{'id':'HY3-TEST','state':'ready'}]})
                coop.git('add','.')
                coop.git('commit','-m','dispatch')
                coop.git('push','-u','origin','main')
                coop.doctor('hy3')
                self.assertEqual(coop.select_task('hy3'),task)
                real_git=coop.git
                failed_once=[False]
                def flaky_push(*args,**kwargs):
                    if args[0]=='push' and 'refs/heads/work/' in ' '.join(args) and not failed_once[0]:
                        failed_once[0]=True
                        raise RuntimeError('Simulated network interruption after local commit')
                    return real_git(*args,**kwargs)
                coop.git=flaky_push
                with self.assertRaisesRegex(RuntimeError,'Simulated network'):
                    coop.run_task(task,'commands')
                report=coop.run_task(task,'commands')
                self.assertEqual(report['status'],'completed')
                self.assertTrue(all(x['exit_code']==0 for x in report['checks']))
                coop.fetch()
                received=coop.remote_json('handoff/HY3-TEST/result.json','work/hy3/HY3-TEST-a1')
                self.assertEqual(received['task_sha256'],coop.task_digest(task))
                self.assertEqual(received['artifact_hash_basis'],'canonical_git_blob')
                for name,digest in received['artifacts_sha256'].items():
                    raw=subprocess.check_output(['git','show',f"origin/work/hy3/HY3-TEST-a1:{name}"],cwd=root)
                    self.assertEqual(hashlib.sha256(raw).hexdigest(),digest,name)
                self.assertIsNone(coop.select_task('hy3'))
                status=coop.remote_json('status.json','status/hy3')
                self.assertEqual(status['state'],'submitted')
                self.assertEqual(coop.git('status','--porcelain'),'')
            finally:
                coop.git=original_git
                coop.ROOT,coop.RUNTIME=old_root,old_runtime

    def test_result_arriving_during_chief_turn_wakes_the_next_turn(self):
        test_root=coop.ROOT/'.runtime/protocol-tests'
        test_root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=test_root) as temp:
            runtime=Path(temp)
            checkpoint=runtime/'chief-seen.json'
            coop.dump(checkpoint,{'schema_version':2,'fingerprint':'older'})
            current=['before-turn']
            def execute(*args,**kwargs):
                current[0]='worker-result-arrived'
                return {'exit_code':0}
            with (patch.object(coop,'RUNTIME',runtime),
                  patch.object(coop,'chief_fingerprint',side_effect=lambda:current[0]),
                  patch.object(coop.shutil,'which',return_value='codex'),
                  patch.object(coop,'publish_status'),
                  patch.object(coop,'execute_process',side_effect=execute) as run,
                  patch.object(coop,'git',return_value=''),
                  patch.object(coop,'fetch')):
                self.assertTrue(coop.chief_tick())
                self.assertEqual(json.loads(checkpoint.read_text())['fingerprint'],'before-turn')
                self.assertTrue(coop.chief_tick())
                self.assertEqual(json.loads(checkpoint.read_text())['fingerprint'],'worker-result-arrived')
                self.assertFalse(coop.chief_tick())
                self.assertEqual(run.call_count,2)

    def test_legacy_checkpoint_gets_one_recovery_turn_without_repeat(self):
        test_root=coop.ROOT/'.runtime/protocol-tests'
        test_root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=test_root) as temp:
            runtime=Path(temp)
            checkpoint=runtime/'chief-seen.json'
            coop.dump(checkpoint,{'fingerprint':'already-swallowed-result'})
            with (patch.object(coop,'RUNTIME',runtime),
                  patch.object(coop,'chief_fingerprint',return_value='already-swallowed-result'),
                  patch.object(coop.shutil,'which',return_value='codex'),
                  patch.object(coop,'publish_status'),
                  patch.object(coop,'execute_process',return_value={'exit_code':0}) as run,
                  patch.object(coop,'git',return_value=''),
                  patch.object(coop,'fetch')):
                self.assertTrue(coop.chief_tick())
                self.assertEqual(json.loads(checkpoint.read_text())['schema_version'],2)
                self.assertFalse(coop.chief_tick())
                self.assertEqual(run.call_count,1)

    def test_failed_chief_turn_does_not_acknowledge_pending_result(self):
        test_root=coop.ROOT/'.runtime/protocol-tests'
        test_root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=test_root) as temp:
            runtime=Path(temp)
            checkpoint=runtime/'chief-seen.json'
            coop.dump(checkpoint,{'schema_version':2,'fingerprint':'previous'})
            original=checkpoint.read_bytes()
            with (patch.object(coop,'RUNTIME',runtime),
                  patch.object(coop,'chief_fingerprint',return_value='pending-result'),
                  patch.object(coop.shutil,'which',return_value='codex'),
                  patch.object(coop,'publish_status'),
                  patch.object(coop,'execute_process',side_effect=[{'exit_code':1},{'exit_code':0}]),
                  patch.object(coop,'git',return_value=''),
                  patch.object(coop,'fetch')):
                with self.assertRaisesRegex(RuntimeError,'Coordinator turn failed'):
                    coop.chief_tick()
                self.assertEqual(checkpoint.read_bytes(),original)
                self.assertTrue(coop.chief_tick())
                self.assertEqual(json.loads(checkpoint.read_text())['fingerprint'],'pending-result')

if __name__=='__main__':
    unittest.main()
