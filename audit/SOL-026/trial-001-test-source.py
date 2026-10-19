"""Generated seams only. Source bootstrap precedes every SafeInvest import."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import copy
import csv
import hashlib
import io
import json
import math
import os
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch
from dataclasses import replace
from safeinvest import policy_writer as w
from safeinvest.policy_calibration import build_synthetic_calibrations
from safeinvest.policy_cases import build_case_tables


def fixture(n=4,t=6):
    stream=io.StringIO(newline=''); writer=csv.writer(stream,lineterminator='\n');writer.writerow(w.FIELDS)
    for s in range(1,n+1):
        for p in range(1,t+1):
            # Positive prior encourages deployment; sudden loss forces lagged review.
            values=(.18,.08,.001,.01) if p not in (2,3) else ((-.7,-.5,-.2,.02) if p==2 else (.04,.01,.005,.02))
            writer.writerow((s,p,*values))
    return stream.getvalue().encode()


def fresh():
    return Path(tempfile.mkdtemp(prefix='safeinvest-SOL026-synthetic-'))


def snapshot(root):
    return {p.relative_to(root).as_posix():w.sha(p.read_bytes()) for p in root.rglob('*') if p.is_file()}


def source_bytes():
    return {p:w.sha((ROOT/p).read_bytes()) for p in w.CLOSURE if (ROOT/p).exists()}


def internal_config(group='doubled'):
    # In-memory boundary object only; never saved or accepted by the CLI.
    h='a'*64
    c=dict(schema_version=1,run_id='boundary_fixture',split='development',execution_authorized=True,
        source_commit='b'*40,source_sha256={p:h for p in w.CLOSURE},
        acceptance={p:'c'*40 for p in ('SOL-021','SOL-022','SOL-025','SOL-026')},
        input=dict(path=w.INPUT_PATH,sha256=w.INPUT_HASH,scenario_ids=[1,120],periods=30),
        policy_config=dict(path=w.POLICY,sha256=h),layout_config=dict(path=w.LAYOUT,sha256=h),
        group=group,horizons=list(w.HORIZONS),references=[],expected_counts=w.expected_counts(group),
        execution=dict(cpu_only=True,required_python='3.12',max_seconds=1500,max_artifact_bytes=w.LIMIT))
    return c


class WriterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=fixture();cls.rows=w._input_rows(cls.data,4,6)
        cls.cal=build_synthetic_calibrations(cls.data,scenario_count=4,periods=6)
        cls.home=fresh();cls.output=cls.home/'doubled'
        cls.provenance={'kind':'synthetic_internal','source_sha256':source_bytes()}
        cls.manifest=w._synthetic_bundle(cls.output,cls.data,n=4,t=6,horizons=(1,5,6),group='doubled',provenance=cls.provenance)

    def check(self,output=None):
        return w._check_saved(output or self.output,data=self.data,expected_provenance=self.provenance,
                             expected_configuration={'kind':'synthetic_internal','group':'doubled'})

    def test_generated_eight_modes_two_fees_and_no_primary_baseline_callback(self):
        before=snapshot(self.output);sources=source_bytes();data=self.data
        report=self.check();self.assertGreater(report['independent_scalar_facts'],5000)
        imports={m:build_case_tables(self.rows,calibrations=self.cal,mode=m,fee_rate=.0025,split='synthetic',horizons=(1,5,6)) for m in w.BASELINES}
        called=[]
        def compute(*a,**kw):
            self.assertNotIn(kw['mode'],w.BASELINES);called.append((kw['mode'],kw['fee_rate']))
            return build_case_tables(*a,**kw)
        output=fresh()/'primary'
        w._synthetic_bundle(output,data,n=4,t=6,horizons=(1,5,6),group='primary',imports=imports,compute=compute)
        r=w._check_saved(output,data=data,expected_provenance={'kind':'synthetic_internal'},
            expected_configuration={'kind':'synthetic_internal','group':'primary'},imports=imports)
        self.assertEqual(len(called),5);self.assertEqual({k for _,k in called},{.0025})
        self.assertEqual(before,snapshot(self.output));self.assertEqual(sources,source_bytes());self.assertEqual(data,self.data)
        self.assertEqual(report['counts'],r['counts'])
        # Both fees pass decision fee and accounting fee identities in check_case.
        self.assertEqual(report['counts']['annual_ledgers'],192)
        self.assertEqual(report['counts']['decisions'],120)

    def test_declared_csv_types_all_columns_and_boundaries(self):
        for table,schema in w.SCHEMAS.items():
            for name,typ,nullable in schema:
                value={'str':'label','int':7,'float':-.0,'bool':False}[typ]
                row={n:({'str':'x','int':1,'float':.1,'bool':True}[t]) for n,t,_ in schema}
                row[name]=value
                self.assertTrue(w.exact(w.decode_csv(w.encode_csv([row],schema),schema)[0],row))
                if nullable:
                    row[name]=None
                    self.assertIsNone(w.decode_csv(w.encode_csv([row],schema),schema)[0][name])
                else:
                    row[name]=None
                    with self.assertRaises(ValueError):w.encode_csv([row],schema)
                for bad in ('nan','Infinity','True','1.5' if typ=='int' else ''):
                    if typ=='str' or (bad=='' and nullable):continue
                    with self.assertRaises((ValueError,OverflowError)):w._decode(bad,typ,nullable)
        schema=w._schema('id:int x:float null:bool? flag:bool')
        rows=[dict(id=i,x=x,null=None,flag=False) for i,x in enumerate((-.0,math.nextafter(.1,-math.inf),.1,math.nextafter(.1,math.inf),.01))]
        self.assertTrue(w.exact(rows,w.decode_csv(w.encode_csv(rows,schema),schema,('id',))))
        self.assertEqual(rows[-1]['x'],.01);self.assertNotEqual(rows[-1]['x'],1.)
        for data in (b'id,x,null,flag,extra\n',b'id,x,null\n',b'id,x,x,flag\n',b'id,x,null,flag\n0,0,,false,extra\n',
                     b'id,x,null,flag\n0,0,,false\n0,0,,false\n'):
            with self.assertRaises(ValueError):w.decode_csv(data,schema,('id',))
        self.assertFalse(w.exact(False,0));self.assertFalse(w.exact(-.0,0.))
        self.assertEqual((.11-.01).hex(),'0x1.999999999999ap-4')
        with self.assertRaises(ValueError):w._close(0.,2.91271096747931e-15,'tiny fee')

    def test_seven_corruptions_read_only_rehashed_numeric(self):
        # Compact overlays, no seven full copies. Original snapshots survive all rejections.
        original=snapshot(self.output); source=source_bytes(); evidence=[]
        manifest_raw=(self.output/'run_manifest.json').read_bytes()
        name='cases/equal_weight_annual/annual_ledgers.csv';raw=(self.output/name).read_bytes()
        schema=w.SCHEMAS['annual_ledgers']
        rows=w.decode_csv(raw,schema,w.KEYS['annual_ledgers'])
        operations={
            'missing_file':('cases/bills_keep/summary.csv',None),
            'altered_numeric':(name,None),
            'false_source':('run_manifest.json',None),
            'wrong_config':('run_manifest.json',None),
            'duplicate_key':(name,None),
            'bogus_count':('run_manifest.json',None),
            'incomplete_status':('run_manifest.json',None)}
        for label,(target,_) in operations.items():
            m=w.strict_json(manifest_raw);overrides={}
            if label=='missing_file':overrides[target]=None
            elif label in ('altered_numeric','duplicate_key'):
                changed=copy.deepcopy(rows)
                if label=='altered_numeric':changed[0]['fee']=0.
                else:changed.append(dict(changed[0]))
                edited=w.encode_csv(changed,schema);overrides[target]=edited
                m['artifacts'][name].update(sha256=w.sha(edited),bytes=len(edited),rows=len(changed))
                overrides['run_manifest.json']=w._json_bytes(m)
            else:
                if label=='false_source':m['provenance']['kind']='false'
                elif label=='wrong_config':m['configuration']['group']='primary'
                elif label=='bogus_count':m['artifacts'][name]['rows']+=1
                else:m['status']='failed'
                overrides['run_manifest.json']=w._json_bytes(m)
            original_read=Path.read_bytes
            def read(p):
                try:rel=p.relative_to(self.output).as_posix()
                except ValueError:return original_read(p)
                if rel in overrides:
                    if overrides[rel] is None:raise FileNotFoundError(rel)
                    return overrides[rel]
                return original_read(p)
            with patch.object(Path,'read_bytes',read):
                try:self.check()
                except (ValueError,FileNotFoundError) as exc:diagnosis=str(exc)
                else:self.fail(label+' accepted')
            evidence.append(dict(category=label,rejection=diagnosis,
                overlays={p:None if v is None else dict(bytes=len(v),sha256=w.sha(v)) for p,v in overrides.items()}))
            self.assertEqual(original,snapshot(self.output));self.assertEqual(source,source_bytes())
        self.assertIn('exact fee',evidence[1]['rejection'])
        self.corruption_evidence=evidence

    def test_strict_config_guard(self):
        c=internal_config();w.validate_config(c)
        changes=[('schema_version',True),('split','final'),('group','search'),('horizons',[True,6,15,25,30]),
                 ('references',[{}]),('source_commit','x'),('acceptance',{'SOL-023':'c'*40})]
        for k,v in changes:
            bad=copy.deepcopy(c);bad[k]=v
            with self.assertRaises(ValueError):w.validate_config(bad)
        for raw in (b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":Infinity}'):
            with self.assertRaises(ValueError):w.strict_json(raw)
        for path,value in ((('input','periods'),True),(('execution','max_seconds'),True),
                           (('execution','max_seconds'),1501),(('execution','cpu_only'),1),
                           (('expected_counts','cases'),True)):
            bad=copy.deepcopy(c);bad[path[0]][path[1]]=value
            with self.assertRaises(ValueError):w.validate_config(bad)
        for key in c:
            bad=copy.deepcopy(c);bad.pop(key)
            with self.assertRaises(ValueError):w.validate_config(bad)
        bad=copy.deepcopy(c);bad['unknown']=1
        with self.assertRaises(ValueError):w.validate_config(bad)
        bad=copy.deepcopy(c);bad['source_sha256'].pop('src/safeinvest/accounting.py')
        with self.assertRaises(ValueError):w.validate_config(bad)

    def test_publication_task_binding_and_P_later_than_E(self):
        # Generated Git boundary seam. No synthetic authorization objects are saved.
        task=dict(id='HY3-boundary',attempt=1,owner='hy3',kind='commands',base_commit='e'*40)
        P='f'*40
        q=dict(id=task['id'],attempt=1,owner='hy3',state='ready',branch='work/hy3/HY3-boundary-a1',task_sha256=w.sha(w.canonical(task)))
        objects={(P,'ops/tasks/HY3-boundary.json'):w.canonical(task),(P,'ops/queue.json'):w.canonical({'tasks':[q]})}
        def blob(root,c,p):return objects[c,p]
        with patch.object(w,'blob',blob),patch.object(w,'ancestor') as ancestor,patch.object(w,'git',return_value=b'f'*40):
            result=w.validate_publication(ROOT,task,P)
            self.assertEqual(result['base_commit'],'e'*40)
            ancestor.assert_any_call(ROOT,'e'*40,P)
            for field,value in (('attempt',2),('base_commit','d'*40),('kind','agent')):
                bad=dict(task);bad[field]=value
                with self.assertRaises(ValueError):w.validate_publication(ROOT,bad,P)
            for field,value in (('task_sha256','0'*64),('branch','other'),('state','cancelled'),('owner','sol')):
                wrong=dict(q);wrong[field]=value;objects[P,'ops/queue.json']=w.canonical({'tasks':[wrong]})
                with self.assertRaises(ValueError):w.validate_publication(ROOT,task,P)
            with self.assertRaises(KeyError):w.validate_publication(ROOT,task,'a'*40)

    def test_fixed_raw_input_grid_and_symlink_guards(self):
        home=fresh();p=home/w.INPUT_PATH;p.parent.mkdir(parents=True)
        data=fixture(120,30);p.write_bytes(data)
        # Internal boundary mock changes only hash oracle, never CLI config.
        with patch.object(w,'INPUT_HASH',w.sha(data)):
            raw,rows=w.load_fixed_input(home);self.assertEqual(len(rows),3600);self.assertEqual(raw,data)
            p.write_bytes(data+b'\n')
            with self.assertRaises(ValueError):w.load_fixed_input(home)
        bad=data.decode().splitlines();bad[-1]=bad[-2]
        with self.assertRaises(ValueError):w._input_rows(('\n'.join(bad)+'\n').encode(),120,30)
        for bad in (fixture(4,6),b'x,y\n1,2\n'):
            with self.assertRaises(ValueError):w._input_rows(bad,120,30)
        with self.assertRaises(ValueError):w.safe_path(home,'../outside')
        # Test resolution guard even on hosts without symlink creation privileges.
        original=Path.resolve
        def resolve(p,*a,**kw):
            if p==home/w.INPUT_PATH:return home/'outside.csv'
            return original(p,*a,**kw)
        with patch.object(Path,'resolve',resolve):
            with self.assertRaises(ValueError):w.safe_path(home,w.INPUT_PATH)

    def test_calibration_digest_membership_and_separate_attestation(self):
        attest=w.calibration_attestation(self.data,self.rows,4,6,self.cal,'synthetic')
        self.assertFalse(attest['production_origin_verified']);self.assertEqual(self.cal.manifest()['split'],'synthetic')
        for fold in self.cal.folds:
            self.assertEqual(len(fold.training_ids),3);self.assertEqual(len(fold.evaluation_ids),1)
            self.assertEqual(len(fold.training_keys),18)
        for field,value in (('training_rows_sha256','0'*64),('real_gross_sha256','0'*64),('training_ids',(1,2,3)),('training_keys',((1,1),))):
            c=replace(self.cal,folds=(replace(self.cal.folds[0],**{field:value}),*self.cal.folds[1:]))
            with self.assertRaises(ValueError):w.calibration_attestation(self.data,self.rows,4,6,c,'synthetic')

    def test_exact_HY3_import_without_simulation(self):
        before=source_bytes();C='8d00ca8eafc00fd636273be4125216e981289804'
        # Accepted output Git blobs only; no source competition CSV access.
        with patch('safeinvest.policy_cases.simulate_policy',side_effect=AssertionError('baseline simulation')):
            cases,index=w.import_references(ROOT,C)
        self.assertEqual(set(cases),set(w.BASELINES));self.assertFalse(index['baseline_simulation'])
        self.assertEqual(sum(len(x.annual_ledgers) for x in cases.values()),10800)
        for m,c in cases.items():
            self.assertFalse(c.decisions);self.assertFalse(c.target_scores)
            self.assertTrue(all(r['growth_units']=='percent/year' for r in c.scenario_metrics))
            for table in w.TABLES:
                records=list(getattr(c,table))
                self.assertTrue(w.exact(records,w.decode_csv(w.encode_csv(records,w.SCHEMAS[table]),w.SCHEMAS[table],w.KEYS[table])))
        self.assertEqual(before,source_bytes())

    def test_t_minus_one_review_latch_and_future_prefix(self):
        original=build_case_tables(self.rows,calibrations=self.cal,mode='balanced_context',fee_rate=.005,split='synthetic',horizons=(1,5,6))
        changed=copy.deepcopy(self.rows);changed[2]['equity_return']='.9';changed[2]['inflation']='.3'
        later=build_case_tables(changed,calibrations=self.cal,mode='balanced_context',fee_rate=.005,split='synthetic',horizons=(1,5,6))
        a=[r for r in original.decisions if r['scenario_id']==1 and r['period']<=3]
        b=[r for r in later.decisions if r['scenario_id']==1 and r['period']<=3]
        self.assertTrue(w.exact(a,b));self.assertTrue(any(r['human_review_latched'] for r in original.decisions))
        for s in range(1,5):
            latch=False
            for d in [r for r in original.decisions if r['scenario_id']==s]:
                if latch:self.assertTrue(d['human_review_latched']);self.assertEqual(d['action'],'human_review')
                latch=d['human_review_latched']

    def test_exclusive_existing_failure_and_size_budget(self):
        for status in ('completed','failed'):
            home=fresh();(home/'status').write_text(status)
            with patch.object(w,'_input_rows',side_effect=AssertionError('input read')):
                with self.assertRaises(ValueError):w._synthetic_bundle(home,self.data,n=4,t=6,horizons=(1,5,6),group='doubled')
        home=fresh()/'failure'
        def fail(stage,started):
            w._write(stage/'partial.txt',b'partial')
            raise RuntimeError('deliberate synthetic failure')
        with self.assertRaises(RuntimeError):w._stage_output(home,fail)
        self.assertEqual(len(list(home.glob('partial-*/failure.json'))),1)
        self.assertEqual(len(list(home.glob('partial-*/partial.txt'))),1)
        home=fresh()/'oversized'
        with self.assertRaises(ValueError):w._stage_output(home,lambda stage,start:w._write(stage/'x',b'12345',4))
        self.assertTrue(list(home.glob('partial-*/failure.json')))
        home=fresh()/'timeout'
        with self.assertRaises(ValueError):w._stage_output(home,lambda stage,start:None,max_seconds=-1)
        self.assertTrue(list(home.glob('partial-*/failure.json')))

    def test_import_help_no_data_access_and_cli_surface(self):
        code="""import sys,pathlib,runpy;sys.path.insert(0,'src');sys.dont_write_bytecode=True
import builtins
original=builtins.open
reads=[]
def guard(file,*args,**kw):
 p=str(file).replace('\\\\','/')
 if '/data/' in p or p.startswith('data/'):raise AssertionError('data access: '+p)
 return original(file,*args,**kw)
builtins.open=guard
import safeinvest.policy_writer
sys.argv=['scripts/run_development_policy.py','--help']
runpy.run_path('scripts/run_development_policy.py',run_name='__main__')
"""
        env={k:v for k,v in os.environ.items() if k.upper()!='PYTHONPATH'}
        before=source_bytes();result=subprocess.run([sys.executable,'-B','-c',code],cwd=ROOT,env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        for flag in ('--config','--output','--check','--help'):self.assertIn(flag,result.stdout)
        for flag in ('--synthetic','--input','--fee','--final'):self.assertNotIn(flag,result.stdout)
        self.assertEqual(before,source_bytes())


if __name__=='__main__':unittest.main()
