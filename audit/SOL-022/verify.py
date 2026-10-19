#!/usr/bin/env python3
"""SOL-022: generated inputs only. Python 3.12 + standard library + local Git.

Default creates NEW evidence (refuses overwrite); --check is strictly read-only.
Source is loaded from explicit Git blobs, never HEAD or the working src tree.
Expected fold, factor and digest values do not call production helpers.
"""
import argparse
from collections import Counter
from dataclasses import FrozenInstanceError
from fractions import Fraction as Q
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import types
from datetime import datetime, timezone

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'audit' / 'SOL-022'
SOURCE = '79a9a63d939c14d4af242d86ceeaa42c044803c4'
TASK_HASH = 'f724ad93de4463b4f3f70970332e3d37137111ebf40d70aa2803c892611bbaa8'
FIELDS = ('scenario_id','period','equity_return','bond_return','bill_proxy_return','inflation')
ASSETS = FIELDS[2:5]
CLOSURE = {
 'src/safeinvest/__init__.py':'b986566f8c42973164639cc7e296ed70fbc64479411e79a81f522cfc27ec14ef',
 'src/safeinvest/accounting.py':'0c73b143ed9755924be16d9c4fe9d9e8d8888931cb5c8a8c303434e2280389e5',
 'src/safeinvest/metrics.py':'efb7dad73e71515b9f164a95935231479ebca14b46c5b086a14de4bf5d38df9e',
 'src/safeinvest/backtest.py':'bbe2e602124adf068da424df0a28c9f40f970f81c126bed393f61ebb25b244b6',
}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def lf(path):
    return Path(path).read_bytes().replace(b'\r\n', b'\n')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT,
        env={**os.environ, 'GIT_OPTIONAL_LOCKS':'0'}, stderr=subprocess.PIPE)


def blob(path):
    return git('show', SOURCE + ':' + path)


def canonical(value):
    # Independent serializer for the contract's restricted ASCII data types.
    # Deliberately does not use json.dumps or any production digest helper.
    if value is None:
        return b'null'
    if value is True:
        return b'true'
    if value is False:
        return b'false'
    if type(value) is int:
        return str(value).encode('ascii')
    if type(value) is str:
        out = ['"']
        for c in value:
            k = ord(c)
            if c in ('"','\\'):
                out.append('\\' + c)
            elif k < 32 or k > 126:
                out.append('\\u%04x' % k)
            else:
                out.append(c)
        return (''.join(out) + '"').encode('ascii')
    if isinstance(value, (list, tuple)):
        return b'[' + b','.join(canonical(x) for x in value) + b']'
    if type(value) is dict:
        return b'{' + b','.join(canonical(k)+b':'+canonical(value[k]) for k in sorted(value)) + b'}'
    raise TypeError(type(value).__name__)


def csv_bytes(rows, newline='\n', header=FIELDS):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, lineterminator=newline)
    writer.writerow(header)
    writer.writerows(rows)
    return stream.getvalue().encode('utf-8')


def explicit_rows():
    # Every annual source row is explicit; values include decimal/non-dyadic,
    # signed zero, negative return, inflation and deflation.
    return [
        [1,1,'0.1','0.02','-0.0','0.02'],
        [1,2,'-0.5','0.25','0','-0.125'],
        [2,1,'0.5','-0.25','0.125','0.25'],
        [2,2,'0.25','0','0.0625','0.125'],
        [3,1,'-0.125','0.5','0.25','-0.25'],
        [3,2,'0.75','0.125','0','0.5'],
        [4,1,'0','-0.5','0.5','0'],
        [4,2,'1','0.25','-0.125','0.25'],
    ]


def generated_rows(n=120, p=30):
    rows = []
    for s in range(1,n+1):
        for t in range(1,p+1):
            k = (s + 3*t) % 8
            rows.append([s,t,str((k-3)/16),str((4-k)/32),
                         str(k/64),str((k%3-1)/16)])
    return rows


def parsed(rows):
    return [(int(r[0]),int(r[1]),*(float(x) for x in r[2:])) for r in rows]


def exact_real(values):
    # Mathematical transform of parsed binary64 inputs, evaluated rationally.
    return tuple((1+Q(x))/(1+Q(values[3])) for x in values[:3])


def rounded_real(values):
    # Exact emulation of EACH correctly rounded binary64 operation in
    # (1+r)/(1+i), separate from mathematical-rational accuracy comparisons.
    denominator = Q(float(1+Q(values[3])))
    return tuple(float(Q(float(1+Q(x)))/denominator) for x in values[:3])


def ce_oracle(gross, weights, recent=()):
    w = [Q(x) for x in weights]
    w = [x/sum(w) for x in w]
    def inv(row):
        return sum(x*Q(g) for x,g in zip(w,row)) ** -3
    moment = (15*sum(map(inv,gross))/len(gross)+sum(map(inv,recent)))/(15+len(recent))
    # Root of x^3 * moment = 1; rational midpoint and ties-to-even.
    def number(bits):
        return struct.unpack('>d', struct.pack('>Q',bits))[0]
    lo,hi = 0,0x7fefffffffffffff
    while hi-lo > 1:
        mid=(lo+hi)//2
        if Q(number(mid))**3*moment <= 1:
            lo=mid
        else:
            hi=mid
    side=((Q(number(lo))+Q(number(hi)))/2)**3*moment
    expected=number(hi if side<1 else lo if side>1 else lo if lo%2==0 else hi)
    return expected, str(moment)


class Checks:
    def __init__(self):
        self.counts=Counter()
        self.failures=[]
    def test(self, group, condition, detail=None):
        self.counts[group]+=1
        if not condition:
            self.failures.append({'group':group,'detail':detail})
    def equal(self, group, actual, expected):
        self.test(group,actual==expected,{'actual':actual,'expected':expected} if actual!=expected else None)
    def close(self, group, actual, expected, rel=3e-13):
        self.test(group,math.isclose(actual,expected,rel_tol=rel,abs_tol=0),
                  {'actual':actual,'expected':expected,'relative_tolerance':rel})


def load_source(task, checks):
    pins={**task['parameters']['source_sha256'],**CLOSURE}
    sources={p:blob(p) for p in pins}
    for p,h in pins.items():
        if sha(sources[p])!=h:
            raise RuntimeError('Pinned Git blob mismatch: '+p)
        checks.equal('source_hash',sha(sources[p]),h)
    # Execute an isolated package entirely from pinned Git bytes in memory.
    for name in list(sys.modules):
        if name=='safeinvest' or name.startswith('safeinvest.'):
            del sys.modules[name]
    package=types.ModuleType('safeinvest')
    package.__path__=[]
    package.__package__='safeinvest'
    sys.modules['safeinvest']=package
    for short in ('accounting','metrics','backtest','policy_pilot','policy_calibration','__init__'):
        name='safeinvest' if short=='__init__' else 'safeinvest.'+short
        module=package if short=='__init__' else types.ModuleType(name)
        module.__package__='safeinvest'
        path='src/safeinvest/'+short+'.py'
        module.__file__='git:'+SOURCE+':'+path
        sys.modules[name]=module
        exec(compile(sources[path],module.__file__,'exec'),module.__dict__)
        if short!='__init__':
            setattr(package,short,module)
    return sys.modules['safeinvest.policy_calibration'], {
        p:{'sha256':sha(b),'bytes':len(b)} for p,b in sorted(sources.items())}


def fold_expected(rows, n, p, f):
    # Explicit residue-class partition, independent of production fold_id.
    evaluation=tuple(range(f+1,n+1,4))
    training=tuple(sorted(set(range(1,n+1))-set(evaluation)))
    by_key={(r[0],r[1]):r for r in parsed(rows)}
    keys=tuple((s,t) for s in training for t in range(1,p+1))
    selected=[by_key[key] for key in keys]
    gross=tuple(rounded_real(r[2:]) for r in selected)
    raw={'schema':'training-annual-simple-v1','fields':list(FIELDS),
         'rows':[[r[0],r[1],*(x.hex() for x in r[2:])] for r in selected]}
    derived={'schema':'training-real-gross-v1','asset_order':list(ASSETS),
             'rows':[[*key,*(x.hex() for x in g)] for key,g in zip(keys,gross)]}
    return training,evaluation,keys,selected,gross,sha(canonical(raw)),sha(canonical(derived))


def inspect_fixture(api, checks, rows, n, p, label):
    data=csv_bytes(rows)
    bundle=api.build_synthetic_calibrations(data,scenario_count=n,periods=p)
    checks.equal('input_hash',bundle.input_sha256,sha(data))
    checks.equal('input_length',bundle.input_bytes,len(data))
    checks.equal('shape',(bundle.scenario_count,bundle.periods,len(bundle.folds)),(n,p,4))
    evaluation_all=[]
    facts=[]
    for f,got in enumerate(bundle.folds):
        train,evaluation,keys,selected,gross,raw_hash,gross_hash=fold_expected(rows,n,p,f)
        checks.equal('fold_identity',got.fold,f)
        checks.equal('training_ids',got.training_ids,train)
        checks.equal('evaluation_ids',got.evaluation_ids,evaluation)
        checks.test('disjoint',not set(got.training_ids)&set(got.evaluation_ids))
        checks.equal('complete_training_keys',got.training_keys,keys)
        checks.equal('prior_row_count',len(got.prior.gross),len(keys))
        checks.equal('training_digest',got.training_rows_sha256,raw_hash)
        checks.equal('derived_digest',got.real_gross_sha256,gross_hash)
        for key,source,actual,expected in zip(keys,selected,got.prior.gross,gross):
            checks.equal('source_key',key,source[:2])
            checks.equal('gross_row_width',len(actual),3)
            for a,b,q in zip(actual,expected,exact_real(source[2:])):
                checks.equal('binary64_factor_hex',a.hex(),b.hex())
                checks.close('rational_factor',a,float(q),rel=4e-16)
        weights=(Q(1,4),Q(1,4),Q(1,2))
        expected,moment=ce_oracle(gross,weights)
        observed=got.prior.certainty_equivalent(tuple(map(float,weights)))
        checks.close('equal_weight_ce',observed,expected)
        samples=[]
        for i in sorted({0,len(keys)//2,len(keys)-1}):
            samples.append({'training_index_0':i,'source_csv_line':(keys[i][0]-1)*p+keys[i][1]+1,
                'key':list(keys[i]),'nominal_inflation_hex':[x.hex() for x in selected[i][2:]],
                'gross_hex':[x.hex() for x in got.prior.gross[i]]})
        expected_manifest={'fold_id':f,'training_scenario_ids':list(train),
            'evaluation_scenario_ids':list(evaluation),'training_row_keys':[list(k) for k in keys],
            'training_row_count':len(keys),'training_rows_sha256':raw_hash,'real_gross_sha256':gross_hash,
            'annual_weight':'1 / training_row_count','asset_order':list(ASSETS)}
        checks.equal('fold_manifest_truth',got.manifest(),expected_manifest)
        facts.append({'fold':f,'manifest':got.manifest(),'annual_weight_exact':str(Q(1,len(keys))),
                      'ce':{'expected':expected,'observed':observed,'inverse_cube_moment':moment},
                      'source_row_samples':samples})
        evaluation_all.extend(got.evaluation_ids)
    checks.equal('fold_cover',sorted(evaluation_all),list(range(1,n+1)))
    manifest=bundle.manifest()
    checks.equal('bundle_manifest_provenance',
        (manifest['input_sha256'],manifest['input_bytes'],manifest['scenario_count'],manifest['periods']),
        (sha(data),len(data),n,p))
    checks.equal('manifest_fold_assignment',manifest['fold_assignment'],'(scenario_id - 1) % 4')
    checks.equal('manifest_schema',manifest['schema_version'],1)
    checks.equal('manifest_serialization',manifest['canonical_serialization'],
        'safeinvest-calibration-v1: compact ASCII JSON, sorted object keys, float.hex, no newline')
    checks.equal('manifest_fold_records',manifest['folds'],[x['manifest'] for x in facts])
    checks.equal('manifest_split',bundle.manifest()['split'],'synthetic')
    checks.equal('manifest_authorization',bundle.manifest()['production_execution_authorized'],False)
    return bundle,{'name':label,'input_sha256':sha(data),'input_bytes':len(data),
                  'shape':[n,p],'folds':facts}


def perturbations(api,checks,rows,n,p,base):
    facts=[]
    for f in range(4):
        changed=[r.copy() for r in rows]
        changed_keys=[]
        for r in changed:
            if int(r[0]) in range(f+1,n+1,4):
                r[2]=str(float(r[2])+0.25)
                r[5]=str(float(r[5])+0.125)
                changed_keys.append(r[:2])
        data=csv_bytes(changed)
        new=api.build_synthetic_calibrations(data,scenario_count=n,periods=p)
        checks.test('perturb_input_changes',new.input_sha256!=base.input_sha256)
        checks.equal('perturb_input_hash',new.input_sha256,sha(data))
        checks.equal('heldout_complete_fit_unchanged',new.folds[f],base.folds[f])
        # Challenge each selected row of each changed fit against the oracle,
        # including numerical values and both source/derived digest semantics.
        for j in range(4):
            tr,ev,keys,sel,gross,rh,gh=fold_expected(changed,n,p,j)
            a,b=base.folds[j],new.folds[j]
            checks.equal('perturb_ids',b.training_ids,tr)
            checks.equal('perturb_keys',b.training_keys,keys)
            checks.equal('perturb_gross_rows',b.prior.gross,gross)
            checks.equal('perturb_raw_digest',b.training_rows_sha256,rh)
            checks.equal('perturb_derived_digest',b.real_gross_sha256,gh)
            if j!=f:
                checks.test('other_fold_raw_changed',a.training_rows_sha256!=b.training_rows_sha256)
                checks.test('other_fold_gross_changed',a.real_gross_sha256!=b.real_gross_sha256)
                checks.test('other_fold_prior_changed',a.prior.gross!=b.prior.gross)
        facts.append({'heldout_fold':f,'changed_source_keys':changed_keys,
            'input_sha256':new.input_sha256,'input_bytes':new.input_bytes,
            'fold_hashes':[{'raw':x.training_rows_sha256,'gross':x.real_gross_sha256} for x in new.folds]})
    return facts


def provenance(api,checks,rows,base):
    variants={}
    def build(data):
        return api.build_synthetic_calibrations(data,scenario_count=4,periods=2)
    crlf=csv_bytes(rows,'\r\n')
    other=build(crlf)
    checks.equal('crlf_semantic_rows',other.folds,base.folds)
    checks.equal('crlf_length',other.input_bytes,base.input_bytes+len(rows)+1)
    checks.equal('crlf_input_sha',other.input_sha256,sha(crlf))
    checks.test('crlf_raw_distinct',other.input_sha256!=base.input_sha256)
    variants['crlf']={'sha256':sha(crlf),'bytes':len(crlf)}
    lexical=[r.copy() for r in rows]
    lexical[0][2]='1e-1'
    lexical[0][3]='0.0200000000000000000'
    lex=build(csv_bytes(lexical))
    checks.equal('lexical_same_parsed_rows',lex.folds,base.folds)
    checks.test('lexical_raw_distinct',lex.input_sha256!=base.input_sha256)
    variants['lexical']={'sha256':lex.input_sha256,'bytes':lex.input_bytes}
    zero=[r.copy() for r in rows]
    zero[0][4]='0.0'
    z=build(csv_bytes(zero))
    # Signed zeros have equal numerical value, distinct float.hex source records.
    for f in range(4):
        checks.equal('signed_zero_gross_same',z.folds[f].real_gross_sha256,base.folds[f].real_gross_sha256)
        checks.equal('signed_zero_raw_semantics',z.folds[f].training_rows_sha256==base.folds[f].training_rows_sha256,f==0)
    variants['signed_zero']={'input_sha256':z.input_sha256,'negative_zero_hex':float('-0').hex(),
                             'positive_zero_hex':float('0').hex()}
    a=[[s,t,'0','0','0','0'] for s in range(1,5) for t in range(1,3)]
    b=[[s,t,'1','1','1','1'] for s in range(1,5) for t in range(1,3)]
    left,right=build(csv_bytes(a)),build(csv_bytes(b))
    for f in range(4):
        checks.test('nominal_source_distinct',left.folds[f].training_rows_sha256!=right.folds[f].training_rows_sha256)
        checks.equal('nominal_same_derived',left.folds[f].real_gross_sha256,right.folds[f].real_gross_sha256)
        checks.equal('nominal_same_prior',left.folds[f].prior,right.folds[f].prior)
    variants['nominal_transform']={'zero_manifest':left.manifest(),'one_manifest':right.manifest()}
    checks.test('binary64_not_decimal',Q(float('0.1'))!=Q(1,10))
    values=parsed(rows)[0][2:]
    variants['decimal_detail']={'input':'0.1','parsed_hex':float('0.1').hex(),
        'parsed_exact_rational':str(Q(float('0.1'))),
        'mathematical_real_from_binary_inputs':[str(x) for x in exact_real(values)],
        'staged_binary64_real_hex':[x.hex() for x in rounded_real(values)]}
    return variants


def invalid_inputs(api,checks,rows):
    results=[]
    def reject(label,data,n=4,p=2):
        try:
            api.build_synthetic_calibrations(data,scenario_count=n,periods=p)
        except (ValueError,TypeError) as e:
            checks.test('invalid_rejected',True)
            results.append({'case':label,'exception':type(e).__name__,'message':str(e)})
        else:
            checks.test('invalid_rejected',False,label)
            results.append({'case':label,'exception':None})
    for label,data in [('path_string','generated.csv'),('bytearray',bytearray(csv_bytes(rows))),
                       ('empty',b''),('bad_utf8',b'\xff')]:
        reject(label,data)
    for n,p in [(0,2),(3,2),(6,2),(True,2),(4.0,2),(4,0),(4,-1),(4,True),(4,2.0)]:
        reject('shape_'+repr((n,p)),csv_bytes(rows),n,p)
    for label,header in [('reordered',FIELDS[::-1]),('duplicate',(*FIELDS[:-1],FIELDS[2])),
                         ('missing',FIELDS[:-1]),('extra',(*FIELDS,'extra')),('BOM',('\ufeffscenario_id',*FIELDS[1:]))]:
        reject('header_'+label,csv_bytes(rows,header=header))
    for label,bad in [('missing_row',rows[:-1]),('extra_row',rows+[rows[-1]]),
                      ('reversed',rows[::-1]),('duplicate_key',[rows[0],*rows[:-1]])]:
        reject(label,csv_bytes(bad))
    for field,value in [(0,'01'),(0,'0'),(0,'1.0'),(0,'121'),(1,'01'),(1,'0'),(1,'3')]:
        bad=[r.copy() for r in rows];bad[0][field]=value
        reject('key_'+str(field)+'_'+value,csv_bytes(bad))
    for label,row in [('missing_cell',rows[0][:-1]),('extra_cell',rows[0]+['0']),
                       ('empty_number',rows[0][:2]+['',*rows[0][3:]]),
                       ('text_number',rows[0][:2]+['True',*rows[0][3:]])]:
        bad=[r.copy() for r in rows];bad[0]=row
        reject(label,csv_bytes(bad))
    # For every fold, place every invalid numeric field in THAT held-out fold.
    for f in range(4):
        for field in range(2,6):
            for value in ('-1','-1.01','nan','inf','-inf'):
                bad=[r.copy() for r in rows];bad[2*f][field]=value
                reject('heldout_%d_field_%d_%s'%(f,field,value),csv_bytes(bad))
        for label,r,i in [('overflow','1.7976931348623157e308','-0.9999999999999999'),
                          ('underflow','-0.9999999999999999','1.7976931348623157e308')]:
            bad=[r.copy() for r in rows];bad[2*f][2]=r;bad[2*f][5]=i
            reject('heldout_%d_derived_%s'%(f,label),csv_bytes(bad))
    for value in (0,-1,True,'1',1.5):
        try:
            api.fold_id(value)
        except ValueError:
            checks.test('invalid_fold_id',True)
        else:
            checks.test('invalid_fold_id',False,repr(value))
    return results


def mutation_checks(api,checks,base):
    before=base.manifest()
    prior=base.folds[0].prior.gross
    attempts=[]
    def attempt(label,action):
        try:
            action()
        except (FrozenInstanceError,TypeError,AttributeError) as e:
            checks.test('immutable_nested',True)
            attempts.append({'case':label,'exception':type(e).__name__})
        else:
            checks.test('immutable_nested',False,label)
    attempt('bundle_field',lambda:setattr(base,'periods',99))
    attempt('fold_field',lambda:setattr(base.folds[0],'fold',99))
    attempt('prior_field',lambda:setattr(base.folds[0].prior,'gross',()))
    attempt('fold_tuple',lambda:base.folds.__setitem__(0,None))
    attempt('training_id_tuple',lambda:base.folds[0].training_ids.__setitem__(0,99))
    attempt('training_key_tuple',lambda:base.folds[0].training_keys[0].__setitem__(0,99))
    attempt('prior_rows_tuple',lambda:base.folds[0].prior.gross.__setitem__(0,()))
    attempt('prior_inner_tuple',lambda:base.folds[0].prior.gross[0].__setitem__(0,99))
    def damage(value):
        if isinstance(value,dict):
            for key,item in list(value.items()):
                if isinstance(item,(dict,list)):
                    damage(item)
                else:
                    value[key]='CORRUPTED'
            value['false_provenance']='final'
        elif isinstance(value,list):
            for item in value:
                damage(item)
            value.clear()
    returned=base.manifest()
    checks.test('fresh_manifest_identity',returned is not base.manifest())
    checks.test('fresh_nested_identity',returned['folds'][0] is not base.manifest()['folds'][0])
    damage(returned)
    checks.equal('returned_json_mutation_safe',base.manifest(),before)
    decoded=json.loads(json.dumps(base.manifest()))
    decoded['split']='final';decoded['production_execution_authorized']=True
    decoded['folds'][0]['training_row_keys'][0][0]=999
    decoded['folds'][0]['training_scenario_ids'].clear()
    checks.equal('json_roundtrip_mutation_safe',base.manifest(),before)
    fold_manifest=base.folds[0].manifest();damage(fold_manifest)
    checks.equal('fold_manifest_mutation_safe',base.manifest(),before)
    checks.equal('prior_mutation_safe',base.folds[0].prior.gross,prior)
    return attempts


def chief_log(checks):
    meta_path='audit/chief/policy-calibration/20261019T170940Z-evidence.json'
    meta=json.loads(blob(meta_path))
    data=blob(meta['log'])
    checks.test('chief_log_git_lf_only',b'\r' not in data)
    reconstructed=data.replace(b'\n',b'\r\n')
    checks.equal('chief_raw_windows_log_hash',sha(reconstructed),meta['log_sha256'])
    checks.test('chief_lf_hash_is_different',sha(data)!=meta['log_sha256'])
    checks.equal('chief_not_independent',meta['independent_acceptance'],False)
    return {'evidence_path':meta_path,'git_lf_sha256':sha(data),'git_lf_bytes':len(data),
       'raw_windows_crlf_sha256':sha(reconstructed),'raw_windows_crlf_bytes':len(reconstructed),
       'reported_log_sha256':meta['log_sha256'],'historical_python':meta['python'],
       'historical_kernel_sha256':meta['source_sha256_lf']['src/safeinvest/policy_pilot.py'],
       'current_kernel_sha256':json.loads(lf(HERE/'task-lock.json'))['parameters']['source_sha256']['src/safeinvest/policy_pilot.py'],
       'role':'Historical chief evidence, not new independent acceptance; no log rewritten.'}


def recompute():
    if sys.version_info[:2]!=(3,12):
        raise RuntimeError('Python 3.12 required')
    task_bytes=lf(HERE/'task-lock.json')
    if sha(task_bytes)!=TASK_HASH:
        raise RuntimeError('Immutable task snapshot hash mismatch')
    task=json.loads(task_bytes)
    if (task['id'],task['attempt'],task['owner'],task['base_commit'],task['allowed_paths']) != ('SOL-022',1,'sol',SOURCE,['audit/SOL-022']):
        raise RuntimeError('Immutable task identity mismatch')
    checks=Checks()
    api,sources=load_source(task,checks)
    checks.equal('canonical_known_vector',canonical({'z':['0x0.0p+0',1],'a':'x'}),b'{"a":"x","z":["0x0.0p+0",1]}')
    small=explicit_rows()
    base,small_fact=inspect_fixture(api,checks,small,4,2,'explicit-4x2')
    full=generated_rows()
    large,large_fact=inspect_fixture(api,checks,full,120,30,'generated-120x30')
    perturbed={'explicit':perturbations(api,checks,small,4,2,base),
               'generated':perturbations(api,checks,full,120,30,large)}
    # Additional scalar axis weights and 15:n interface checks, n=0..5.
    ce_facts=[]
    gross=base.folds[0].prior.gross
    recent_pool=((0.75,1.0,1.25),(1.5,0.875,1.0),(1.0,1.25,0.5),(0.5,1.0,1.5),(1.25,0.75,1.0))
    for w in ((1.,0.,0.),(0.,1.,0.),(0.,0.,1.),(0.25,0.25,0.5)):
        for n in range(6):
            recent=recent_pool[:n]
            expected,moment=ce_oracle(gross,w,recent)
            actual=base.folds[0].prior.certainty_equivalent(w,recent)
            checks.close('prior_recent_interface',actual,expected)
            ce_facts.append({'weights':list(w),'n':n,'expected':expected,'observed':actual,'moment':moment})
    prov=provenance(api,checks,small,base)
    invalid=invalid_inputs(api,checks,small)
    mutations=mutation_checks(api,checks,base)
    historical=chief_log(checks)
    queue=json.loads(blob('ops/queue.json'))
    entries=queue.get('tasks',queue.get('queue',[]))
    release=[e for e in entries if e['id']=='SOL-021']
    # SOURCE has no SOL-021 acceptance. Never fetch or infer newer main.
    accepted=any(e.get('state')=='accepted' and e.get('code_verdict')=='approve' for e in release)
    checks.equal('historical_design_approval',json.loads(blob('audit/chief/SOL-013-review.json'))['corrected_design_verdict'],'approve')
    checks.equal('historical_kernel_negative',json.loads(blob('audit/chief/SOL-017-review.json'))['code_verdict'],'changes_required')
    return {'schema_version':1,'source_commit':SOURCE,'task_snapshot_sha256_lf':TASK_HASH,
        'source_hash_basis':'exact canonical Git blob bytes','sources':sources,
        'oracle':'Independent Fraction arithmetic, exact binary64 rounding, scalar inverse-cube moment and restricted canonical ASCII serializer',
        'tolerances':{'rational_real_relative':4e-16,'ce_relative':3e-13,'absolute':0,
                      'hashes_keys_hex_and_saved_fact_structure':'exact'},
        'fixtures':[small_fact,large_fact],'perturbations':perturbed,
        'prior_recent_interface':ce_facts,'provenance':prov,'invalid_inputs':invalid,
        'mutation_attempts':mutations,'chief_historical_log':historical,
        'dependency_gate':{'accepted_positive_SOL_021_at_source':accepted,'queue_entries':release,
                           'status':'verified' if accepted else 'not_verifiable_at_pinned_base'},
        'check_counts':dict(sorted(checks.counts.items())),'check_count':sum(checks.counts.values()),
        'failures':checks.failures,'code_verdict':'changes_required' if checks.failures else 'approve',
        'competition_csv_read':False,'strategy_outcomes_run':False}


def json_text(value):
    return json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n'


def same_saved(a,b,path='facts'):
    # Exact types/keys/hex/hashes; tolerances only for numeric observations,
    # never for source identity, row keys, counts, moments, or expected floats.
    if type(a)!=type(b):
        return False
    if type(a) is dict:
        return a.keys()==b.keys() and all(same_saved(a[k],b[k],path+'.'+k) for k in a)
    if type(a) is list:
        return len(a)==len(b) and all(same_saved(x,y,path) for x,y in zip(a,b))
    if type(a) is float and path.endswith('.observed'):
        return math.isfinite(a) and math.isclose(a,b,rel_tol=3e-13,abs_tol=0)
    return a==b


def artifact_hashes(directory):
    return {name:sha(lf(directory/name)) for name in ('verify.py','task-lock.json','findings.json','review.md')}


def check_saved(path, directory):
    saved=json.loads(path.read_bytes())
    if set(saved)!= {'schema_version','created_at_utc','python','facts','artifact_sha256_lf'} or saved['schema_version']!=1:
        raise RuntimeError('Saved evidence schema mismatch')
    if saved['artifact_sha256_lf']!=artifact_hashes(directory):
        raise RuntimeError('Saved artifact hash mismatch; read-only evidence preserved')
    facts=recompute()
    if not same_saved(saved['facts'],facts):
        raise RuntimeError('Saved numerical/source evidence mismatch; read-only evidence preserved')
    findings=json.loads((directory/'findings.json').read_bytes())
    if findings['code_verdict']!=facts['code_verdict'] or findings['source_commit']!=SOURCE:
        raise RuntimeError('Verdict/source mismatch')
    # A supported negative verdict is valid evidence, not a replay failure.
    return facts


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--evidence',type=Path,default=HERE/'verification.json')
    parser.add_argument('--artifact-dir',type=Path,default=HERE)
    args=parser.parse_args()
    if args.check:
        facts=check_saved(args.evidence,args.artifact_dir)
    else:
        if args.evidence.exists():
            raise FileExistsError('Refuse overwrite: '+str(args.evidence))
        facts=recompute()
        findings=json.loads((args.artifact_dir/'findings.json').read_bytes())
        if findings['code_verdict']!=facts['code_verdict']:
            raise RuntimeError('Findings verdict must match executed facts')
        value={'schema_version':1,'created_at_utc':datetime.now(timezone.utc).isoformat(),
               'python':sys.version,'facts':facts,'artifact_sha256_lf':artifact_hashes(args.artifact_dir)}
        with args.evidence.open('x',encoding='utf-8',newline='\n') as stream:
            stream.write(json_text(value))
    print(json.dumps({'evidence_integrity_verdict':'passed','code_verdict':facts['code_verdict'],
        'check_count':facts['check_count'],'failed_comparisons':len(facts['failures']),
        'release_gate':facts['dependency_gate']['status'],'read_only':args.check},sort_keys=True))


if __name__=='__main__':
    main()
