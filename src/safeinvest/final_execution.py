"""Authenticated fixed refit/final persistence; inert on import, CPU only.

No production call opens final observations until immutable source, published
task/config, accepted development evidence, refit, freeze and gate checks pass.
Generated tests enter only private explicit-row arithmetic seams.
"""

import argparse
import csv
from dataclasses import asdict
import io
import math
from pathlib import Path
import platform
import sys
import time

from . import policy_writer as w
from .backtest import _simulate_policy_arithmetic, TRADE_THRESHOLD
from .baselines import POLICIES
from .experiments import COMMON_UNITS, drawdown_locations, ledger_row, summary_row
from .final_paths import _OutcomeRow, _outcomes, prior_support_digest
from .final_refit import build_generated_refit
from .metrics import _compute_metrics_arithmetic, linear_quantile
from .policy_calibration import FIELDS
from .policy_cases import _diagnostics
from .policy_pilot import CENTRAL_TARGET, CostAwarePolicy, EmpiricalPrior

DEV_PATH=w.INPUT_PATH
DEV_HASH=w.INPUT_HASH
FINAL_PATH='data/final_holdout/scenarios_121_180.csv'
FINAL_HASH='3270445e7864abf2e88c56e4012d7f582eae3b5e30c40ade1a4c9ef2b54bbf29'
MODES=('bills_keep','equal_weight_annual','equal_weight_buy_hold',*CENTRAL_TARGET)
FEES=(.0025,.005)
HORIZONS=(5,6,15,25,30)
PROFILES={'A':(5,10),'B':(15,25),'C':(30,40),'D':(25,15),'E':(6,35)}
CONTRASTS=tuple((m,'equal_weight_annual') for m in MODES if m!='equal_weight_annual')+(
    ('balanced_context','balanced_cost'),('balanced_adaptive','balanced_context'),
    ('balanced_adaptive','balanced_cost'))
CLOSURE=tuple(dict.fromkeys((*w.CLOSURE,
    'src/safeinvest/final_refit.py','src/safeinvest/final_paths.py',
    'src/safeinvest/final_execution.py','scripts/run_final_evaluation.py',
    'specs/FINAL_EVALUATION.md','specs/FINAL_OUTPUT_NOTES.md',
    'specs/final_evaluation_contract_v1.json')))
CONFIG_KEYS=('schema_version','run_id','stage','source_commit','source_sha256',
             'source_review','development_review','primary_mode','profile_choices',
             'refit','freeze','freeze_attestation','execution')


def _reference(root,reference):
    w.keys(reference,('commit','path','sha256'))
    w.hash_string(reference['commit'],40);w.hash_string(reference['sha256'])
    w.safe_path(root,reference['path'])
    raw=w.blob(root,reference['commit'],reference['path'])
    w.require(w.sha(raw)==reference['sha256'],'referenced Git artifact hash mismatch')
    return raw


def validate_choices(choices):
    w.require(type(choices) is list and len(choices)==10,'all ten frozen profile/fee rows required')
    expected=[(p,k) for p in PROFILES for k in FEES]
    for row,key in zip(choices,expected):
        w.keys(row,('profile_id','fee_rate','proposed_class','eligible','reason'))
        w.require((row['profile_id'],row['fee_rate'])==key and type(row['fee_rate']) is float,
                  'profile/fee order or type mismatch')
        w.require(type(row['eligible']) is bool and type(row['reason']) is str and row['reason'],
                  'explicit eligibility and reason required')
        w.require(row['proposed_class'] in (None,'conservative','balanced','growth'),
                  'invalid frozen proposed class')
        w.require(not row['eligible'] or row['proposed_class'] is not None,
                  'eligible rule must have a fixed class; preserve historical referral proposal')
    return choices


def validate_config(c):
    w.keys(c,CONFIG_KEYS)
    w.require(c['schema_version']==1 and type(c['schema_version']) is int,'schema version')
    w.require(c['stage'] in ('refit','final'),'explicit refit/final stage required')
    w.require(type(c['run_id']) is str and c['run_id'] and '/' not in c['run_id'],'invalid run ID')
    w.hash_string(c['source_commit'],40)
    w.require(type(c['source_sha256']) is dict and set(c['source_sha256'])==set(CLOSURE),
              'exact final source closure required')
    for value in c['source_sha256'].values(): w.hash_string(value)
    w.require(c['primary_mode'] in ('balanced_cost','balanced_context','balanced_adaptive'),
              'frozen accepted Balanced primary required')
    validate_choices(c['profile_choices'])
    w.keys(c['execution'],('cpu_only','required_python','max_seconds','max_artifact_bytes','output'))
    e=c['execution'];w.require(e['cpu_only'] is True and e['required_python']=='3.12','Python3.12 CPU only')
    w.integer(e['max_seconds'],1,1800);w.integer(e['max_artifact_bytes'],w.LIMIT,w.LIMIT)
    if c['stage']=='refit':
        w.require(c['refit'] is None and c['freeze'] is None and c['freeze_attestation'] is None,
                  'refit precedes final freeze')
    else:
        w.require(all(type(c[key]) is dict for key in ('refit','freeze','freeze_attestation')),
                  'accepted refit and external freeze review required')
    return c


def authenticate(root,config_path,output,task,publication):
    """Complete source/config/task/development checks without reading input CSV."""
    root=Path(root).resolve()
    raw=w.safe_path(root,config_path).read_bytes();c=validate_config(w.strict_json(raw))
    binding=_published_task(root,task,publication)
    w.require(task.get('split')==('final' if c['stage']=='final' else 'development'),
              'task split mismatch')
    w.integer(task['max_seconds'],1,1800)
    w.require(c['execution']['max_seconds']<=task['max_seconds'],'task budget mismatch')
    w.require(c['execution']['output']==output,'fixed output mismatch')
    params=task.get('parameters',{})
    w.require(params.get('config_path')==config_path and params.get('config_sha256')==w.sha(w.canonical(c))
              and params.get('output_path')==output and params.get('execution_stage')==c['stage'],
              'task/config/output binding mismatch')
    command=['{python}','-B','scripts/run_final_evaluation.py','--config',config_path,'--output',output]
    w.require(task.get('commands',[]).count(command)==1 and command+['--check'] in task['commands'],
              'one fixed producer followed by saved check required')
    w.require(task['commands'].index(command)<task['commands'].index(command+['--check']),
              'saved check must follow producer')
    canonical_config=w.blob(root,task['base_commit'],config_path)
    w.require(w.exact(w.strict_json(canonical_config),c),'config differs from immutable task base')
    w.ancestor(root,c['source_commit'],task['base_commit'])
    sources=w.source_snapshot(root,c)
    source_review=w.strict_json(_reference(root,c['source_review']))
    w.require(source_review.get('status')=='accepted'
              and source_review.get('source_commit')==c['source_commit']
              and w.exact(source_review.get('source_sha256'),c['source_sha256']),
              'exact new source acceptance required')
    w.ancestor(root,c['source_commit'],c['source_review']['commit'])
    w.ancestor(root,c['source_review']['commit'],task['base_commit'])
    development=w.strict_json(_reference(root,c['development_review']))
    w.ancestor(root,c['development_review']['commit'],task['base_commit'])
    w.require(development.get('status')=='accepted'
              and development.get('primary_mode')==c['primary_mode']
              and w.exact(development.get('profile_choices'),c['profile_choices'])
              and development.get('all_ten_rescreens_accepted') is True,
              'accepted generic selection and all ten own-horizon rescreens required')
    evidence=development.get('evidence')
    w.require(type(evidence) is list and len(evidence)>=2,'actual accepted result references required')
    for reference in evidence: _reference(root,reference)
    control=w.strict_json(w.safe_path(root,'ops/control.json').read_bytes())
    w.require(control.get('state')=='running' and not (root/'.runtime/STOP').exists(),
              'local/global stop prevents new execution')
    if c['stage']=='refit':
        w.require(control.get('final_data_open') is False,'actual refit must precede final gate opening')
    w.require(output in task['allowed_paths'] or any(output.startswith(p.rstrip('/')+'/') for p in task['allowed_paths']),
              'output outside task scope')
    return c,dict(binding=binding,sources=sources,configuration_sha256=w.sha(w.canonical(c)))


def _published_task(root,task,publication):
    """Same immutable publication guard for honest chief or HY3 ownership."""
    owner=task.get('owner')
    w.require(owner in ('chief','hy3') and task.get('kind')=='commands','fixed chief/HY3 commands only')
    w.require(type(task.get('id')) is str and task['id'] and
              all(ch.isalnum() or ch in '_-' for ch in task['id']),'safe task ID required')
    w.hash_string(task['base_commit'],40);w.integer(task['attempt'],1)
    w.ancestor(root,task['base_commit'],publication)
    origin=w.git(root,'rev-parse','origin/main').decode().strip();w.ancestor(root,publication,origin)
    raw=w.blob(root,publication,'ops/tasks/'+task['id']+'.json')
    w.require(w.exact(w.strict_json(raw),task),'runtime/published task mismatch')
    queue=w.strict_json(w.blob(root,publication,'ops/queue.json'))
    matches=[row for row in queue['tasks'] if row['id']==task['id']]
    w.require(len(matches)==1,'single published queue entry required')
    row=matches[0];digest=w.sha(w.canonical(task))
    w.require(row['state']=='ready' and row['owner']==owner and row['task_sha256']==digest
              and w.exact(row['attempt'],task['attempt'])
              and row['branch']=='work/'+owner+'/'+task['id']+'-a'+str(task['attempt']),
              'published queue ownership/digest/branch mismatch')
    return {'publication_commit':publication,'task_blob_sha256':w.sha(raw),'task_digest':digest,
            'task_id':task['id'],'attempt':task['attempt'],'base_commit':task['base_commit'],
            'owner':owner,'kind':'commands'}


def _read_fixed(root,path,expected,exposure):
    target=w.safe_path(root,path)
    exposure.append({'event':'input_open_attempt','path':path})
    raw=target.read_bytes()
    exposure.append({'event':'input_read','path':path,'sha256':w.sha(raw),'bytes':len(raw)})
    w.require(w.sha(raw)==expected,'locked original input bytes mismatch')
    return raw


def _parse_final(raw,ids=tuple(range(121,181))):
    reader=csv.DictReader(io.StringIO(raw.decode('utf-8',errors='strict'),newline=''))
    w.require(tuple(reader.fieldnames or ())==FIELDS,'exact final CSV schema required')
    rows=tuple(reader)
    w.require(len(rows)==30*len(ids),'complete final shape required')
    for index,row in enumerate(rows):
        s,t=divmod(index,30)
        w.require(tuple(row)==FIELDS and row['scenario_id']==str(ids[s]) and row['period']==str(t+1),
                  'complete ordered final IDs/periods required')
        _outcomes(row)
    return rows


def _refit_manifest(refit):
    # The pure component contains no authenticated-origin claim. Production
    # provenance is a new record, never an edited generated-only manifest.
    return {'schema_version':1,'calibration_kind':'all_development_refit',
            'split':'development','input_origin':DEV_PATH,'source_verified':True,
            'input_sha256':refit.input_sha256,'input_bytes':refit.input_bytes,
            'training_scenario_ids':list(range(1,121)),
            'training_row_keys':[list(key) for key in refit.training_keys],
            'training_row_count':len(refit.training_keys),'annual_weight':'1 / 3600',
            'training_rows_sha256':refit.training_rows_sha256,
            'real_gross_sha256':refit.real_gross_sha256,
            'prior_support_sha256':prior_support_digest(refit.prior),
            'gross':refit.prior.gross,'asset_order':list(FIELDS[2:5]),
            'fold_id':None,'fold_status':'not_applicable'}


def _load_refit(root,c):
    artifact=w.strict_json(_reference(root,c['refit']))
    w.require(artifact.get('status')=='completed_refit' and artifact.get('source_verified') is True,
              'completed authenticated refit required')
    old=validate_config(artifact['configuration'])
    w.require(old['stage']=='refit' and old['source_commit']==c['source_commit']
              and w.exact(old['source_sha256'],c['source_sha256'])
              and w.exact(old['profile_choices'],c['profile_choices'])
              and old['primary_mode']==c['primary_mode'], 'refit source/development choices mismatch')
    refit=artifact['refit']
    expected_keys=[[s,t] for s in range(1,121) for t in range(1,31)]
    w.require(refit.get('input_sha256')==DEV_HASH and refit.get('training_row_count')==3600
              and refit.get('training_row_keys')==expected_keys
              and refit.get('training_scenario_ids')==list(range(1,121)),
              'actual complete all-development refit required')
    prior=EmpiricalPrior(refit['gross'])
    w.require(len(prior.gross)==3600 and prior_support_digest(prior)==refit['prior_support_sha256'],
              'refit actual support mismatch')
    gross_payload={'schema':'training-real-gross-v1','asset_order':list(FIELDS[2:5]),
                   'rows':[[*key,*(v.hex() for v in gross)]
                           for key,gross in zip(expected_keys,prior.gross)]}
    w.require(w.sha(w.canonical(gross_payload))==refit['real_gross_sha256'],
              'refit canonical key/gross support digest mismatch')
    # Actual artifact must have been independently accepted, not just supplied.
    review_ref=artifact.get('external_acceptance')
    w.require(review_ref is None,'refit acceptance is external, never self-referential')
    return prior,artifact


def _final_gate(root,c,task,config_digest):
    w.require(c['freeze']['path']=='ops/freeze.json','fixed published freeze path required')
    raw=_reference(root,c['freeze']);freeze=w.strict_json(raw)
    base=task['base_commit']
    w.require(w.blob(root,base,'ops/freeze.json')==raw,'freeze differs from immutable task-base bytes')
    for reference in (c['refit'],c['freeze'],c['freeze_attestation']):
        w.ancestor(root,reference['commit'],base)
    runner_hash=w.sha(raw.decode('utf-8',errors='strict').strip().encode('utf-8'))
    w.require(task.get('freeze_sha256')==runner_hash,'runner freeze text digest mismatch')
    attestation=w.strict_json(_reference(root,c['freeze_attestation']))
    w.require(attestation.get('status')=='accepted'
              and attestation.get('freeze_blob_sha256')==w.sha(raw)
              and attestation.get('freeze_runner_sha256')==runner_hash
              and w.exact(attestation.get('refit'),c['refit']),
              'external exact-byte freeze/refit acceptance required')
    w.ancestor(root,attestation['refit_acceptance']['commit'],base)
    refit_review=w.strict_json(_reference(root,attestation['refit_acceptance']))
    w.require(refit_review.get('status')=='accepted' and w.exact(refit_review.get('refit'),c['refit']),
              'external exact-artifact refit acceptance required')
    w.require(c['freeze_attestation']['commit']!=c['freeze']['commit'],'freeze review must be external later commit')
    w.ancestor(root,c['freeze']['commit'],c['freeze_attestation']['commit'])
    # Config's freeze reference creates a cycle if the freeze stores the entire
    # config digest. Bind its immutable effective execution payload instead.
    effective={k:v for k,v in c.items() if k not in ('freeze','freeze_attestation')}
    w.require(freeze.get('source_commit')==c['source_commit']
              and w.exact(freeze.get('source_sha256'),c['source_sha256'])
              and freeze.get('effective_configuration_sha256')==w.sha(w.canonical(effective))
              and freeze.get('primary_mode')==c['primary_mode']
              and w.exact(freeze.get('profile_choices'),c['profile_choices'])
              and w.exact(freeze.get('refit'),c['refit'])
              and freeze.get('input_path')==FINAL_PATH and freeze.get('input_sha256')==FINAL_HASH,
              'freeze effective configuration/source/input binding mismatch')
    control=w.strict_json(w.safe_path(root,'ops/control.json').read_bytes())
    w.require(control.get('state')=='running' and control.get('final_data_open') is True,
              'recorded final data gate closed')
    return {'freeze_blob_sha256':w.sha(raw),'freeze_runner_sha256':runner_hash,
            'configuration_sha256':config_digest}


def _path(rows,mode,prior,horizon,fee,threshold):
    policy=CostAwarePolicy(mode,prior,fee_rate=fee,review_drawdown_pct=threshold) if mode in CENTRAL_TARGET else None
    result=_simulate_policy_arithmetic(tuple(_OutcomeRow(row) for row in rows),horizon=horizon,
             split='final',callback=policy if policy is not None else POLICIES[mode],fee_rate=fee)
    return result,tuple(policy.reviews) if policy is not None else ()


def _metric(result,reviews,mode,fee,horizon):
    ledger=result.ledger[:horizon]
    m=_compute_metrics_arithmetic((e.real_wealth_end for e in ledger),
         (e.real_wealth_after_fee for e in ledger),split='final')
    trades=[e.intended_transfer>TRADE_THRESHOLD for e in ledger]
    return {**asdict(m),'mode':mode,'policy':mode,'fee_rate':fee,'scenario_id':result.scenario_id,
            'terminal_real_wealth':ledger[-1].real_wealth_end,'nominal_fee_sum':math.fsum(e.fee for e in ledger),
            'trade_count':sum(trades),'review_count':horizon,'later_trade_count':sum(trades[1:]),
            'later_review_count':horizon-1,'trade_share_pct':100*sum(trades)/horizon,
            'trade_share_ex_initial_pct':100*sum(trades[1:])/(horizon-1) if horizon>1 else None,
            **drawdown_locations(ledger),**_diagnostics(reviews,horizon),
            'fold_id':None,'fold_status':'not_applicable',**COMMON_UNITS,'growth_units':'percent/year'}


def _evaluate_rows(rows,prior,primary_mode,choices,ids=tuple(range(121,181))):
    """Pure explicit-row calculation; no file access or source authentication."""
    validate_choices(choices)
    generic={};all_metrics=[];summaries=[];paired=[];comparisons=[]
    for fee in FEES:
        for mode in MODES:
            paths=[];metrics=[]
            for index,scenario in enumerate(ids):
                result,reviews=_path(rows[index*30:(index+1)*30],mode,prior,30,fee,25)
                w.require(result.scenario_id==scenario,'scenario path identity')
                paths.append((result,reviews))
                metrics.extend(_metric(result,reviews,mode,fee,h) for h in HORIZONS)
            case_summaries=[summary_row(mode,h,[r for r in metrics if r['horizon']==h])|
                            {'fee_rate':fee,'mode':mode,'fold_status':'not_applicable','growth_units':'percent/year'} for h in HORIZONS]
            generic[(mode,fee)]={'paths':paths,'metrics':metrics,'summary':case_summaries}
            all_metrics.extend(metrics);summaries.extend(case_summaries)
        for h in HORIZONS:
            for alternative,reference in CONTRASTS:
                a=[r for r in generic[(alternative,fee)]['metrics'] if r['horizon']==h]
                b=[r for r in generic[(reference,fee)]['metrics'] if r['horizon']==h]
                delta=[x['net_real_cagr_pct']-y['net_real_cagr_pct'] for x,y in zip(a,b)]
                paired.extend({'split':'final','fee_rate':fee,'horizon':h,'scenario_id':x['scenario_id'],
                               'alternative_mode':alternative,'reference_mode':reference,
                               'growth_difference_pct':d,
                               'loss_difference_pct':x['max_real_drawdown_pct']-y['max_real_drawdown_pct'],
                               'trade_share_difference_pct':x['trade_share_pct']-y['trade_share_pct'],
                               'trade_share_ex_initial_difference_pct':x['trade_share_ex_initial_pct']-y['trade_share_ex_initial_pct'],
                               'terminal_real_wealth_difference':x['terminal_real_wealth']-y['terminal_real_wealth'],
                               'nominal_fee_difference':x['nominal_fee_sum']-y['nominal_fee_sum'],
                               'growth_difference_units':'percentage points/year',
                               'loss_difference_units':'percentage points; positive is worse',
                               'fee_difference_units':'nominal wealth units'}
                              for x,y,d in zip(a,b,delta))
                comparisons.append({'split':'final','fee_rate':fee,'horizon':h,'alternative_mode':alternative,
                    'reference_mode':reference,'paired_median_growth_difference_pct':linear_quantile(delta,.5),
                    'marginal_p10_growth_difference_pct':linear_quantile((r['net_real_cagr_pct'] for r in a),.1)-linear_quantile((r['net_real_cagr_pct'] for r in b),.1),
                    'marginal_p90_loss_difference_pct':linear_quantile((r['max_real_drawdown_pct'] for r in a),.9)-linear_quantile((r['max_real_drawdown_pct'] for r in b),.9),
                    'fold_support':None,'fold_status':'not_applicable','promotion':None,
                    'promotion_status':'not_applicable','frozen_primary_mode':primary_mode})
    personalized=[];personal_cases={}
    for choice in choices:
        profile,fee=choice['profile_id'],choice['fee_rate'];h,tolerance=PROFILES[profile]
        base={'split':'final',**choice,'horizon':h,'loss_tolerance_pct':tolerance}
        if not choice['eligible']:
            personalized.append(base|{'status':'development_referral','scenario_count':0,'denominator':0,
                'recommended_class':None,'p90_loss_pct':None,'p10_growth_pct':None,'exceedance_count':None,
                'exceedance_fraction':None,'risk_pass':None,'purchasing_power_pass':None,
                'median_loss_pct':None,'severe_loss_pct':None,'trade_share_pct':None,
                'trade_share_ex_initial_pct':None,'severe_scenario_id':None,'case_path':None})
            continue
        mode=choice['proposed_class']+'_cost';paths=[];metrics=[]
        for index,scenario in enumerate(ids):
            result,reviews=_path(rows[index*30:(index+1)*30],mode,prior,h,fee,tolerance)
            paths.append((result,reviews));metrics.append(_metric(result,reviews,mode,fee,h))
        loss=linear_quantile((r['max_real_drawdown_pct'] for r in metrics),.9)
        growth=linear_quantile((r['net_real_cagr_pct'] for r in metrics),.1)
        count=sum(r['max_real_drawdown_pct']>tolerance for r in metrics)
        risk,power=loss<=tolerance,growth>=0
        severe=min(metrics,key=lambda row:(-row['max_real_drawdown_pct'],row['scenario_id']))
        label='personalized/'+profile+'/'+str(fee)
        personal_cases[(profile,fee)]={'paths':paths,'metrics':metrics}
        personalized.append(base|{'status':'frozen_rule_supported_on_final_sample' if risk and power else 'final_validation_failed_human_review',
            'scenario_count':len(ids),'denominator':len(ids),'recommended_class':choice['proposed_class'] if risk and power else None,
            'p90_loss_pct':loss,'p10_growth_pct':growth,'exceedance_count':count,'exceedance_fraction':count/len(ids),
            'risk_pass':risk,'purchasing_power_pass':power,
            'median_loss_pct':linear_quantile((r['max_real_drawdown_pct'] for r in metrics),.5),
            'severe_loss_pct':max(r['max_real_drawdown_pct'] for r in metrics),
            'severe_scenario_id':severe['scenario_id'],
            'trade_share_pct':sum(r['trade_count'] for r in metrics)*100/(len(ids)*h),
            'trade_share_ex_initial_pct':sum(r['later_trade_count'] for r in metrics)*100/(len(ids)*(h-1)),
            'case_path':label})
    return dict(generic=generic,scenario_metrics=all_metrics,summary=summaries,
                paired_differences=paired,comparisons=comparisons,personalized=personalized,
                personal_cases=personal_cases)


def _csv(rows):
    w.require(bool(rows),'CSV requires an explicit nonempty table')
    output=io.StringIO(newline='');writer=csv.DictWriter(output,fieldnames=list(rows[0]),lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({k:('' if v is None else w.canonical(v).decode() if isinstance(v,(dict,list,tuple)) else v)
                         for k,v in row.items()})
    return output.getvalue().encode()


def _write(stage,name,raw,inventory):
    w.require(len(raw)<=w.LIMIT,'artifact exceeds10MiB')
    target=stage/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    inventory[name]={'sha256':w.sha(raw),'bytes':len(raw)}


def produce(root,config_path,output):
    root=Path(root).resolve();output_path=w.safe_path(root,output)
    w.require(not output_path.exists(),'existing output refused')
    exposure=[]
    def operation(stage,started):
        try:
            w.require(sys.version_info[:2]==(3,12),'Python3.12 required')
            task=w.strict_json((root/'.runtime/task.json').read_bytes())
            publication=w.git(root,'rev-parse','origin/main').decode().strip()
            c,provenance=authenticate(root,config_path,output,task,publication)
            inventory={}
            if c['stage']=='refit':
                raw=_read_fixed(root,DEV_PATH,DEV_HASH,exposure)
                refit=build_generated_refit(raw,scenario_count=120,periods=30)
                report={'status':'completed_refit','source_verified':True,'external_acceptance':None,
                        'refit':_refit_manifest(refit),'provenance':provenance,
                        'configuration':c,'exposure':exposure,'python':platform.python_version()}
            else:
                prior,refit=_load_refit(root,c)
                freeze=_final_gate(root,c,task,provenance['configuration_sha256'])
                raw=_read_fixed(root,FINAL_PATH,FINAL_HASH,exposure)
                data=_parse_final(raw)
                tables=_evaluate_rows(data,prior,c['primary_mode'],c['profile_choices'])
                for name in ('scenario_metrics','summary','paired_differences','comparisons','personalized'):
                    _write(stage,name+'.csv',_csv(tables[name]),inventory)
                    if name in ('comparisons','personalized'):
                        _write(stage,name+'.json',w.canonical(tables[name]),inventory)
                annual_count=personal_annual=personal_metrics=0
                for kind,cases in (('generic',tables['generic']),('personalized',tables['personal_cases'])):
                    for (label,fee),case in cases.items():
                        ledgers=[];decisions=[]
                        for result,reviews in case['paths']:
                            ledgers.extend(ledger_row(label,'final',entry)|{'fee_rate':fee,'growth_units':'percent/year'} for entry in result.ledger)
                            decisions.extend(asdict(review)|{'split':'final','fee_rate':fee,'mode':label} for review in reviews)
                        prefix=kind+'/'+label+'/'+str(fee)+'/'
                        _write(stage,prefix+'annual_ledgers.csv',_csv(ledgers),inventory)
                        _write(stage,prefix+'scenario_metrics.csv',_csv(case['metrics']),inventory)
                        if decisions:_write(stage,prefix+'decisions.csv',_csv(decisions),inventory)
                        if kind=='generic':annual_count+=len(ledgers)
                        else:personal_annual+=len(ledgers);personal_metrics+=len(case['metrics'])
                counts={'generic_cases':len(tables['generic']),'generic_annual_ledgers':annual_count,
                        'generic_metrics':len(tables['scenario_metrics']),'comparison_rows':len(tables['comparisons']),
                        'paired_rows':len(tables['paired_differences']),'profile_rows':len(tables['personalized']),
                        'personalized_annual_ledgers':personal_annual,'personalized_metrics':personal_metrics}
                w.require((counts['generic_cases'],annual_count,counts['generic_metrics'],counts['comparison_rows'],counts['paired_rows'],counts['profile_rows'])
                          ==(16,28800,4800,100,6000,10),'final structural counts mismatch')
                report={'status':'completed_final','split':'final','input_origin':FINAL_PATH,
                        'source_verified':True,'production_execution_authorized':True,
                        'input_sha256':w.sha(raw),'prior_support_sha256':prior_support_digest(prior),
                        'frozen_primary_mode':c['primary_mode'],'counts':counts,'artifacts':inventory,
                        'provenance':provenance,'freeze':freeze,'exposure':exposure,
                        'configuration':c,'python':platform.python_version(),
                        'disclosure':'One frozen evaluation; no final model selection or refitting.'}
            w.require(time.monotonic()-started<=c['execution']['max_seconds'],'run exceeded fixed budget')
            _write(stage,'run_manifest.json',w.canonical(report),{})
            return report
        except BaseException:
            (stage/'exposure.json').write_bytes(w.canonical(exposure))
            raise
    return w._stage_output(output_path,operation,max_seconds=1800)


def check_saved(root,output):
    """Read-only artifact integrity/count audit; does not open either input CSV.

    This is a saved-evidence check, not an independent replay or new source
    approval. Exact numerical review of representative ledgers remains required.
    """
    output=w.safe_path(root,output)
    manifest=w.strict_json((output/'run_manifest.json').read_bytes())
    w.require(manifest.get('status') in ('completed_refit','completed_final'),'incomplete execution')
    facts=0
    if manifest['status']=='completed_refit':
        refit=manifest['refit'];prior=EmpiricalPrior(refit['gross'])
        w.require(len(prior.gross)==3600 and refit['input_sha256']==DEV_HASH
                  and refit['prior_support_sha256']==prior_support_digest(prior)
                  and refit['training_row_keys']==[[s,t] for s in range(1,121) for t in range(1,31)],
                  'saved refit support/keys mismatch')
        facts+=1
    for name,entry in manifest.get('artifacts',{}).items():
        data=w.safe_path(output,name).read_bytes()
        w.require(len(data)==entry['bytes']<=w.LIMIT and w.sha(data)==entry['sha256'],
                  'saved artifact mismatch')
        if name.endswith('.csv'):
            parsed=list(csv.DictReader(io.StringIO(data.decode('utf-8'),newline='')))
            w.require(bool(parsed),'saved table empty')
            if name=='scenario_metrics.csv':w.require(len(parsed)==4800,'generic metrics count')
            if name=='paired_differences.csv':w.require(len(parsed)==6000,'paired count')
            if name=='comparisons.csv':w.require(len(parsed)==100,'comparison count')
            if name=='personalized.csv':w.require(len(parsed)==10,'profile count')
        facts+=1
    return {'status':'passed','read_only':True,'artifact_count':facts,
            'scope':'saved hashes/counts; no original input access or independent numerical acceptance'}


def main(argv=None):
    parser=argparse.ArgumentParser(allow_abbrev=False,description=__doc__)
    parser.add_argument('--config',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args(argv)
    root=Path(__file__).resolve().parents[2]
    report=check_saved(root,args.output) if args.check else produce(root,args.config,args.output)
    print(w.canonical({'status':report['status']}).decode())


if __name__=='__main__':main()
