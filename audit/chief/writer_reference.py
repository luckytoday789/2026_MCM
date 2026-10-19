"""Independent writer import/label references; no experiment or raw CSV access.

Prepared before writer delivery. This is expected evidence for a later adapter,
not a production implementation or acceptance of one. --check is read-only.
"""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
BASELINE='7652410d73425371110784ef5fa97c03470a074e'
DEFAULT=ROOT/'audit/chief/writer-reference.json'
MODES=('bills_keep','equal_weight_annual','equal_weight_buy_hold')
HORIZONS=(5,6,15,25,30)
LEGACY='percentage points per year'
LEVEL='percent/year'
RENAMES={'policy':'mode','year':'period','action':'engine_action'}


def sha(data):return hashlib.sha256(data).hexdigest()
def blob(path):return subprocess.check_output(['git','show',BASELINE+':'+path],cwd=ROOT)
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()


def map_reference(row):
    """Expected lossless field-name/label mapping; preserves source cell strings."""
    if row['growth_units']!=LEGACY:
        raise ValueError('unexpected original growth unit')
    if any(target in row for target in RENAMES.values()):
        raise ValueError('ambiguous source key mapping')
    mapped={RENAMES.get(k,k):(LEVEL if k=='growth_units' else v) for k,v in row.items()}
    inverse={v:k for k,v in RENAMES.items()}
    original={inverse.get(k,k):(LEGACY if k=='growth_units' else v) for k,v in mapped.items()}
    assert original==row
    return mapped


def typed(value):
    if isinstance(value,float):return {'type':'float','hex':value.hex()}
    if isinstance(value,dict):return {k:typed(v) for k,v in value.items()}
    if isinstance(value,list):return [typed(v) for v in value]
    return {'type':type(value).__name__,'value':value}


def calculate():
    receipt=json.loads(blob('handoff/HY3-003/result.json'))
    acceptance=json.loads((ROOT/'audit/chief/HY3-003-review.json').read_bytes())
    assert acceptance['reviewed_commit']==BASELINE
    assert acceptance['status']=='accepted_development_baseline_evidence'
    tables={};total=0
    for name,count,per_mode in [('annual_ledgers.csv',10800,3600),('scenario_metrics.csv',1800,600),('summary.csv',15,5)]:
        path='results/development/HY3-003/'+name
        raw=blob(path)
        assert sha(raw)==receipt['artifacts_sha256'][path]==acceptance['artifacts_sha256'][path]
        # Exact source blobs are sufficient; a local checkout's CRLF is recorded separately.
        current=(ROOT/path).read_bytes()
        assert current in (raw,raw.replace(b'\n',b'\r\n'))
        reader=csv.DictReader(io.StringIO(raw.decode(),newline=''))
        fields=reader.fieldnames; assert len(fields)==len(set(fields))
        rows=list(reader);assert len(rows)==count
        assert set(row['policy'] for row in rows)==set(MODES)
        metadata=[]
        for mode in MODES:
            selected=[r for r in rows if r['policy']==mode]
            assert len(selected)==per_mode and all(r['split']=='development' for r in selected)
            if name=='annual_ledgers.csv':
                keys=[(int(r['scenario_id']),int(r['year'])) for r in selected]
                assert set(keys)=={(s,t) for s in range(1,121) for t in range(1,31)}
            elif name=='scenario_metrics.csv':
                keys=[(int(r['scenario_id']),int(r['horizon'])) for r in selected]
                assert set(keys)=={(s,h) for s in range(1,121) for h in HORIZONS}
            else:
                keys=[int(r['horizon']) for r in selected]
                assert set(keys)==set(HORIZONS)
                assert all(int(r['scenario_count'])==120 for r in selected)
            assert len(keys)==len(set(keys))
            normalized=[map_reference(r) for r in selected]
            # The inverse proves EVERY cell preserved, including numeric spellings,
            # empty/null cells and location labels, rather than selected aggregates.
            metadata.append({'mode':mode,'count':len(selected),
                'source_cells_sha256':sha(canonical(selected)),
                'normalized_reference_cells_sha256':sha(canonical(normalized)),
                'ordered_keys_sha256':sha(canonical(keys)),
                'all_cells_inverse_mapping_exact':True})
        tables[name]={'source_path':path,'canonical_git_sha256':sha(raw),'canonical_git_bytes':len(raw),
            'canonical_git_crlf_sha256':sha(raw.replace(b'\n',b'\r\n')),
            'source_fields':fields,'normalized_fields':[RENAMES.get(k,k) for k in fields],
            'count':count,'by_mode':metadata,'local_checkout_equivalent':True}
        assert (ROOT/path).read_bytes()==current
        total+=count
    fixture={'net_real_cagr_pct':0.01,'negative_zero':-0.0,'zero':0.0,
        'below_gate':math.nextafter(0.1,-math.inf),'gate':0.1,'above_gate':math.nextafter(0.1,math.inf),
        'first_latch_year':None,'human_review_latched':False,'initial_allocation_deferred':True,
        'growth_units':LEVEL,'growth_difference_units':LEGACY}
    original=typed(fixture)
    roundtrip=json.loads(json.dumps(fixture,allow_nan=False))
    assert typed(roundtrip)==original
    analysis_copy=dict(roundtrip);analysis_copy['growth_units']=LEGACY
    restored=dict(analysis_copy);restored['growth_units']=LEVEL
    assert typed(restored)==original and typed(fixture)==original
    difference=0.11-0.01
    assert fixture['net_real_cagr_pct']==0.01 and fixture['net_real_cagr_pct']!=1.0
    assert math.copysign(1,restored['negative_zero'])==-1
    invalid={'split':'development','policy':'bills_keep','growth_units':'decimal'}
    try:map_reference(invalid)
    except ValueError:pass
    else:raise AssertionError('unknown unit accepted')
    # Empty CSV cells cannot represent null/boolean without a separately declared
    # column schema. The writer must supply that schema; this oracle invents none.
    return {'schema_version':1,'kind':'preimplementation_expected_writer_reference',
        'baseline_commit':BASELINE,'baseline_receipt_sha256':sha(blob('handoff/HY3-003/result.json')),
        'source_artifacts':tables,'exact_source_rows_checked':total,
        'mapping':{'renames':RENAMES,'field':'growth_units','original':LEGACY,'destination':LEVEL,
            'numerical_conversion':'none','analysis_bridge':'detached copy; LEVEL -> LEGACY'},
        'synthetic_boundary_fixture':fixture,'expected_typed_values':original,
        'paired_growth_difference':{'candidate':0.11,'reference':0.01,'binary64_difference':difference,
            'difference_hex':difference.hex(),'units':LEGACY},
        'unknown_unit_rejected':True,'json_roundtrip_preserves_types_and_float_hex':True,
        'not_yet_tested':['delivered writer normalization','delivered CSV column type decoder',
            'saved-bundle checker corruption rejection','production path/source/config guards'],
        'competition_input_read':False,'baseline_experiment_rerun':False,'new_policy_outcomes_run':False,
        'writer_accepted':False,'final_data_open':False}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');parser.add_argument('--evidence',type=Path,default=DEFAULT)
    args=parser.parse_args()
    if not args.check and args.evidence.exists():raise FileExistsError(args.evidence)
    actual=calculate()
    if args.check:
        before=args.evidence.read_bytes();expected=json.loads(before)
        assert typed(expected)==typed(actual),'saved reference differs'
        assert args.evidence.read_bytes()==before
    else:
        with args.evidence.open('x',encoding='utf-8',newline='\n') as f:json.dump(actual,f,indent=2);f.write('\n')
    print(json.dumps({'status':'passed','read_only':args.check,'reference_rows':actual['exact_source_rows_checked'],'reference_tables':3,'writer_accepted':False}))

if __name__=='__main__':main()
