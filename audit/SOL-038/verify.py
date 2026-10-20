"""Read-only SOL-038 verifier. Scratch checkouts never modify saved evidence.

Replays actual recorded Git objects and accepted pure analysis only. No producer
generation, original competition CSV, calibration fit, strategy or network call.
"""
from copy import deepcopy
import importlib.util
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

if not __debug__:raise RuntimeError('optimized Python is unsupported for scalar audit assertions')
ROOT=Path(__file__).resolve().parents[2]
DIR=ROOT/'audit/SOL-038'
BASE='b75389aefeb06ed750c9b7aa891ecc383af9ce1a'
PUBLICATION='95eb627ce6536662b8c583dfd2e6046c3aaf0ea9'
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'src'))
from safeinvest import policy_analysis_writer as a
w=a.w
spec=importlib.util.spec_from_file_location('generated038',DIR/'generated.py')
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)


def independent_boundaries():
    """Scalar expectations assigned independently; no tested routine creates them."""
    facts=[]
    config=w.strict_json((ROOT/a.POLICY).read_bytes())
    for v,expected in ((math.nextafter(.1,-math.inf),False),(.1,True),(math.nextafter(.1,math.inf),True)):
        groups,hashes=g.grid(context=v)
        for r in groups['primary']['balanced_cost']['scenario_metrics']:r['net_real_cagr_pct']=0.
        metrics,_,_=a._bridge(groups,split='synthetic',n=4,source_hashes=hashes)
        tables=a._tables(metrics,config,'synthetic')
        row=next(r for r in tables.comparison_gates if (r['candidate_mode'],r['reference_mode'],r['fee_rate'],r['horizon'])==('balanced_context','balanced_cost',.0025,30))
        # Four identical gains: (v + v)/2 is the scalar median, folds each v.
        assert row['median_paired_growth_gain_pp'].hex()==((v+v)/2).hex()
        assert row['flags']['gain_at_least_0_10'] is expected
        facts.append(dict(value_hex=v.hex(),gain_pass=expected))
    groups,hashes=g.grid(referral=True)
    metrics,_,_=a._bridge(groups,split='synthetic',n=4,source_hashes=hashes)
    tables=a._tables(metrics,config,'synthetic')
    for r in tables.profile_screen:
        assert r['p10_growth_pct']==-.01 and r['p90_loss_pct']==60.
        assert not r['qualified'] and 'risk_pass' in r['reasons'] and 'purchasing_power_pass' in r['reasons']
    for r in tables.profile_recommendations:
        assert r['selected_class'] is None and r['action']=='human_review'
        assert r['maximum_qualifying_median_growth_pct'] is None and r['personalized_overlay_pending'] is True
    # Paired and marginal statistics differ. Direct scalar arithmetic on explicit arrays.
    groups,hashes=g.grid()
    for mode,values in (('balanced_cost',[0.,10.,20.,30.]),('balanced_context',[31.,1.,11.,21.])):
        for r in groups['primary'][mode]['scenario_metrics']:r['net_real_cagr_pct']=values[r['scenario_id']-1]
    metrics,_,_=a._bridge(groups,split='synthetic',n=4,source_hashes=hashes)
    tables=a._tables(metrics,config,'synthetic')
    row=next(r for r in tables.comparison_gates if (r['candidate_mode'],r['reference_mode'],r['fee_rate'],r['horizon'])==('balanced_context','balanced_cost',.0025,30))
    paired=sorted([31.-0.,1.-10.,11.-20.,21.-30.])
    paired_median=(paired[1]+paired[2])/2
    fraction=3*.1
    marginal=(1.-fraction)*1.+fraction*11.-((1.-fraction)*0.+fraction*10.)
    assert row['median_paired_growth_gain_pp']==paired_median==-9.
    assert row['marginal_p10_growth_difference_pp']==marginal
    # Declared CSV scalar fixture preserves null/bool/signed zero and both neighbors.
    schema=w._schema('n:float z:float b:bool? count:int? label:str')
    original=[dict(n=v,z=-0.0,b=b,count=None,label='percent/year') for v,b in (
        (.01,None),(math.nextafter(.1,-math.inf),False),(math.nextafter(.1,math.inf),True))]
    assert w.exact(w.decode_csv(w.encode_csv(original,schema),schema),original)
    assert (.11-.01).hex()=='0x1.999999999999ap-4'
    return dict(thresholds=facts,all_referrals=10,paired_median=paired_median,marginal_p10=marginal,typed_rows=3)


def evidence_inventory():
    return {p.relative_to(ROOT).as_posix():a.sha(p.read_bytes()) for p in DIR.rglob('*') if p.is_file()}


def check():
    before=evidence_inventory()
    v=w.strict_json((DIR/'verification.json').read_bytes())
    w.keys(v,('schema_version','task_id','base_commit','publication_commit','task_digest','task_blob_sha256','files','accepted_sources'))
    assert v['schema_version']==1 and v['task_id']=='SOL-038' and v['base_commit']==BASE and v['publication_commit']==PUBLICATION
    task_raw=w.blob(ROOT,PUBLICATION,'ops/tasks/SOL-038.json');task=w.strict_json(task_raw)
    assert a.sha(task_raw)==v['task_blob_sha256'] and a.sha(a.canonical(task))==v['task_digest']
    assert task['base_commit']==BASE and w.exact(w.strict_json((DIR/'task.json').read_bytes()),task)
    assert w.exact(v['accepted_sources'],task['parameters']['source_sha256'])
    for p,h in v['accepted_sources'].items():
        canonical=w.blob(ROOT,BASE,p);current=(ROOT/p).read_bytes()
        assert a.sha(canonical)==h and current in (canonical,canonical.replace(b'\n',b'\r\n')), 'changed accepted source '+p
    for p,h in v['files'].items():
        raw=(ROOT/p).read_bytes()
        assert (a.sha(raw),len(raw)) in {(h['sha256'],h['bytes']),(h['crlf_sha256'],h['crlf_bytes'])}, 'changed audit/code/output evidence '+p
    # Historical failure is separately authenticated, never an approval dependency.
    recovery=w.strict_json((DIR/'recovery.json').read_bytes())
    assert recovery['task_id']=='SOL-038' and recovery['base_commit']==BASE and recovery['publication_commit']==PUBLICATION
    w.ancestor(ROOT,BASE,PUBLICATION)
    publication_queue=w.strict_json(w.blob(ROOT,PUBLICATION,'ops/queue.json'))
    published=[q for q in publication_queue['tasks'] if q['id']=='SOL-038']
    assert len(published)==1 and published[0]['task_sha256']==v['task_digest']
    released=w.strict_json(w.blob(ROOT,recovery['release_snapshot'],'ops/queue.json'))
    release=[q for q in released['tasks'] if q['id']=='SOL-038']
    assert len(release)==1 and release[0]['state']=='ready' and release[0]['owner']=='sol'
    assert release[0]['task_sha256']==v['task_digest'] and release[0]['attempt']==1
    probe=[q for q in released['tasks'] if q['id']=='SOL-037']
    assert len(probe)==1 and probe[0]['state']=='accepted'

    predecessor=task['parameters']['failed_predecessor']
    assert predecessor['task_id']=='SOL-034' and predecessor['receipt_status']=='failed'
    assert predecessor['result_commit']=='632c95f03d3bbfeed1f847598eed3e6cfc5be264'
    oldraw=w.blob(ROOT,predecessor['result_commit'],'handoff/SOL-034/result.json')
    assert a.sha(oldraw)==predecessor['receipt_sha256']
    oldreceipt=w.strict_json(oldraw)
    assert oldreceipt['status']=='failed' and oldreceipt['artifact_hash_basis']=='canonical_git_blob'
    assert oldreceipt['artifacts_sha256']==recovery['failed_predecessor']['artifacts_sha256']
    for name,digest in oldreceipt['artifacts_sha256'].items():
        assert a.sha(w.blob(ROOT,predecessor['result_commit'],name))==digest,'changed failed predecessor object '+name
    schema=w.strict_json((DIR/'schema.json').read_bytes())
    assert set(schema['$defs']['config']['properties']['acceptance']['properties'])==set(a.ACCEPTED)|{'SOL-038'}
    assert 'SOL-034' not in json.dumps(schema)
    for name in ('src/safeinvest/policy_analysis_writer.py','scripts/run_development_analysis.py'):
        assert 'SOL-034' not in (ROOT/name).read_text(encoding='utf8')
    # Sealed inventory must include every original fixture file; unknown extras fail.
    expected={p for p in v['files'] if p.startswith('audit/SOL-038/fixture/')}
    actual={'audit/SOL-038/fixture/'+p for p in a._files(DIR/'fixture')}
    assert actual==expected,'missing/extra fixture evidence'
    facts=w.strict_json((DIR/'scalar-facts.json').read_bytes())
    for record in facts['boundary']['success']+[facts['boundary']['failure']]:
        assert record['stdout_sha256']==a.sha(record['stdout'].encode()) and record['stderr_sha256']==a.sha(record['stderr'].encode())
        assert record['pythonpath_absent'] is True and record['argv'][1]=='-B' and record['argv'][-1]=='--check'
        child=w.strict_json(record['stdout'].strip())
        assert child['guard']=='passed' and child['exit']==record['returncode']
        if 'modules' in child:
            assert 'safeinvest.policy_writer' in child['modules'] and 'safeinvest.policy_analysis_writer' not in child['modules']
    assert [r['returncode'] for r in facts['boundary']['success']]==[0,0]
    assert facts['boundary']['failure']['returncode']==9 and facts['boundary']['analysis_called_after_failure'] is False
    boundary=w.strict_json((DIR/'boundary-module-records.json').read_bytes())
    assert boundary['analysis_called_after_failure'] is False
    assert a.sha(boundary['source_text'].encode())==boundary['source_sha256']
    assert [r['returncode'] for r in boundary['records']]==[0,0,9]
    for record in boundary['records']:
        assert record['script_sha256'] in (boundary['source_sha256'],a.sha(boundary['source_text'].encode().replace(b'\n',b'\r\n')))
        assert record['stdout_sha256']==a.sha(record['stdout'].encode()) and record['stderr_sha256']==a.sha(record['stderr'].encode())
        child=w.strict_json(record['stdout'].strip())
        assert child['exit']==record['returncode'] and child['guard']=='passed'
        assert 'safeinvest.policy_writer' in child['modules'] and 'safeinvest.policy_analysis_writer' not in child['modules']
        assert child['checked_saved_generated_fixture'] is True
        for module,info in child['modules'].items():
            rel=info['relative_path'];obj=w.blob(ROOT,BASE,rel)
            assert info['sha256'] in (a.sha(obj),a.sha(obj.replace(b'\n',b'\r\n')))
            assert info['path'].replace(chr(92),'/').endswith('/'+rel)
    with tempfile.TemporaryDirectory() as scratch:
        checkout=Path(scratch)/'checkout'
        subprocess.run(['git','clone','--quiet',str(DIR/'fixture/objects.bundle'),str(checkout)],check=True,capture_output=True)
        g.git(checkout,'update-ref','refs/remotes/origin/main',facts['git']['later_HEAD'])
        # Replace only scratch working bytes by actual saved bytes. No generation.
        for p in checkout.iterdir():
            if p.name!='.git':
                if p.is_dir():shutil.rmtree(p)
                else:p.unlink()
        shutil.copytree(DIR/'fixture/bytes',checkout,dirs_exist_ok=True)
        binding=w.strict_json((DIR/'fixture/binding.json').read_bytes())
        groups,hashes=g.authenticate(checkout,binding)
        tables=a._synthetic_check(DIR/'fixture/analysis',ROOT,groups,hashes)
        expected_facts=g.scalar_facts(tables)
        for key,value in expected_facts.items():assert w.exact(facts[key],value), 'changed scalar expectation'
        # Rejected corruption calls read only. Real Git canonical bytes remain authoritative.
        original=(checkout/'source.txt').read_bytes();(checkout/'source.txt').write_bytes(original+b'corruption')
        corrupted=g.inventory(checkout)
        try:g.authenticate(checkout,binding)
        except ValueError:pass
        else:raise AssertionError('source corruption accepted')
        assert corrupted==g.inventory(checkout)
        (checkout/'source.txt').write_bytes(original)
        bad=Path(scratch)/'bad-output';shutil.copytree(DIR/'fixture/analysis',bad)
        m=w.strict_json((bad/'run_manifest.json').read_bytes());m['counts']['profile_screen']=29
        (bad/'run_manifest.json').write_bytes(w._json_bytes(m));corrupted=g.inventory(bad)
        try:a._synthetic_check(bad,ROOT,groups,hashes)
        except ValueError:pass
        else:raise AssertionError('count corruption accepted')
        assert corrupted==g.inventory(bad)
        output=w.strict_json((bad/'selection.json').read_bytes());output['selected_mode']='bills_keep'
        raw=w._json_bytes(output);(bad/'selection.json').write_bytes(raw)
        m['counts']['profile_screen']=30;m['artifacts']['selection.json'].update(sha256=a.sha(raw),bytes=len(raw))
        (bad/'run_manifest.json').write_bytes(w._json_bytes(m));corrupted=g.inventory(bad)
        try:a._synthetic_check(bad,ROOT,groups,hashes)
        except ValueError:pass
        else:raise AssertionError('rehashed output corruption accepted')
        assert corrupted==g.inventory(bad)
        # Missing/duplicate keys and changed rehashed metric values remain failures.
        original_groups=deepcopy(groups)
        for label in ('missing','duplicate','changed'):
            altered=deepcopy(groups);rows=altered['primary']['balanced_cost']['scenario_metrics']
            if label=='missing':rows.pop()
            elif label=='duplicate':rows[1]=deepcopy(rows[0])
            else:rows[0]['net_real_cagr_pct']=.12
            immutable=a.canonical(altered)
            try:a._synthetic_check(DIR/'fixture/analysis',ROOT,altered,hashes)
            except (ValueError,KeyError):pass
            else:raise AssertionError('wrong metric accepted: '+label)
            assert immutable==a.canonical(altered)
        assert w.exact(groups,original_groups)
    independent=independent_boundaries()
    assert before==evidence_inventory(),'verifier changed original evidence'
    modules={k:str(Path(m.__file__).resolve()) for k,m in sys.modules.items() if k=='safeinvest' or k.startswith('safeinvest.')}
    print(json.dumps(dict(status='passed',read_only=True,task_id='SOL-038',independent=independent,modules=modules)))


if __name__=='__main__':
    if sys.argv[1:]!=['--check']:raise SystemExit('only read-only --check is supported')
    check()
