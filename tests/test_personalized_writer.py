"""Generated-only personalized writer tests; no competition input or final data."""
from copy import deepcopy
from dataclasses import replace
import csv
import importlib.util
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from safeinvest import personalized_writer as p
from safeinvest.policy_calibration import FIELDS

spec=importlib.util.spec_from_file_location('personalized_generated',ROOT/'audit/chief/takeover-analysis/generated.py')
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
spec=importlib.util.spec_from_file_location('personalized_cli',ROOT/'scripts/run_personalized_development.py')
cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)


def fixture(*,referral=False,returns=0.,inflation=0.):
    groups,hashes=g.grid(referral=referral)
    metrics,_,_=p.aw._bridge(groups,split='synthetic',n=4,source_hashes=hashes)
    tables=p.aw._tables(metrics,p.strict_json((ROOT/p.w.POLICY).read_bytes()),'synthetic')
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=FIELDS,lineterminator='\n')
    writer.writeheader();writer.writerows(dict(zip(FIELDS,(s,t,returns,returns,returns,inflation)))
        for s in range(1,5) for t in range(1,31))
    return stream.getvalue().encode(),tables.profile_recommendations,tables.profile_screen


def inventory(output):
    return {p.relative_to(output).as_posix():p.read_bytes() for p in output.rglob('*') if p.is_file()}


class PersonalizedWriterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.dir=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()

    def test_all_referrals_never_fit_or_simulate_and_keep_nulls(self):
        data,recs,screens=fixture(referral=True);out=self.dir/'referral'
        with (patch('safeinvest.policy_personalized.simulate_policy',side_effect=AssertionError('no simulation')),
             patch.object(p.w,'build_synthetic_calibrations',side_effect=AssertionError('no fit'))):
            m=p._synthetic_persist(out,data,recs,screens)
            roots=p._synthetic_check(out,data,recs,screens)
        self.assertEqual(m['counts']['executed_pairs'],0);self.assertEqual(m['counts']['root_rows'],10)
        self.assertEqual(set(inventory(out)),set(p.FILES))
        for row in roots:
            payload=row['component_payload'];self.assertIsNone(row['source_case_path'])
            self.assertIs(payload['source_verified'],False);self.assertIs(row['bridge_authentication']['verified'],False)
            self.assertEqual(payload['scenario_count'],0);self.assertEqual(payload['denominator'],0)
            for name in ('median_growth_pct','p90_loss_pct','risk_pass','exceedance_count','exceedance_fraction'):
                self.assertIsNone(payload[name])
            self.assertEqual(payload['reasons'],row['upstream_record']['reasons'])

    def test_all_assigned_counts_full_training_and_read_only_roundtrip(self):
        data,recs,screens=fixture();out=self.dir/'all';before=p.canonical([recs,screens])
        from safeinvest.policy_personalized import build_personalized_case_tables
        seen=[]
        def capture(rows,**kwargs):
            calibration=kwargs['calibrations'];seen.append(kwargs['profile_id'])
            self.assertEqual(calibration.periods,30)
            self.assertTrue(all(len(f.training_keys)==90 and len(f.prior.gross)==90 for f in calibration.folds))
            return build_personalized_case_tables(rows,**kwargs)
        m=p._synthetic_persist(out,data,recs,screens,compute=capture);saved=inventory(out)
        self.assertEqual(len(seen),10)
        roots=p._synthetic_check(out,data,recs,screens)
        self.assertEqual(inventory(out),saved);self.assertEqual(before,p.canonical([recs,screens]))
        self.assertEqual(m['counts'],dict(annual_ledgers=648,decisions=648,scenario_metrics=40,
            summary=10,target_scores=648,root_rows=10,executed_pairs=10,upstream_referrals=0))
        for row in roots:
            payload=row['component_payload'];self.assertEqual(payload['scenario_count'],4)
            self.assertEqual(payload['horizon'],p.PROFILES[payload['profile_id']][0])
            self.assertEqual(payload['review_threshold_pct'],p.PROFILES[payload['profile_id']][1])
            decisions=p.w.decode_csv((out/row['source_case_path']/'decisions.csv').read_bytes(),p.SCHEMAS['decisions'])
            self.assertTrue(all(r['prior_mass']==1. for r in decisions))
        with self.assertRaisesRegex(ValueError,'existing output'):p._synthetic_persist(out,data,recs,screens)

    def test_failed_own_screen_keeps_all_observations_and_proposed_class(self):
        data,recs,screens=fixture(returns=.125,inflation=.25);out=self.dir/'fails'
        p._synthetic_persist(out,data,recs,screens);roots=p._synthetic_check(out,data,recs,screens)
        for row in roots:
            payload=row['component_payload'];self.assertIsNotNone(payload['proposed_class'])
            self.assertIsNone(payload['recommended_class']);self.assertEqual(payload['scenario_count'],4)
            self.assertEqual(payload['status'],'human_review_after_rescreen');self.assertEqual(payload['exceedance_count'],4)
            self.assertIn('p10_growth_negative',payload['reasons'])
            self.assertIsNotNone(row['source_case_path'])

    def test_mixed_fee_classes_and_referrals_use_only_their_own_upstream_class(self):
        data,_,_=fixture();groups,hashes=g.grid()
        for group in ('primary','doubled'):
            for cls in p.CLASSES:
                for row in groups[group][cls+'_cost']['scenario_metrics']:
                    row['net_real_cagr_pct']=float(p.CLASSES.index(cls)) if group=='primary' else (
                        .3 if cls=='conservative' else .1)
                    if row['horizon']==25:row['max_real_drawdown_pct']=60.
        metrics,_,_=p.aw._bridge(groups,split='synthetic',n=4,source_hashes=hashes)
        t=p.aw._tables(metrics,p.strict_json((ROOT/p.w.POLICY).read_bytes()),'synthetic');out=self.dir/'mixed'
        m=p._synthetic_persist(out,data,t.profile_recommendations,t.profile_screen)
        roots=p._synthetic_check(out,data,t.profile_recommendations,t.profile_screen)
        self.assertEqual(m['counts']['executed_pairs'],8);self.assertEqual(m['counts']['upstream_referrals'],2)
        self.assertEqual(m['counts']['annual_ledgers'],448)
        index={(r['component_payload']['profile_id'],r['component_payload']['fee_rate']):r for r in roots}
        self.assertEqual(index['C',.0025]['component_payload']['proposed_class'],'growth')
        self.assertEqual(index['C',.005]['component_payload']['proposed_class'],'conservative')
        for fee in p.FEES:self.assertIsNone(index['D',fee]['source_case_path'])

    def test_assignment_order_key_screen_status_and_class_tampering_rejected_before_compute(self):
        data,recs,screens=fixture()
        changes=[]
        a,b=deepcopy(recs),deepcopy(screens);a.reverse();changes.append((a,b))
        a,b=deepcopy(recs),deepcopy(screens);a[0]=deepcopy(a[1]);changes.append((a,b))
        a,b=deepcopy(recs),deepcopy(screens);b[0]['qualified']=False;changes.append((a,b))
        a,b=deepcopy(recs),deepcopy(screens);a[0]['selected_mode']='balanced_adaptive';changes.append((a,b))
        a,b=deepcopy(recs),deepcopy(screens);a[0]['personalized_overlay_pending']=False;changes.append((a,b))
        a,b=deepcopy(recs),deepcopy(screens);b[0]['source_metric_keys'].reverse();changes.append((a,b))
        a,b=deepcopy(recs),deepcopy(screens);b[0]['flags']['risk_pass']=1;changes.append((a,b))
        for number,(a,b) in enumerate(changes):
            out=self.dir/str(number)
            with patch('safeinvest.policy_personalized.simulate_policy',side_effect=AssertionError('no simulation')):
                with self.assertRaises(ValueError):p._synthetic_persist(out,data,a,b)
            self.assertFalse(out.exists())

    def test_corrupt_rehashed_metrics_path_null_bool_missing_files_rejected_read_only(self):
        data,recs,screens=fixture()
        for change in ('metric','path','null','bool','missing'):
            out=self.dir/change;p._synthetic_persist(out,data,recs,screens)
            manifest=p.strict_json((out/'run_manifest.json').read_bytes())
            roots=p.strict_json((out/'personalized_results.json').read_bytes())
            if change=='metric':
                relative=roots[0]['source_case_path']+'/scenario_metrics.csv'
                rows=p.w.decode_csv((out/relative).read_bytes(),p.SCHEMAS['scenario_metrics'])
                rows[0]['net_real_cagr_pct']=math.nextafter(rows[0]['net_real_cagr_pct'],math.inf)
                raw=p.w.encode_csv(rows,p.SCHEMAS['scenario_metrics']);(out/relative).write_bytes(raw)
            elif change=='missing':
                relative=roots[0]['source_case_path']+'/summary.csv';(out/relative).unlink();raw=None
            else:
                relative='personalized_results.json'
                if change=='path':roots[0]['source_case_path']='cases/WRONG'
                elif change=='null':roots[0]['component_payload']['first_latch_year']=0
                else:roots[0]['component_payload']['source_verified']=True
                raw=p.w._json_bytes(roots);(out/relative).write_bytes(raw)
            if raw is not None:manifest['artifacts'][relative]=dict(sha256=p.sha(raw),bytes=len(raw))
            (out/'run_manifest.json').write_bytes(p.w._json_bytes(manifest));before=inventory(out)
            with self.assertRaises(ValueError):p._synthetic_check(out,data,recs,screens)
            self.assertEqual(before,inventory(out))

    def test_wrong_full_fold_prior_rejected_and_failed_staging_preserved(self):
        data,recs,screens=fixture();cal=p.w.build_synthetic_calibrations(data,scenario_count=4,periods=30)
        cal=replace(cal,folds=(replace(cal.folds[0],training_keys=cal.folds[0].training_keys[:-1]),*cal.folds[1:]))
        out=self.dir/'wrong-prior'
        with patch.object(p.w,'build_synthetic_calibrations',return_value=cal):
            with self.assertRaisesRegex(ValueError,'training keys'):p._synthetic_persist(out,data,recs,screens)
        # Computation happens before the synthetic persistence stage; invalid inputs do not create output.
        self.assertFalse(out.exists())

    def test_binary64_signed_zero_nullable_and_boolean_codec(self):
        schema=p.w._schema('value:float maybe:float? flag:bool number:int')
        for value in (-0.0,math.nextafter(.1,-math.inf),.1,math.nextafter(.1,math.inf)):
            original=[dict(value=value,maybe=None,flag=True,number=0)]
            restored=p.w.decode_csv(p.w.encode_csv(original,schema),schema)
            self.assertTrue(p.exact(original,restored))
        with self.assertRaises(ValueError):p.w.encode_csv([dict(value=0.,maybe=None,flag=1,number=0)],schema)

    def test_private_bundle_git_checkout_roundtrip_and_later_head(self):
        data,recs,screens=fixture();repo=self.dir/'repo';repo.mkdir();out=repo/'output'
        p._synthetic_persist(out,data,recs,screens)
        def git(*args):return subprocess.run(['git',*args],cwd=repo,capture_output=True,check=True)
        git('init','--quiet');git('config','user.email','generated@example.invalid');git('config','user.name','Generated test')
        git('config','core.autocrlf','false');git('add','output');git('commit','--quiet','-m','generated fixture')
        original=inventory(out)
        git('checkout','--','output');p._synthetic_check(out,data,recs,screens)
        (repo/'later.txt').write_text('later generated HEAD\n');git('add','later.txt');git('commit','--quiet','-m','later fixture')
        p._synthetic_check(out,data,recs,screens);self.assertEqual(original,inventory(out))

    def test_failed_checker_does_not_import_bridge_or_create_output(self):
        config=self.dir/'config.json';config.write_text('{}');output='output'
        with (patch.object(cli,'_preflight',return_value={}),patch.object(cli,'_children',side_effect=ValueError('checker failed')),
             patch.object(p,'produce_authenticated',side_effect=AssertionError('must not call'))):
            with self.assertRaisesRegex(ValueError,'checker failed'):cli._create(self.dir,'config.json',output)
        self.assertFalse((self.dir/output).exists())
        self.assertTrue(list((self.dir/'.runtime/personalized-preflight').rglob('failure.json')))

    def test_no_final_override_or_parameter_search_cli(self):
        with self.assertRaises(SystemExit):cli.main(['--config','x','--output','y','--fee','.01'])
        with self.assertRaises(ValueError):cli._path(self.dir,'../final.csv')
        with self.assertRaises(ValueError):cli._path(self.dir,'data\\final.csv')

    def test_failed_production_staging_keeps_diagnosis_without_success_marker(self):
        out=self.dir/'failed-stage'
        def fail(stage):
            p.w._write(stage/'partial.txt',b'preserved negative evidence\n')
            raise ValueError('generated failure')
        with self.assertRaisesRegex(ValueError,'generated failure'):
            p._stage(out,fail,started=time.monotonic(),max_seconds=30)
        self.assertFalse((out/'run_manifest.json').exists())
        self.assertTrue(list(out.rglob('partial.txt')));self.assertTrue(list(out.rglob('failure.json')))

    def test_large_upstream_manifest_is_hash_bound_without_duplicate_row_map(self):
        manifest=dict(binding={'task':'generated'},configuration={'kind':'generated'},
            counts={'metric_rows':9600},producers=[{'calibration':{'folds':[0,1,2,3]}}],
            metric_sources=[{'source_row_sha256':'a'*64} for _ in range(9600)])
        proof=dict(analysis_manifest=manifest,sources={},analysis_consumed={},
            recommendations=[{'generated':True}],screens=[{'generated':False}])
        saved=p._persisted_proof(proof)
        self.assertLess(len(p.canonical(saved)),1000)
        self.assertEqual(saved['upstream_counts'],{'metric_rows':9600})
        self.assertEqual(saved['producer_calibration_sha256'],[p.sha(p.canonical({'folds':[0,1,2,3]}))])
        altered=deepcopy(proof);altered['recommendations'][0]['generated']=False
        self.assertNotEqual(saved['upstream_assignment_sha256'],p._persisted_proof(altered)['upstream_assignment_sha256'])


if __name__=='__main__':unittest.main()
