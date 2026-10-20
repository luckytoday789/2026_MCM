"""Independent stdlib-only refit oracle. Opens fixed development input, never final."""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
FIELDS=('scenario_id','period','equity_return','bond_return','bill_proxy_return','inflation')
INPUT='data/development/scenarios_001_120.csv'
INPUT_SHA256='9c4ad83f5dda86251a754e126528a71dd930ae88ed7cdb8a0663a327b6bfb7c7'


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')
def sha(raw):return hashlib.sha256(raw).hexdigest()


def verify(raw,saved):
    assert sha(raw)==INPUT_SHA256,'original development input identity mismatch'
    assert saved['status']=='completed_refit' and saved['source_verified'] is True
    assert saved['configuration']['stage']=='refit' and saved.get('external_acceptance') is None
    reader=csv.DictReader(io.StringIO(raw.decode('utf8'),newline=''))
    assert tuple(reader.fieldnames)==FIELDS
    records=list(reader);assert len(records)==3600
    keys=[];nominal=[];gross=[];checks=0
    for index,row in enumerate(records):
        sid,t=divmod(index,30);key=[sid+1,t+1]
        assert tuple(row)==FIELDS and row['scenario_id']==str(key[0]) and row['period']==str(key[1])
        values=[float(row[n]) for n in FIELDS[2:]]
        assert all(math.isfinite(x) and x>-1 for x in values)
        actual=[(1+x)/(1+values[3]) for x in values[:3]]
        assert all(math.isfinite(x) and x>0 for x in actual)
        keys.append(key);nominal.append(key+[v.hex() for v in values]);gross.append(actual)
    r=saved['refit']
    assert r['calibration_kind']=='all_development_refit' and r['split']=='development'
    assert r['input_origin']==INPUT and r['input_sha256']==INPUT_SHA256 and r['input_bytes']==len(raw)
    assert r['training_scenario_ids']==list(range(1,121)) and r['training_row_keys']==keys
    assert r['training_row_count']==3600 and r['annual_weight']=='1 / 3600'
    assert r['asset_order']==list(FIELDS[2:5]) and r['fold_id'] is None and r['fold_status']=='not_applicable'
    assert len(r['gross'])==3600
    for expected,got in zip(gross,r['gross']):
        assert len(got)==3
        for x,y in zip(expected,got):
            assert type(y) is float and x.hex()==y.hex(),'binary64 prior support mismatch';checks+=1
    nominal_hash=sha(canonical(dict(schema='training-annual-simple-v1',fields=list(FIELDS),rows=nominal)))
    gross_hash=sha(canonical(dict(schema='training-real-gross-v1',asset_order=list(FIELDS[2:5]),
        rows=[key+[x.hex() for x in vector] for key,vector in zip(keys,gross)])))
    support_hash=sha(canonical(dict(schema='all-development-prior-support-v1',asset_order=list(FIELDS[2:5]),
        rows=[[x.hex() for x in vector] for vector in gross])))
    assert r['training_rows_sha256']==nominal_hash and r['real_gross_sha256']==gross_hash
    assert r['prior_support_sha256']==support_hash
    return dict(status='passed',read_only=True,independent_stdlib=True,input_sha256=INPUT_SHA256,
        training_rows=3600,prior_scalar_checks=checks,training_rows_sha256=nominal_hash,
        real_gross_sha256=gross_hash,prior_support_sha256=support_hash,
        scope='Independent actual development/refit support oracle; no final input access or source approval.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True)
    p.add_argument('--manifest-sha256');args=p.parse_args()
    if len(args.manifest)>41 and args.manifest[40]==':':
        commit,path=args.manifest.split(':',1)
        raw_manifest=subprocess.check_output(['git','show',commit+':'+path],cwd=ROOT)
    else:
        path=(ROOT/args.manifest).resolve();assert path.is_relative_to(ROOT)
        raw_manifest=path.read_bytes()
    if args.manifest_sha256:assert sha(raw_manifest)==args.manifest_sha256
    original=(ROOT/INPUT).read_bytes()
    report=verify(original,json.loads(raw_manifest))
    assert sha((ROOT/INPUT).read_bytes())==sha(original),'development input changed during check'
    assert not any(name=='safeinvest' or name.startswith('safeinvest.') for name in sys.modules)
    report['manifest_sha256']=sha(raw_manifest)
    print(json.dumps(report,sort_keys=True))
