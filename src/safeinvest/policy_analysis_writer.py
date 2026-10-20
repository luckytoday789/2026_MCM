"""Authenticated persistence for fixed development analysis (no experiment API).

Only the CLI performs original writer checks, in fresh children before this
module is imported. Private generated seams are Python-only and never config keys.
"""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

from . import policy_writer as w

LIMIT = 10485760
POLICY = w.POLICY
FILES = ('paired_differences.csv', 'comparison_gates.json', 'selection.json',
         'profile_screen.json', 'profile_recommendations.json')
CLOSURE = (*w.CLOSURE, 'src/safeinvest/policy_analysis.py',
           'src/safeinvest/policy_analysis_writer.py', 'scripts/run_development_analysis.py',
           'specs/POLICY_ANALYSIS.md', 'specs/POLICY_ANALYSIS_ASSEMBLY.md',
           'specs/DEVELOPMENT_CASE_RESULTS_REVIEW.md',
           'audit/chief/writer_reference.py', 'audit/chief/writer-reference.json',
           'audit/chief/HY3-003-review.json', 'audit/SOL-038/schema.json')
ACCEPTED = {
    'SOL-016': 'ceec2b6d1107a4137ee3d24d689ba7ba614703c2',
    'SOL-021': 'd154f90d1c50b37990b75ec0a45aa01a38252343',
    'SOL-022': '21ad493707d71240f83d7f01ed6d133e1380e8fb',
    'SOL-025': '803b7a085284405ee5ee4d4f0d5720ebaa2e67f7',
    'SOL-031': 'a24dca5d5494455407207e0fd70c06b258d4fd1f',
    'SOL-032': 'd168757efbc70e4641deacc911976f1fa3bd7a7c'}
CONFIG_KEYS = ('schema_version', 'run_id', 'split', 'execution_authorized',
               'source_commit', 'source_sha256', 'acceptance', 'input',
               'policy_config', 'producers', 'expected_counts', 'execution')
TASK_KEYS = ('schema_version','id','attempt','owner','kind','base_commit','depends_on',
             'split','max_seconds','scope','parameters','allowed_paths','deliverables',
             'commands','validation_commands','acceptance_checks','instructions')
PRODUCER_KEYS = ('group','task_id','attempt','task_digest','result_commit',
                 'receipt_sha256','acceptance_path','acceptance_sha256','root',
                 'config_path','artifacts_sha256','numerical_review')
MANIFEST_KEYS = ('schema_version','status','split','configuration','binding','sources',
                 'producers','mapping','metric_rows','metric_input_sha256','metric_sources',
                 'schema','counts','artifacts','checker_executions','python',
                 'elapsed_seconds','max_seconds','max_artifact_bytes')
EXPECTED = dict(metric_rows=9600, paired_differences=12000, comparison_gates=100,
                selection=1, profile_screen=30, profile_recommendations=10)
KEY_FIELDS = ('mode','fee_rate','horizon','scenario_id','fold_id','split')
PAIRED_SCHEMA = w._schema('candidate_mode:str reference_mode:str fee_rate:float horizon:int '
    'scenario_id:int fold_id:int split:str net_real_cagr_pct_difference:float '
    'max_real_drawdown_pct_difference:float terminal_real_wealth_difference:float '
    'nominal_fee_sum_difference:float trade_share_pct_difference:float '
    'trade_share_ex_initial_pct_difference:float human_review_count_difference:int? '
    'human_review_share_pct_difference:float? target_change_count_difference:int? '
    'growth_difference_units:str loss_difference_units:str terminal_real_wealth_difference_units:str '
    'nominal_fee_difference_units:str trade_share_difference_units:str '
    'human_review_share_difference_units:str count_difference_units:str')
PAIRED_KEYS = ('candidate_mode','reference_mode','fee_rate','horizon','scenario_id')
require, sha, canonical, strict_json, keys, exact = w.require, w.sha, w.canonical, w.strict_json, w.keys, w.exact


def _path(root, name):
    return w.safe_path(root, name)


def _blob(root, commit, name):
    return w.blob(root, commit, name)


def _text_match(actual, pinned):
    return actual == pinned or actual == pinned.replace(b'\n', b'\r\n')


def _files(root):
    paths=list(Path(root).rglob('*'))
    require(all(not p.is_symlink() for p in paths),'symlink in artifact inventory')
    return {p.relative_to(root).as_posix() for p in paths if p.is_file()}


def _entry(root, name, commit, expected):
    pinned = _blob(root, commit, name)
    require(sha(pinned) == expected, 'canonical Git blob mismatch: ' + name)
    raw = _path(root, name).read_bytes()
    require(len(raw)<=LIMIT and len(pinned)<=LIMIT, 'producer/source byte limit')
    require(_text_match(raw, pinned), 'consumed checkout differs from Git blob: ' + name)
    return raw, dict(canonical_sha256=expected, consumed_sha256=sha(raw), bytes=len(raw))


def _approval(root, base, ident, commit, *, result=False, path=None, digest=None):
    queue = strict_json(_blob(root, base, 'ops/queue.json'))
    matches = [q for q in queue['tasks'] if q['id'] == ident]
    require(len(matches) == 1, 'missing/duplicate acceptance: ' + ident)
    q = matches[0]
    verdict = 'result_verdict' if result else 'code_verdict'
    require(q['state'] == 'accepted' and q['reviewed_commit'] == commit and
            q.get(verdict) == 'approve', 'exact positive ' + verdict + ' required: ' + ident)
    if path is not None:
        require(q['acceptance_evidence'] == path, 'wrong chief acceptance path')
    raw = _blob(root, base, q['acceptance_evidence'])
    if digest is not None:
        require(sha(raw) == digest, 'wrong chief acceptance digest')
    review = strict_json(raw)
    require(review.get('task_id') == ident and review.get('reviewed_commit') == commit and
            review.get(verdict) == 'approve', 'chief positive verdict required')
    return q, review


def validate_config(c):
    keys(c, CONFIG_KEYS)
    w.integer(c['schema_version'], 1, 1)
    require(type(c['run_id']) is str and re.fullmatch(r'[A-Za-z0-9_-]+', c['run_id']), 'run id')
    require(c['split'] == 'development' and c['execution_authorized'] is True, 'closed production gate')
    w.hash_string(c['source_commit'], 40)
    require(type(c['source_sha256']) is dict and set(c['source_sha256']) == set(CLOSURE), 'complete computational closure required')
    for h in c['source_sha256'].values(): w.hash_string(h)
    keys(c['acceptance'], (*ACCEPTED, 'SOL-038'))
    for ident, commit in ACCEPTED.items():
        require(c['acceptance'][ident] == commit, 'wrong accepted dependency')
    w.hash_string(c['acceptance']['SOL-038'], 40)
    require(exact(c['input'], dict(path=w.INPUT_PATH, sha256=w.INPUT_HASH, scenario_ids=[1,120], periods=30)), 'original input identity required')
    require(exact(c['policy_config'], dict(path=POLICY, sha256=c['source_sha256'][POLICY])), 'unchanged policy config pin')
    require(exact(c['expected_counts'], EXPECTED), 'structural counts are fixed')
    keys(c['execution'], ('cpu_only','required_python','max_seconds','max_artifact_bytes'))
    e = c['execution']
    require(e['cpu_only'] is True and e['required_python'] == '3.12', 'Python 3.12 CPU only')
    w.integer(e['max_seconds'], 1, 1500); w.integer(e['max_artifact_bytes'], LIMIT, LIMIT)
    require(type(c['producers']) is list and len(c['producers']) == 2, 'exactly two producers')
    require([p.get('group') for p in c['producers']] == ['primary','doubled'], 'ordered primary/doubled required')
    require(len({p.get('task_id') for p in c['producers']}) == 2 and
            len({p.get('root') for p in c['producers']}) == 2, 'duplicate/swapped producer')
    require(len({p.get('numerical_review',{}).get('task_id') for p in c['producers']})==2, 'distinct independent reviews required')
    for p in c['producers']:
        keys(p, PRODUCER_KEYS)
        require(type(p['task_id']) is str and re.fullmatch(r'HY3-[0-9]+', p['task_id']), 'producer task id')
        w.integer(p['attempt'], 1); w.hash_string(p['result_commit'], 40)
        for k in ('task_digest','receipt_sha256','acceptance_sha256'): w.hash_string(p[k])
        expected = {p['root']+'/'+name for name in producer_files()}
        require(type(p['artifacts_sha256']) is dict and set(p['artifacts_sha256']) == expected, 'full 44-file inventory required')
        for h in p['artifacts_sha256'].values(): w.hash_string(h)
        n = p['numerical_review']
        keys(n, ('task_id','reviewed_commit','acceptance_path','acceptance_sha256'))
        require(type(n['task_id']) is str and re.fullmatch(r'SOL-[0-9]+', n['task_id']), 'independent Sol review required')
        w.hash_string(n['reviewed_commit'],40); w.hash_string(n['acceptance_sha256'])
    return c


def producer_files():
    return {'run_manifest.json','checks.json','calibrations.json','reference_imports.json'} | {
        'cases/'+m+'/'+t+'.csv' for m in w.MODES for t in w.TABLES}


def _bind(root, c, config_path, raw, output, task, P):
    keys(task, TASK_KEYS)
    w.integer(task['schema_version'],1,1); w.integer(task['max_seconds'],1,1500)
    binding = w.validate_publication(root, task, P)
    E = task['base_commit']
    w.ancestor(root, c['source_commit'], E)
    require(c['source_commit'] != E and E != P, 'distinct C then E then P required')
    require(task['split'] == 'development', 'task split')
    pinned = _blob(root,E,config_path)
    require(_text_match(raw,pinned) and exact(strict_json(pinned),c), 'task base configuration mismatch')
    keys(task['parameters'], (*CONFIG_KEYS,'config_path','config_sha256'))
    require(task['parameters']['config_path'] == config_path and task['parameters']['config_sha256'] == sha(pinned), 'task config digest mismatch')
    for k in CONFIG_KEYS:
        require(exact(task['parameters'][k],c[k]), 'task parameter mismatch: '+k)
    required = set(c['acceptance']) | {p['task_id'] for p in c['producers']} | {p['numerical_review']['task_id'] for p in c['producers']}
    require(type(task['depends_on']) is list and len(task['depends_on']) == len(required) and set(task['depends_on']) == required, 'exact task dependencies required')
    expected = {output+'/'+f for f in (*FILES,'run_manifest.json')}
    require(task['allowed_paths'] == [output] and type(task['deliverables']) is list and
            len(task['deliverables']) == 6 and set(task['deliverables']) == expected, 'six exact output files required')
    command = ['{python}','-B','scripts/run_development_analysis.py','--config',config_path,'--output',output]
    require(task['commands'] == [command] and task['validation_commands'] == [command+['--check']], 'fixed assembly commands required')
    require(c['execution']['max_seconds'] <= task['max_seconds'], 'budget exceeds task')
    for ident, commit in c['acceptance'].items(): _approval(root,E,ident,commit)
    binding.update(config_path=config_path,config_blob_sha256=sha(pinned),source_commit=c['source_commit'],task=task,output=output)
    return binding


def _sources(root, c):
    result = {}
    for name,h in c['source_sha256'].items():
        _, result[name] = _entry(root,name,c['source_commit'],h)
    # A malicious source dictionary cannot move any imported module elsewhere.
    for name,module in tuple(sys.modules.items()):
        if name == 'safeinvest' or name.startswith('safeinvest.'):
            p = Path(module.__file__).resolve()
            rel = 'src/safeinvest/'+p.name
            require(rel in result and p == _path(root,rel), 'unlisted/outside imported module')
    # Source acceptance is tied to exact reviewed bytes, not a caller's hashes.
    for name in CLOSURE:
        approved = c['acceptance']['SOL-038'] if name in (
            'src/safeinvest/policy_analysis_writer.py','scripts/run_development_analysis.py',
            'audit/SOL-038/schema.json') else 'b75389aefeb06ed750c9b7aa891ecc383af9ce1a'
        require(_blob(root,approved,name)==_blob(root,c['source_commit'],name),
                'source differs from exact accepted bytes: '+name)
    return result


def _authenticate_producer(root, p, c, base):
    q, review = _approval(root,base,p['task_id'],p['result_commit'],result=True,
                           path=p['acceptance_path'],digest=p['acceptance_sha256'])
    require(q['task_sha256'] == p['task_digest'] and exact(q['attempt'],p['attempt']), 'producer queue identity')
    nr = p['numerical_review']
    _, numerical = _approval(root,base,nr['task_id'],nr['reviewed_commit'],
        path=nr['acceptance_path'],digest=nr['acceptance_sha256'])
    require(numerical.get('reviewed_result_commit') == p['result_commit'] and
            numerical.get('producer_task_id') == p['task_id'] and numerical.get('result_verdict') == 'approve', 'independent numerical result approval required')
    receipt_raw = _blob(root,p['result_commit'],'handoff/'+p['task_id']+'/result.json')
    require(sha(receipt_raw) == p['receipt_sha256'], 'wrong original receipt')
    receipt = strict_json(receipt_raw)
    require(receipt.get('task_id') == p['task_id'] and exact(receipt.get('attempt'),p['attempt']) and
        receipt.get('role') == 'hy3' and receipt.get('task_sha256') == p['task_digest'] and
        receipt.get('status') == 'completed' and receipt.get('failure') is None and
        receipt.get('artifact_hash_basis') == 'canonical_git_blob' and
        receipt.get('started_from_pinned_source') is True, 'failed/wrong producer receipt')
    require(type(receipt.get('checks')) is list and receipt['checks'] and all(type(x.get('exit_code')) is int and x['exit_code']==0 for x in receipt['checks']), 'producer failed checks')
    # Runner receipts can also inventory handoff logs; exactly the 44 output files must match.
    rh = receipt['artifacts_sha256']
    require({k:v for k,v in rh.items() if k.startswith(p['root']+'/')} == p['artifacts_sha256'], 'receipt artifact inventory mismatch')
    require({k:v for k,v in review.get('artifacts_sha256',{}).items() if k.startswith(p['root']+'/')} == p['artifacts_sha256'], 'chief artifact inventory mismatch')
    require({n for n in q.get('accepted_paths',[]) if n.startswith(p['root']+'/')}==set(p['artifacts_sha256']), 'chief must accept all 44 producer files')
    actual_files = _files(_path(root,p['root']))
    require(actual_files == producer_files(), 'missing/extra producer file')
    raw = {}; consumed = {}
    for name,h in p['artifacts_sha256'].items():
        raw[name[len(p['root'])+1:]], consumed[name] = _entry(root,name,p['result_commit'],h)
    m = strict_json(raw['run_manifest.json']); keys(m,w.MANIFEST_KEYS)
    require(m['status']=='completed' and m['split']=='development' and m['group']==p['group'] and
            exact(m['fee_rate'],.0025 if p['group']=='primary' else .005), 'swapped/incomplete producer')
    require(exact(m['scenario_count'],120) and exact(m['periods'],30) and exact(m['horizons'],list(w.HORIZONS)), 'producer shape')
    pc = w.validate_config(m['configuration'])
    require(pc['group']==p['group'] and exact(pc['input'],c['input']) and
            all(pc['source_sha256'][n]==c['source_sha256'][n] for n in w.CLOSURE), 'mixed producer source/config/input')
    require(m['input_sha256']==c['input']['sha256'], 'producer input mismatch')
    prov=m['provenance']; keys(prov,('kind','binding','sources','python','dependencies'))
    require(prov['kind']=='published_production', 'producer is not production evidence')
    b=prov['binding']; pt=b['task']
    require(pt['id']==p['task_id'] and exact(pt['attempt'],p['attempt']) and
            receipt['base_commit']==pt['base_commit'] and b['task_digest']==p['task_digest'] and
            b['config_path']==p['config_path'], 'producer task binding mismatch')
    pr = _blob(root,pt['base_commit'],p['config_path'])
    require(exact(strict_json(pr),pc) and _text_match(_path(root,p['config_path']).read_bytes(),pr), 'producer configuration checkout mismatch')
    require(exact(w.bind_task(root,pc,p['config_path'],pr,p['root'],pt,b['publication_commit']),b), 'original C/E/P producer binding')
    require(prov['sources']['canonical']==pc['source_sha256'], 'false producer source attestation')
    for name,h in pc['source_sha256'].items():
        canonical_source=_blob(root,pc['source_commit'],name)
        require(sha(canonical_source)==h and prov['sources']['consumed'].get(name) in
                (h,sha(canonical_source.replace(b'\n',b'\r\n'))), 'producer consumed source mismatch')
    for name,key in (('calibrations.json','calibrations_sha256'),('reference_imports.json','references_sha256'),('checks.json','checks_sha256')):
        require(sha(_blob(root,p['result_commit'],p['root']+'/'+name))==m[key], 'producer root hash')
    cal=strict_json(raw['calibrations.json'])
    require(cal['attestation']['input_sha256']==c['input']['sha256'] and
            cal['attestation']['production_origin_verified'] is True and
            exact(cal['attestation']['scenario_count'],120) and exact(cal['attestation']['periods'],30), 'calibration identity')
    checks=strict_json(raw['checks.json'])
    require(checks['status']=='passed' and checks['prefix_replay'] is True, 'producer checks failed')
    imports=strict_json(raw['reference_imports.json'])
    if p['group']=='primary':
        # This accepted API reads exact old Git blobs only; it never reruns HY3-003.
        _, original = w.import_references(root,base,pc['references'][0])
        require(exact(imports,original), 'wrong original HY3-003 imports')
    else:
        require(exact(imports,dict(status='no_imports',modes=[])) and pc['references']==[], 'doubled imports forbidden')
    require(set(m['artifacts'])==producer_files()-{'run_manifest.json','checks.json','calibrations.json','reference_imports.json'}, 'producer case inventory')
    cases={}; counts={t:0 for t in w.TABLES}
    for mode in w.MODES:
        cases[mode]={}
        for table in w.TABLES:
            name='cases/'+mode+'/'+table+'.csv'; e=m['artifacts'][name]
            keys(e,('sha256','bytes','rows','schema','keys','applicable'))
            blobraw=_blob(root,p['result_commit'],p['root']+'/'+name)
            require(e['sha256']==sha(blobraw) and e['bytes']==len(blobraw) and
                    exact(e['schema'],[list(x) for x in w.SCHEMAS[table]]) and exact(e['keys'],list(w.KEYS[table])), 'declared producer schema/hash')
            records=w.decode_csv(raw[name],w.SCHEMAS[table],w.KEYS[table])
            require(type(e['rows']) is int and len(records)==e['rows'], 'producer row count')
            require(e['applicable'] is (not(mode in w.BASELINES and table in ('decisions','target_scores'))), 'producer applicability')
            for r in records:
                require(r['mode']==mode and r['split']=='development' and exact(r['fee_rate'],m['fee_rate']), 'case mixed identity')
                if 'growth_units' in r: require(r['growth_units']=='percent/year', 'producer unit mismatch')
            if table=='scenario_metrics':
                require([(r['scenario_id'],r['horizon']) for r in records]==[(s,h) for s in range(1,121) for h in w.HORIZONS], 'metric grid mismatch')
                require(all(r['fold_id']==(r['scenario_id']-1)%4 for r in records), 'fold mismatch')
            cases[mode][table]=records; counts[table]+=len(records)
    ec=w.expected_counts(p['group'])
    require(all(counts[t]==ec[t] for t in w.TABLES[:-1]) and counts['target_scores']<=ec['target_scores_max'] and exact(checks['counts'],counts), 'producer counts mismatch')
    return cases,dict(identity=p,consumed=consumed,manifest=m,calibration=cal)


def _bridge(groups, *, split, n, source_hashes):
    """Detached typed bridge. No numeric coercion, filling, or unit guessing."""
    require(set(groups)=={'primary','doubled'}, 'missing/extra bundle')
    rows=[]; sources=[]
    for group,fee in (('primary',.0025),('doubled',.005)):
        require(set(groups[group])==set(w.MODES), 'missing/extra mode')
        for mode in w.MODES:
            original=groups[group][mode]['scenario_metrics']
            require(len(original)==n*5, 'source metric count')
            for index,r in enumerate(original):
                # Accepted codec validates exact keys, booleans, nulls and binary64 types.
                w.encode_csv([r],w.SCHEMAS['scenario_metrics'])
                require(r['growth_units']=='percent/year' and r['split']==split and
                        r['mode']==mode and exact(r['fee_rate'],fee), 'unexpected bridge identity/unit')
                s,h=divmod(index,5)
                require((r['scenario_id'],r['horizon'],r['fold_id'])==(s+1,w.HORIZONS[h],s%4), 'bridge missing/duplicate key')
                detached=deepcopy(r);detached['growth_units']='percentage points per year'
                rows.append(detached)
                sources.append(dict(group=group,case=mode,row_key={k:r[k] for k in KEY_FIELDS},
                    source_blob_sha256=source_hashes[group][mode],source_row_sha256=sha(canonical(r)),
                    analysis_row_sha256=sha(canonical(detached))))
    mapping=dict(field='growth_units',source_literal='percent/year',
                 destination_literal='percentage points per year',direction='detached producer to analysis input',
                 numeric_conversion='none',source_schema=[list(x) for x in w.SCHEMAS['scenario_metrics']],
                 source_schema_sha256=sha(canonical(w.SCHEMAS['scenario_metrics'])))
    return rows,sources,mapping


def _authenticate(root,c,config_path,raw,output,task,P):
    binding=_bind(root,c,config_path,raw,output,task,P)
    sources=_sources(root,c);groups={};proofs=[];hashes={}
    for p in c['producers']:
        cases,proof=_authenticate_producer(root,p,c,task['base_commit'])
        groups[p['group']]=cases;proofs.append(proof)
        hashes[p['group']]={m:p['artifacts_sha256'][p['root']+'/cases/'+m+'/scenario_metrics.csv'] for m in w.MODES}
    require(exact(proofs[0]['calibration'],proofs[1]['calibration']), 'mixed calibration identity')
    metrics,metric_sources,mapping=_bridge(groups,split='development',n=120,source_hashes=hashes)
    return binding,sources,proofs,metrics,metric_sources,mapping


def _tables(metrics, config, split):
    # Exactly one accepted pure call; authentication has already completed.
    from .policy_analysis import build_analysis_tables
    return build_analysis_tables(metrics,config=config,split=split)


def _counts(t, metric_count):
    return dict(metric_rows=metric_count,paired_differences=len(t.paired_differences),
        comparison_gates=len(t.comparison_gates),selection=1,profile_screen=len(t.profile_screen),
        profile_recommendations=len(t.profile_recommendations))


def _encode_tables(t):
    return {FILES[0]:w.encode_csv(t.paired_differences,PAIRED_SCHEMA),
        **{name:w._json_bytes(getattr(t,attr)) for name,attr in zip(FILES[1:],
            ('comparison_gates','selection','profile_screen','profile_recommendations'))}}


def _execution_records(records,c):
    require(type(records) is list and len(records)==2, 'two actual child checks required')
    for r,p in zip(records,c['producers']):
        keys(r,('group','argv','returncode','elapsed_seconds','stdout','stderr','stdout_sha256',
                'stderr_sha256','python','pythonpath_absent','script_sha256'))
        expected=['-B','scripts/run_development_policy.py','--config',p['config_path'],'--output',p['root'],'--check']
        require(r['group']==p['group'] and type(r['argv']) is list and len(r['argv'])==8 and
                r['argv'][1:]==expected and type(r['argv'][0]) is str, 'checker argv mismatch')
        require(type(r['returncode']) is int and r['returncode']==0, 'failed child is authentication failure')
        require(type(r['elapsed_seconds']) is float and 0<=r['elapsed_seconds']<=c['execution']['max_seconds'], 'child timing')
        require(type(r['stdout']) is str and type(r['stderr']) is str and
            sha(r['stdout'].encode())==r['stdout_sha256'] and sha(r['stderr'].encode())==r['stderr_sha256'], 'checker log hash')
        require(r['pythonpath_absent'] is True and type(r['python']) is str and
                re.fullmatch(r'3\.12\.[0-9]+',r['python']) and
                r['script_sha256']==c['source_sha256']['scripts/run_development_policy.py'], 'checker runtime/source')
        report=strict_json(r['stdout'].strip())
        require(exact(report,dict(status='passed',read_only=True,result='passed')), 'checker did not report successful read-only check')


def _persist(stage,started,*,root,c,binding,sources,proofs,metrics,metric_sources,mapping,records,split='development'):
    tables=_tables(metrics,strict_json(_path(root,POLICY).read_bytes()),split)
    expected=EXPECTED if split=='development' else dict(EXPECTED,metric_rows=len(metrics),paired_differences=len(metrics)//80*100)
    counts=_counts(tables,len(metrics));require(exact(counts,expected), 'complete analysis counts required')
    artifacts={}
    for name,raw in _encode_tables(tables).items():
        w._write(stage/name,raw,c['execution']['max_artifact_bytes'])
        artifacts[name]=dict(sha256=sha(raw),bytes=len(raw),rows=counts[name.split('.')[0]])
    schema=dict(paired_differences=[list(x) for x in PAIRED_SCHEMA],
                nested_json='strict UTF-8 JSON; exact recursive types/keys/finite binary64',
                schema_sha256=c['source_sha256'].get('audit/SOL-038/schema.json'))
    manifest=dict(schema_version=1,status='completed',split=split,configuration=c,binding=binding,
        sources=sources,producers=proofs,mapping=mapping,metric_rows=len(metrics),
        metric_input_sha256=sha(canonical(metrics)),metric_sources=metric_sources,schema=schema,
        counts=counts,artifacts=artifacts,checker_executions=records,python=platform.python_version(),
        elapsed_seconds=time.monotonic()-started,max_seconds=c['execution']['max_seconds'],
        max_artifact_bytes=c['execution']['max_artifact_bytes'])
    w._write(stage/'run_manifest.json',canonical(manifest)+b'\n',c['execution']['max_artifact_bytes'])
    return manifest


def produce_authenticated(root,config_path,output,stage,started,records):
    """Only called by the stdlib-only CLI after its actual successful children."""
    root=Path(root).resolve();raw=_path(root,config_path).read_bytes();c=validate_config(strict_json(raw))
    require(sys.version_info[:2]==(3,12),'Python 3.12 required')
    task=strict_json((root/'.runtime/task.json').read_bytes())
    P=w.git(root,'rev-parse','origin/main').decode().strip()
    b,s,p,m,ms,mp=_authenticate(root,c,config_path,raw,output,task,P)
    _execution_records(records,c)
    require(time.monotonic()-started<=c['execution']['max_seconds'],'authentication runtime budget')
    return _persist(stage,started,root=root,c=c,binding=b,sources=s,proofs=p,metrics=m,
                    metric_sources=ms,mapping=mp,records=records)


def _compare_output(output,m,tables):
    require(_files(output)==set(FILES)|{'run_manifest.json'}, 'missing/extra assembly file')
    require(exact(m['counts'],_counts(tables,m['metric_rows'])), 'wrong saved counts')
    require(set(m['artifacts'])==set(FILES), 'output inventory')
    for name,expected_raw in _encode_tables(tables).items():
        e=m['artifacts'][name];keys(e,('sha256','bytes','rows'))
        raw=_path(output,name).read_bytes()
        require(len(raw)<=LIMIT and exact(e,dict(sha256=sha(raw),bytes=len(raw),rows=m['counts'][name.split('.')[0]])), 'output hash/bytes/count mismatch')
        if name.endswith('.csv'):
            saved=w.decode_csv(raw,PAIRED_SCHEMA,PAIRED_KEYS)
            expected=w.decode_csv(expected_raw,PAIRED_SCHEMA,PAIRED_KEYS)
        else:
            saved=strict_json(raw);expected=strict_json(expected_raw)
        require(exact(saved,expected), 'saved output types/numbers/keys differ: '+name)


def check_production(root,config_path,output):
    """Read-only historical replay: no children, input reads or evidence writes."""
    require(sys.version_info[:2]==(3,12),'Python 3.12 required')
    root=Path(root).resolve();output=_path(root,output)
    raw_manifest=(output/'run_manifest.json').read_bytes();require(len(raw_manifest)<=LIMIT,'manifest size')
    m=strict_json(raw_manifest);keys(m,MANIFEST_KEYS)
    require(m['status']=='completed' and m['split']=='development','incomplete or nonproduction status')
    c=validate_config(m['configuration']);b=m['binding']
    require(b['config_path']==config_path,'wrong check config')
    raw=_path(root,config_path).read_bytes()
    actual,sources,proofs,metrics,ms,mapping=_authenticate(root,c,config_path,raw,
        output.relative_to(root).as_posix(),b['task'],b['publication_commit'])
    require(exact(actual,b) and exact(proofs,m['producers']), 'false source/task/producer provenance')
    # Historical LF/CRLF checkout records are authenticated individually, not overwritten.
    require(set(m['sources'])==set(sources),'false source closure')
    for name,s in m['sources'].items():
        keys(s,('canonical_sha256','consumed_sha256','bytes'))
        obj=_blob(root,c['source_commit'],name)
        require(s['canonical_sha256']==c['source_sha256'][name] and
            (s['consumed_sha256'],s['bytes']) in {(sha(obj),len(obj)),(sha(obj.replace(b'\n',b'\r\n')),len(obj.replace(b'\n',b'\r\n')))}, 'false historical consumed source')
    require(exact(mapping,m['mapping']) and exact(ms,m['metric_sources']) and
            exact(m['metric_rows'],9600) and m['metric_input_sha256']==sha(canonical(metrics)), 'false typed mapping/source rows')
    require(exact(m['schema'],dict(paired_differences=[list(x) for x in PAIRED_SCHEMA],
        nested_json='strict UTF-8 JSON; exact recursive types/keys/finite binary64',schema_sha256=c['source_sha256']['audit/SOL-038/schema.json'])), 'false output schema')
    require(exact(m['counts'],EXPECTED),'wrong expected counts')
    _execution_records(m['checker_executions'],c)
    require(type(m['python']) is str and re.fullmatch(r'3\.12\.[0-9]+',m['python']) and
        exact(m['max_seconds'],c['execution']['max_seconds']) and exact(m['max_artifact_bytes'],LIMIT) and
        type(m['elapsed_seconds']) is float and 0<=m['elapsed_seconds']<=m['max_seconds'], 'false runtime provenance')
    tables=_tables(metrics,strict_json(_path(root,POLICY).read_bytes()),'development')
    _compare_output(output,m,tables)
    return dict(status='passed',read_only=True,metric_rows=9600)


def _synthetic_persist(output,root,groups,hashes,*,binding=None):
    """PRIVATE generated metric seam; no production configuration can select it."""
    metrics,ms,mapping=_bridge(groups,split='synthetic',n=4,source_hashes=hashes)
    c={'execution':dict(max_seconds=1500,max_artifact_bytes=LIMIT),'source_sha256':{}}
    return w._stage_output(output,lambda stage,start:_persist(stage,start,root=root,c=c,
        binding=binding or {'kind':'PRIVATE GENERATED METRICS'},sources={},proofs=[],metrics=metrics,
        metric_sources=ms,mapping=mapping,records=[],split='synthetic'))


def _synthetic_check(output,root,groups,hashes):
    """PRIVATE read-only generated replay, never reachable from CLI."""
    m=strict_json((Path(output)/'run_manifest.json').read_bytes());keys(m,MANIFEST_KEYS)
    require(m['status']=='completed' and m['split']=='synthetic','incomplete synthetic fixture')
    metrics,ms,mapping=_bridge(groups,split='synthetic',n=4,source_hashes=hashes)
    require(exact(m['metric_sources'],ms) and exact(m['mapping'],mapping) and
        m['metric_input_sha256']==sha(canonical(metrics)) and exact(m['metric_rows'],320), 'synthetic provenance corruption')
    require(exact(m['binding'],{'kind':'PRIVATE GENERATED METRICS'}) and m['sources']=={} and m['producers']==[] and m['checker_executions']==[], 'false synthetic provenance')
    t=_tables(metrics,strict_json(_path(root,POLICY).read_bytes()),'synthetic')
    _compare_output(Path(output),m,t)
    return t
