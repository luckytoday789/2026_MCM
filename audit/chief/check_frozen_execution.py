"""Independent stdlib-only exact freeze audit; no SafeInvest imports or CSV opens."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
MODES=['bills_keep','equal_weight_annual','equal_weight_buy_hold','conservative_cost','balanced_cost','growth_cost','balanced_context','balanced_adaptive']
FEES=[.0025,.005];HORIZONS=[5,6,15,25,30];PROFILES={'A':(5,10),'B':(15,25),'C':(30,40),'D':(25,15),'E':(6,35)}
MODULES=['__init__','accounting','backtest','baselines','metrics','experiments','policy_pilot','policy_calibration','policy_cases','policy_writer','final_refit','final_paths','final_execution']
SPECS=['PROBLEM_LOCK.md','ACCOUNTING.md','DEVELOPMENT_POLICY_PILOT_V2.md','POLICY_CORRECTION_V2.md','POLICY_NUMERIC_K1.md','POLICY_NUMERIC_K2.md','POLICY_CASE_ENGINE.md','POLICY_RESULT_WRITER.md','POLICY_WRITER_COMPATIBILITY.md','POLICY_WRITER_ACCEPTANCE_REFERENCES.md','POLICY_WRITER_EXECUTION_CONFIG.md','POLICY_WRITER_TASK_BINDING.md','POLICY_WRITER_RECOVERY.md','POLICY_WRITER_GIT_PORTABILITY.md','POLICY_WRITER_FILE_DELIVERABLES.md','FINAL_EVALUATION.md','FINAL_OUTPUT_NOTES.md','final_evaluation_contract_v1.json','development_policy_pilot_v2.json','policy_driver_layout_v2.json']
CLOSURE={*('src/safeinvest/'+n+'.py' for n in MODULES),*('specs/'+n for n in SPECS),'scripts/run_development_policy.py','scripts/run_final_evaluation.py'}


def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def exact(a,b):return type(a) is type(b) and (a.hex()==b.hex() if type(a) is float else set(a)==set(b) and all(exact(a[k],b[k]) for k in a) if type(a) is dict else len(a)==len(b) and all(exact(x,y) for x,y in zip(a,b)) if type(a) is list else a==b)


def safe(name):
    assert type(name) is str and '\\' not in name and not Path(name).is_absolute() and '..' not in Path(name).parts
    path=(ROOT/name).resolve();assert path.is_relative_to(ROOT) and not name.lower().endswith('.csv'),'CSV access forbidden'
    return path


def pairs(items):
    result={}
    for k,v in items:assert k not in result,'duplicate JSON key';result[k]=v
    return result


def js(raw):return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda s:(_ for _ in ()).throw(ValueError('nonfinite JSON')))
def blob(commit,path):
    assert len(commit)==40 and all(c in '0123456789abcdef' for c in commit);safe(path)
    return subprocess.check_output(['git','show',commit+':'+path],cwd=ROOT)
def ancestor(a,b):assert subprocess.run(['git','merge-base','--is-ancestor',a,b],cwd=ROOT,capture_output=True).returncode==0,'unpublished reference ancestry'


def reference(ref,base):
    assert set(ref)=={'commit','path','sha256'};ancestor(ref['commit'],base)
    raw=blob(ref['commit'],ref['path']);assert sha(raw)==ref['sha256'],'referenced byte digest mismatch'
    return js(raw)


def audit(freeze_ref,effective_path):
    F,path=freeze_ref.split(':',1);assert path=='ops/freeze.json'
    raw=blob(F,path);freeze=js(raw);effective_file=Path(effective_path).resolve()
    assert effective_file.is_relative_to(ROOT) and effective_file.suffix=='.json'
    control=js(safe('ops/control.json').read_bytes());assert control['final_data_open'] is False,'pre-gate audit only'
    effective_raw=effective_file.read_bytes();c=js(effective_raw)
    assert not {'freeze','freeze_attestation'}&set(c),'supply exact effective payload, not future self-referential config'
    assert c['stage']=='final' and sha(canonical(c))==freeze['effective_configuration_sha256']
    C=c['source_commit'];ancestor(C,F)
    assert freeze['source_commit']==C and exact(freeze['source_sha256'],c['source_sha256'])
    assert set(c['source_sha256'])==CLOSURE,'complete independent computational closure required'
    for name,digest in c['source_sha256'].items():
        data=blob(C,name);assert sha(data)==digest and safe(name).read_bytes() in (data,data.replace(b'\n',b'\r\n')),'source Git/checkout mismatch'
    policy=js(blob(C,'specs/development_policy_pilot_v2.json'));contract=js(blob(C,'specs/final_evaluation_contract_v1.json'))
    assert exact(freeze['policy_parameters'],policy) and exact(freeze['evaluation_contract'],contract)
    assert contract['modes']==policy['modes']==MODES and contract['fee_rates']==policy['fee_rates']==FEES
    assert contract['horizons']==policy['horizons']==HORIZONS
    contrasts=[[m,'equal_weight_annual'] for m in MODES if m!='equal_weight_annual']+[['balanced_context','balanced_cost'],['balanced_adaptive','balanced_context'],['balanced_adaptive','balanced_cost']]
    assert freeze['contrasts']==contrasts and len(contrasts)==10
    assert exact(freeze['primary_mode'],c['primary_mode']) and exact(freeze['profile_choices'],c['profile_choices'])
    assert c['primary_mode'] in ('balanced_cost','balanced_context','balanced_adaptive')
    assert len(c['profile_choices'])==10
    for row,(p,k) in zip(c['profile_choices'],[(p,k) for p in PROFILES for k in FEES]):
        assert set(row)=={'profile_id','fee_rate','proposed_class','eligible','reason'}
        assert (row['profile_id'],row['fee_rate'])==(p,k) and type(row['fee_rate']) is float
        assert type(row['eligible']) is bool and type(row['reason']) is str and row['reason'] and row['proposed_class'] in (None,'conservative','balanced','growth')
        assert not row['eligible'] or row['proposed_class'] is not None
    for name in ('source_review','development_review'):assert exact(freeze[name],c[name])
    source=reference(c['source_review'],F);ancestor(C,c['source_review']['commit'])
    assert source['status']=='accepted' and source['source_commit']==C and exact(source['source_sha256'],c['source_sha256'])
    development=reference(c['development_review'],F)
    assert development['status']=='accepted' and development['all_ten_rescreens_accepted'] is True
    assert development['primary_mode']==c['primary_mode'] and exact(development['profile_choices'],c['profile_choices'])
    assert len(development['evidence'])>=2
    for item in development['evidence']:reference(item,F)
    assert exact(freeze['refit'],c['refit']);refit=reference(c['refit'],F)
    assert refit['status']=='completed_refit' and refit['source_verified'] is True
    old=refit['configuration'];assert old['stage']=='refit' and old['source_commit']==C
    assert exact(old['source_sha256'],c['source_sha256']) and old['primary_mode']==c['primary_mode']
    assert exact(old['profile_choices'],c['profile_choices'])
    r=refit['refit'];assert r['training_row_count']==3600 and len(r['gross'])==3600
    assert r['training_scenario_ids']==list(range(1,121)) and r['training_row_keys']==[[s,t] for s in range(1,121) for t in range(1,31)]
    assert all(len(row)==3 and all(type(v) is float and math.isfinite(v) and v>0 for v in row) for row in r['gross'])
    support=dict(schema='all-development-prior-support-v1',asset_order=['equity_return','bond_return','bill_proxy_return'],rows=[[v.hex() for v in row] for row in r['gross']])
    assert sha(canonical(support))==r['prior_support_sha256'] and r['annual_weight']=='1 / 3600'
    accepted=reference(freeze['refit_acceptance'],F)
    assert accepted['status']=='accepted' and exact(accepted['refit'],c['refit'])
    manifest=js(blob(C,'data/manifest.json'));inputs={e['path']:e['sha256'] for e in manifest['files']}
    assert exact(freeze['input_files_sha256'],inputs)
    assert freeze['input_path']=='data/final_holdout/scenarios_121_180.csv'
    assert freeze['input_sha256']==inputs[freeze['input_path']]
    assert r['input_sha256']==inputs['data/development/scenarios_001_120.csv']
    planned=freeze['planned_execution'];e=c['execution']
    assert e['cpu_only'] is True and e['required_python']=='3.12' and type(e['max_seconds']) is int and 0<e['max_seconds']<=1800 and e['max_artifact_bytes']==10485760
    assert planned['config_path']=='specs/execution/'+c['run_id']+'.json' and e['output']=='results/final/'+c['run_id']
    command=['{python}','-B','scripts/run_final_evaluation.py','--config',planned['config_path'],'--output',e['output']]
    assert planned['commands']==[command,command+['--check']] and planned['output']==e['output']
    assert planned['max_seconds']==e['max_seconds'] and planned['max_artifact_bytes']==e['max_artifact_bytes']
    assert planned['scenario_ids']==list(range(121,181)),'one complete declared final shard required'
    eligible=[row for row in c['profile_choices'] if row['eligible']]
    counts=dict(generic_cases=16,generic_scenario_paths=960,generic_annual_ledgers=28800,generic_metrics=4800,comparisons=100,paired_rows=6000,profile_rows=10,personalized_cases=len(eligible),personalized_metrics=60*len(eligible),personalized_annual_ledgers=60*sum(PROFILES[row['profile_id']][0] for row in eligible))
    assert exact(freeze['counts'],counts) and freeze['failure_rule']==contract['correction_rule']
    assert sha(effective_file.read_bytes())==sha(effective_raw) and not any(n=='safeinvest' or n.startswith('safeinvest.') for n in sys.modules)
    return dict(status='passed',independent_stdlib=True,no_csv_access=True,freeze_commit=F,freeze_blob_sha256=sha(raw),freeze_runner_sha256=sha(raw.decode('utf8').strip().encode('utf8')),effective_configuration_sha256=sha(canonical(c)),source_commit=C,source_files=len(CLOSURE),counts=counts,refit_support_sha256=r['prior_support_sha256'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--freeze',required=True);p.add_argument('--effective',required=True);args=p.parse_args()
    print(json.dumps(audit(args.freeze,args.effective),sort_keys=True))
