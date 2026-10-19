"""Exclusive synthetic evidence creation; --check is read-only, including failures.

No competition source CSV is opened. Exact HY3-003 output blobs are import fixtures.
No production configuration is created. The saved inventory never hashes itself.
"""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'tests'))
import argparse
import copy
import json
import platform
import os
import subprocess
import tempfile
import uuid
import shutil
import time
from unittest.mock import patch
from safeinvest import policy_writer as w
from safeinvest.policy_calibration import build_synthetic_calibrations
from safeinvest.policy_cases import build_case_tables
from test_policy_writer import fixture, snapshot, source_bytes

AUDIT=ROOT/'audit/SOL-029'
BASE='df038cb116c4818c14454231500f992af3f26d0f'
PUBLICATION='10fd3892b4352f856155b85ef3548b31fa5320b5'
DELIVERED=('src/safeinvest/policy_writer.py','scripts/run_development_policy.py',
           'tests/test_policy_writer.py','audit/SOL-029/verify.py',
           'audit/SOL-029/implementation.md','audit/SOL-029/findings.json','audit/SOL-029/schema.json')


def identity():
    task_raw=w.blob(ROOT,PUBLICATION,'ops/tasks/SOL-029.json');task=w.strict_json(task_raw)
    w.require(task['id']=='SOL-029' and task['attempt']==1 and task['base_commit']==BASE and
              task['owner']=='sol' and task['kind']=='agent' and task['split']=='synthetic','task identity')
    w.require(task['allowed_paths']==['src/safeinvest/policy_writer.py','scripts/run_development_policy.py',
              'tests/test_policy_writer.py','audit/SOL-029'],'allowed paths identity')
    w.ancestor(ROOT,BASE,PUBLICATION)
    w.ancestor(ROOT,PUBLICATION,w.git(ROOT,'rev-parse','origin/main').decode().strip())
    queue=w.strict_json(w.blob(ROOT,PUBLICATION,'ops/queue.json'))
    entries=[q for q in queue['tasks'] if q['id']=='SOL-029']
    w.require(len(entries)==1,'publication task count')
    q=entries[0]
    w.require(q['task_sha256']==w.sha(w.canonical(task)) and q['state']=='ready' and
              q['owner']=='sol' and q['attempt']==1 and q['branch']=='work/sol/SOL-029-a1',
              'immutable task publication digest/state')
    pins={};consumed={}
    for name,h in task['parameters']['source_sha256'].items():
        raw=w.blob(ROOT,BASE,name);actual=w.safe_path(ROOT,name).read_bytes()
        w.require(w.sha(raw)==h and actual in (raw,raw.replace(b'\n',b'\r\n')),'source pin '+name)
        pins[name]=h;consumed[name]=w.sha(actual)
    queue=w.strict_json(w.blob(ROOT,BASE,'ops/queue.json'));dependencies={}
    for name,commit in task['parameters']['accepted_dependencies'].items():
        records=[q for q in queue['tasks'] if q['id']==name]
        w.require(len(records)==1,'dependency missing/duplicate')
        record=records[0]
        w.require(record['state']=='accepted' and record['reviewed_commit']==commit,'dependency identity')
        review=w.strict_json(w.blob(ROOT,BASE,record['acceptance_evidence']))
        w.require(review.get('task_id')==name and review['reviewed_commit']==commit,'dependency chief identity')
        if name in ('SOL-016','SOL-021','SOL-022','SOL-025'):
            w.require(record['code_verdict']==review['code_verdict']=='approve','positive computational approval')
        dependencies[name]=commit
    failed=next(q for q in queue['tasks'] if q['id']=='SOL-026')
    w.require(failed['state']=='cancelled' and failed.get('code_verdict')!='approve','failed writer relabelled')
    imported={}
    for name,module in sorted(sys.modules.items()):
        if name=='safeinvest' or name.startswith('safeinvest.'):
            p=Path(module.__file__).resolve();rel=p.relative_to(ROOT).as_posix();raw=p.read_bytes()
            w.require(rel in w.CLOSURE,'unlisted import '+rel)
            imported[name]=dict(path=rel,consumed_sha256=w.sha(raw),canonical_lf_sha256=w.sha(raw.replace(b'\r\n',b'\n')))
    return dict(task_id='SOL-029',attempt=1,base_commit=BASE,publication_commit=PUBLICATION,
        task_blob_sha256=w.sha(task_raw),task_digest=w.sha(w.canonical(task)),source_pins=pins,
        consumed_checkout_sha256=consumed,accepted_dependencies=dependencies,imported_modules=imported,
        delivered_sha256={p:w.sha((ROOT/p).read_bytes().replace(b'\r\n',b'\n')) for p in DELIVERED})


def check_identity(saved,actual=None):
    actual=identity() if actual is None else actual
    w.keys(saved,actual)
    for key in actual:
        if key not in ('consumed_checkout_sha256','imported_modules'):
            w.require(w.exact(actual[key],saved[key]),'audit identity mismatch: '+key)
    w.keys(saved['consumed_checkout_sha256'],actual['consumed_checkout_sha256'])
    for p,h in saved['consumed_checkout_sha256'].items():
        raw=(ROOT/p).read_bytes().replace(b'\r\n',b'\n');w.hash_string(h)
        w.require(h in (w.sha(raw),w.sha(raw.replace(b'\n',b'\r\n'))),'false consumed checkout hash')
    w.keys(saved['imported_modules'],actual['imported_modules'])
    for name,item in saved['imported_modules'].items():
        w.keys(item,('path','consumed_sha256','canonical_lf_sha256'))
        expected=actual['imported_modules'][name]
        w.require(item['path']==expected['path'] and item['canonical_lf_sha256']==expected['canonical_lf_sha256'],
                  'imported module identity')
        raw=(ROOT/item['path']).read_bytes().replace(b'\r\n',b'\n');w.hash_string(item['consumed_sha256'])
        w.require(item['consumed_sha256'] in (w.sha(raw),w.sha(raw.replace(b'\n',b'\r\n'))),'false imported consumed hash')
    return actual


def corruptions(output,data,provenance):
    """Reconstruct compact malicious overlays, including updated file hashes.

    Overlay recipes describe the smallest mutation. Saved original bytes are
    never edited. This deliberately does not rerun a case to repair its evidence.
    """
    original=snapshot(output);sources=source_bytes();manifest_raw=(output/'run_manifest.json').read_bytes()
    name='cases/equal_weight_annual/annual_ledgers.csv';raw=(output/name).read_bytes()
    schema=w.SCHEMAS['annual_ledgers'];rows=w.decode_csv(raw,schema,w.KEYS['annual_ledgers'])
    records=[]
    for label in ('missing_file','altered_numeric','false_source','wrong_config','duplicate_key','bogus_count','incomplete_status'):
        m=w.strict_json(manifest_raw);overrides={};recipe={}
        if label=='missing_file':
            overrides['cases/bills_keep/summary.csv']=None;recipe={'remove':'cases/bills_keep/summary.csv'}
        elif label in ('altered_numeric','duplicate_key'):
            changed=copy.deepcopy(rows)
            if label=='altered_numeric':
                recipe={'table':name,'row':0,'column':'fee','original_hex':changed[0]['fee'].hex(),'replacement':0.0,'recompute_manifest_file_hash':True}
                changed[0]['fee']=0.0
            else:
                changed.append(dict(changed[0]));recipe={'table':name,'append_copy_of_row':0,'recompute_manifest_file_hash':True}
            edited=w.encode_csv(changed,schema);overrides[name]=edited
            m['artifacts'][name].update(sha256=w.sha(edited),bytes=len(edited),rows=len(changed))
            overrides['run_manifest.json']=w._json_bytes(m)
        else:
            if label=='false_source':m['provenance']['kind']='false';recipe={'path':['provenance','kind'],'value':'false'}
            elif label=='wrong_config':m['configuration']['group']='primary';recipe={'path':['configuration','group'],'value':'primary'}
            elif label=='bogus_count':m['artifacts'][name]['rows']+=1;recipe={'path':['artifacts',name,'rows'],'add':1}
            else:m['status']='failed';recipe={'path':['status'],'value':'failed'}
            overrides['run_manifest.json']=w._json_bytes(m)
        original_read=Path.read_bytes
        def read(p):
            try:rel=p.relative_to(output).as_posix()
            except ValueError:return original_read(p)
            if rel in overrides:
                if overrides[rel] is None:raise FileNotFoundError(rel)
                return overrides[rel]
            return original_read(p)
        with patch.object(Path,'read_bytes',read):
            try:w._check_saved(output,data=data,expected_provenance=provenance,
                expected_configuration={'kind':'synthetic_internal','group':'doubled'})
            except (ValueError,FileNotFoundError) as exc:reason=str(exc)
            else:raise AssertionError('corruption accepted '+label)
        w.require(snapshot(output)==original and source_bytes()==sources,'read-only corruption changed evidence')
        records.append(dict(category=label,recipe=recipe,rejection=reason,
            overlay_sha256={p:None if v is None else w.sha(v) for p,v in overrides.items()},original_unchanged=True))
    w.require('exact fee multiplication' in records[1]['rejection'],'rehash hid numeric corruption')
    return dict(schema_version=1,status='passed',method='reconstructable read-only byte overlays; no copied bundle',
                corruptions=records,source_bytes_unchanged=True,output_bytes_unchanged=True)


def binding_corruptions(saved):
    records=[]
    edits=[('task_id','SOL-026'),('base_commit','0'*40),('publication_commit','0'*40),
           ('task_digest','0'*64),('task_blob_sha256','0'*64)]
    candidates=[]
    for key,value in edits:
        bad=copy.deepcopy(saved);bad[key]=value;candidates.append((key,bad))
    for key in ('source_pins','delivered_sha256','consumed_checkout_sha256'):
        bad=copy.deepcopy(saved);name=next(iter(bad[key]));bad[key][name]='0'*64;candidates.append((key,bad))
    for key in ('consumed_sha256','canonical_lf_sha256','path'):
        bad=copy.deepcopy(saved);bad['imported_modules']['safeinvest.policy_writer'][key]='0'*64
        candidates.append(('imported_'+key,bad))
    original=source_bytes();actual=identity()
    for label,bad in candidates:
        try:check_identity(bad,actual)
        except ValueError as exc:reason=str(exc)
        else:raise AssertionError('identity corruption accepted '+label)
        w.require(source_bytes()==original,'source repaired by rejected check')
        records.append(dict(category=label,rejection=reason,repair=False))
    # Alter actual final source bytes through a read overlay, without editing disk.
    original_read=Path.read_bytes;target=ROOT/'src/safeinvest/policy_writer.py'
    def read(p):return original_read(p)+b'\n# false final source\n' if p==target else original_read(p)
    with patch.object(Path,'read_bytes',read):
        try:check_identity(saved)
        except ValueError as exc:reason=str(exc)
        else:raise AssertionError('changed final source accepted')
    records.append(dict(category='actual_final_source_bytes',rejection=reason,repair=False))
    w.require(source_bytes()==original,'final source corruption changed disk')
    return records


def _preserve_failures(fixtures):
    def fail(stage,started):
        w._write(stage/'partial.txt',b'explicit generated partial fixture\n')
        raise RuntimeError('deliberate SOL-029 synthetic failure')
    attempts=[('partial',fail,{}),('oversized',lambda stage,start:w._write(stage/'oversized.bin',b'12345',4),{})]
    records=[]
    for name,operation,options in attempts:
        output=fixtures/('failed-'+name)
        try:w._stage_output(output,operation,**options)
        except (ValueError,RuntimeError) as exc:reason=str(exc)
        else:raise AssertionError('failed fixture completed')
        before=snapshot(output)
        try:w._stage_output(output,operation,**options)
        except ValueError as exc:refusal=str(exc)
        else:raise AssertionError('failed root reused')
        w.require(before==snapshot(output),'failed staging changed')
        records.append(dict(kind=name,rejection=reason,repeat_refusal=refusal,inventory=before))
    output=fixtures/'failed-timeout'
    with patch.object(w.time,'monotonic',side_effect=[0.,2.,2.]):
        try:w._stage_output(output,lambda stage,start:None,max_seconds=1)
        except ValueError as exc:reason=str(exc)
        else:raise AssertionError('timeout accepted')
    records.append(dict(kind='timeout',method='deterministic monotonic boundary, one-second allowance',
                        rejection=reason,inventory=snapshot(output)))
    return records


def creation():
    w.require(not (AUDIT/'verification.json').exists() and not (AUDIT/'integrity-self-tests.json').exists(),
              'evidence already exists; use --check; new trials must be exclusive')
    started=time.monotonic();ident=identity()
    runtime=w.strict_json((ROOT/'.runtime/task.json').read_bytes())
    published=w.strict_json(w.blob(ROOT,PUBLICATION,'ops/tasks/SOL-029.json'))
    w.require(w.exact(runtime,published),'assigned recovery task differs from publication')
    data=fixture();rows=w._input_rows(data,4,6)
    calibration=build_synthetic_calibrations(data,scenario_count=4,periods=6)
    fixtures=AUDIT/('synthetic-'+uuid.uuid4().hex);fixtures.mkdir()
    w._write(fixtures/'generated.csv',data)
    provenance={'kind':'synthetic_internal','source_sha256':source_bytes()}
    imports={m:build_case_tables(rows,calibrations=calibration,mode=m,fee_rate=.0025,split='synthetic',horizons=(1,5,6)) for m in w.BASELINES}
    calls=[]
    def compute(*args,**kw):
        w.require(kw['mode'] not in w.BASELINES,'primary baseline simulation callback invoked')
        calls.append(kw['mode']);return build_case_tables(*args,**kw)
    start=time.monotonic()
    w._synthetic_bundle(fixtures/'primary',data,n=4,t=6,horizons=(1,5,6),group='primary',imports=imports,provenance=provenance,compute=compute)
    w._synthetic_bundle(fixtures/'doubled',data,n=4,t=6,horizons=(1,5,6),group='doubled',provenance=provenance)
    w.require(calls==list(w.MODES[:5]),'primary new mode callback list')
    generation_seconds=time.monotonic()-start
    integrity=corruptions(fixtures/'doubled',data,provenance)
    integrity['binding_corruptions']=binding_corruptions(ident)
    failures=_preserve_failures(fixtures)
    w._write(AUDIT/'integrity-self-tests.json',w._json_bytes(integrity))
    evidence=dict(schema_version=1,kind='synthetic_writer_recovery_evidence',identity=ident,
        fixture_root=fixtures.relative_to(ROOT).as_posix(),provenance=provenance,
        generated_input_sha256=w.sha(data),synthetic_generation_seconds=generation_seconds,
        primary_computed_modes=calls,baseline_callback_invocations=0,preserved_failure_trials=failures,
        evidence_sha256={'audit/SOL-029/integrity-self-tests.json':w.sha((AUDIT/'integrity-self-tests.json').read_bytes())},
        fixture_bytes_sha256=snapshot(fixtures),fixture_actual_bytes={p.relative_to(fixtures).as_posix():p.stat().st_size
            for p in fixtures.rglob('*') if p.is_file()},production_execution=False,competition_input_read=False,
        independent_outcome_acceptance=False,final_data_open=False,
        creation_argv=sys.argv,python=platform.python_version(),creation_elapsed_seconds=time.monotonic()-started)
    # No self hash or forward hash of command logs. The command envelope hashes this file later.
    w._write(AUDIT/'verification.json',w._json_bytes(evidence))
    return replay(evidence)


def replay(evidence):
    w.keys(evidence,('schema_version','kind','identity','fixture_root','provenance','generated_input_sha256',
        'synthetic_generation_seconds','primary_computed_modes','baseline_callback_invocations','preserved_failure_trials',
        'evidence_sha256','fixture_bytes_sha256','fixture_actual_bytes','production_execution','competition_input_read',
        'independent_outcome_acceptance','final_data_open','creation_argv','python','creation_elapsed_seconds'))
    w.require(evidence['schema_version']==1 and evidence['kind']=='synthetic_writer_recovery_evidence','evidence kind')
    w.require(all(evidence[k] is False for k in ('production_execution','competition_input_read',
              'independent_outcome_acceptance','final_data_open')),'false execution claim')
    w.require(evidence['primary_computed_modes']==list(w.MODES[:5]) and
              type(evidence['baseline_callback_invocations']) is int and evidence['baseline_callback_invocations']==0,
              'primary computation identity')
    actual=check_identity(evidence['identity'])
    fixtures=w.safe_path(ROOT,evidence['fixture_root']);before=snapshot(fixtures);sources=source_bytes()
    w.require(before==evidence['fixture_bytes_sha256'],'fixture byte inventory changed')
    w.require({p.relative_to(fixtures).as_posix():p.stat().st_size for p in fixtures.rglob('*') if p.is_file()}==
              evidence['fixture_actual_bytes'],'fixture byte sizes changed')
    data=(fixtures/'generated.csv').read_bytes()
    w.require(w.sha(data)==evidence['generated_input_sha256'],'generated input changed')
    proof=evidence['provenance'];w.keys(proof,('kind','source_sha256'))
    w.require(proof['kind']=='synthetic_internal','synthetic provenance kind')
    w.keys(proof['source_sha256'],w.CLOSURE)
    for name,h in proof['source_sha256'].items():
        raw=(ROOT/name).read_bytes().replace(b'\r\n',b'\n');w.hash_string(h)
        w.require(h in (w.sha(raw),w.sha(raw.replace(b'\n',b'\r\n'))),'synthetic consumed-source proof differs')
    reports={};start=time.monotonic()
    for group in ('primary','doubled'):
        reports[group]=w._check_saved(fixtures/group,data=data,expected_provenance=evidence['provenance'],
            expected_configuration={'kind':'synthetic_internal','group':group})
    # Exact accepted outputs only. These imported historical fixtures are never simulated.
    with patch('safeinvest.policy_cases.simulate_policy',side_effect=AssertionError('historical baseline simulation')):
        imports,index=w.import_references(ROOT,BASE)
    w.require(sum(len(c.annual_ledgers) for c in imports.values())==10800,'accepted import fixture count')
    integrity=corruptions(fixtures/'doubled',data,evidence['provenance'])
    integrity['binding_corruptions']=binding_corruptions(evidence['identity'])
    w.require(w.exact(integrity,w.strict_json((AUDIT/'integrity-self-tests.json').read_bytes())),'corruption evidence differs')
    w.require(set(evidence['evidence_sha256'])=={'audit/SOL-029/integrity-self-tests.json'},'evidence closure')
    for name,h in evidence['evidence_sha256'].items():w.require(w.sha((ROOT/name).read_bytes())==h,'evidence hash mismatch')
    w.require(before==snapshot(fixtures) and sources==source_bytes(),'read-only replay changed bytes')
    return dict(status='passed',read_only=True,synthetic_check_seconds=time.monotonic()-start,
        facts={k:v['independent_scalar_facts'] for k,v in reports.items()},corruption_rejections=7,
        binding_corruption_rejections=len(integrity['binding_corruptions']),authenticated_reference_ledger_rows=10800,
        imported_module_paths={name:str(Path(module.__file__).resolve()) for name,module in sorted(sys.modules.items())
            if name=='safeinvest' or name.startswith('safeinvest.')},production_execution=False,independent_outcome_acceptance=False)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    def audit(event,args):
        if event=='open' and isinstance(args[0],str):
            p=args[0].replace(chr(92),'/')
            if any(x in p for x in ('data/raw/','data/development/','data/final_holdout/')) and p.lower().endswith('.csv'):
                raise AssertionError('competition source CSV access forbidden')
    sys.addaudithook(audit)
    if args.check:
        original={p:p.read_bytes() for p in AUDIT.rglob('*') if p.is_file()}
        source_original=source_bytes()
        evidence=w.strict_json((AUDIT/'verification.json').read_bytes());result=replay(evidence)
        w.require(all(p.read_bytes()==b for p,b in original.items()),'audit bytes changed during final verifier')
        w.require(set(original)=={p for p in AUDIT.rglob('*') if p.is_file()},'audit file generation during check')
        w.require(source_original==source_bytes(),'source bytes changed during final verifier')
    else:result=creation()
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
