"""Generated local Git/typed/boundary fixtures; no competition CSV or strategy runs."""
from copy import deepcopy
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from safeinvest import policy_analysis_writer as a
w=a.w
spec=importlib.util.spec_from_file_location('generated038',ROOT/'audit/SOL-038/generated.py')
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
spec=importlib.util.spec_from_file_location('cli038',ROOT/'scripts/run_development_analysis.py')
cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)


class AssemblyTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        print(json.dumps({'actual_module_paths':{k:str(Path(m.__file__).resolve()) for k,m in sys.modules.items() if k=='safeinvest' or k.startswith('safeinvest.')}}))

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.dir=Path(self.tmp.name)
        self.groups,self.hashes=g.grid()
    def tearDown(self):self.tmp.cleanup()

    def test_typed_detached_unit_only_and_no_mutation(self):
        rows=self.groups['primary']['balanced_cost']['scenario_metrics']
        rows[0]['net_real_cagr_pct']=.01
        rows[1]['net_real_cagr_pct']=math.nextafter(.1,-math.inf)
        rows[2]['net_real_cagr_pct']=math.nextafter(.1,math.inf)
        old=deepcopy(self.groups)
        metrics,source,mapping=a._bridge(self.groups,split='synthetic',n=4,source_hashes=self.hashes)
        self.assertTrue(w.exact(old,self.groups));self.assertEqual(len(metrics),320)
        for r in metrics:
            original=next(x for x in self.groups['primary' if r['fee_rate']==.0025 else 'doubled'][r['mode']]['scenario_metrics'] if x['scenario_id']==r['scenario_id'] and x['horizon']==r['horizon'])
            copy=dict(r);copy['growth_units']='percent/year'
            self.assertTrue(w.exact(copy,original));self.assertIsNot(copy,original)
        self.assertEqual(mapping['numeric_conversion'],'none');self.assertEqual(len(source),320)
        for mode in w.MODES:
            raw=w.encode_csv(self.groups['primary'][mode]['scenario_metrics'],w.SCHEMAS['scenario_metrics'])
            self.assertTrue(w.exact(w.decode_csv(raw,w.SCHEMAS['scenario_metrics'],w.KEYS['scenario_metrics']),self.groups['primary'][mode]['scenario_metrics']))
        self.assertEqual(rows[0]['nominal_fee_sum'].hex(),'-0x0.0p+0')

    def test_genuine_typed_persistence_scalar_selection_and_immutability(self):
        output=self.dir/'output';before=w.canonical(self.groups)
        m=a._synthetic_persist(output,ROOT,self.groups,self.hashes)
        inv=g.inventory(output);t=a._synthetic_check(output,ROOT,self.groups,self.hashes)
        g.scalar_facts(t)
        self.assertEqual(inv,g.inventory(output));self.assertEqual(before,w.canonical(self.groups))
        self.assertEqual(m['counts'],dict(a.EXPECTED,metric_rows=320,paired_differences=400))
        self.assertEqual(a._files(output),set(a.FILES)|{'run_manifest.json'})
        with self.assertRaisesRegex(ValueError,'existing output'):a._synthetic_persist(output,ROOT,self.groups,self.hashes)

    def test_all_referrals_are_completed_analysis_not_authentication_failure(self):
        groups,hashes=g.grid(referral=True);out=self.dir/'referral'
        a._synthetic_persist(out,ROOT,groups,hashes);t=a._synthetic_check(out,ROOT,groups,hashes)
        for r in t.profile_recommendations:
            self.assertEqual(r['action'],'human_review');self.assertIsNone(r['selected_class'])
            self.assertIsNone(r['maximum_qualifying_median_growth_pct']);self.assertIs(r['personalized_overlay_pending'],True)
        for r in t.profile_screen:
            self.assertIn('risk_pass',r['reasons']);self.assertIn('purchasing_power_pass',r['reasons'])

    def test_exact_threshold_neighbors_and_own_horizon_indifference(self):
        for val,passed in ((math.nextafter(.1,-math.inf),False),(.1,True),(math.nextafter(.1,math.inf),True)):
            groups,_=g.grid(context=val)
            for r in groups['primary']['balanced_cost']['scenario_metrics']:r['net_real_cagr_pct']=0.
            metrics,_,_=a._bridge(groups,split='synthetic',n=4,source_hashes=self.hashes)
            t=a._tables(metrics,w.strict_json((ROOT/a.POLICY).read_bytes()),'synthetic')
            gate=next(r for r in t.comparison_gates if (r['candidate_mode'],r['reference_mode'],r['fee_rate'],r['horizon'])==('balanced_context','balanced_cost',.0025,30))
            self.assertIs(gate['flags']['gain_at_least_0_10'],passed)
        for val,cls in ((math.nextafter(.1,-math.inf),'conservative'),(.1,'conservative'),(math.nextafter(.1,math.inf),'balanced')):
            groups,_=g.grid()
            for r in groups['primary']['balanced_cost']['scenario_metrics']:r['net_real_cagr_pct']=val
            metrics,_,_=a._bridge(groups,split='synthetic',n=4,source_hashes=self.hashes)
            t=a._tables(metrics,w.strict_json((ROOT/a.POLICY).read_bytes()),'synthetic')
            r=next(r for r in t.profile_recommendations if r['profile']=='B' and r['fee_rate']==.0025)
            self.assertEqual((r['horizon'],r['selected_class']),(15,cls))
        for field,values,flag in (
            ('net_real_cagr_pct',[(math.nextafter(-.1,-math.inf),False),(-.1,True),(math.nextafter(-.1,math.inf),True)],'tail_growth_at_least_minus_0_10'),
            ('max_real_drawdown_pct',[(math.nextafter(1.,-math.inf),True),(1.,True),(math.nextafter(1.,math.inf),False)],'tail_loss_at_most_1_00')):
            for val,expected in values:
                groups,_=g.grid()
                for mode in ('balanced_cost','balanced_context'):
                    for r in groups['primary'][mode]['scenario_metrics']:r[field]=0. if mode=='balanced_cost' else val
                metrics,_,_=a._bridge(groups,split='synthetic',n=4,source_hashes=self.hashes)
                t=a._tables(metrics,w.strict_json((ROOT/a.POLICY).read_bytes()),'synthetic')
                gate=next(r for r in t.comparison_gates if (r['candidate_mode'],r['reference_mode'],r['fee_rate'],r['horizon'])==('balanced_context','balanced_cost',.0025,30))
                self.assertIs(gate['flags'][flag],expected)

    def test_typed_corruptions_and_source_grid_rejected(self):
        bads=[]
        def add(label,change):
            groups=deepcopy(self.groups);change(groups);bads.append((label,groups))
        add('units',lambda d:d['primary']['balanced_cost']['scenario_metrics'][0].update(growth_units='percentage points per year'))
        add('bool',lambda d:d['primary']['balanced_cost']['scenario_metrics'][0].update(initial_allocation_deferred='false'))
        add('null',lambda d:d['primary']['bills_keep']['scenario_metrics'][0].update(human_review_count=0))
        add('missing key',lambda d:d['primary']['balanced_cost']['scenario_metrics'][0].pop('horizon'))
        add('duplicate row',lambda d:d['primary']['balanced_cost']['scenario_metrics'].__setitem__(1,d['primary']['balanced_cost']['scenario_metrics'][0]))
        add('count',lambda d:d['primary']['balanced_cost']['scenario_metrics'].pop())
        add('fee swap',lambda d:d.__setitem__('primary',d['doubled']))
        add('extra mode',lambda d:d['primary'].__setitem__('extra',{}))
        for label,groups in bads:
            with self.subTest(label=label),self.assertRaises((ValueError,KeyError)):
                a._synthetic_persist(self.dir/label,ROOT,groups,self.hashes)

    def test_read_only_rehashed_output_corruption_rejected(self):
        out=self.dir/'good';a._synthetic_persist(out,ROOT,self.groups,self.hashes)
        mutations={
          'lost_null':('paired_differences.csv',lambda rows:rows[0].update(human_review_count_difference=0)),
          'signed_zero':('paired_differences.csv',lambda rows:rows[0].update(nominal_fee_sum_difference=-0.0)),
          'number':('comparison_gates.json',lambda rows:rows[0].update(median_paired_growth_gain_pp=99.)),
          'bool_type':('profile_screen.json',lambda rows:rows[0].update(personalized_overlay_pending=1)),
          'lost_boolean':('profile_recommendations.json',lambda rows:rows[0].update(personalized_overlay_pending=False)),
          'missing_key':('selection.json',lambda row:row.pop('context')),
          'extra_key':('selection.json',lambda row:row.update(extra=True))}
        for label,(name,mutation) in mutations.items():
            with self.subTest(label=label):
                bad=self.dir/label;shutil.copytree(out,bad)
                raw=(bad/name).read_bytes()
                obj=w.decode_csv(raw,a.PAIRED_SCHEMA) if name.endswith('.csv') else w.strict_json(raw)
                mutation(obj)
                raw=w.encode_csv(obj,a.PAIRED_SCHEMA) if name.endswith('.csv') else w._json_bytes(obj)
                (bad/name).write_bytes(raw)
                m=w.strict_json((bad/'run_manifest.json').read_bytes());m['artifacts'][name].update(sha256=w.sha(raw),bytes=len(raw))
                (bad/'run_manifest.json').write_bytes(w._json_bytes(m));before=g.inventory(bad)
                with self.assertRaises(ValueError):a._synthetic_check(bad,ROOT,self.groups,self.hashes)
                self.assertEqual(before,g.inventory(bad))
        for label,mutation in (
            ('false_provenance',lambda m:m.update(binding={'kind':'forged'})),
            ('wrong_count',lambda m:m['counts'].update(metric_rows=321)),
            ('incomplete',lambda m:m.update(status='failed')),
            ('mapping',lambda m:m['mapping'].update(numeric_conversion='factor 100'))):
            bad=self.dir/label;shutil.copytree(out,bad);m=w.strict_json((bad/'run_manifest.json').read_bytes());mutation(m)
            (bad/'run_manifest.json').write_bytes(w._json_bytes(m));before=g.inventory(bad)
            with self.assertRaises(ValueError):a._synthetic_check(bad,ROOT,self.groups,self.hashes)
            self.assertEqual(before,g.inventory(bad))
        bad=self.dir/'missingfile';shutil.copytree(out,bad);(bad/'selection.json').unlink()
        with self.assertRaises((ValueError,FileNotFoundError)):a._synthetic_check(bad,ROOT,self.groups,self.hashes)
        with self.assertRaises(ValueError):w.strict_json(b'{"a":1,"a":2}')

    def test_actual_git_checkout_authentication_and_rehashed_metric(self):
        repo=self.dir/'repo';binding=g.create(repo);before=g.inventory(repo)
        groups,hashes=g.authenticate(repo,binding)
        clone=self.dir/'checkout';g.checkout(repo,clone)
        self.assertEqual(before,g.inventory(clone));g.authenticate(clone,binding)
        # Later HEAD and absent runtime task are already real, not mocked.
        self.assertNotEqual(g.git(repo,'rev-parse','HEAD').decode().strip(),binding['P'])
        self.assertFalse((repo/'.runtime/task.json').exists())
        for label,path,mutate in (
            ('source','source.txt',lambda b:b+b'changed'),
            ('config','config.json',lambda b:b.replace(b'320',b'321')),
            ('input','config.json',lambda b:b.replace(b'PRIVATE GENERATED CONFIG',b'WRONG GENERATED CONFIG')),
            ('metric','bundles/primary/cases/balanced_cost/scenario_metrics.csv',lambda b:b.replace(b'0.1,',b'0.11,',1)),
            ('swapped','bundles/primary/run_manifest.json',lambda b:b.replace(b'primary',b'doubled')),
            ('failed','bundles/doubled/run_manifest.json',lambda b:b.replace(b'completed',b'failed'))):
            original=(repo/path).read_bytes();(repo/path).write_bytes(mutate(original));inv=g.inventory(repo)
            with self.subTest(label=label),self.assertRaises(ValueError):g.authenticate(repo,binding)
            self.assertEqual(inv,g.inventory(repo));(repo/path).write_bytes(original)
        for key in ('C','E','P'):
            wrong=deepcopy(binding);wrong[key]=binding['C'] if key=='P' else g.git(repo,'rev-parse','HEAD').decode().strip()
            with self.assertRaises((ValueError,subprocess.CalledProcessError)):g.authenticate(repo,wrong)
        # Rehashing a changed manifest cannot override an exact accepted Git blob.
        name='bundles/primary/cases/balanced_cost/scenario_metrics.csv';original=(repo/name).read_bytes()
        (repo/name).write_bytes(original.replace(b'0.1,',b'0.12,',1))
        config=w.strict_json((repo/'config.json').read_bytes());config['producers'][0]['artifacts_sha256'][name]=w.sha((repo/name).read_bytes())
        (repo/'config.json').write_bytes(w._json_bytes(config))
        with self.assertRaises(ValueError):g.authenticate(repo,binding)

    def test_negative_or_unaccepted_result_not_completed_status(self):
        repo=self.dir/'repo';binding=g.create(repo)
        c=w.strict_json((repo/'config.json').read_bytes());producer=c['producers'][0]
        # Genuine saved accepted objects pass; an exact different commit cannot.
        a._approval(repo,binding['E'],producer['task_id'],producer['result_commit'],result=True)
        with self.assertRaisesRegex(ValueError,'positive'):
            a._approval(repo,binding['E'],producer['task_id'],binding['C'],result=True)
        queue=w.strict_json(w.blob(repo,binding['E'],'ops/queue.json'))
        original=a._blob
        for state,verdict in (('cancelled','approve'),('accepted','reject'),('accepted','pending')):
            bad=deepcopy(queue);bad['tasks'][0].update(state=state,result_verdict=verdict)
            def altered(root,base,name):
                return w._json_bytes(bad) if name=='ops/queue.json' else original(root,base,name)
            with patch.object(a,'_blob',side_effect=altered),self.assertRaisesRegex(ValueError,'positive'):
                a._approval(repo,binding['E'],producer['task_id'],producer['result_commit'],result=True)
        duplicate=deepcopy(queue);duplicate['tasks'].append(deepcopy(duplicate['tasks'][0]))
        with patch.object(a,'_blob',return_value=w._json_bytes(duplicate)),self.assertRaisesRegex(ValueError,'duplicate'):
            a._approval(repo,binding['E'],producer['task_id'],producer['result_commit'],result=True)

    def test_new_approval_schema_and_cli_source_identity(self):
        schema=w.strict_json((ROOT/'audit/SOL-038/schema.json').read_bytes())
        acceptance=schema['$defs']['config']['properties']['acceptance']
        self.assertEqual(set(acceptance['properties']),set(a.ACCEPTED)|{'SOL-038'})
        self.assertEqual(set(acceptance['required']),set(a.ACCEPTED)|{'SOL-038'})
        self.assertIn('audit/SOL-038/schema.json',a.CLOSURE)
        for name in ('src/safeinvest/policy_analysis_writer.py','scripts/run_development_analysis.py'):
            source=(ROOT/name).read_text(encoding='utf8')
            self.assertNotIn('SOL-034',source)
            self.assertIn("['SOL-038']",source)
        self.assertNotIn('SOL-034',json.dumps(schema))
        # Strict dict rejects the failed predecessor before any input/producer access.
        c=dict(schema_version=1,run_id='PRIVATE_SCHEMA_ONLY',split='development',execution_authorized=True,
               source_commit='b75389aefeb06ed750c9b7aa891ecc383af9ce1a',source_sha256={n:'0'*64 for n in a.CLOSURE},
               acceptance=dict(a.ACCEPTED,**{'SOL-034':'632c95f03d3bbfeed1f847598eed3e6cfc5be264'}),
               input={},policy_config={},producers=[],expected_counts={},execution={})
        with self.assertRaisesRegex(ValueError,'keys'):a.validate_config(c)
        c['acceptance'].pop('SOL-034');c['acceptance']['SOL-038']='b75389aefeb06ed750c9b7aa891ecc383af9ce1a'
        with self.assertRaisesRegex(ValueError,'original input identity'):a.validate_config(c)

    def test_actual_fresh_child_guard_success_failure_before_assembly(self):
        boundary=self.dir/'boundary';boundary.mkdir();(boundary/'scripts').mkdir()
        source=dict(source_commit='b75389aefeb06ed750c9b7aa891ecc383af9ce1a',source_sha256={n:w.sha(w.blob(ROOT,'b75389aefeb06ed750c9b7aa891ecc383af9ce1a',n)) for n in w.CLOSURE})
        checker=StringChild(ROOT,source)
        (boundary/'scripts/check.py').write_text(checker,encoding='utf8')
        c=dict(producers=[dict(group=g,config_path=g+'.json',root=g) for g in ('primary','doubled')],execution={'max_seconds':30})
        (boundary/'config.json').write_bytes(w._json_bytes(c))
        for group in ('primary','doubled'):(boundary/(group+'.json')).write_text('0')
        calls=[]
        result=cli._create(boundary,'config.json','success',_synthetic_script='scripts/check.py',_after_checks=lambda records,stage:calls.append(records))
        self.assertEqual(len(calls),1);self.assertTrue(all(r['returncode']==0 for r in calls[0]));self.assertTrue(all(r['pythonpath_absent'] for r in calls[0]))
        (boundary/'primary.json').write_text('9')
        with self.assertRaisesRegex(ValueError,'authentication failure'):
            cli._create(boundary,'config.json','failure',_synthetic_script='scripts/check.py',_after_checks=lambda *args:self.fail('analysis called after nonzero child'))
        failure=next((boundary/'failure').glob('partial-*/checker-primary.json'))
        self.assertEqual(json.loads(failure.read_text())['returncode'],9)
        self.assertTrue(list((boundary/'failure').glob('partial-*/failure.json')))
        with self.assertRaisesRegex(ValueError,'existing output'):
            cli._create(boundary,'MISSING CONFIG','failure',_after_checks=lambda *x:self.fail())

    def test_failure_staging_partial_timeout_oversize(self):
        def partial(stage,start):
            w._write(stage/'partial.txt',b'partial');raise RuntimeError('generated partial failure')
        def timeout(stage,start):
            w._write(stage/'partial.txt',b'partial')
            # Wait for measured elapsed time; fixed tiny sleeps can quantize to zero.
            while time.monotonic()-start<=.05:time.sleep(.01)
        def oversized(stage,start):w._write(stage/'big.bin',b'x'*11,10)
        for label,op,seconds in (('partial',partial,1),('timeout',timeout,.001),('oversize',oversized,1)):
            out=self.dir/label
            with self.assertRaises((RuntimeError,ValueError)):w._stage_output(out,op,max_seconds=seconds,max_bytes=10)
            self.assertTrue(list(out.glob('partial-*/failure.json')))
        with self.assertRaisesRegex(ValueError,'existing output'):cli._create(self.dir,'missing','partial')

    def test_production_cli_closed_and_surface(self):
        command=[sys.executable,'-B',str(ROOT/'scripts/run_development_analysis.py')]
        env={k:v for k,v in os.environ.items() if k.upper()!='PYTHONPATH'}
        r=subprocess.run(command+['--help'],capture_output=True,env=env)
        self.assertEqual(r.returncode,0)
        for option in ('--input','--fee','--threshold','--mode','--final','--synthetic'):
            r=subprocess.run(command+['--config','missing','--output','missing',option,'1'],capture_output=True,env=env)
            self.assertNotEqual(r.returncode,0)
        with self.assertRaises(ValueError):a.validate_config({'source_verified':True})


def StringChild(root,source):
    # Exercise the accepted writer's actual source_snapshot import guard in a fresh
    # Python child, then replay only its existing small generated saved fixture.
    # No competition input or producer generation; no mocked exit.
    return ('import argparse,json,os,sys\nfrom pathlib import Path\n'
        + 'sys.path.insert(0,'+repr(str(root/'src'))+')\n'
        + 'from safeinvest import policy_writer as w\n'
        + 'assert not any(k.upper()=="PYTHONPATH" for k in os.environ)\n'
        + 'assert "safeinvest.policy_analysis_writer" not in sys.modules\n'
        + 'p=argparse.ArgumentParser();p.add_argument("--config");p.add_argument("--output");p.add_argument("--check",action="store_true");a=p.parse_args()\n'
        + 'snapshot=w.source_snapshot(Path('+repr(str(root))+'),json.loads('+repr(json.dumps(source))+'))\n'
        + 'fixture=Path('+repr(str(root/'audit/SOL-031/synthetic-delivery'))+');saved=fixture/a.output;m=w.strict_json((saved/"run_manifest.json").read_bytes())\n'
        + 'inventory={str(p):w.sha(p.read_bytes()) for p in fixture.rglob("*") if p.is_file()}\n'
        + 'w._check_saved(saved,data=(fixture/"generated.csv").read_bytes(),expected_provenance=m["provenance"],expected_configuration=m["configuration"])\n'
        + 'assert inventory=={str(p):w.sha(p.read_bytes()) for p in fixture.rglob("*") if p.is_file()}\n'
        + 'code=int(Path(a.config).read_text());print(json.dumps({"checked_saved_generated_fixture":True,"guard":"passed","exit":code,"modules":snapshot["imported"],"executable":sys.executable}));sys.exit(code)\n')


if __name__=='__main__':unittest.main()
