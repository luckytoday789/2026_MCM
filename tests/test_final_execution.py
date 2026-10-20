"""Generated-only final gate, immutable task, and descriptive output checks."""

import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from safeinvest import final_execution as f
from safeinvest.policy_pilot import EmpiricalPrior


def choices(eligible=False):
    return [dict(profile_id=p,fee_rate=k,proposed_class='conservative' if eligible else None,
                 eligible=eligible,reason='generated deterministic development fixture')
            for p in f.PROFILES for k in f.FEES]


def rows(ids=(121,122)):
    return [dict(zip(f.FIELDS,(str(s),str(t),'.1' if t%2 else '-.05','.02','.01','.015')))
            for s in ids for t in range(1,31)]


def config(stage='final'):
    ref={'commit':'1'*40,'path':'audit/fixture.json','sha256':'2'*64}
    return dict(schema_version=1,run_id='generated',stage=stage,source_commit='3'*40,
                source_sha256={name:'4'*64 for name in f.CLOSURE},source_review=dict(ref),
                development_review=dict(ref),primary_mode='balanced_cost',profile_choices=choices(),
                refit=dict(ref) if stage=='final' else None,
                freeze=dict(ref,path='ops/freeze.json') if stage=='final' else None,
                freeze_attestation=dict(ref,commit='5'*40) if stage=='final' else None,
                execution=dict(cpu_only=True,required_python='3.12',max_seconds=1800,
                               max_artifact_bytes=f.w.LIMIT,output='results/final/generated'))


class FinalExecutionTests(unittest.TestCase):
    def test_referrals_are_ten_explicit_null_rows_with_no_personalized_paths(self):
        tables=f._evaluate_rows(rows(),EmpiricalPrior(((1.1,1.02,1.),)),
                                'balanced_cost',choices(),ids=(121,122))
        self.assertEqual(len(tables['generic']),16)
        self.assertEqual(len(tables['scenario_metrics']),160)
        self.assertEqual(len(tables['comparisons']),100)
        self.assertEqual(len(tables['paired_differences']),200)
        self.assertEqual(len(tables['personalized']),10)
        self.assertEqual(tables['personal_cases'],{})
        for row in tables['personalized']:
            self.assertEqual((row['scenario_count'],row['denominator']),(0,0))
            for name in ('risk_pass','purchasing_power_pass','p90_loss_pct','exceedance_count','case_path'):
                self.assertIsNone(row[name])
        for row in tables['comparisons']:
            self.assertIsNone(row['fold_support']);self.assertIsNone(row['promotion'])
            self.assertEqual(row['frozen_primary_mode'],'balanced_cost')

    def test_personalized_own_horizons_fees_thresholds_and_no_reselection(self):
        tables=f._evaluate_rows(rows(),EmpiricalPrior(((1.12,1.04,1.),)),
                                'balanced_adaptive',choices(True),ids=(121,122))
        self.assertEqual(len(tables['personal_cases']),10)
        expected_annual=2*2*sum(h for h,t in f.PROFILES.values())
        actual=sum(len(result.ledger) for case in tables['personal_cases'].values()
                   for result,reviews in case['paths'])
        self.assertEqual(actual,expected_annual)
        for row in tables['personalized']:
            self.assertEqual(row['horizon'],f.PROFILES[row['profile_id']][0])
            self.assertEqual(row['denominator'],2)
            self.assertEqual(row['proposed_class'],'conservative')
            self.assertIn(row['recommended_class'],('conservative',None))
        self.assertTrue(all(row['promotion'] is None for row in tables['comparisons']))

    def test_generic_fee_and_future_perturbation_use_accepted_arithmetic(self):
        prior=EmpiricalPrior(((1.1,1.04,1.),))
        original=rows((121,));changed=[dict(row) for row in original]
        for row in changed[10:]:row['equity_return']='.7'
        a,ar=f._path(original,'balanced_context',prior,30,.0025,25)
        b,br=f._path(changed,'balanced_context',prior,30,.0025,25)
        self.assertEqual(ar[:11],br[:11]);self.assertEqual(a.ledger[:10],b.ledger[:10])
        flat=rows((121,))
        for row in flat:
            for name in f.FIELDS[2:]:row[name]='0'
        result,reviews=f._path(flat,'equal_weight_buy_hold',prior,30,.0025,25)
        self.assertAlmostEqual(result.ledger[0].fee,1/6,delta=1e-13)
        self.assertEqual(result.split,'final')
        self.assertAlmostEqual(f._metric(result,reviews,'equal_weight_buy_hold',.0025,30)['max_real_drawdown_pct'],1/6,delta=1e-12)

    def test_full_final_shape_and_bad_keys_factors_rejected(self):
        full=rows(tuple(range(121,181)))
        stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=f.FIELDS,lineterminator='\n')
        writer.writeheader();writer.writerows(full)
        self.assertEqual(len(f._parse_final(stream.getvalue().encode())),1800)
        for name,value in (('period','01'),('equity_return','nan'),('inflation','-1')):
            bad=stream.getvalue().replace('121,1,', '121,01,',1) if name=='period' else None
            if bad is None:
                altered=[dict(row) for row in full];altered[-1][name]=value
                out=io.StringIO(newline='');w=csv.DictWriter(out,fieldnames=f.FIELDS);w.writeheader();w.writerows(altered);bad=out.getvalue()
            with self.assertRaises(ValueError):f._parse_final(bad.encode())

    def test_config_rejects_missing_source_refit_bad_choice_or_runtime(self):
        self.assertEqual(f.validate_config(config())['stage'],'final')
        for key,value in (('source_sha256',{}),('profile_choices',choices()[:-1]),('refit',None)):
            c=config();c[key]=value
            with self.assertRaises(ValueError):f.validate_config(c)
        c=config();c['execution']['max_seconds']=1801
        with self.assertRaises(ValueError):f.validate_config(c)

    def test_exact_freeze_bytes_external_refit_acceptance_and_control_gate(self):
        c=config();effective={k:v for k,v in c.items() if k not in ('freeze','freeze_attestation')}
        freeze={'source_commit':c['source_commit'],'source_sha256':c['source_sha256'],
                'effective_configuration_sha256':f.w.sha(f.w.canonical(effective)),
                'primary_mode':c['primary_mode'],'profile_choices':c['profile_choices'],
                'refit':c['refit'],'input_path':f.FINAL_PATH,'input_sha256':f.FINAL_HASH}
        raw=f.w.canonical(freeze);runner=f.w.sha(raw.decode().strip().encode())
        attestation={'status':'accepted','freeze_blob_sha256':f.w.sha(raw),
                     'freeze_runner_sha256':runner,'refit':c['refit'],
                     'refit_acceptance':{'commit':'6'*40,'path':'audit/refit.json','sha256':'7'*64}}
        refit_review={'status':'accepted','refit':c['refit']}
        def reference(root,ref):
            if ref==c['freeze']:return raw
            if ref==c['freeze_attestation']:return f.w.canonical(attestation)
            return f.w.canonical(refit_review)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'ops').mkdir();control=root/'ops/control.json'
            control.write_text('{"state":"running","final_data_open":true}')
            with patch.object(f,'_reference',side_effect=reference),patch.object(f.w,'ancestor'):
                self.assertEqual(f._final_gate(root,c,{'freeze_sha256':runner},'a'*64)['freeze_runner_sha256'],runner)
                control.write_text('{"state":"running","final_data_open":false}')
                with self.assertRaises(ValueError):f._final_gate(root,c,{'freeze_sha256':runner},'a'*64)
                control.write_text('{"state":"running","final_data_open":true}')
                with self.assertRaises(ValueError):f._final_gate(root,c,{'freeze_sha256':'b'*64},'a'*64)
                refit_review['status']='pending'
                with self.assertRaises(ValueError):f._final_gate(root,c,{'freeze_sha256':runner},'a'*64)

    def test_production_gate_failure_preserves_exposure_without_opening_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'.runtime').mkdir();(root/'.runtime/task.json').write_text('{}')
            with (patch.object(f,'authenticate',side_effect=ValueError('source approval absent')),
                  patch.object(f.w,'git',return_value=b'1'*40),patch.object(f,'_read_fixed') as read):
                with self.assertRaisesRegex(ValueError,'source approval absent'):
                    f.produce(root,'config.json','results/generated')
                read.assert_not_called()
            partial=list((root/'results/generated').glob('partial-*'))
            self.assertEqual(json.loads((partial[0]/'exposure.json').read_text()),[])
            self.assertTrue((partial[0]/'failure.json').exists())

    def test_actual_git_reference_acceptance_and_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            def git(*args):return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.PIPE)
            git('init','--quiet');git('config','user.name','Generated Test');git('config','user.email','fixture@example.invalid')
            (root/'audit').mkdir();raw=b'{"status":"accepted"}'
            (root/'audit/fixture.json').write_bytes(raw);git('add','audit/fixture.json');git('commit','--quiet','-m','generated')
            commit=git('rev-parse','HEAD').decode().strip()
            ref={'commit':commit,'path':'audit/fixture.json','sha256':f.w.sha(raw)}
            self.assertEqual(f._reference(root,ref),raw)
            with self.assertRaises(ValueError):f._reference(root,dict(ref,sha256='0'*64))

    def test_actual_published_chief_and_hy3_tasks_preserve_honest_owner(self):
        for owner in ('chief','hy3'):
            with self.subTest(owner=owner),tempfile.TemporaryDirectory() as directory:
                root=Path(directory)
                def git(*args):return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.PIPE)
                git('init','--quiet');git('config','user.name','Fixture');git('config','user.email','fixture@example.invalid')
                (root/'initial').write_text('generated');git('add','initial');git('commit','--quiet','-m','base')
                base=git('rev-parse','HEAD').decode().strip()
                task=dict(id='GENERATED-001',attempt=1,owner=owner,kind='commands',base_commit=base)
                (root/'ops/tasks').mkdir(parents=True)
                (root/'ops/tasks/GENERATED-001.json').write_bytes(f.w.canonical(task))
                queue={'tasks':[dict(id=task['id'],attempt=1,owner=owner,state='ready',
                                    task_sha256=f.w.sha(f.w.canonical(task)),branch='work/'+owner+'/GENERATED-001-a1')]}
                (root/'ops/queue.json').write_bytes(f.w.canonical(queue))
                git('add','ops');git('commit','--quiet','-m','publication')
                publication=git('rev-parse','HEAD').decode().strip()
                git('update-ref','refs/remotes/origin/main',publication)
                self.assertEqual(f._published_task(root,task,publication)['owner'],owner)
                with self.assertRaises(ValueError):f._published_task(root,dict(task,attempt=2),publication)


if __name__=='__main__':unittest.main()
