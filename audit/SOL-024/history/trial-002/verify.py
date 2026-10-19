"""SOL-024 independent metadata/scalar review. No project imports or CSV reads.
Create once without arguments; --check recomputes without writes, including bytecode.
Scratch evidence can be checked with --evidence-dir; sources always use pinned Git.
"""
import argparse
import ast
import datetime as dt
from fractions import Fraction as F
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BASE = '6c1997c0ac20430af0b7e11d9fb0b29ab8506a11'
PUBLICATION = 'cf0fec40a27fb603d8b36bde2d7b77d84f4541a0'
TASK_BLOB = '5323d75883ef842689dde661f9fe8284671fce7d42e2277f02bba1fb5c2c3dd4'
TASK_DIGEST = '3150dc39fdb242ea3f4dc8256fc009d2dcd1060861276fabd3265a6639c23a77'
ARTIFACTS = ('task-lock.json', 'review.md', 'findings.json', 'verify.py', 'execution_history.json')
DERIVED_FLOAT_PATHS = {
    ('references', 'ordinary', 'cagr_pct'),
    ('references', 'ordinary', 'sample_std_pct'),
    ('references', 'ordinary', 'p10_marginal_difference'),
    ('references', 'ordinary', 'p10_paired_difference'),
}

def require(ok, message):
    if not ok:
        raise ValueError(message)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def canonical(raw):
    return raw.replace(b'\r\n', b'\n')

def packed(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('utf-8')

def blob(commit, path):
    require(len(commit) == 40 and all(c in '0123456789abcdef' for c in commit), 'unpinned source commit')
    require(not path.endswith('.csv') and not path.startswith('src/'), 'forbidden evidence read')
    proc = subprocess.run(['git', 'show', commit + ':' + path], cwd=ROOT,
                          capture_output=True, check=True)
    proc.stdout.decode('utf-8', errors='strict')
    return proc.stdout

def quantile(values, p):
    ordered = sorted(map(F, values))
    position = (len(ordered)-1) * F(p)
    lo = position.numerator // position.denominator
    hi = min(lo+1, len(ordered)-1)
    return ordered[lo] + (position-lo) * (ordered[hi]-ordered[lo])

def drawdown(events):
    peak = events[0][2]
    peak_at = events[0][:2]
    selected_peak = selected_trough = peak_at
    worst = 0.0
    for year, kind, wealth in events:
        require(math.isfinite(wealth) and wealth > 0, 'invalid scalar wealth')
        if wealth > peak:
            peak, peak_at = wealth, (year, kind)
        loss = 1.0 - wealth/peak
        if loss > worst:
            worst, selected_peak, selected_trough = loss, peak_at, (year, kind)
    return {'loss': worst, 'peak': list(selected_peak), 'trough': list(selected_trough)}

def severe(items):
    return min(items, key=lambda item: (-item[1], item[0]))[0]

def reference_checks(config, v2, personal, texts):
    fees = [0.0025, 0.005]
    horizons = [5, 6, 15, 25, 30]
    modes = ['bills_keep', 'equal_weight_annual', 'equal_weight_buy_hold',
             'conservative_cost', 'balanced_cost', 'growth_cost',
             'balanced_context', 'balanced_adaptive']
    profiles = {'A': (5,10,'high'), 'B': (15,25,'medium'), 'C': (30,40,'low'),
                'D': (25,15,'medium'), 'E': (6,35,'high')}
    require(config['modes'] == v2['modes'] == modes, 'changed generic menu')
    require(config['fee_rates'] == v2['fee_rates'] == personal['fee_rates'] == fees, 'changed fees')
    require(config['horizons'] == v2['horizons'] == horizons, 'changed horizons')
    require(config['profiles'] == v2['profiles'] == personal['profiles'], 'profile disagreement')
    require(config['profiles'] == {p:dict(horizon=h,loss_tolerance_pct=t,liquidity=l)
                                 for p,(h,t,l) in profiles.items()}, 'changed profile boundary')
    require(config['development_ids'] == [1,120] and config['final_ids'] == [121,180], 'split boundary')
    require(config['execution_authorized'] is False and config['final_data_open'] is False, 'proposal authorizes execution')
    require(v2['final_outcomes_allowed'] is False and personal['final_data_open'] is False, 'old gate relaxed')
    require(config['comparison_horizon'] == 30 and config['max_task_seconds'] == 1800, 'runtime or H change')
    require(config['max_artifact_bytes'] == 10485760, 'size limit change')
    require(config['refit'] == {'training_scenarios':120,'training_rows':3600,
        'weighting':'equal annual rows; one prior shared across all cases and fees',
        'final_rows_allowed':False}, 'refit change')
    require(v2['folds']['training_rows'] == 2700 and v2['history_window'] == 5
            and v2['prior_equivalent_years'] == 15, 'OOF/context reference change')
    case_keys = list(itertools.product(modes, fees))
    path_keys = [(m,k,s) for m,k in case_keys for s in range(121,181)]
    ledger_keys = [(m,k,s,t) for m,k,s in path_keys for t in range(1,31)]
    metric_keys = [(m,k,s,h) for m,k,s in path_keys for h in horizons]
    contrasts = [(m,'equal_weight_annual') for m in modes if m!='equal_weight_annual'] + [
        ('balanced_context','balanced_cost'),('balanced_adaptive','balanced_context'),
        ('balanced_adaptive','balanced_cost')]
    comparison_keys = [(a,b,k,h) for a,b in contrasts for k in fees for h in horizons]
    paired_keys = [(a,b,k,h,s) for a,b,k,h in comparison_keys for s in range(121,181)]
    for name,keys in [('ledger',ledger_keys),('metrics',metric_keys),('paired',paired_keys)]:
        require(len(keys)==len(set(keys)), 'duplicate generated '+name+' key')
    counts = dict(cases=len(case_keys),scenarios_per_case=60,scenario_paths=len(path_keys),
                  annual_ledger_rows=len(ledger_keys),scenario_horizon_metrics=len(metric_keys),
                  comparison_summaries=len(comparison_keys),paired_rows=len(paired_keys))
    require(counts==config['generic_counts'], 'generic contract counts wrong')
    prefix_counts = {str(h):sum(1 for *_,t in ledger_keys if t<=h) for h in horizons}
    require(prefix_counts=={'5':4800,'6':5760,'15':14400,'25':24000,'30':28800}, 'prefix count')
    # Generated keys only; no outcome values or calibration helpers.
    training_keys = [(s,t) for s in range(1,121) for t in range(1,31)]
    require(len(training_keys)==3600 and set(s for s,_ in training_keys)==set(range(1,121)), 'refit keys')
    oof = [sum((s-1)%4!=f for s,t in training_keys) for f in range(4)]
    require(oof==[2700]*4, 'old OOF membership changed')
    windows = {}
    for s in (121,180):
        for t in (1,2,5,6,30):
            window=[(s,y) for y in range(max(1,t-5),t)]
            require(len(window)==min(5,t-1) and all(a==s and b<t for a,b in window), 'prefix leak')
            windows[str((s,t))]=window
    all_profile_keys=list(itertools.product(profiles,fees))
    def personalized(eligible):
        rows=[]
        for p,k in all_profile_keys:
            h,tol,_=profiles[p]
            executed=(p,k) in eligible
            rows.append({'profile':p,'fee':k,'horizon':h,'scenario_count':60 if executed else 0,
                'denominator':60 if executed else 0,'selected_class':'conservative' if executed else None,
                'mode':'conservative_cost' if executed else None,
                'source_case':f'synthetic/{p}/{k}' if executed else None,
                'risk_pass':True if executed else None,'power_pass':True if executed else None,
                'p90_loss':0 if executed else None,'p10_growth':0 if executed else None,
                'exceedance_count':0 if executed else None,'exceedance_fraction':0 if executed else None,
                'simulation_status':'executed' if executed else 'not_run_upstream_referral'})
        n=len(eligible)
        return {'summary_rows':len(rows),'executed_cases':n,'metrics':60*n,
                'ledger_rows':60*sum(profiles[p][0] for p,k in eligible), 'rows':rows}
    all_assigned=personalized(set(all_profile_keys))
    none_assigned=personalized(set())
    partial=personalized({('A',fees[0]),('B',fees[1]),('D',fees[0])})
    require((all_assigned['ledger_rows'],all_assigned['metrics'])==(9720,600), 'personal H sum wrong')
    require((partial['ledger_rows'],partial['metrics'])==(2700,180), 'partial personalized count wrong')
    require(none_assigned['ledger_rows']==none_assigned['metrics']==0, 'referral has simulation')
    require(all(x['summary_rows']==10 for x in (all_assigned,none_assigned,partial)), 'root row disappearance')
    require(config['personalized_counts']['upstream_referral_scenario_count']==0, 'referral count change')
    # 55 observations at the tolerance, five beyond: passing p90 still has exceedances.
    losses=[F(10)]*55+[F(20)]*5
    p90=quantile(losses,F(9,10))
    exceed=sum(x>10 for x in losses)
    require(p90==10 and exceed==5 and F(exceed,60)==F(1,12), 'risk/strict denominator fixture')
    screens=[]
    for loss,growth in [(F(10),F(0)),(F(11),F(0)),(F(10),F(-1)),(F(11),F(-1))]:
        risk,power=loss<=10,growth>=0
        screens.append({'p90':str(loss),'p10':str(growth),'risk_pass':risk,'power_pass':power,
            'status':'frozen_rule_supported_on_final_sample' if risk and power else 'final_validation_failed_human_review',
            'recommended_class':'conservative' if risk and power else None,
            'proposed_class':'conservative','replacement_search':False})
    require([r['risk_pass'] and r['power_pass'] for r in screens]==[True,False,False,False], 'screen conjunction')
    events=[(0,'initial',100.0),(1,'post_fee',99.75),(1,'end',100.0),
        (2,'post_fee',100.0),(2,'end',75.0),(3,'post_fee',75.0),
        (3,'end',100.0),(4,'post_fee',100.0),(4,'end',75.0)]
    dd=drawdown(events)
    require(dd=={'loss':0.25,'peak':[0,'initial'],'trough':[2,'end']}, 'earliest severe location')
    fee_dd=drawdown([(0,'initial',100.0),(1,'post_fee',99.75),(1,'end',110.0)])
    require(fee_dd['trough']==[1,'post_fee'] and fee_dd['loss']>0, 'post fee loss omitted')
    zero=drawdown([(0,'initial',100.0),(1,'post_fee',100.0),(1,'end',101.0)])
    require(zero=={'loss':0.0,'peak':[0,'initial'],'trough':[0,'initial']}, 'zero sentinel')
    exact=severe([(122,0.25),(121,0.25)])
    near=severe([(121,0.25),(122,math.nextafter(0.25,math.inf))])
    require(exact==121 and near==122, 'epsilon severe tie contamination')
    later=drawdown(events+[(5,'post_fee',100.0),(5,'end',math.nextafter(75.0,0.0))])
    require(later['trough']==[5,'end'] and later['loss']>0.25, 'strict location improvement lost')
    own_id=severe([(121,0.3),(122,0.1)])
    baseline_id=severe([(121,0.2),(122,0.4)])
    require(own_id==121 and baseline_id==122, 'baseline severe distinction')
    # Ordinary derived checks use independent rational identities and relative tolerances.
    real_terminal=F(121,1)
    cagr=100*(float(real_terminal/100)**(1/2)-1)
    annual=[F(10),F(-5),F(5)]
    mean=sum(annual)/3
    variance=sum((x-mean)**2 for x in annual)/2
    std=statistics.stdev(map(float,annual))
    require(math.isclose(cagr,10,rel_tol=1e-10,abs_tol=1e-9), 'CAGR arithmetic')
    require(math.isclose(std*std,float(variance),rel_tol=1e-10,abs_tol=1e-9), 'ddof arithmetic')
    a=[0,10,11,12]; b=[9,0,10,13]; paired=[F(x)-y for x,y in zip(a,b)]
    marginal=quantile(a,F(1,10))-quantile(b,F(1,10))
    paired_tail=quantile(paired,F(1,10))
    require(marginal==F(3,10) and paired_tail==F(-33,5), 'paired versus marginal confusion')
    # Deliberately fake freeze texts remain in memory only. Not gate artifacts.
    fake='{"z": 1, "a": 2}'
    runner=lambda value:sha(value.strip().encode('utf-8'))
    sorted_text=json.dumps(json.loads(fake),sort_keys=True,separators=(',',':'))
    variants={'base':fake,'outer':' \n\t'+fake+'\r\n ',
        'internal':'{"z":  1, "a": 2}','reordered':sorted_text,
        'semantic':'{"z": 1, "a": 3}','crlf_internal':'{\r\n"z": 1, "a": 2\r\n}',
        'lf_internal':'{\n"z": 1, "a": 2\n}', 'bom':'\ufeff'+fake}
    hashes={k:{'runner':runner(v),'blob':sha(v.encode('utf-8'))} for k,v in variants.items()}
    require(hashes['base']['runner']==hashes['outer']['runner']
            and hashes['base']['blob']!=hashes['outer']['blob'], 'outer whitespace hashing')
    for k in ['internal','reordered','semantic','bom']:
        require(hashes[k]['runner']!=hashes['base']['runner'], 'hash failed '+k)
    require(hashes['crlf_internal']['runner']!=hashes['lf_internal']['runner'], 'internal newline hashing')
    require(json.loads(fake)==json.loads(variants['internal'])==json.loads(sorted_text), 'semantic equivalence fixture')
    # Static AST inspection only. No execution or import of scripts/coop.py.
    tree=ast.parse(texts['scripts/coop.py'])
    git_fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='git')
    git_source=ast.get_source_segment(texts['scripts/coop.py'],git_fn)
    require("p.stdout.decode('utf-8',errors='replace').strip()" in git_source, 'runner decoding/strip changed')
    require('hashlib.sha256(frozen.encode()).hexdigest()' in texts['scripts/coop.py'], 'runner freeze digest changed')
    require('sort_keys=True' not in git_source, 'runner git text sorted unexpectedly')
    bindings=['accepted_source_commit_and_imported_hashes','effective_policy_and_numerical_parameters',
        'metrics_units_quantiles_reporting','severe_rule','fixed_case_contrast_inventory',
        'frozen_primary_choice_with_accepted_development_evidence',
        'ten_profile_fee_choices_referrals_with_accepted_rescreens','all_development_refit_artifact_hashes',
        'input_paths_hashes','commands_output_paths_shard_membership_counts_runtime',
        'independent_acceptance_commits','failure_and_disclosure_rule']
    require(config['freeze_required_bindings']==bindings, 'freeze bindings omitted')
    require(config['freeze_runner_digest']=='sha256(utf8(git_blob_text.strip()))', 'digest contract changed')
    require(config['final_fold_promotion']=='not_applicable; never reselect primary', 'final selection leak')
    # Fake predeclared case shards are disjoint. Reject duplicate and missing membership.
    shards=[set(case_keys[:8]),set(case_keys[8:])]
    require(not shards[0]&shards[1] and set.union(*shards)==set(case_keys), 'shard coverage')
    malformed=[set(case_keys[:9]),set(case_keys[8:])]
    require(bool(malformed[0]&malformed[1]), 'overlap fixture did not challenge')
    stages=['accepted_code_refit_config','complete_freeze','external_freeze_review','gate_and_later_task','final_execution']
    edges=list(zip(stages,stages[1:]))
    require(all(stages.index(a)<stages.index(b) for a,b in edges), 'publication cycle')
    # Source commit intentionally differs from later task base; computational hashes must agree.
    source_pin='1'*40; task_pin='2'*40
    require(source_pin!=task_pin and sha(b'fake computational bytes')==sha(b'fake computational bytes'), 'source/base fixture')
    correction={'parent_runner_digest':hashes['base']['runner'],'original_freeze_preserved':True,
        'new_source_commit':'3'*40,'changed_source_hash':sha(b'minimal fake bug patch'),
        'immutable_correction_task':True,'independent_review_required':True,
        'exposure_preserved':True,'partial_results_preserved':True,
        'policy_parameters_unchanged':True,'untouched_holdout_claim':False}
    final_text=texts['specs/FINAL_EVALUATION.md']
    for phrase in ['do not create a second model-selection opportunity','This is a new all-development calibration',
        'original freeze','strict improvement','upstream development referral','<=1800-second']:
        require(phrase in final_text, 'missing reviewed prose boundary: '+phrase)
    return {'generic_counts':counts,'generated_key_sha256':{'ledger':sha(packed(ledger_keys)),
        'metrics':sha(packed(metric_keys)),'paired':sha(packed(paired_keys))},
        'contrasts':contrasts,'generic_prefix_rows':prefix_counts,
        'refit':{'keys':len(training_keys),'key_sha256':sha(packed(training_keys)),
            'development_oof_rows_per_prior':oof,'context_windows':windows,
            'prior_mass_first':str(F(15,15)),'prior_mass_at_five':str(F(15,20)),
            'each_recent_mass_at_five':str(F(1,20))},
        'personalized':{'all':all_assigned,'none':none_assigned,'partial':partial,
            'ledger_equals_decisions':True,'max_target_score_rows':9720,
            'not_run_numeric_metrics_flags_source_null':True},
        'screens':{'cases':screens,'p90_boundary':str(p90),'strict_exceedances':exceed,
            'denominator':60,'fraction':str(F(exceed,60))},
        'severe':{'earliest':dd,'post_fee':fee_dd,'zero':zero,'strict_later':later,
            'exact_tie_id':exact,'near_tie_id':near,'own_severe_id':own_id,
            'baseline_same_path_id':own_id,'baseline_own_severe_id':baseline_id},
        'ordinary':{'cagr_pct':cagr,'sample_std_pct':std,'exact_sample_variance':str(variance),
            'median_paired_difference':str(statistics.median(paired)),
            'p10_marginal_difference':float(marginal),'p10_paired_difference':float(paired_tail)},
        'freeze_text_hashes':hashes,'freeze_bindings':bindings,
        'shards':{'sizes':list(map(len,shards)),'overlap_rejected':True,'fixed_before_access':True},
        'publication':{'stages':stages,'edges':edges,'source_task_base_can_differ':True,
            'freeze_review_is_external_not_self_hashed':True},
        'correction_requirements':correction}

def compute(evidence_dir):
    require(sys.version_info[:2]==(3,12), 'Python 3.12 required')
    lock=json.loads((evidence_dir/'task-lock.json').read_text(encoding='utf-8'))
    require(lock['base_commit']==BASE and lock['publication_commit']==PUBLICATION, 'task/base pin corrupt')
    raw_task=blob(PUBLICATION,'ops/tasks/SOL-024.json')
    require(sha(raw_task)==TASK_BLOB==lock['task_blob_sha256'], 'immutable task blob changed')
    task=json.loads(raw_task)
    require(sha(packed(task))==TASK_DIGEST==lock['task_digest_sha256'], 'task semantic digest mismatch')
    require(task['id']=='SOL-024' and task['attempt']==1 and task['owner']=='sol'
            and task['base_commit']==BASE and task['split']=='synthetic', 'wrong assigned task')
    require(task['allowed_paths']==lock['allowed_paths']==['audit/SOL-024'], 'wrong allowed paths')
    require(task['max_seconds']==900 and task['parameters']['required_python']=='3.12'
            and task['parameters']['cpu_only'] is True, 'wrong runtime boundary')
    require(task['parameters']['source_sha256']==lock['source_sha256'], 'source pins changed')
    texts={}; source_hashes={}
    for path,expected in task['parameters']['source_sha256'].items():
        raw=blob(BASE,path)
        require(sha(raw)==expected, 'pinned source mismatch: '+path)
        source_hashes[path]=sha(raw); texts[path]=raw.decode('utf-8')
    config=json.loads(texts['specs/final_evaluation_contract_v1.json'])
    v2=json.loads(texts['specs/development_policy_pilot_v2.json'])
    personal=json.loads(texts['specs/personalized_review_v1.json'])
    manifest=json.loads(texts['data/manifest.json'])
    metadata={x['path']:x['sha256'] for x in manifest['files']}
    require(all(metadata[p]==h for p,h in config['input_sha256'].items()), 'input metadata hash mismatch')
    previous=json.loads(texts['audit/chief/SOL-013-review.json'])
    accepted_personal=json.loads(texts['audit/chief/SOL-020-review.json'])
    previous_personal=json.loads(texts['audit/SOL-020/findings.json'])
    require(previous['corrected_design_verdict']=='approve' and previous['code_verdict']=='changes_required', 'historical negative verdict lost')
    require(accepted_personal['design_verdict']=='approve'
            and previous_personal['historical_kernel_verdict']=='changes_required', 'acceptance conflation')
    findings=json.loads((evidence_dir/'findings.json').read_text(encoding='utf-8'))
    require(findings['design_verdict']=='approve' and findings['implementation_verdict']=='not_reviewed'
            and findings['historical_kernel_verdict']=='changes_required'
            and findings['execution_authorized'] is False, 'review verdict corruption')
    return {'schema_version':1,'task_bindings':{'base_commit':BASE,'publication_commit':PUBLICATION,
        'task_blob_sha256':TASK_BLOB,'task_digest_sha256':TASK_DIGEST,
        'allowed_paths':['audit/SOL-024'],'python_major_minor':[3,12]},
        'source_sha256':source_hashes,
        'artifact_sha256':{name:sha(canonical((evidence_dir/name).read_bytes())) for name in ARTIFACTS},
        'references':reference_checks(config,v2,personal,texts),
        'design_verdict':'approve','implementation_verdict':'not_reviewed',
        'historical_kernel_verdict':'changes_required','execution_authorized':False,
        'competition_outcomes_read':False,'policy_helpers_executed':False}

def compare(saved, actual, path=()):
    if isinstance(actual, tuple):
        actual = list(actual)
    require(type(saved) is type(actual), 'evidence type mismatch: '+str(path))
    if isinstance(actual,dict):
        require(saved.keys()==actual.keys(), 'evidence keys mismatch: '+str(path))
        for k in actual: compare(saved[k],actual[k],path+(k,))
    elif isinstance(actual,list):
        require(len(saved)==len(actual), 'evidence list length mismatch: '+str(path))
        for i,(a,b) in enumerate(zip(saved,actual)): compare(a,b,path+(i,))
    elif path in DERIVED_FLOAT_PATHS:
        require(math.isfinite(saved) and math.isclose(saved,actual,abs_tol=1e-9,rel_tol=1e-10),
                'derived evidence mismatch: '+str(path))
    else:
        require(saved==actual, 'saved evidence differs from read-only recomputation: '+str(path))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--evidence-dir',type=Path,default=HERE)
    args=parser.parse_args()
    directory=args.evidence_dir.resolve()
    if args.check:
        original={p:p.read_bytes() for p in directory.rglob('*') if p.is_file()}
        document=json.loads((directory/'verification.json').read_text(encoding='utf-8'))
        require(document['schema_version']==1, 'verification schema')
        require(document['created_with_python'].startswith('3.12.'), 'unexecuted Python version')
        dt.datetime.fromisoformat(document['created_utc'])
        compare(document['evidence'],compute(directory))
        require(all(p.read_bytes()==raw for p,raw in original.items()), 'checker altered original evidence')
        print(json.dumps({'evidence_integrity_verdict':'verified','design_verdict':'approve',
            'implementation_verdict':'not_reviewed','historical_kernel_verdict':'changes_required',
            'read_only':True,'reference_groups':len(document['evidence']['references'])}))
    else:
        require(directory==HERE, 'creation allowed only in assigned audit directory')
        target=directory/'verification.json'
        require(not target.exists(), 'exclusive creation refuses existing verification')
        document={'schema_version':1,'created_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
                  'created_with_python':sys.version,'evidence':compute(directory)}
        with target.open('x',encoding='utf-8',newline='\n') as stream:
            json.dump(document,stream,ensure_ascii=False,indent=2,allow_nan=False)
            stream.write('\n')
        print(json.dumps({'created_exclusively':True,'reference_groups':len(document['evidence']['references'])}))

if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        print(type(exc).__name__+': '+str(exc),file=sys.stderr)
        raise SystemExit(1)
