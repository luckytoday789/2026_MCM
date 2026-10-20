"""Create schema metadata only; no executable production configuration."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from safeinvest import policy_analysis_writer as a

def obj(properties,required=None):
    return dict(type='object',properties=properties,required=list(properties) if required is None else required,additionalProperties=False)
def arr(item,**kw):return dict(type='array',items=item,**kw)
hex64=dict(type='string',pattern='^[0-9a-f]{64}$')
commit=dict(type='string',pattern='^[0-9a-f]{40}$')
path=dict(type='string',pattern=r'^(?!/)(?!.*\\)(?!.*(?:^|/)\.\.(?:/|$))[^\x00]+$')
integer=dict(type='integer',minimum=1)
review=obj(dict(task_id=dict(type='string',pattern='^SOL-[0-9]+$'),reviewed_commit=commit,acceptance_path=path,acceptance_sha256=hex64))
producer=obj(dict(group=dict(enum=['primary','doubled']),task_id=dict(type='string',pattern='^HY3-[0-9]+$'),attempt=integer,
    task_digest=hex64,result_commit=commit,receipt_sha256=hex64,acceptance_path=path,acceptance_sha256=hex64,root=path,
    config_path=path,artifacts_sha256=dict(type='object',minProperties=44,maxProperties=44,additionalProperties=hex64),numerical_review=review))
config=obj(dict(schema_version=dict(const=1),run_id=dict(type='string',pattern='^[A-Za-z0-9_-]+$'),split=dict(const='development'),
    execution_authorized=dict(const=True),source_commit=commit,source_sha256=obj({n:hex64 for n in a.CLOSURE}),
    acceptance=obj({**{k:dict(const=v) for k,v in a.ACCEPTED.items()},'SOL-034':commit}),
    input=dict(const=dict(path=a.w.INPUT_PATH,sha256=a.w.INPUT_HASH,scenario_ids=[1,120],periods=30)),
    policy_config=obj(dict(path=dict(const=a.POLICY),sha256=hex64)),
    producers=dict(type='array',prefixItems=[dict(allOf=[producer,dict(properties={'group':dict(const='primary')})]),dict(allOf=[producer,dict(properties={'group':dict(const='doubled')})])],minItems=2,maxItems=2),
    expected_counts=dict(const=a.EXPECTED),execution=obj(dict(cpu_only=dict(const=True),required_python=dict(const='3.12'),
    max_seconds=dict(type='integer',minimum=1,maximum=1500),max_artifact_bytes=dict(const=10485760)))))
parameters=obj(dict(config['properties'],config_path=path,config_sha256=hex64))
task=obj(dict(schema_version=dict(const=1),id=dict(type='string',pattern='^HY3-[0-9]+$'),attempt=integer,
    owner=dict(const='hy3'),kind=dict(const='commands'),base_commit=commit,depends_on=arr(dict(type='string'),uniqueItems=True),
    split=dict(const='development'),max_seconds=dict(type='integer',minimum=1,maximum=1500),scope=dict(type='string'),
    parameters=parameters,allowed_paths=arr(path,minItems=1,maxItems=1),deliverables=arr(path,minItems=6,maxItems=6,uniqueItems=True),
    commands=arr(arr(dict(type='string')),minItems=1,maxItems=1),validation_commands=arr(arr(dict(type='string')),minItems=1,maxItems=1),
    acceptance_checks=arr(dict(type='string')),instructions=dict(type='string')))
schema={'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'safeinvest:SOL-034:analysis-assembly-v1',
 '$defs':dict(config=config,task=task,producer=producer),
 'publication_contract':dict(sequence='accepted source C; later configuration E; later task publication P',
    no_self_reference='E is task.base_commit, P is recorded publication; neither is embedded into config bytes',
    canonical_task_digest='sha256(json.dumps(task,sort_keys=True,separators=(comma,colon)).encode())',
    source_closure=list(a.CLOSURE),runtime_validation='exact Python types, finite floats and float.hex equality; schema is documentation plus pinned metadata',
    producers='ordered primary 0.0025 and doubled 0.005; 44 exact files each; actual canonical_git_blob receipts and exact positive queue/chief result_verdict=approve at E',
    numerical_reviews='distinct SOL review tasks: queue/chief code_verdict=approve and chief producer_task_id, reviewed_result_commit, result_verdict=approve',
    task_binding='exact config mirrored in parameters plus config_path/config_sha256; exactly one create and one check command; exact six file deliverables',
    dependencies='exact accepted six source dependencies plus accepted SOL-034 plus both producers and both independent numerical reviews',
    originals='primary exact HY3-003 original reference identity; doubled no imports',
    output_completion='exclusive reserved output root; unique partial directory; manifest published last as atomic completion marker',
    production_counts_are='structural expectations, never observations'),
 'producer_csv_types':{k:[list(x) for x in v] for k,v in a.w.SCHEMAS.items()},
 'paired_csv_types':[list(x) for x in a.PAIRED_SCHEMA],
 'mapping':dict(field='growth_units',source='percent/year',destination='percentage points per year',numeric_conversion='none',direction='detached producer to accepted pure analysis input'),
 'nested_json_contract':'all accepted recursive keys and exact types/finite binary64 preserved; no fallback filling',
 'synthetic_seams':'private Python helpers only; never selectable by CLI or config'}
(ROOT/'audit/SOL-034/schema.json').write_text(json.dumps(schema,indent=2,sort_keys=True)+'\n',encoding='utf8',newline='\n')
