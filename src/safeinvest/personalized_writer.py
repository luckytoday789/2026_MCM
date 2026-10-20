"""Fixed own-horizon development persistence; never select a replacement class.

The CLI authenticates and replays upstream checkers before importing this module.
Generated seams are private Python APIs, unavailable in production configurations.
"""
from copy import deepcopy
from pathlib import Path
import platform
import re
import sys
import time
import traceback
import uuid

from . import policy_writer as w
from . import policy_analysis_writer as aw

require, exact, sha, canonical, strict_json = w.require, w.exact, w.sha, w.canonical, w.strict_json
LIMIT = w.LIMIT
FEES = (.0025, .005)
CLASSES = ('conservative', 'balanced', 'growth')
PROFILES = {'A': (5, 10, 'high'), 'B': (15, 25, 'medium'), 'C': (30, 40, 'low'),
            'D': (25, 15, 'medium'), 'E': (6, 35, 'high')}
FILES = ('personalized_results.json', 'personalized_summary.csv', 'run_manifest.json')
CLOSURE = tuple(dict.fromkeys((*aw.CLOSURE, 'src/safeinvest/policy_personalized.py',
    'src/safeinvest/personalized_writer.py', 'scripts/run_personalized_development.py',
    'specs/PERSONALIZED_PRODUCTION_BRIDGE.md', 'specs/PERSONALIZED_OUTPUT_NOTES.md',
    'specs/PERSONALIZED_REVIEW.md', 'specs/personalized_review_v1.json')))
CONFIG_KEYS = ('schema_version', 'run_id', 'split', 'execution_authorized', 'source_commit',
    'source_sha256', 'acceptance', 'input', 'policy_config', 'analysis', 'execution')
ANALYSIS_KEYS = ('task_id', 'result_commit', 'root', 'config_path', 'artifacts_sha256',
    'acceptance_path', 'acceptance_sha256', 'receipt')
ROOT_SCHEMA = w._schema('profile_id:str split:str fee_rate:float horizon:int loss_tolerance_pct:int '
    'liquidity:str review_threshold_pct:int proposed_class:str? mode:str? recommended_class:str? '
    'status:str simulation_status:str scenario_count:int denominator:int risk_pass:bool? '
    'purchasing_power_pass:bool? horizon_pass:bool? reserve_pass:bool? exceedance_count:int? '
    'exceedance_fraction:float? median_growth_pct:float? p10_growth_pct:float? median_loss_pct:float? '
    'p90_loss_pct:float? pooled_trade_share_pct:float? pooled_trade_share_ex_initial_pct:float? '
    'pooled_human_review_count:int? pooled_human_review_share_pct:float? '
    'component_source_verified:bool bridge_provenance_verified:bool source_case_path:str?')
SCHEMAS = {name: (*schema, ('profile_id', 'str', False), ('review_threshold_pct', 'int', False))
           for name, schema in w.SCHEMAS.items()}


def validate_config(c):
    w.keys(c, CONFIG_KEYS)
    require(exact(c['schema_version'], 1) and c['split'] == 'development' and
            c['execution_authorized'] is True, 'fixed development authorization required')
    require(type(c['run_id']) is str and re.fullmatch(r'[A-Z0-9_-]+', c['run_id']), 'run ID')
    w.hash_string(c['source_commit'], 40)
    require(set(c['source_sha256']) == set(CLOSURE), 'complete source closure required')
    for value in c['source_sha256'].values(): w.hash_string(value)
    require(c['acceptance'] == {'CHIEF-PERSONALIZED-V2-20261020': c['source_commit']},
            'exact positive personalized source approval required')
    require(c['input'] == {'path': w.INPUT_PATH, 'sha256': w.INPUT_HASH}, 'fixed original development input')
    require(c['policy_config'] == {'path': w.POLICY,
        'sha256': 'd7b20f38196831befc80dfdcc69c6653d1ae8352d1c87c79e19bcc09d5c84df3'}, 'fixed policy')
    a = c['analysis']; w.keys(a, ANALYSIS_KEYS); w.hash_string(a['result_commit'], 40)
    require(type(a['task_id']) is str and a['task_id'], 'analysis task identity')
    require(type(a['artifacts_sha256']) is dict and set(a['artifacts_sha256']) ==
        {a['root']+'/'+name for name in (*aw.FILES, 'run_manifest.json')}, 'complete six-file analysis inventory')
    for value in a['artifacts_sha256'].values(): w.hash_string(value)
    w.hash_string(a['acceptance_sha256'])
    require(a['receipt'] is None or (type(a['receipt']) is dict and
        set(a['receipt']) == {'path', 'sha256'}), 'explicit receipt or chief-origin null')
    if a['receipt'] is not None: w.hash_string(a['receipt']['sha256'])
    e=c['execution']; w.keys(e, ('required_python', 'max_seconds', 'max_artifact_bytes', 'cpu_only'))
    require(e['required_python']=='3.12' and e['cpu_only'] is True and
        type(e['max_seconds']) is int and 1<=e['max_seconds']<=1500 and
        exact(e['max_artifact_bytes'], LIMIT), 'bounded Python 3.12 CPU execution')
    return c


def _entry(root, commit, name, digest):
    return aw._entry(root, name, commit, digest)


def _approval(root, base, name, digest, ident, commit, verdict):
    raw = w.blob(root, base, name); require(sha(raw)==digest, 'approval digest mismatch')
    local = w.safe_path(root, name).read_bytes()
    require(aw._text_match(local, raw), 'approval checkout mismatch')
    review = strict_json(raw)
    require(review.get('task_id')==ident and review.get('reviewed_commit')==commit and
            review.get(verdict)=='approve', 'positive exact approval required')
    if ident.startswith('CHIEF-'):
        require(review.get('kind')=='chief_takeover_approval' and
                review.get('authorization')=='user-directed-two-node-takeover-20261020',
                'chief takeover authorization required')
    else:
        queue = strict_json(w.blob(root, base, 'ops/queue.json'))['tasks']
        found = [q for q in queue if q['id']==ident]
        require(len(found)==1 and found[0]['state']=='accepted' and
            found[0]['reviewed_commit']==commit and found[0]['acceptance_evidence']==name,
            'analysis task is not accepted')
    return review


def authenticate(root, c, config_path, config_raw, output, task, publication):
    """Original-byte/source/task authentication, before fitting or output creation."""
    root=Path(root).resolve(); validate_config(c)
    owner=task.get('owner')
    require(owner in ('chief','hy3') and task.get('kind')=='commands' and
        task.get('split')=='development', 'published chief/HY3 command task required')
    E=task['base_commit']; C=c['source_commit']; w.ancestor(root, C, E); w.ancestor(root, E, publication)
    require(C!=E and E!=publication, 'distinct source/config/task publications required')
    published = strict_json(w.blob(root, publication, 'ops/tasks/'+task['id']+'.json'))
    require(exact(task, published), 'runtime task differs from immutable publication')
    q=[x for x in strict_json(w.blob(root, publication, 'ops/queue.json'))['tasks'] if x['id']==task['id']]
    require(len(q)==1 and q[0]['owner']==owner and q[0]['state']=='ready' and
        exact(q[0]['attempt'],task['attempt']) and q[0]['task_sha256']==sha(canonical(task)) and
        q[0]['branch']=='work/'+owner+'/'+task['id']+'-a'+str(task['attempt']), 'published task/queue binding')
    pinned=w.blob(root, E, config_path)
    require(aw._text_match(config_raw,pinned) and task['parameters']==
        dict(c,config_path=config_path,config_sha256=sha(pinned)), 'fixed task configuration mismatch')
    cmd=['{python}','-B','scripts/run_personalized_development.py','--config',config_path,'--output',output]
    require(task['commands']==[cmd] and task['validation_commands']==[cmd+['--check']] and
        task['allowed_paths']==[output] and type(task['max_seconds']) is int and
        c['execution']['max_seconds']<=task['max_seconds']<=1500, 'fixed executable command/scope')
    ident='CHIEF-PERSONALIZED-V2-20261020'; path='audit/chief/'+ident+'-review.json'
    review_raw=w.blob(root,E,path)
    review=_approval(root,E,path,sha(review_raw),ident,C,'code_verdict')
    require(review.get('source_sha256')==c['source_sha256'], 'approval source closure mismatch')
    sources={}
    for name,digest in c['source_sha256'].items():
        _,sources[name]=_entry(root,C,name,digest)
    require(c['policy_config']['sha256']==c['source_sha256'][w.POLICY], 'policy closure mismatch')
    a=c['analysis']; approval=_approval(root,E,a['acceptance_path'],a['acceptance_sha256'],
        a['task_id'],a['result_commit'],'result_verdict')
    consumed={}; blobs={}
    for name,digest in a['artifacts_sha256'].items():
        raw,consumed[name]=_entry(root,a['result_commit'],name,digest); blobs[name]=raw
    require(aw._files(w.safe_path(root,a['root']))==set((*aw.FILES,'run_manifest.json')), 'analysis inventory mismatch')
    m=strict_json(blobs[a['root']+'/run_manifest.json'])
    require(m['status']=='completed' and m['split']=='development' and
        m['binding']['config_path']==a['config_path'], 'analysis manifest identity')
    if a['receipt'] is None:
        require(a['task_id'].startswith('CHIEF-') and approval.get('kind')=='chief_takeover_approval',
                'a real worker receipt is required for worker-origin analysis')
    else:
        receipt_raw,_=_entry(root,a['result_commit'],a['receipt']['path'],a['receipt']['sha256'])
        receipt=strict_json(receipt_raw)
        require(receipt['status']=='completed' and receipt['task_id']==a['task_id'] and
            all(receipt['artifacts_sha256'].get(k)==v for k,v in a['artifacts_sha256'].items()), 'analysis receipt mismatch')
    recommendations=strict_json(blobs[a['root']+'/profile_recommendations.json'])
    screens=strict_json(blobs[a['root']+'/profile_screen.json'])
    mapped=map_assignments(recommendations,screens,split='development',n=120)
    wanted=set(expected_deliverables(output,mapped))
    require(len(task['deliverables'])==len(wanted) and set(task['deliverables'])==wanted,
            'conditional personalized deliverables mismatch')
    binding=dict(task=task,publication_commit=publication,config_path=config_path,
                 config_sha256=sha(pinned),configuration_commit=E,source_commit=C)
    return dict(binding=binding,sources=sources,analysis_manifest=m,analysis_consumed=consumed,
                recommendations=recommendations,screens=screens,mapped=mapped)


def map_assignments(recommendations,screens,*,split,n):
    """Translate authenticated actual analysis fields; never infer or rerank."""
    require(type(recommendations) is list and type(screens) is list and
            len(recommendations)==10 and len(screens)==30, 'ten recommendations/thirty screens required')
    expected=[(profile,fee) for fee in FEES for profile in PROFILES]
    require([(r.get('profile'),r.get('fee_rate')) for r in recommendations]==expected,
            'recommendation ordering/duplicate keys')
    require([(r.get('profile'),r.get('fee_rate'),r.get('candidate_class')) for r in screens]==
        [(p,f,cls) for f in FEES for p in PROFILES for cls in CLASSES], 'candidate screen ordering/duplicate keys')
    mapped=[]
    for rec in recommendations:
        profile,fee=rec['profile'],rec['fee_rate']; h,tol,liq=PROFILES[profile]
        candidates=[r for r in screens if (r['profile'],r['fee_rate'])==(profile,fee)]
        for r in [rec,*candidates]:
            require(r['split']==split and exact(r['fee_rate'],fee) and exact(r['horizon'],h) and
                exact(r['loss_tolerance_pct'],tol) and r['liquidity']==liq and r['status']=='provisional' and
                r['personalized_overlay_pending'] is True, 'fixed profile/status/split mismatch')
        require(type(fee) is float and fee in FEES and type(rec['reasons']) is list and rec['reasons'] and
            all(type(x) is str and x for x in rec['reasons']), 'explicit upstream reasons required')
        require(rec['pending_holdings_initial']=='retain original bills' and
            rec['pending_holdings_existing']=='keep current component dollars', 'pending-holdings mismatch')
        for screen,outcome in zip(candidates,rec['candidate_outcomes']):
            require(screen['mode']==screen['candidate_class']+'_cost' and
                type(screen['flags']) is dict and set(screen['flags'])==
                {'horizon_eligible','willingness_eligible','liquidity_pass','risk_pass','purchasing_power_pass'} and
                all(type(v) is bool for v in screen['flags'].values()) and
                screen['qualified'] is all(screen['flags'].values()) and
                screen['reasons']==[k for k in ('horizon_eligible','willingness_eligible',
                    'liquidity_pass','risk_pass','purchasing_power_pass') if not screen['flags'][k]], 'screen flag/reason mismatch')
            require(screen['scenario_count']==n and screen['exceedance_denominator']==n and
                    len(screen['source_metric_keys'])==n, 'screen scenario membership count')
            require(exact(screen['source_metric_keys'],[dict(mode=screen['mode'],fee_rate=fee,horizon=h,
                scenario_id=s,fold_id=(s-1)%4,split=split) for s in range(1,n+1)]), 'screen full ordered metric keys')
            require(outcome['candidate_class']==screen['candidate_class'] and outcome['mode']==screen['mode'] and
                exact(outcome['qualified'],screen['qualified']) and exact(outcome['reasons'],screen['reasons']) and
                exact(outcome['median_growth_pct'],screen['median_growth_pct']) and
                exact(outcome['source_metric_keys'],screen['source_metric_keys']), 'candidate outcome translation mismatch')
        require(len(rec['candidate_outcomes'])==3 and rec['failed_candidate_reasons']==
            {r['candidate_class']:r['reasons'] for r in candidates}, 'candidate outcome/failure inventory')
        cls=rec['selected_class']
        if cls is None:
            require(rec['selected_mode'] is None and rec['action']=='human_review' and
                rec['reasons']==['no_qualifying_class'] and not any(r['qualified'] for r in candidates) and
                rec['qualifying_classes']==[] and rec['indifference_classes']==[], 'invalid upstream referral')
            selected=None
        else:
            require(cls in CLASSES and rec['selected_mode']==cls+'_cost' and
                rec['action']=='provisional_assignment', 'fixed selected class/mode required')
            selected=next(r for r in candidates if r['candidate_class']==cls)
            require(selected['qualified'] is True and all(v is True for v in selected['flags'].values()),
                    'selected screen does not qualify')
            require(cls in rec['qualifying_classes'] and cls in rec['indifference_classes'], 'upstream class lists')
        follow=rec['personalized_follow_up']
        require(follow=={'mode':rec['selected_mode'],'horizon':h,'review_drawdown_pct':tol,
            'rescreen':['risk','purchasing_power'],'failure_action':'human_review_no_reselection'}, 'own-horizon follow-up mismatch')
        mapped.append(dict(profile_id=profile,fee_rate=fee,proposed_class=cls,
            upstream_reasons=deepcopy(rec['reasons']),upstream=deepcopy(rec),screens=deepcopy(candidates),selected=deepcopy(selected)))
    return mapped


def case_path(item):
    return 'cases/'+item['profile_id']+('-primary' if item['fee_rate']==.0025 else '-doubled')


def expected_deliverables(output,mapped):
    paths=[output+'/'+name for name in FILES]
    for item in mapped:
        if item['proposed_class'] is not None:
            paths.extend(output+'/'+case_path(item)+'/'+name for name in
                         [*(t+'.csv' for t in w.TABLES),'component_payload.json'])
    return paths


def _root_projection(payload,path,upstream,authentication):
    require(payload['source_verified'] is False, 'pure component flag must remain false')
    return dict(component_payload=deepcopy(payload), source_case_path=path,
        upstream_record=deepcopy(upstream['upstream']), candidate_screens=deepcopy(upstream['screens']),
        upstream_identity=dict(recommendation_key={k:upstream['upstream'][k] for k in ('profile','fee_rate')},
            recommendation_sha256=sha(canonical(upstream['upstream'])),
            selected_screen_sha256=None if upstream['selected'] is None else sha(canonical(upstream['selected'])),
            candidate_screen_sha256=[sha(canonical(s)) for s in upstream['screens']]),
        bridge_authentication=deepcopy(authentication))


def _csv_projection(root_row):
    p=root_row['component_payload']; result={name:p[name] for name,_,_ in ROOT_SCHEMA
        if name not in ('component_source_verified','bridge_provenance_verified','source_case_path')}
    return result | dict(component_source_verified=p['source_verified'],
        bridge_provenance_verified=root_row['bridge_authentication']['verified'],source_case_path=root_row['source_case_path'])


def _compute(mapped,rows,calibration,*,split,n,authentication,compute=None):
    from .policy_personalized import build_personalized_case_tables
    compute=compute or build_personalized_case_tables
    outputs={};roots=[];counts={name:0 for name in w.TABLES};executed=0
    for item in mapped:
        assigned=item['proposed_class'] is not None
        out=compute(rows if assigned else None,calibrations=calibration if assigned else None,
            profile_id=item['profile_id'],proposed_class=item['proposed_class'],fee_rate=item['fee_rate'],
            split=split,upstream_reasons=item['upstream_reasons'])
        payload=out.rescreen
        require(payload['source_verified'] is False and payload['proposed_class']==item['proposed_class'] and
            payload['profile_id']==item['profile_id'] and exact(payload['fee_rate'],item['fee_rate']), 'pure output identity')
        if not assigned:
            require(out.case is None and payload['scenario_count']==payload['denominator']==0 and
                payload['simulation_status']=='not_run_upstream_referral' and
                payload['risk_pass'] is payload['purchasing_power_pass'] is payload['exceedance_count'] is None,
                'upstream referral must not become a simulated result')
            path=None
        else:
            require(out.case is not None and payload['simulation_status']=='completed' and
                payload['scenario_count']==payload['denominator']==n, 'incomplete personalized execution')
            path=case_path(item); executed+=1; h=PROFILES[item['profile_id']][0]
            expected=dict(annual_ledgers=n*h,decisions=n*h,scenario_metrics=n,summary=1)
            for name in w.TABLES:
                records=list(getattr(out.case,name)); raw=w.encode_csv(records,SCHEMAS[name])
                require(exact(w.decode_csv(raw,SCHEMAS[name],w.KEYS[name]),records), 'lossy typed case serialization')
                if name in expected: require(len(records)==expected[name], 'conditional case row count')
                else: require(len(records)<=n*h, 'too many target scores')
                counts[name]+=len(records); outputs[path+'/'+name+'.csv']=raw
            outputs[path+'/component_payload.json']=w._json_bytes(payload)
        roots.append(_root_projection(payload,path,item,authentication))
    require(len(roots)==10 and counts['scenario_metrics']==n*executed, 'ten-row/conditional count mismatch')
    outputs['personalized_results.json']=w._json_bytes(roots)
    outputs['personalized_summary.csv']=w.encode_csv([_csv_projection(r) for r in roots],ROOT_SCHEMA)
    require(exact(w.decode_csv(outputs['personalized_summary.csv'],ROOT_SCHEMA,('profile_id','fee_rate')),
        [_csv_projection(r) for r in roots]), 'lossy typed root projection')
    return outputs,counts|dict(root_rows=10,executed_pairs=executed,upstream_referrals=10-executed),roots


def _persist(stage,started,*,c,binding,proof,data,rows,calibration,mapped,records,split,n):
    authentication=dict(verified=split=='development',scope='exact accepted analysis/input/policy/source/full-fold identities',
        analysis_result_commit=None if c is None else c['analysis']['result_commit'],
        analysis_inventory_sha256=None if c is None else sha(canonical(c['analysis']['artifacts_sha256'])),
        input_sha256=sha(data),calibration_sha256=None if calibration is None else sha(canonical(calibration.manifest())))
    outputs,counts,roots=_compute(mapped,rows,calibration,split=split,n=n,authentication=authentication)
    artifacts={}
    for name,raw in outputs.items():
        w._write(stage/name,raw,LIMIT); artifacts[name]=dict(sha256=sha(raw),bytes=len(raw))
    m=dict(schema_version=1,status='completed',split=split,configuration=c,binding=binding,
        authentication=authentication,proof=proof,checker_executions=records,
        calibration=None if calibration is None else dict(arithmetic_manifest=calibration.manifest(),
            attestation=w.calibration_attestation(data,rows,n,30,calibration,split)),
        schema=dict(root_csv=[list(x) for x in ROOT_SCHEMA],cases={k:[list(x) for x in v] for k,v in SCHEMAS.items()},
                    json='strict UTF-8 LF JSON; preserve null/bool/int/binary64 incl signed zero'),
        counts=counts,artifacts=artifacts,python=platform.python_version(),
        elapsed_seconds=time.monotonic()-started,max_artifact_bytes=LIMIT,
        max_seconds=1500 if c is None else c['execution']['max_seconds'])
    w._write(stage/'run_manifest.json',w._json_bytes(m),LIMIT)
    return m


def _records(records,c,analysis_config):
    require(type(records) is list and len(records)==3,'two producers and one assembly actual child checks required')
    for r in records:
        require(r['returncode']==0 and type(r['returncode']) is int and r['pythonpath_absent'] is True and
            type(r['stdout']) is str and type(r['stderr']) is str and
            sha(r['stdout'].encode())==r['stdout_sha256'] and sha(r['stderr'].encode())==r['stderr_sha256'] and
            r['before_inventory']==r['after_inventory'], 'failed or writing prerequisite checker')
    require([r['group'] for r in records]==['primary','doubled','analysis'],'checker ordering')
    aw._execution_records([{k:v for k,v in r.items() if k not in ('before_inventory','after_inventory')}
        for r in records[:2]],analysis_config)
    require(records[-1]['argv'][1:]==['-B','scripts/run_development_analysis.py','--config',
        c['analysis']['config_path'],'--output',c['analysis']['root'],'--check'],'assembly check command')
    require(strict_json(records[-1]['stdout'].strip())==dict(status='passed',read_only=True,result='passed') and
        re.fullmatch(r'3\.12\.[0-9]+',records[-1]['python']) is not None, 'assembly checker success/runtime report')


def _stage(output,operation,*,started,max_seconds):
    output=Path(output);require(not output.exists() and not output.is_symlink(),'existing output root refused')
    output.mkdir(parents=True,exist_ok=False);stage=output/('partial-'+uuid.uuid4().hex);stage.mkdir()
    try:
        result=operation(stage)
        require(time.monotonic()-started<=max_seconds,'total immutable task budget exceeded')
        for p in stage.rglob('*'):
            if p.is_file():require(p.stat().st_size<=LIMIT,'actual byte limit exceeded')
        for p in sorted(stage.iterdir()):
            if p.name!='run_manifest.json':p.rename(output/p.name)
        (stage/'run_manifest.json').rename(output/'run_manifest.json');stage.rmdir()
        return result
    except BaseException as exc:
        w._write(stage/'failure.json',w._json_bytes(dict(status='failed',exception=type(exc).__name__,
            diagnosis=str(exc),traceback=traceback.format_exc(),elapsed_seconds=time.monotonic()-started)))
        raise


def _calibration(root,c,proof):
    data,rows=w.load_fixed_input(root)
    assigned=any(i['proposed_class'] is not None for i in proof['mapped'])
    if not assigned: return data,rows,None
    calibration=w.build_synthetic_calibrations(data,scenario_count=120,periods=30)
    actual=dict(arithmetic_manifest=calibration.manifest(),
                attestation=w.calibration_attestation(data,rows,120,30,calibration,'development'))
    producers=proof['analysis_manifest']['producers']
    require(len(producers)==2 and all(exact(p['calibration'],actual) for p in producers),
            'full 90x30 other-fold priors differ from accepted generic producers')
    return data,rows,calibration


def _persisted_proof(proof):
    """Bind the complete accepted manifest by digest without duplicating its 9600 row map."""
    m=proof['analysis_manifest']
    return dict(sources=proof['sources'],analysis_consumed=proof['analysis_consumed'],
        upstream_binding=m['binding'],upstream_configuration_sha256=sha(canonical(m['configuration'])),
        upstream_counts=deepcopy(m['counts']),
        upstream_assignment_sha256=dict(recommendations=sha(canonical(proof['recommendations'])),
            screens=sha(canonical(proof['screens']))),
        producer_calibration_sha256=[sha(canonical(p['calibration'])) for p in m['producers']])


def produce_authenticated(root,config_path,output,records,*,started=None):
    require(sys.version_info[:2]==(3,12),'Python 3.12 required')
    root=Path(root).resolve(); raw=w.safe_path(root,config_path).read_bytes(); c=validate_config(strict_json(raw))
    task=strict_json((root/'.runtime/task.json').read_bytes())
    P=w.git(root,'rev-parse','origin/main').decode().strip()
    started=time.monotonic() if started is None else started
    proof=authenticate(root,c,config_path,raw,output,task,P); _records(records,c,proof['analysis_manifest']['configuration'])
    data,rows,calibration=_calibration(root,c,proof)
    require(time.monotonic()-started<c['execution']['max_seconds'],'authentication/calibration exhausted budget')
    return _stage(w.safe_path(root,output),lambda stage:_persist(stage,started,c=c,
        binding=proof['binding'],proof=_persisted_proof(proof),
        data=data,rows=rows,calibration=calibration,mapped=proof['mapped'],records=records,split='development',n=120),
        started=started,max_seconds=c['execution']['max_seconds'])


def _check_outputs(output,m,outputs,counts):
    require(aw._files(output)==set(outputs)|{'run_manifest.json'},'missing/extra personalized artifacts')
    require(exact(m['counts'],counts) and set(m['artifacts'])==set(outputs),'personalized manifest count/inventory mismatch')
    for name,expected in outputs.items():
        raw=(output/name).read_bytes(); spec=m['artifacts'][name]
        require(raw==expected and spec==dict(sha256=sha(raw),bytes=len(raw)) and len(raw)<=LIMIT,
                'changed/rehashed wrong personalized result: '+name)


def _historical_entries(root,saved,expected,commit):
    require(set(saved)==set(expected),'historical source inventory mismatch')
    for name,entry in saved.items():
        w.keys(entry,('canonical_sha256','consumed_sha256','bytes'))
        blob=w.blob(root,commit,name)
        require(entry['canonical_sha256']==sha(blob)==expected[name]['canonical_sha256'] and
            (entry['consumed_sha256'],entry['bytes']) in {(sha(blob),len(blob)),
                (sha(blob.replace(b'\n',b'\r\n')),len(blob.replace(b'\n',b'\r\n')))},
                'false historical consumed source identity')


def check_production(root,config_path,output):
    require(sys.version_info[:2]==(3,12),'Python 3.12 required')
    root=Path(root).resolve(); path=w.safe_path(root,output); m=strict_json((path/'run_manifest.json').read_bytes())
    require(m['status']=='completed' and m['split']=='development','completed development bundle required')
    c=validate_config(m['configuration']); raw=w.safe_path(root,config_path).read_bytes(); binding=m['binding']
    proof=authenticate(root,c,config_path,raw,output,binding['task'],binding['publication_commit'])
    require(exact(proof['binding'],binding),'historical task/config binding mismatch')
    _records(m['checker_executions'],c,proof['analysis_manifest']['configuration'])
    saved_proof=_persisted_proof(proof)
    require(set(saved_proof)==set(m['proof']),'changed upstream/source proof inventory')
    _historical_entries(root,m['proof']['sources'],saved_proof['sources'],c['source_commit'])
    _historical_entries(root,m['proof']['analysis_consumed'],saved_proof['analysis_consumed'],c['analysis']['result_commit'])
    require(all(exact(m['proof'][k],v) for k,v in saved_proof.items()
        if k not in ('sources','analysis_consumed')),'changed upstream/source proof')
    data,rows,calibration=_calibration(root,c,proof)
    expected_cal=None if calibration is None else dict(arithmetic_manifest=calibration.manifest(),
        attestation=w.calibration_attestation(data,rows,120,30,calibration,'development'))
    require(exact(m['calibration'],expected_cal),'wrong saved full-fold calibration')
    require(exact(m['schema'],dict(root_csv=[list(x) for x in ROOT_SCHEMA],
        cases={k:[list(x) for x in v] for k,v in SCHEMAS.items()},
        json='strict UTF-8 LF JSON; preserve null/bool/int/binary64 incl signed zero')) and
        type(m['python']) is str and re.fullmatch(r'3\.12\.[0-9]+',m['python']) is not None and
        type(m['elapsed_seconds']) is float and 0<=m['elapsed_seconds']<=c['execution']['max_seconds'] and
        exact(m['max_seconds'],c['execution']['max_seconds']) and exact(m['max_artifact_bytes'],LIMIT),
        'false schema/runtime provenance')
    auth=dict(verified=True,scope='exact accepted analysis/input/policy/source/full-fold identities',
        analysis_result_commit=c['analysis']['result_commit'],
        analysis_inventory_sha256=sha(canonical(c['analysis']['artifacts_sha256'])),
        input_sha256=sha(data),calibration_sha256=None if calibration is None else sha(canonical(calibration.manifest())))
    require(exact(m['authentication'],auth),'false bridge authentication')
    outputs,counts,_=_compute(proof['mapped'],rows,calibration,split='development',n=120,authentication=auth)
    _check_outputs(path,m,outputs,counts)
    return dict(status='passed',read_only=True,root_rows=10,executed_pairs=counts['executed_pairs'])


def _synthetic_persist(output,data,recommendations,screens,*,compute=None):
    """PRIVATE generated seam; absent from CLI, no production configuration."""
    mapped=map_assignments(recommendations,screens,split='synthetic',n=4)
    rows=w._input_rows(data,4,30)
    calibration=w.build_synthetic_calibrations(data,scenario_count=4,periods=30) if any(
        r['proposed_class'] is not None for r in mapped) else None
    auth=dict(verified=False,scope='PRIVATE generated fixtures only',input_sha256=sha(data))
    outputs,counts,roots=_compute(mapped,rows,calibration,split='synthetic',n=4,authentication=auth,compute=compute)
    def save(stage,started):
        for name,raw in outputs.items():w._write(stage/name,raw)
        m=dict(schema_version=1,status='completed',split='synthetic',authentication=auth,counts=counts,
            artifacts={k:dict(sha256=sha(v),bytes=len(v)) for k,v in outputs.items()})
        w._write(stage/'run_manifest.json',w._json_bytes(m)); return m
    return w._stage_output(output,save)


def _synthetic_check(output,data,recommendations,screens):
    path=Path(output);m=strict_json((path/'run_manifest.json').read_bytes())
    require(m['split']=='synthetic' and m['authentication']==dict(verified=False,
        scope='PRIVATE generated fixtures only',input_sha256=sha(data)), 'false generated provenance')
    mapped=map_assignments(recommendations,screens,split='synthetic',n=4);rows=w._input_rows(data,4,30)
    cal=w.build_synthetic_calibrations(data,scenario_count=4,periods=30) if any(r['proposed_class'] is not None for r in mapped) else None
    outputs,counts,roots=_compute(mapped,rows,cal,split='synthetic',n=4,authentication=m['authentication'])
    _check_outputs(path,m,outputs,counts); return roots
