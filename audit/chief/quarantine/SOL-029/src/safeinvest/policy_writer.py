"""Bounded case persistence. Import is inert; production has no synthetic switch.

All arithmetic fixtures enter through private Python seams. The CLI authenticates
published C/E/P objects before opening the single fixed development input.
"""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
import traceback
import uuid

from .policy_calibration import FIELDS, build_synthetic_calibrations
from .policy_cases import CaseTables, build_case_tables
from .experiments import COMMON_UNITS

MODES = ('conservative_cost','balanced_cost','growth_cost','balanced_context',
         'balanced_adaptive','bills_keep','equal_weight_annual','equal_weight_buy_hold')
BASELINES = MODES[5:]
TABLES = ('annual_ledgers','scenario_metrics','summary','decisions','target_scores')
HORIZONS = (5,6,15,25,30)
INPUT_PATH = 'data/development/scenarios_001_120.csv'
INPUT_HASH = '9c4ad83f5dda86251a754e126528a71dd930ae88ed7cdb8a0663a327b6bfb7c7'
REFERENCE_COMMIT = '7652410d73425371110784ef5fa97c03470a074e'
LIMIT = 10485760
POLICY = 'specs/development_policy_pilot_v2.json'
LAYOUT = 'specs/policy_driver_layout_v2.json'
CLOSURE = tuple('src/safeinvest/'+n+'.py' for n in
                ('__init__','accounting','backtest','baselines','metrics','experiments',
                 'policy_pilot','policy_calibration','policy_cases','policy_writer')) + (
    'scripts/run_development_policy.py', POLICY, LAYOUT,
    'specs/PROBLEM_LOCK.md','specs/ACCOUNTING.md','specs/DEVELOPMENT_POLICY_PILOT_V2.md',
    'specs/POLICY_CORRECTION_V2.md','specs/POLICY_NUMERIC_K1.md','specs/POLICY_NUMERIC_K2.md',
    'specs/POLICY_CASE_ENGINE.md','specs/POLICY_RESULT_WRITER.md',
    'specs/POLICY_WRITER_COMPATIBILITY.md','specs/POLICY_WRITER_ACCEPTANCE_REFERENCES.md',
    'specs/POLICY_WRITER_EXECUTION_CONFIG.md','specs/POLICY_WRITER_TASK_BINDING.md',
    'specs/POLICY_WRITER_RECOVERY.md')
CONFIG_KEYS = ('schema_version','run_id','split','execution_authorized','source_commit',
 'source_sha256','acceptance','input','policy_config','layout_config','group','horizons',
 'references','expected_counts','execution')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()


def _pairs(pairs):
    result = {}
    for k,v in pairs:
        require(k not in result, 'duplicate JSON key: '+k)
        result[k] = v
    return result


def strict_json(data):
    if type(data) is bytes:
        data=data.decode('utf-8',errors='strict')
    require(type(data) is str,'UTF-8 JSON text required')
    def number(text):
        value=float(text)
        require(math.isfinite(value),'nonfinite JSON number')
        return value
    return json.loads(data,object_pairs_hook=_pairs,parse_float=number,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def keys(value, expected):
    require(type(value) is dict and set(value)==set(expected), 'unknown/missing object keys')


def integer(v, lo=0, hi=None):
    require(type(v) is int and v>=lo and (hi is None or v<=hi), 'invalid integer')


def hash_string(v, n=64):
    require(type(v) is str and re.fullmatch('[0-9a-f]{'+str(n)+'}',v), 'invalid digest')


def exact(a,b):
    if type(a) is not type(b):
        return False
    if type(a) is float:
        return a.hex()==b.hex()
    if type(a) is dict:
        return a.keys()==b.keys() and all(exact(a[k],b[k]) for k in a)
    if type(a) in (list,tuple):
        return len(a)==len(b) and all(exact(x,y) for x,y in zip(a,b))
    return a==b


def _schema(text):
    # Explicit declarations; ? means nullable. No inference from observed cells.
    return tuple((a.split(':')[0], a.split(':')[1].rstrip('?'),a.endswith('?')) for a in text.split())


_UNITS = ' '.join(k+':str' for k in COMMON_UNITS)
_BASE = 'split:str mode:str'
_VEC = ' '.join(p+'_'+a+':float'+('?' if p=='target' else '')
                for p in ('target','holdings_before','holdings_after_fee','holdings_end','return')
                for a in ('equity','bond','bill_proxy'))
_DIAGNOSTICS = ('human_review_count:int? human_review_share_pct:float? first_latch_year:int? '
                'target_change_count:int? first_deployment_year:int? initial_allocation_deferred:bool?')
SCHEMAS = {
 'annual_ledgers':_schema(_BASE+' scenario_id:int period:int engine_action:str '+_VEC+' '+
 'wealth_before:float cpi_before:float real_wealth_before:float intended_transfer:float fee:float '
 'wealth_after_fee:float real_wealth_after_fee:float inflation:float wealth_end:float cpi_end:float '
 'real_wealth_end:float annual_net_real_return:float '+_UNITS+' fee_rate:float fold_id:int'),
 'scenario_metrics':_schema(_BASE+' scenario_id:int horizon:int net_real_cagr_pct:float '
 'annual_real_volatility_pct:float? max_real_drawdown_pct:float terminal_real_wealth:float nominal_fee_sum:float '
 'trade_count:int review_count:int later_trade_count:int later_review_count:int trade_share_pct:float '
 'trade_share_ex_initial_pct:float? drawdown_peak_year:int drawdown_peak_kind:str drawdown_trough_year:int '
 'drawdown_trough_kind:str '+_UNITS+' fee_rate:float fold_id:int '+_DIAGNOSTICS),
 'summary':_schema(_BASE+' horizon:int scenario_count:int median_growth_pct:float p10_growth_pct:float '
 'median_loss_pct:float p90_loss_pct:float median_volatility_pct:float? median_terminal_real_wealth:float '
 'median_nominal_fee_sum:float pooled_trade_count:int pooled_review_count:int pooled_later_trade_count:int '
 'pooled_later_review_count:int pooled_trade_share_pct:float pooled_trade_share_ex_initial_pct:float? '
 'severe_scenario_id:int severe_net_real_cagr_pct:float severe_max_real_drawdown_pct:float '
 'severe_terminal_real_wealth:float severe_drawdown_peak_year:int severe_drawdown_peak_kind:str '
 'severe_drawdown_trough_year:int severe_drawdown_trough_kind:str severe_trade_share_pct:float '
 'severe_trade_share_ex_initial_pct:float? '+_UNITS+' fee_rate:float pooled_human_review_count:int? '
 'pooled_human_review_share_pct:float? pooled_target_change_count:int?'),
 'decisions':_schema(_BASE+' fee_rate:float scenario_id:int fold_id:int period:int action:str '
 'active_before:str active_after:str proposed_target:str? selected_target:str? ce_keep:float? '
 'prior_mass:float recent_count:int observed_max_drawdown_pct:float human_review_latched:bool '
 'initial_allocation_deferred:bool intended_transfer:float actual_fee:float is_trade:bool '
 'executed_target_change:bool reason:str first_deployment_year:int?'),
 'target_scores':_schema(_BASE+' fee_rate:float scenario_id:int fold_id:int period:int target_name:str '
 'target_equity:float target_bond:float target_bill_proxy:float ce_target:float tau:float fee_fraction:float '
 'pre_cost_benefit:float modeled_fee_impact:float conservative_score:float true_net_ce:float')}
KEYS = {'annual_ledgers':('scenario_id','period'), 'scenario_metrics':('scenario_id','horizon'),
        'summary':('horizon',), 'decisions':('scenario_id','period'),
        'target_scores':('scenario_id','period','target_name')}


def _encode(value, typ, nullable):
    if value is None:
        require(nullable,'nonnullable empty cell')
        return ''
    require(type(value).__name__==typ,'wrong column type: '+typ)
    if typ=='float':
        require(math.isfinite(value),'nonfinite float')
        return repr(value)
    if typ=='bool':
        return 'true' if value else 'false'
    require(typ!='str' or value!='','empty string cannot alias null')
    return str(value)


def _decode(value, typ, nullable):
    if value=='':
        require(nullable,'nonnullable empty cell')
        return None
    if typ=='str':
        return value
    if typ=='bool':
        require(value in ('true','false'),'malformed boolean')
        return value=='true'
    if typ=='int':
        require(re.fullmatch(r'-?(0|[1-9][0-9]*)',value) is not None,'malformed integer')
        return int(value)
    require(typ=='float' and re.fullmatch(r'-?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?',value),
            'malformed float')
    v=float(value)
    require(math.isfinite(v),'nonfinite float')
    return v


def encode_csv(rows, schema):
    out=io.StringIO(newline='')
    writer=csv.writer(out,lineterminator='\n')
    names=[a for a,_,_ in schema]
    writer.writerow(names)
    for row in rows:
        require(set(row)==set(names),'missing/extra CSV columns')
        writer.writerow([_encode(row[n],t,q) for n,t,q in schema])
    return out.getvalue().encode()


def decode_csv(data, schema, key_fields=()):
    reader=csv.reader(io.StringIO(data.decode('utf-8'),newline=''),strict=True)
    names=[n for n,_,_ in schema]
    require(next(reader,None)==names,'missing/extra/duplicate/order CSV columns')
    rows=[]; seen=set()
    for cells in reader:
        require(len(cells)==len(names),'malformed CSV row')
        row={n:_decode(v,t,q) for (n,t,q),v in zip(schema,cells)}
        if key_fields:
            k=tuple(row[n] for n in key_fields)
            require(k not in seen,'duplicate row key')
            seen.add(k)
        rows.append(row)
    return rows


def expected_counts(group):
    require(group in ('primary','doubled'),'fixed group required')
    return dict(cases=8,new_cases=5 if group=='primary' else 8,
                imported_cases=3 if group=='primary' else 0,annual_ledgers=28800,
                scenario_metrics=4800,summary=40,decisions=18000,target_scores_max=24000)


def validate_config(c, task_budget=1500):
    keys(c,CONFIG_KEYS)
    integer(c['schema_version'],1,1)
    require(type(c['run_id']) is str and re.fullmatch(r'[A-Za-z0-9_-]+',c['run_id']),'invalid run_id')
    require(c['split']=='development' and c['execution_authorized'] is True,'no execution authorization')
    hash_string(c['source_commit'],40)
    require(type(c['source_sha256']) is dict and set(c['source_sha256'])==set(CLOSURE),'incomplete source closure')
    for h in c['source_sha256'].values(): hash_string(h)
    require(type(c['acceptance']) is dict and set(c['acceptance'])>={'SOL-021','SOL-022','SOL-025','SOL-029'},
            'positive kernel/calibration/case/writer approvals required')
    for h in c['acceptance'].values(): hash_string(h,40)
    keys(c['input'],('path','sha256','scenario_ids','periods'))
    require(exact(c['input'],dict(path=INPUT_PATH,sha256=INPUT_HASH,scenario_ids=[1,120],periods=30)),
            'fixed development input only')
    for k,p in (('policy_config',POLICY),('layout_config',LAYOUT)):
        keys(c[k],('path','sha256'))
        require(c[k]['path']==p and c[k]['sha256']==c['source_sha256'][p],'configuration source mismatch')
    require(exact(c['horizons'],list(HORIZONS)),'fixed horizons required')
    require(exact(c['expected_counts'],expected_counts(c['group'])),'wrong structural counts/types')
    keys(c['execution'],('cpu_only','required_python','max_seconds','max_artifact_bytes'))
    e=c['execution']
    require(e['cpu_only'] is True and e['required_python']=='3.12','Python 3.12 CPU only')
    integer(e['max_seconds'],1,min(1500,task_budget)); integer(e['max_artifact_bytes'],LIMIT,LIMIT)
    require(type(c['references']) is list,'references list required')
    if c['group']=='doubled':
        require(c['references']==[],'doubled imports inapplicable')
    else:
        require(len(c['references'])==1,'exact primary reference required')
        r=c['references'][0]
        keys(r,('task_id','reviewed_commit','receipt_sha256','artifacts_sha256'))
        require(r['task_id']=='HY3-003' and r['reviewed_commit']==REFERENCE_COMMIT,'wrong reference identity')
        hash_string(r['receipt_sha256'])
        require(type(r['artifacts_sha256']) is dict and set(r['artifacts_sha256'])=={
            'results/development/HY3-003/'+x for x in
            ('annual_ledgers.csv','scenario_metrics.csv','summary.csv','run_manifest.json','checks.json')},
            'exact five reference artifact paths required')
        for h in r['artifacts_sha256'].values():hash_string(h)
    return c


def git(root,*args):
    return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.PIPE)


def blob(root,commit,name):
    hash_string(commit,40)
    return git(root,'show',commit+':'+name)


def ancestor(root,a,b):
    for c in (a,b):
        hash_string(c,40)
        require(git(root,'cat-file','-t',c).strip()==b'commit','not a commit')
    require(subprocess.run(['git','merge-base','--is-ancestor',a,b],cwd=root,
                           capture_output=True).returncode==0,'invalid commit ancestry')


def safe_path(root,name):
    root=Path(root).resolve()
    require(type(name) is str and name and '\\' not in name,'relative POSIX path required')
    p=root/name
    require(not Path(name).is_absolute() and '..' not in Path(name).parts,'path escape')
    require(p.resolve()==p and all(not x.is_symlink() for x in (p,*p.parents) if x!=root.parent),
            'symlink/reparse escape')
    return p


def source_snapshot(root,c):
    canonical_hashes={}; consumed={}; imported={}
    for name,h in c['source_sha256'].items():
        data=blob(root,c['source_commit'],name)
        require(sha(data)==h,'canonical source mismatch: '+name)
        actual=safe_path(root,name).read_bytes()
        require(actual in (data,data.replace(b'\n',b'\r\n')),'checkout source mismatch: '+name)
        canonical_hashes[name]=h; consumed[name]=sha(actual)
    for name,module in tuple(sys.modules.items()):
        if name=='safeinvest' or name.startswith('safeinvest.'):
            p=Path(module.__file__).resolve()
            rel='src/safeinvest/'+p.name
            require(rel in canonical_hashes,'unlisted imported computational module: '+name)
            data=p.read_bytes()
            require(sha(data.replace(b'\r\n',b'\n'))==canonical_hashes[rel], 'imported source mismatch')
            require(p==safe_path(root,rel),'imported module outside authenticated checkout')
            imported[name]={'path':str(p),'relative_path':rel,'sha256':sha(data)}
    return dict(canonical=canonical_hashes,consumed=consumed,imported=imported)


def validate_publication(root,task,P):
    require(type(task.get('id')) is str and re.fullmatch(r'[A-Za-z0-9_-]+',task['id']),'invalid task id')
    integer(task['attempt'],1); hash_string(task['base_commit'],40)
    E=task['base_commit']; ancestor(root,E,P)
    origin=git(root,'rev-parse','origin/main').decode().strip(); ancestor(root,P,origin)
    name='ops/tasks/'+task['id']+'.json'; raw=blob(root,P,name)
    published=strict_json(raw)
    require(exact(published,task),'published/runtime task mismatch')
    queue=strict_json(blob(root,P,'ops/queue.json'))
    matches=[q for q in queue['tasks'] if q['id']==task['id']]
    require(len(matches)==1,'published queue task missing/duplicate')
    q=matches[0]; digest=sha(canonical(task))
    require(q['task_sha256']==digest and q['state']=='ready' and
            q['owner']==task['owner']=='hy3' and task['kind']=='commands' and
            type(task['attempt']) is int and exact(q['attempt'],task['attempt']) and
            q['branch']=='work/hy3/'+task['id']+'-a'+str(task['attempt']), 'published queue binding mismatch')
    return dict(publication_commit=P,task_blob_sha256=sha(raw),task_digest=digest,
                task_id=task['id'],attempt=task['attempt'],base_commit=E,owner='hy3',kind='commands')


def bind_task(root,c,config_path,config_raw,output,task,P):
    integer(task['max_seconds'],1,1500)
    validate_config(c,task['max_seconds'])
    binding=validate_publication(root,task,P)
    E=task['base_commit']; ancestor(root,c['source_commit'],E)
    require(task['split']=='development','task split mismatch')
    pinned_config=blob(root,E,config_path)
    require(config_raw in (pinned_config,pinned_config.replace(b'\n',b'\r\n')),'base config mismatch')
    # These names mirror the configuration, avoiding a second ad hoc parameter vocabulary.
    p=task['parameters']
    require(p.get('config_path')==config_path and p.get('config_sha256')==sha(blob(root,E,config_path)),
            'task config pin mismatch')
    for k in CONFIG_KEYS:
        require(k in p and exact(p[k],c[k]),'task parameter mismatch: '+k)
    rel=safe_path(root,output).relative_to(Path(root).resolve()).as_posix()
    require(rel in task['deliverables'],'undeclared output root')
    command=['{python}','-B','scripts/run_development_policy.py','--config',config_path,'--output',rel]
    require(command in task['commands'],'fixed CLI command mismatch')
    queue=strict_json(blob(root,E,'ops/queue.json'))
    for ident,commit in c['acceptance'].items():
        entries=[q for q in queue['tasks'] if q['id']==ident]
        require(len(entries)==1,'dependency missing/duplicate')
        q=entries[0]
        require(q['state']=='accepted' and q['reviewed_commit']==commit and q.get('code_verdict')=='approve',
                'dependency lacks exact positive approval')
        review=strict_json(blob(root,E,q['acceptance_evidence']))
        require(review['task_id']==ident and review['reviewed_commit']==commit and
                review.get('code_verdict')=='approve','chief acceptance mismatch')
    binding.update(config_path=config_path,config_blob_sha256=sha(blob(root,E,config_path)),
                   source_commit=c['source_commit'],task=task,output=rel)
    return binding


def load_fixed_input(root):
    data=safe_path(root,INPUT_PATH).read_bytes()
    require(sha(data)==INPUT_HASH,'raw input hash mismatch')
    rows=_input_rows(data,120,30)
    return data,rows


def _input_rows(data,n,t):
    reader=csv.DictReader(io.StringIO(data.decode('utf-8'),newline=''))
    require(tuple(reader.fieldnames or ())==FIELDS,'six ordered input fields required')
    rows=list(reader)
    require(len(rows)==n*t,'input grid count mismatch')
    for j,r in enumerate(rows):
        s,p=divmod(j,t)
        require(tuple(r)==FIELDS and r['scenario_id']==str(s+1) and r['period']==str(p+1),
                'input grid keys mismatch')
        for k in FIELDS[2:]:
            require(math.isfinite(float(r[k])) and float(r[k])>-1,'invalid input factor')
    return rows


def calibration_attestation(data,rows,n,t,bundle,split):
    require(bundle.input_sha256==sha(data) and bundle.input_bytes==len(data) and
            (bundle.scenario_count,bundle.periods)==(n,t),'calibration input mismatch')
    records=[]
    for f,c in enumerate(bundle.folds):
        train=tuple(s for s in range(1,n+1) if (s-1)%4!=f)
        evaluation=tuple(s for s in range(1,n+1) if (s-1)%4==f)
        selected=[r for r in rows if int(r['scenario_id']) in train]
        rowkeys=tuple((int(r['scenario_id']),int(r['period'])) for r in selected)
        nominal=[[int(r['scenario_id']),int(r['period']),*(float(r[k]).hex() for k in FIELDS[2:])] for r in selected]
        gross=tuple(tuple((1+float(r[k]))/(1+float(r['inflation'])) for k in FIELDS[2:5]) for r in selected)
        require(c.fold==f and c.training_ids==train and c.evaluation_ids==evaluation and c.training_keys==rowkeys,
                'calibration membership/key mismatch')
        rh=sha(canonical(dict(schema='training-annual-simple-v1',fields=list(FIELDS),rows=nominal)))
        gh=sha(canonical(dict(schema='training-real-gross-v1',asset_order=list(FIELDS[2:5]),
                    rows=[[*key,*(x.hex() for x in g)] for key,g in zip(rowkeys,gross)])))
        require(c.training_rows_sha256==rh and c.real_gross_sha256==gh and exact(c.prior.gross,gross),
                'calibration digest/support mismatch')
        records.append(c.manifest())
    require(len(records)==4 and bundle.manifest()['split']=='synthetic','unchanged arithmetic manifest required')
    return dict(schema_version=1,split=split,input_sha256=sha(data),input_bytes=len(data),
                scenario_count=n,periods=t,arithmetic_seam='build_synthetic_calibrations; unchanged synthetic object',
                production_origin_verified=split=='development',folds=records)


def import_references(root, evidence_commit, declared=None):
    """Authenticate exact accepted Git blobs; no baseline callback is reachable."""
    receipt_raw=blob(root,REFERENCE_COMMIT,'handoff/HY3-003/result.json')
    receipt=strict_json(receipt_raw)
    review=strict_json(blob(root,evidence_commit,'audit/chief/HY3-003-review.json'))
    oracle=strict_json(blob(root,evidence_commit,'audit/chief/writer-reference.json'))
    require(review['reviewed_commit']==REFERENCE_COMMIT and
            review['status']=='accepted_development_baseline_evidence','reference not positively accepted')
    require(oracle['baseline_receipt_sha256']==sha(receipt_raw),'oracle receipt mismatch')
    paths=['results/development/HY3-003/'+name for name in
           ('annual_ledgers.csv','scenario_metrics.csv','summary.csv','run_manifest.json','checks.json')]
    blobs={p:blob(root,REFERENCE_COMMIT,p) for p in paths}
    for p,data in blobs.items():
        require(sha(data)==receipt['artifacts_sha256'][p]==review['artifacts_sha256'][p],
                'reference artifact authentication failed')
    index=dict(task_id='HY3-003',reviewed_commit=REFERENCE_COMMIT,receipt_sha256=sha(receipt_raw),
               artifacts_sha256={p:sha(b) for p,b in blobs.items()})
    if declared is not None: require(exact(declared,index),'declared reference mismatch')
    by_mode={m:{} for m in BASELINES}
    renames={'policy':'mode','year':'period','action':'engine_action'}
    for table in TABLES[:3]:
        p='results/development/HY3-003/'+table+'.csv'
        oracle_table=oracle['source_artifacts'][table+'.csv']
        reader=csv.DictReader(io.StringIO(blobs[p].decode(),newline=''))
        require(reader.fieldnames==oracle_table['source_fields'],'reference schema mismatch')
        source=list(reader)
        require(len(source)==oracle_table['count'],'reference count mismatch')
        for mode in BASELINES:
            selected=[r for r in source if r['policy']==mode]
            expected=next(x for x in oracle_table['by_mode'] if x['mode']==mode)
            require(sha(canonical(selected))==expected['source_cells_sha256'],'reference source cells mismatch')
            normalized=[]; strings=[]
            for row in selected:
                require(row['growth_units']=='percentage points per year','unexpected growth unit')
                mapped={renames.get(k,k):('percent/year' if k=='growth_units' else v) for k,v in row.items()}
                strings.append(mapped)
                typed={}
                declarations={n:(t,q) for n,t,q in SCHEMAS[table]}
                for k,v in mapped.items(): typed[k]=_decode(v,*declarations[k])
                typed['fee_rate']=.0025
                if table!='summary': typed['fold_id']=(typed['scenario_id']-1)%4
                for n,t,q in SCHEMAS[table]:
                    if n not in typed:
                        require(q,'missing inherited required field'); typed[n]=None
                normalized.append(typed)
            require(sha(canonical(strings))==expected['normalized_reference_cells_sha256'],
                    'lossless mapping mismatch')
            # Typed CSV round-trip also checks full unique original keys.
            normalized=decode_csv(encode_csv(normalized,SCHEMAS[table]),SCHEMAS[table],KEYS[table])
            by_mode[mode][table]=tuple(normalized)
    cases={}
    for mode,tables in by_mode.items():
        tables.update(decisions=(),target_scores=())
        cases[mode]=CaseTables(**tables,counts={k:len(v) for k,v in tables.items()},units={},
             metadata=dict(diagnostics_applicable=False,imported=True))
    index.update(modes=list(BASELINES),status='authenticated_import',
                 legacy_growth_units='percentage points per year',growth_units='percent/year',
                 renames=renames,numeric_conversion='none',baseline_simulation=False)
    return cases,index


def _close(a,b,label,rel=2e-12):
    # No absolute tolerance: zero cannot swallow a positive fee or transfer.
    require(type(a) in (int,float) and math.isfinite(a) and
            (a==b if a==0 or b==0 else math.isclose(a,b,rel_tol=rel,abs_tol=0)),
            'independent identity: '+label)


def _q(values,p):
    v=sorted(values); x=(len(v)-1)*p; i=int(x); f=x-i
    return (1.0-f)*v[i]+f*v[min(i+1,len(v)-1)]


def check_case(tables,mode,fee,rows,n,t,horizons,split,calibration):
    """Scalar identities plus prefix-only decision replay; no experiment rebuild."""
    from .policy_pilot import CostAwarePolicy
    from .backtest import Observation, DecisionContext
    from dataclasses import fields
    from .policy_pilot import PolicyReview
    case={k:list(getattr(tables,k)) for k in TABLES}
    expected={'annual_ledgers':[(s,p) for s in range(1,n+1) for p in range(1,t+1)],
              'scenario_metrics':[(s,h) for s in range(1,n+1) for h in horizons],
              'summary':[(h,) for h in horizons]}
    if mode not in BASELINES: expected['decisions']=expected['annual_ledgers']
    for name,records in case.items():
        encoded=encode_csv(records,SCHEMAS[name]); decoded=decode_csv(encoded,SCHEMAS[name],KEYS[name])
        require(exact(decoded,records),'typed round-trip mismatch')
        actualkeys=[tuple(r[k] for k in KEYS[name]) for r in records]
        if name in expected: require(actualkeys==expected[name],'missing/extra/unordered keys: '+name)
        if mode in BASELINES and name in ('decisions','target_scores'):require(not records,'baseline sidecar inapplicable')
        for r in records:
            require(r['split']==split and r['mode']==mode and exact(r['fee_rate'],fee),'case identity mismatch')
            for k,v in COMMON_UNITS.items():
                if k in r: require(r[k]==('percent/year' if k=='growth_units' else v),'units mismatch')
            if 'fold_id' in r:require(r['fold_id']==(r['scenario_id']-1)%4,'fold key mismatch')
    decisions={(r['scenario_id'],r['period']):r for r in case['decisions']}
    scorekeys={(r['scenario_id'],r['period'],r['target_name']) for r in case['target_scores']}
    facts=0
    assets=('equity','bond','bill_proxy')
    for s in range(1,n+1):
        ledger=case['annual_ledgers'][(s-1)*t:s*t]
        previous=(0.,0.,100.); cpi=1.; real=100.; history=[]; latched=False
        policy=CostAwarePolicy(mode,calibration.folds[(s-1)%4].prior,fee_rate=fee,review_drawdown_pct=25.) if mode not in BASELINES else None
        peak=100.; loss=0.; peak_at=selected_peak=selected_trough=(0,'initial')
        returns=[]; snapshot=[]
        for p,r in enumerate(ledger,1):
            before=tuple(r['holdings_before_'+a] for a in assets)
            after=tuple(r['holdings_after_fee_'+a] for a in assets)
            end=tuple(r['holdings_end_'+a] for a in assets)
            target=tuple(r['target_'+a] for a in assets)
            require(all(math.isfinite(x) and x>=0 for x in (*before,*after,*end)),'negative/nonfinite holdings')
            require(exact(before,previous),'holdings continuity')
            require(exact(r['wealth_before'],math.fsum(before)),'exact wealth before')
            require(exact(r['wealth_after_fee'],math.fsum(after)),'exact wealth after')
            require(exact(r['wealth_end'],math.fsum(end)),'exact wealth end')
            if r['engine_action']=='keep':
                require(exact(before,after) and r['fee']==0 and r['intended_transfer']==0 and target==(None,)*3,'keep exact')
            else:
                require(r['engine_action']=='rebalance' and all(x is not None and 0<=x<=1 for x in target),'target')
                _close(math.fsum(target),1.,'fully invested target')
                transfer=r['wealth_before']/2*math.fsum(abs(w-h/r['wealth_before']) for w,h in zip(target,before))
                _close(r['intended_transfer'],transfer,'transfer')
                # Fee is one binary64 multiplication of recorded exact transfer.
                require(exact(r['fee'],fee*r['intended_transfer']),'exact fee multiplication')
                for x,w in zip(after,target):_close(x,(r['wealth_before']-r['fee'])*w,'post-fee allocation')
            _close(r['wealth_before'],r['wealth_after_fee']+r['fee'],'budget')
            source=rows[(s-1)*t+p-1]
            require(exact(tuple(r['return_'+a] for a in assets),tuple(float(source[k]) for k in FIELDS[2:5])) and
                    exact(r['inflation'],float(source['inflation'])),'ledger/source outcomes mismatch')
            for a,x,y in zip(assets,after,end):require(exact(y,x*(1+r['return_'+a])),'fee-before-return')
            require(exact(r['cpi_before'],cpi),'CPI continuity')
            cpi=cpi*(1+r['inflation']);require(exact(r['cpi_end'],cpi),'compounded CPI')
            for realkey,nominal,den in (('real_wealth_before',r['wealth_before'],r['cpi_before']),
                    ('real_wealth_after_fee',r['wealth_after_fee'],r['cpi_before']),('real_wealth_end',r['wealth_end'],cpi)):
                require(exact(r[realkey],nominal/den),'exact deflation')
            ret=r['real_wealth_end']/real-1
            require(exact(r['annual_net_real_return'],ret),'annual real return')
            if policy is not None:
                decision=policy(DecisionContext(s,p,before,tuple(history)))
                require(decision.action==r['engine_action'] and exact(decision.target,None if target==(None,)*3 else target),
                        'prefix decision mismatch')
                d=decisions[s,p]; review=policy.reviews[-1]
                for field in fields(PolicyReview):
                    if field.name not in ('scores','scenario_id','period'):
                        require(exact(d[field.name],getattr(review,field.name)),'prefix review mismatch: '+field.name)
                require(not latched or d['human_review_latched'],'review latch released')
                latched=d['human_review_latched']
                if latched:require(d['action']=='human_review' and r['engine_action']=='keep','review pending holdings')
                expectedscore={(s,p,x.name) for x in review.scores}
                require({k for k in scorekeys if k[:2]==(s,p)}==expectedscore,'score eligibility/count/link')
                for x in review.scores:
                    saved=next(v for v in case['target_scores'] if (v['scenario_id'],v['period'],v['target_name'])==(s,p,x.name))
                    for name in ('ce_target','tau','fee_fraction','pre_cost_benefit','modeled_fee_impact','conservative_score','true_net_ce'):
                        require(exact(saved[name],getattr(x,name)),'score value mismatch')
                    require(exact(tuple(saved['target_'+a] for a in assets),x.target),'score target mismatch')
            else:
                action='keep' if mode=='bills_keep' or (mode=='equal_weight_buy_hold' and p>1) else 'rebalance'
                require(r['engine_action']==action,'baseline action')
                if action=='rebalance':require(exact(target,(1/3,)*3),'baseline target')
            history.append(Observation(s,p,tuple(float(source[k]) for k in FIELDS[2:5]),float(source['inflation'])))
            real=r['real_wealth_end']; previous=end; returns.append(ret)
            for kind,v in (('post_fee',r['real_wealth_after_fee']),('end',real)):
                if v>peak:peak=v;peak_at=(p,kind)
                dd=1-v/peak
                if dd>loss:loss=dd;selected_peak=peak_at;selected_trough=(p,kind)
            snapshot.append((loss,selected_peak,selected_trough))
            facts+=30
        for h in horizons:
            m=next(r for r in case['scenario_metrics'] if r['scenario_id']==s and r['horizon']==h)
            pre=ledger[:h]; endreal=pre[-1]['real_wealth_end']; values=returns[:h]
            require(exact(m['net_real_cagr_pct'],100*((endreal/100)**(1/h)-1)),'exact CAGR identity')
            require(exact(m['max_real_drawdown_pct'],100*snapshot[h-1][0]),'exact drawdown identity')
            require(exact(m['terminal_real_wealth'],endreal),'terminal')
            require(exact(m['nominal_fee_sum'],math.fsum(r['fee'] for r in pre)),'fee sum')
            if h>1:
                from statistics import stdev
                require(exact(m['annual_real_volatility_pct'],100*stdev(values)),'exact sample volatility')
                mean=math.fsum(values)/h
                _close(m['annual_real_volatility_pct'],100*math.sqrt(math.fsum((v-mean)**2 for v in values)/(h-1)),'volatility',1e-10)
            else:require(m['annual_real_volatility_pct'] is None,'H1 volatility null')
            trade=sum(r['intended_transfer']>1e-10 for r in pre);later=sum(r['intended_transfer']>1e-10 for r in pre[1:])
            for key,v in dict(trade_count=trade,review_count=h,later_trade_count=later,later_review_count=h-1,
                trade_share_pct=100.*trade/h,trade_share_ex_initial_pct=100.*later/(h-1) if h>1 else None,
                drawdown_peak_year=snapshot[h-1][1][0],drawdown_peak_kind=snapshot[h-1][1][1],
                drawdown_trough_year=snapshot[h-1][2][0],drawdown_trough_kind=snapshot[h-1][2][1]).items():
                require(exact(m[key],v),'metric identity: '+key)
            diagnostic=[decisions[s,p] for p in range(1,h+1)] if policy is not None else []
            if diagnostic:
                v=dict(human_review_count=sum(d['action']=='human_review' for d in diagnostic),
                    human_review_share_pct=100*sum(d['action']=='human_review' for d in diagnostic)/h,
                    first_latch_year=next((d['period'] for d in diagnostic if d['human_review_latched']),None),
                    target_change_count=sum(d['executed_target_change'] for d in diagnostic),
                    first_deployment_year=diagnostic[-1]['first_deployment_year'],
                    initial_allocation_deferred=diagnostic[-1]['initial_allocation_deferred'])
                require(all(exact(m[k],x) for k,x in v.items()),'diagnostic metric mismatch')
            else:require(all(m[k] is None for k,_,_ in _schema(_DIAGNOSTICS)),'baseline diagnostic null')
            facts+=18
    for r in case['summary']:
        h=r['horizon']; group=[m for m in case['scenario_metrics'] if m['horizon']==h]
        require(r['scenario_count']==n,'summary count')
        for out,metric,p in (('median_growth_pct','net_real_cagr_pct',.5),('p10_growth_pct','net_real_cagr_pct',.1),
           ('median_loss_pct','max_real_drawdown_pct',.5),('p90_loss_pct','max_real_drawdown_pct',.9),
           ('median_volatility_pct','annual_real_volatility_pct',.5),('median_terminal_real_wealth','terminal_real_wealth',.5),
           ('median_nominal_fee_sum','nominal_fee_sum',.5)):
            if h==1 and out=='median_volatility_pct': require(r[out] is None,'H1 summary null')
            else:require(exact(r[out],_q([m[metric] for m in group],p)),'exact summary quantile '+out)
        for k in ('trade_count','review_count','later_trade_count','later_review_count'):
            require(r['pooled_'+k]==sum(m[k] for m in group),'pooled count')
        _close(r['pooled_trade_share_pct'],100.*r['pooled_trade_count']/r['pooled_review_count'],'pooled share')
        if h>1:_close(r['pooled_trade_share_ex_initial_pct'],100.*r['pooled_later_trade_count']/r['pooled_later_review_count'],'later share')
        else:require(r['pooled_trade_share_ex_initial_pct'] is None,'later null')
        severe=min(group,key=lambda m:(-m['max_real_drawdown_pct'],m['scenario_id']))
        for k in severe:
            if 'severe_'+k in r:require(exact(r['severe_'+k],severe[k]),'severe identity')
        for out,metric in (('pooled_human_review_count','human_review_count'),('pooled_target_change_count','target_change_count')):
            v=None if mode in BASELINES else sum(m[metric] for m in group)
            require(exact(r[out],v),'pooled diagnostic')
        v=None if mode in BASELINES else 100*r['pooled_human_review_count']/(n*h)
        require(exact(r['pooled_human_review_share_pct'],v),'pooled review share')
        facts+=24
    return facts


def _compute_cases(rows,calibration,group,split,horizons,imports,compute=build_case_tables):
    fee=.0025 if group=='primary' else .005
    cases={}
    for mode in MODES:
        if group=='primary' and mode in BASELINES:
            require(mode in imports,'missing authenticated reference case')
            cases[mode]=imports[mode]
        else:
            cases[mode]=compute(rows,calibrations=calibration,mode=mode,fee_rate=fee,split=split,horizons=horizons)
    return cases


def _write(path,data,max_bytes=LIMIT):
    require(len(data)<=max_bytes,'artifact exceeds actual byte limit')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:stream.write(data)


def _json_bytes(obj):
    return json.dumps(obj,indent=2,sort_keys=True,allow_nan=False).encode()+b'\n'


def _stage_output(output,operation,max_seconds=1500,max_bytes=LIMIT):
    output=Path(output)
    # Lexists catches dangling symlink roots as existing too.
    require(not output.exists() and not output.is_symlink(),'existing output root refused')
    output.mkdir(parents=True,exist_ok=False)
    stage=output/('partial-'+uuid.uuid4().hex);stage.mkdir()
    started=time.monotonic()
    try:
        result=operation(stage,started)
        require(time.monotonic()-started<=max_seconds,'immutable runtime budget exceeded')
        for p in stage.rglob('*'):
            if p.is_file():require(p.stat().st_size<=max_bytes,'actual artifact byte limit exceeded')
        for p in list(stage.iterdir()):p.rename(output/p.name)
        return result
    except BaseException as exc:
        failure=dict(status='failed',exception=type(exc).__name__,diagnosis=str(exc),
                     elapsed_seconds=time.monotonic()-started,traceback=traceback.format_exc(),
                     partial_path=stage.name)
        with (stage/'failure.json').open('x',encoding='utf-8') as stream:json.dump(failure,stream,indent=2)
        raise


MANIFEST_KEYS=('schema_version','status','split','group','fee_rate','scenario_count','periods','horizons',
 'provenance','configuration','input_sha256','calibrations_sha256','references_sha256','checks_sha256',
 'artifacts','elapsed_seconds','python','max_seconds','max_artifact_bytes')


def _persist(stage,started,*,data,rows,n,t,horizons,group,split,provenance,configuration,imports,import_index,
             max_seconds=1500,max_bytes=LIMIT,compute=build_case_tables):
    calibration=build_synthetic_calibrations(data,scenario_count=n,periods=t)
    attest=calibration_attestation(data,rows,n,t,calibration,split)
    cases=_compute_cases(rows,calibration,group,split,horizons,imports,compute)
    fee=.0025 if group=='primary' else .005
    index={};facts=0;counts={k:0 for k in TABLES}
    for mode,case in cases.items():
        require(time.monotonic()-started<=max_seconds,'runtime budget exceeded')
        facts+=check_case(case,mode,fee,rows,n,t,horizons,split,calibration)
        for table in TABLES:
            records=list(getattr(case,table)); raw=encode_csv(records,SCHEMAS[table])
            name='cases/'+mode+'/'+table+'.csv';_write(stage/name,raw,max_bytes)
            index[name]=dict(sha256=sha(raw),bytes=len(raw),rows=len(records),
                schema=[list(x) for x in SCHEMAS[table]],keys=list(KEYS[table]),
                applicable=not(mode in BASELINES and table in ('decisions','target_scores')))
            counts[table]+=len(records)
    if split=='development':
        e=expected_counts(group)
        require(all(counts[k]==e[k] for k in TABLES[:-1]) and counts['target_scores']<=e['target_scores_max'],
                'production output structural counts mismatch')
    saved={
        'calibrations.json':dict(arithmetic_manifest=calibration.manifest(),attestation=attest),
        'reference_imports.json':import_index,
        'checks.json':dict(status='passed',independent_scalar_facts=facts,counts=counts,
                           prefix_replay=True,absolute_tolerance=0.0)}
    for name,obj in saved.items():_write(stage/name,_json_bytes(obj),max_bytes)
    manifest=dict(schema_version=1,status='completed',split=split,group=group,fee_rate=fee,
        scenario_count=n,periods=t,horizons=list(horizons),provenance=provenance,configuration=configuration,
        input_sha256=sha(data),calibrations_sha256=sha((stage/'calibrations.json').read_bytes()),
        references_sha256=sha((stage/'reference_imports.json').read_bytes()),
        checks_sha256=sha((stage/'checks.json').read_bytes()),artifacts=index,
        elapsed_seconds=time.monotonic()-started,python=platform.python_version(),
        max_seconds=max_seconds,max_artifact_bytes=max_bytes)
    _write(stage/'run_manifest.json',_json_bytes(manifest),max_bytes)
    return manifest


def _synthetic_bundle(output,data,*,n,t,horizons,group,imports=None,provenance=None,compute=build_case_tables):
    """Internal generated-byte seam, absent from configuration and CLI."""
    def operation(stage,started):
        rows=_input_rows(data,n,t)
        return _persist(stage,started,data=data,rows=rows,n=n,t=t,horizons=horizons,group=group,
            split='synthetic',provenance=provenance or {'kind':'synthetic_internal'},
            configuration={'kind':'synthetic_internal','group':group},imports=imports or {},
            import_index={'status':'synthetic_fixture_imports','modes':list(imports or {})},compute=compute)
    return _stage_output(output,operation)


def _check_saved(output,*,data,expected_provenance,expected_configuration,imports=None,expected_import_index=None):
    output=Path(output)
    manifest=strict_json((output/'run_manifest.json').read_bytes());keys(manifest,MANIFEST_KEYS)
    require(manifest['status']=='completed','incomplete status')
    require(exact(manifest['provenance'],expected_provenance),'false source/provenance')
    require(exact(manifest['configuration'],expected_configuration),'wrong configuration')
    integer(manifest['schema_version'],1,1);integer(manifest['scenario_count'],4,120)
    integer(manifest['periods'],1,30);integer(manifest['max_seconds'],1,1500)
    integer(manifest['max_artifact_bytes'],1,LIMIT)
    require(type(manifest['elapsed_seconds']) is float and math.isfinite(manifest['elapsed_seconds']) and
            0<=manifest['elapsed_seconds']<=manifest['max_seconds'],'invalid elapsed/budget')
    require(manifest['split'] in ('synthetic','development'),'invalid split')
    require(manifest['group']==expected_configuration['group'],'manifest/config group mismatch')
    require(type(manifest['python']) is str and re.fullmatch(r'3\.12\.[0-9]+',manifest['python']),'invalid recorded Python')
    if manifest['split']=='development':
        require(manifest['max_seconds']==expected_configuration['execution']['max_seconds'] and
                manifest['max_artifact_bytes']==LIMIT and manifest['python']==expected_provenance['python'],
                'recorded execution constraints mismatch')
    require(exact(manifest['fee_rate'],.0025 if manifest['group']=='primary' else .005),'fee/group mismatch')
    n=manifest['scenario_count'];t=manifest['periods'];hs=manifest['horizons']
    require(type(hs) is list and hs and all(type(h) is int and 1<=h<=t for h in hs) and hs==sorted(set(hs)), 'horizons')
    require(sha(data)==manifest['input_sha256'],'input mismatch')
    rows=_input_rows(data,n,t)
    calibration=build_synthetic_calibrations(data,scenario_count=n,periods=t)
    expected_cal=dict(arithmetic_manifest=calibration.manifest(),
        attestation=calibration_attestation(data,rows,n,t,calibration,manifest['split']))
    for name,key in (('calibrations.json','calibrations_sha256'),('reference_imports.json','references_sha256'),('checks.json','checks_sha256')):
        raw=safe_path(output,name).read_bytes()
        require(sha(raw)==manifest[key],'saved root hash mismatch')
    require(exact(strict_json((output/'calibrations.json').read_bytes()),expected_cal),'saved calibration mismatch')
    if expected_import_index is not None:
        require(exact(strict_json((output/'reference_imports.json').read_bytes()),expected_import_index),'reference index mismatch')
    expected_paths={'cases/'+m+'/'+t+'.csv' for m in MODES for t in TABLES}
    require(set(manifest['artifacts'])==expected_paths,'missing/extra index paths')
    actual_files={p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()}
    require(actual_files==expected_paths|{'run_manifest.json','checks.json','calibrations.json','reference_imports.json'},'missing/extra files')
    facts=0; counts={k:0 for k in TABLES}
    for mode in MODES:
        tables={}
        for table in TABLES:
            name='cases/'+mode+'/'+table+'.csv'; entry=manifest['artifacts'][name]
            keys(entry,('sha256','bytes','rows','schema','keys','applicable'))
            require(exact(entry['schema'],[list(x) for x in SCHEMAS[table]]) and entry['keys']==list(KEYS[table]),'schema/type/index mismatch')
            integer(entry['bytes'],0,manifest['max_artifact_bytes']);integer(entry['rows'])
            require(entry['applicable'] is (not(mode in BASELINES and table in ('decisions','target_scores'))),'sidecar applicability')
            raw=safe_path(output,name).read_bytes()
            require(len(raw)==entry['bytes'] and sha(raw)==entry['sha256'],'artifact hash/bytes mismatch')
            tables[table]=tuple(decode_csv(raw,SCHEMAS[table],KEYS[table]))
            require(len(tables[table])==entry['rows'],'bogus row count')
            counts[table]+=len(tables[table])
            if imports and mode in imports:
                require(exact(tables[table],getattr(imports[mode],table)),'pinned imported evidence mismatch')
        case=CaseTables(**tables,counts={},units={},metadata={})
        facts+=check_case(case,mode,manifest['fee_rate'],rows,n,t,hs,manifest['split'],calibration)
    report=dict(status='passed',independent_scalar_facts=facts,counts=counts,prefix_replay=True,absolute_tolerance=0.0)
    require(exact(strict_json((output/'checks.json').read_bytes()),report),'bogus check facts/counts')
    if manifest['split']=='development':
        require((n,t,tuple(hs))==(120,30,HORIZONS),'production shape')
        e=expected_counts(manifest['group'])
        require(all(counts[k]==e[k] for k in TABLES[:-1]) and counts['target_scores']<=e['target_scores_max'],'production counts')
    return report


def produce(root,config_path,output):
    root=Path(root).resolve(); supplied=Path(output)
    output=supplied if supplied.is_absolute() else root/supplied
    require(not output.exists() and not output.is_symlink(),'existing output root refused before config/input')
    def operation(stage,started):
        require(sys.version_info[:2]==(3,12),'Python 3.12 required')
        config_name=Path(config_path).as_posix()
        raw=safe_path(root,config_name).read_bytes(); c=validate_config(strict_json(raw))
        task=strict_json((root/'.runtime/task.json').read_bytes())
        P=git(root,'rev-parse','origin/main').decode().strip()
        rel=output.relative_to(root).as_posix()
        binding=bind_task(root,c,config_name,raw,rel,task,P)
        sources=source_snapshot(root,c)
        imports,index=import_references(root,task['base_commit'],c['references'][0]) if c['group']=='primary' else ({},{'status':'no_imports','modes':[]})
        require(time.monotonic()-started<=min(task['max_seconds'],c['execution']['max_seconds']),'authorization exceeded runtime budget')
        data,rows=load_fixed_input(root)
        provenance=dict(kind='published_production',binding=binding,sources=sources,
                        python=platform.python_version(),dependencies='stdlib only')
        return _persist(stage,started,data=data,rows=rows,n=120,t=30,horizons=HORIZONS,group=c['group'],
            split='development',provenance=provenance,configuration=c,imports=imports,import_index=index,
            max_seconds=min(task['max_seconds'],c['execution']['max_seconds']),max_bytes=LIMIT)
    return _stage_output(output,operation)


def check_source_record(root,c,saved,snapshot):
    """Validate historical consumed/imported bytes without repairing saved proof.

    Absolute installation prefixes may change; exact relative paths, complete
    module sets and canonical LF/full-CRLF byte identities remain mandatory.
    """
    keys(saved,('canonical','consumed','imported'))
    require(exact(snapshot['canonical'],saved['canonical']),'recorded source pins mismatch')
    require(type(saved['consumed']) is dict and set(saved['consumed'])==set(c['source_sha256']),
            'consumed source closure mismatch')
    for name,h in saved['consumed'].items():
        hash_string(h)
        obj=blob(root,c['source_commit'],name)
        require(h in (sha(obj),sha(obj.replace(b'\n',b'\r\n'))),'false consumed source bytes')
    require(type(saved['imported']) is dict and set(saved['imported'])==set(snapshot['imported']),
            'recorded imported module closure mismatch')
    for module,record in saved['imported'].items():
        keys(record,('path','relative_path','sha256'))
        expected=snapshot['imported'][module]
        require(record['relative_path']==expected['relative_path'] and type(record['path']) is str and
                record['path'].replace(chr(92),'/').endswith('/'+expected['relative_path']),
                'recorded imported module path mismatch')
        hash_string(record['sha256'])
        obj=blob(root,c['source_commit'],record['relative_path'])
        require(record['sha256'] in (sha(obj),sha(obj.replace(b'\n',b'\r\n'))),'false imported source bytes')


def check_production(root,config_path,output):
    require(sys.version_info[:2]==(3,12),'Python 3.12 required')
    root=Path(root).resolve();output=Path(output)
    if not output.is_absolute():output=root/output
    m=strict_json((output/'run_manifest.json').read_bytes());keys(m,MANIFEST_KEYS)
    require(m['split']=='development' and m['provenance'].get('kind')=='published_production','CLI cannot check synthetic bundles')
    p=m['provenance'];keys(p,('kind','binding','sources','python','dependencies'))
    b=p['binding'];task=b['task'];c=validate_config(m['configuration'],task['max_seconds'])
    config_name=Path(config_path).as_posix()
    require(config_name==b['config_path'],'wrong check configuration path')
    raw=blob(root,task['base_commit'],config_name)
    require(exact(strict_json(raw),c),'wrong recorded configuration')
    # No .runtime task and no HEAD equality. Explicit P remains the historical authority.
    actual=bind_task(root,c,config_name,raw,output.relative_to(root).as_posix(),task,b['publication_commit'])
    require(exact(actual,b),'recorded task binding mismatch')
    snapshot=source_snapshot(root,c)
    check_source_record(root,c,p['sources'],snapshot)
    require(type(p['python']) is str and re.fullmatch(r'3\.12\.[0-9]+',p['python']) and
            p['dependencies']=='stdlib only','invalid recorded runtime')
    current_config=safe_path(root,config_name).read_bytes()
    require(current_config in (raw,raw.replace(b'\n',b'\r\n')),'changed configuration checkout bytes')
    imports,index=import_references(root,task['base_commit'],c['references'][0]) if c['group']=='primary' else ({},{'status':'no_imports','modes':[]})
    data,_=load_fixed_input(root)
    return _check_saved(output,data=data,expected_provenance=p,expected_configuration=c,imports=imports,expected_import_index=index)


def main(argv=None):
    parser=argparse.ArgumentParser(allow_abbrev=False,description='Fixed development case writer; requires published authorization.')
    parser.add_argument('--config',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args(argv)
    root=Path(__file__).resolve().parents[2]
    result=check_production(root,args.config,args.output) if args.check else produce(root,args.config,args.output)
    print(json.dumps(dict(status='passed',read_only=args.check,result=result.get('status'))))


if __name__=='__main__':main()
