"""Independent SOL-008 exact-commit review. Python 3.12, stdlib only.
No production arithmetic is imported for expected financial answers. Initializer
uses exclusive creation; --check compares evidence without writing any file.
Requires the three pinned commit objects in the local repository; never fetches.
"""
import argparse
import csv
import datetime as dt
import hashlib
import io
import itertools
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import types
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
HY3 = '7652410d73425371110784ef5fa97c03470a074e'
SOURCE = 'ec9653f1a4739bf1f0db36092c64771d014df25e'
BASE = '2561688380d9e2527eb6066100adde70b7d0ea1c'
SCHED = '10b3ff29f72b01d6a1a1bd2ca174f8cd6c7840d4'
TASK_SOURCE = 'ec561aca89076a700561bd17f63f3f4a4b87d09e'
DRAFT = 'f193742daab0f55c166b9b084bd288151c1e764d'
PARENT = '07b112dee30190d2c4f8d6c1aadacc2ab978092e'
INPUT = 'data/development/scenarios_001_120.csv'
OUT = 'results/development/HY3-003/'
POLICIES = ['bills_keep', 'equal_weight_annual', 'equal_weight_buy_hold']
HORIZONS = [5, 6, 15, 25, 30]
ASSETS = ['equity', 'bond', 'bill_proxy']
UNITS = {'monetary_units':'nominal units; real wealth in CPI_0 purchasing power',
 'return_units':'annual simple decimal','cpi_units':'price index; CPI_0=1',
 'growth_units':'percentage points per year',
 'volatility_units':'percentage points; annual sample ddof=1',
 'loss_units':'percent of running real peak','trade_share_units':'percent of annual reviews'}
PAIR_UNITS = {'growth_difference_units':'percentage points per year',
 'loss_difference_units':'percentage points; positive is worse',
 'terminal_real_wealth_difference_units':'CPI_0 purchasing-power units',
 'nominal_fee_difference_units':'nominal units','trade_share_difference_units':'percentage points'}
RES = {}
COUNTS = {}
BINDINGS = {}

def sha(b):
    return hashlib.sha256(b).hexdigest()

def git(*args):
    return subprocess.run(['git', *args],cwd=ROOT,check=True,capture_output=True).stdout

def blob(commit, path):
    # Binary pipes preserve canonical Git bytes, independent of checkout EOLs.
    b = git('show',commit+':'+path)
    BINDINGS[commit+':'+path] = sha(b)
    return b

def require(ok, detail):
    if not ok:
        raise AssertionError(detail)

def eq(got, expected, label):
    require(got == expected, f'{label}: observed={got!r}, expected={expected!r}')

def near(got, expected, group, label=''):
    got, expected = float(got), float(expected)
    require(math.isfinite(got) and math.isfinite(expected),group+': nonfinite '+label)
    err = abs(got-expected)
    scaled = err / max(abs(got),abs(expected),1e-300)
    r = RES.setdefault(group,{'count':0,'max_absolute_residual':0.0,
        'max_scaled_residual':0.0,'worst_absolute_location':'','worst_scaled_location':''})
    r['count'] += 1
    if err > r['max_absolute_residual']:
        r['max_absolute_residual'],r['worst_absolute_location'] = err,label
    if scaled > r['max_scaled_residual']:
        r['max_scaled_residual'],r['worst_scaled_location'] = scaled,label
    require(math.isclose(got,expected,abs_tol=1e-9,rel_tol=1e-10),
            f'{group}/{label}: observed={got}, expected={expected}, residual={err}')

def table(raw):
    require(b'\r' not in raw,'Published CSV must use LF')
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8')))
    rows = list(reader)
    require(len(reader.fieldnames)==len(set(reader.fieldnames)),'duplicate headers')
    require(all(None not in r and None not in r.values() for r in rows),'malformed CSV')
    return rows

def keys(rows, fields, expected, label):
    observed = [tuple(int(r[f]) if f in ('scenario_id','year','horizon') else r[f]
                      for f in fields) for r in rows]
    eq(observed,list(expected),label+' complete unique sorted keys')
    COUNTS[label] = len(rows)

def check_units(rows, units):
    for r in rows:
        eq(r['split'],'development','split')
        for k,v in units.items():
            eq(r[k],v,k)

def provenance():
    lock = json.loads((HERE/'task-lock.json').read_text(encoding='utf-8'))
    # Match scripts/coop.py task_digest: sorted JSON with compact separators.
    runner_digest = sha(json.dumps(lock,sort_keys=True,separators=(',',':')).encode())
    eq(runner_digest,'976e528142a46d73217ce05dd968d5348e951668773811ce638cf4ef3bab6e68','SOL task digest')
    eq(lock['base_commit'],BASE,'base lock')
    eq(lock['id'],'SOL-008','task identity')
    eq(lock,json.loads(blob(TASK_SOURCE,'ops/tasks/SOL-008.json')),'published immutable task')
    historical={}
    for p,h in lock['parameters']['partial_files_sha256'].items():
        raw=blob(DRAFT,p)
        eq(sha(raw),h,'pinned historical draft '+p)
        eq(sha((HERE/'history'/('SOL-006-'+Path(p).name)).read_bytes().replace(b'\r\n',b'\n')),h,'preserved historical file '+p)
        historical[p]=h
    eq(sha((HERE/'scheduler-suite.txt').read_bytes().replace(b'\r\n',b'\n')),historical['audit/SOL-006/scheduler-suite.txt'],'reused suite exact log')
    for p in ('scripts/coop.py','tests/test_coop.py'):
        eq(blob(BASE,p),blob(SCHED,p),'scheduler unchanged at new base '+p)
    eq(lock['allowed_paths'],['audit/SOL-008'],'allowed paths')
    eq(git('rev-parse',HY3+'^').decode().strip(),SOURCE,'HY3 parent')
    eq(git('rev-parse',SCHED+'^').decode().strip(),PARENT,'scheduler parent')
    for p,h in lock['parameters']['source_sha256'].items():
        eq(sha(blob(BASE,p)),h,'base source '+p)
        b=(ROOT/p).read_bytes()
        eq(sha(b.replace(b'\r\n',b'\n')),h,'current source modulo CRLF '+p)
    task_raw=blob(BASE,'ops/tasks/HY3-003.json')
    task=json.loads(task_raw)
    eq(sha(json.dumps(task,sort_keys=True,separators=(',',':')).encode()),
       lock['parameters']['hy3_task_sha256'],'HY3 task semantic digest')
    receipt_raw=blob(HY3,'handoff/HY3-003/result.json')
    receipt=json.loads(receipt_raw)
    for k,v in {'task_id':'HY3-003','attempt':1,'role':'hy3','base_commit':SOURCE,
                'status':'completed','failure':None,'artifact_hash_basis':'canonical_git_blob',
                'started_from_pinned_source':True,'task_sha256':lock['parameters']['hy3_task_sha256']}.items():
        eq(receipt[k],v,'receipt '+k)
    eq(receipt['task_parameters'],task['parameters'],'receipt parameters')
    eq(receipt['artifacts_sha256'],lock['parameters']['reviewed_result_sha256'],'artifact inventory')
    expected_paths = sorted([*receipt['artifacts_sha256'],'handoff/HY3-003/result.json'])
    eq(git('diff-tree','--no-commit-id','--name-only','-r',HY3).decode().splitlines(),expected_paths,'HY3 changed paths')
    artifacts={p:blob(HY3,p) for p in receipt['artifacts_sha256']}
    for p,b in artifacts.items():
        eq(sha(b),receipt['artifacts_sha256'][p],'canonical artifact '+p)
    for p,h in task['parameters']['source_sha256'].items():
        eq(sha(blob(SOURCE,p)),h,'HY3 source '+p)
    manifest=json.loads(artifacts[OUT+'run_manifest.json'])
    checks=json.loads(artifacts[OUT+'checks.json'])
    config=json.loads(blob(SOURCE,'specs/development_baselines_v1_1.json'))
    eq(manifest['effective_config'],config,'effective config')
    eq(manifest['source_commit'],SOURCE,'manifest source')
    eq(manifest['status'],'completed','manifest status')
    eq(manifest['python_version'],'3.12.10','HY3 Python')
    eq(manifest['packages'],{'stdlib':'3.12.10'},'HY3 packages')
    require(receipt['python'].startswith('3.12.10 '),'receipt Python')
    eq(manifest['plan_id'],config['plan_id'],'plan')
    eq(manifest['split'],'development','manifest split')
    eq(manifest['profile_horizons'],{'A':5,'B':15,'C':30,'D':25,'E':6},'profiles')
    eq(manifest['horizons'],HORIZONS,'horizons')
    eq(manifest['comparison_horizon'],30,'comparison horizon')
    source_forms={}
    eq(set(manifest['canonical_git_sources']),set(manifest['consumed_source_sha256']),'source inventory')
    for p,meta in manifest['canonical_git_sources'].items():
        raw=blob(SOURCE,p)
        eq(meta['sha256'],sha(raw),'canonical source SHA256 '+p)
        eq(meta['crlf_checkout_sha256'],sha(raw.replace(b'\n',b'\r\n')),'CRLF form '+p)
        eq(meta['git_blob_sha1'],git('rev-parse',SOURCE+':'+p).decode().strip(),'blob object '+p)
        consumed=manifest['consumed_source_sha256'][p]
        require(consumed in (meta['sha256'],meta['crlf_checkout_sha256']),'unverifiable consumed source '+p)
        source_forms[p]='canonical LF' if consumed==meta['sha256'] else 'CRLF checkout'
        eq(blob(BASE,p),raw,'accepted base code byte equality '+p)
        eq(sha((ROOT/p).read_bytes().replace(b'\r\n',b'\n')),meta['sha256'],'checked-out code modulo CRLF '+p)
    eq(set(manifest['output_sha256']),set(config['output_files'])-{'run_manifest.json'},'manifest output inventory')
    for p,h in manifest['output_sha256'].items():
        eq(sha(artifacts[OUT+p]),h,'manifest output '+p)
    eq(manifest['output_counts'],task['parameters']['expected_counts'],'manifest counts')
    eq(checks['output_counts'],manifest['output_counts'],'checks counts')
    eq(checks['failures'],0,'reported failures')
    eq(checks['status'],'passed','reported checks status')
    eq(sum(v['count'] for v in checks['checks'].values()),checks['count'],'reported check sum')
    for name,v in checks['checks'].items():
        eq(v['status'],'passed','reported '+name)
        eq(v['failures'],0,'reported failures '+name)
        require(v['count']>0 and v['max_absolute_residual']>=0 and v['max_scaled_residual']>=0,'check metadata')
    eq(checks['thresholds'],{'absolute_ledger':1e-9,'absolute_toy':1e-9,'relative_ledger':1e-10,
        'selection_ties':'exact float equality; tolerances are not tie thresholds','trade_amount_epsilon':1e-10},'thresholds')
    commands=task['commands']+task['validation_commands']
    eq(len(receipt['checks']),4,'four commands')
    executable=receipt['checks'][0]['argv'][0]
    for i,(expected,c) in enumerate(zip(commands,receipt['checks'])):
        eq(c['argv'],[executable,*expected[1:]],'receipt argv '+str(i))
        eq(c['exit_code'],0,'command exit '+str(i))
        log=json.loads(artifacts[f'handoff/HY3-003/check-{i}.txt'])
        if i in (0,2):
            eq(log,{'status':'passed','python':'3.12.10','required_python':'3.12','reason':None},'env log')
        else:
            eq(log['status'],'completed' if i==1 else 'passed','result log status')
            eq(log['output_counts'],manifest['output_counts'],'result log counts')
            if i==3:
                eq(log['read_only'],True,'saved check read only')
    eq(manifest['command'],['python',*receipt['checks'][1]['argv'][2:]],'normalized command semantic agreement')
    start,end=[dt.datetime.fromisoformat(manifest[k]) for k in ('utc_start','utc_end')]
    finished=dt.datetime.fromisoformat(receipt['finished_at'])
    require(start<end<=finished,'timestamp order')
    near((end-start).total_seconds(),manifest['elapsed_seconds'],'timing','UTC vs monotonic') if abs((end-start).total_seconds()-manifest['elapsed_seconds'])<1e-9 else None
    # Wall clock and monotonic timers have distinct origins; allow 10ms clock resolution/drift.
    require(abs((end-start).total_seconds()-manifest['elapsed_seconds'])<0.01,'wall vs monotonic timing')
    require(0<manifest['cpu_seconds']<=manifest['elapsed_seconds']+0.02<300,'CPU/elapsed timing')
    raw=blob(SOURCE,INPUT)
    eq(sha(raw),'9c4ad83f5dda86251a754e126528a71dd930ae88ed7cdb8a0663a327b6bfb7c7','development hash')
    eq(manifest['input'],{'fixture':False,'fixture_generator_sha256':None,'origin':INPUT,'sha256':sha(raw)},'input record')
    eq(sha((ROOT/INPUT).read_bytes()),sha(raw),'consumed local development bytes')
    data=table(raw)
    eq(list(data[0]),['scenario_id','period','equity_return','bond_return','bill_proxy_return','inflation'],'six input fields')
    eq([(int(r['scenario_id']),int(r['period'])) for r in data],list(itertools.product(range(1,121),range(1,31))),'development complete sorted keys')
    for r in data:
        require(all(math.isfinite(float(r[f])) and float(r[f])>-1 for f in list(r)[2:]),'input domain')
    return artifacts,data,{'receipt_sha256':sha(receipt_raw),'source_forms':source_forms,
        'task_sha256':runner_digest,'task_source_commit':TASK_SOURCE,'historical_draft_commit':DRAFT,'historical_draft_sha256':historical,'HY3_task_sha256':receipt['task_sha256'],
        'execution':{'HY3_python':'3.12.10','retained_commands':4,'reported_check_comparisons':checks['count'],
        'elapsed_seconds':manifest['elapsed_seconds'],'cpu_seconds':manifest['cpu_seconds'],
        'utc_duration_seconds':(end-start).total_seconds(),'command_semantics':'same script/args; executable normalized to python; -B only suppresses bytecode'}}


def f(row,k):
    return float(row[k])

def drawdown(observations):
    peak=100.0
    peak_at=(0,'initial')
    best=0.0
    pair=((0,'initial'),(0,'initial'))
    for year,kind,value in observations:
        if value>peak:
            peak,peak_at=value,(year,kind)
        loss=1.0-value/peak
        if loss>best:
            best,pair=loss,(peak_at,(year,kind))
    return 100.0*best,pair

def metrics(rows):
    h=len(rows)
    ends=[f(r,'real_wealth_end') for r in rows]
    annual=[v/p-1 for v,p in zip(ends,[100.0]+ends[:-1])]
    mean=sum(annual)/h
    vol=100*math.sqrt(sum((v-mean)**2 for v in annual)/(h-1))
    loss,pair=drawdown([(int(r['year']),kind,f(r,col)) for r in rows
        for kind,col in [('post_fee','real_wealth_after_fee'),('end','real_wealth_end')]])
    traded=[f(r,'intended_transfer')>1e-10 for r in rows]
    return {'net_real_cagr_pct':100*((ends[-1]/100)**(1/h)-1),
        'annual_real_volatility_pct':vol,'max_real_drawdown_pct':loss,
        'terminal_real_wealth':ends[-1],'nominal_fee_sum':sum(f(r,'fee') for r in rows),
        'trade_count':sum(traded),'review_count':h,'later_trade_count':sum(traded[1:]),
        'later_review_count':h-1,'trade_share_pct':100*sum(traded)/h,
        'trade_share_ex_initial_pct':100*sum(traded[1:])/(h-1),
        'drawdown_peak_year':pair[0][0],'drawdown_peak_kind':pair[0][1],
        'drawdown_trough_year':pair[1][0],'drawdown_trough_kind':pair[1][1]}

def compare(row,expected,group,label,locations=True):
    for k,v in expected.items():
        is_location = k.startswith('drawdown_') or k.startswith('severe_drawdown_')
        if is_location or k.endswith('_count') or k in ('scenario_count','severe_scenario_id'):
            if not locations and is_location:
                continue
            eq(int(row[k]) if isinstance(v,int) else row[k],v,group+'/'+label+'/'+k)
        else:
            near(row[k],v,group,label+'/'+k)

def scalar_path(rows,policy,horizon):
    holdings=[0.0,0.0,100.0]
    cpi=1.0
    previous_real=100.0
    answer=[]
    for t,src in enumerate(rows[:horizon],1):
        w=sum(holdings)
        rebalance=policy=='equal_weight_annual' or (policy=='equal_weight_buy_hold' and t==1)
        # Independent scalar formula on ordinary Python scalars; no production imports.
        transfer=w*sum(abs(1/3-h/w) for h in holdings)/2 if rebalance else 0.0
        fee=0.0025*transfer
        post=[(w-fee)/3 for _ in ASSETS] if rebalance else holdings[:]
        returns=[f(src,a+'_return') for a in ASSETS]
        end=[v*(1+r) for v,r in zip(post,returns)]
        end_cpi=cpi*(1+f(src,'inflation'))
        real=sum(end)/end_cpi
        r={'year':str(t),'action':'rebalance' if rebalance else 'keep','wealth_before':w,
           'wealth_after_fee':w-fee,'wealth_end':sum(end),'cpi_before':cpi,'cpi_end':end_cpi,
           'real_wealth_before':w/cpi,'real_wealth_after_fee':(w-fee)/cpi,'real_wealth_end':real,
           'intended_transfer':transfer,'fee':fee,'inflation':f(src,'inflation'),
           'annual_net_real_return':real/previous_real-1}
        for i,a in enumerate(ASSETS):
            r.update({f'holdings_before_{a}':holdings[i],f'holdings_after_fee_{a}':post[i],
                      f'holdings_end_{a}':end[i],f'return_{a}':returns[i]})
        answer.append(r)
        holdings,cpi,previous_real=end,end_cpi,real
    return answer


def numerical(artifacts,data):
    tables={p:table(artifacts[OUT+p]) for p in ['annual_ledgers.csv','scenario_metrics.csv','summary.csv','paired_differences.csv']}
    led,met,summ,pairs=[tables[p] for p in tables]
    keys(led,['policy','scenario_id','year'],itertools.product(POLICIES,range(1,121),range(1,31)),'annual_ledgers.csv')
    keys(met,['policy','scenario_id','horizon'],itertools.product(POLICIES,range(1,121),HORIZONS),'scenario_metrics.csv')
    keys(summ,['policy','horizon'],itertools.product(POLICIES,HORIZONS),'summary.csv')
    keys(pairs,['alternative_policy','scenario_id','horizon'],itertools.product([POLICIES[0],POLICIES[2]],range(1,121),HORIZONS),'paired_differences.csv')
    for rows in [led,met,summ]:
        check_units(rows,UNITS)
    check_units(pairs,PAIR_UNITS)
    inputs={(int(r['scenario_id']),int(r['period'])):r for r in data}
    paths={(p,s):[] for p in POLICIES for s in range(1,121)}
    for r in led:
        p,s,t=r['policy'],int(r['scenario_id']),int(r['year'])
        before=[f(r,'holdings_before_'+a) for a in ASSETS]
        post=[f(r,'holdings_after_fee_'+a) for a in ASSETS]
        end=[f(r,'holdings_end_'+a) for a in ASSETS]
        require(all(math.isfinite(v) and v>=0 for v in before+post+end),'nonnegative holdings')
        prior=paths[p,s][-1] if paths[p,s] else None
        for i,a in enumerate(ASSETS):
            eq(before[i],f(prior,'holdings_end_'+a) if prior else [0.,0.,100.][i],'exact holdings continuity')
        eq(f(r,'cpi_before'),f(prior,'cpi_end') if prior else 1.,'CPI continuity')
        reb=p=='equal_weight_annual' or (p=='equal_weight_buy_hold' and t==1)
        eq(r['action'],'rebalance' if reb else 'keep','policy action')
        for a in ASSETS:
            eq(r['target_'+a],str(1/3) if reb else '', 'target')
        w=sum(before)
        tr=w*sum(abs(1/3-v/w) for v in before)/2 if reb else 0.
        near(r['wealth_before'],w,'ledger','pre wealth')
        near(r['intended_transfer'],tr,'ledger','transfer')
        near(r['fee'],0.0025*tr,'ledger','fee')
        near(f(r,'wealth_after_fee')+f(r,'fee'),w,'ledger','budget')
        near(r['wealth_after_fee'],sum(post),'ledger','fully invested post')
        near(r['wealth_end'],sum(end),'ledger','fully invested end')
        src=inputs[s,t]
        for i,a in enumerate(ASSETS):
            eq(f(r,'return_'+a),f(src,a+'_return'),'saved input return')
            if reb:
                near(post[i],(w-f(r,'fee'))/3,'ledger','target holding')
            else:
                eq(post[i],before[i],'exact keep dollars')
                eq(f(r,'fee'),0.,'no keep fee')
                eq(f(r,'intended_transfer'),0.,'no keep transfer')
            near(end[i],post[i]*(1+f(r,'return_'+a)),'ledger','fee before return')
        eq(f(r,'inflation'),f(src,'inflation'),'saved input inflation')
        near(r['cpi_end'],f(r,'cpi_before')*(1+f(r,'inflation')),'ledger','CPI product')
        for wcol,cpicol,realcol in [('wealth_before','cpi_before','real_wealth_before'),('wealth_after_fee','cpi_before','real_wealth_after_fee'),('wealth_end','cpi_end','real_wealth_end')]:
            near(r[realcol],f(r,wcol)/f(r,cpicol),'ledger',realcol)
        near(r['annual_net_real_return'],f(r,'real_wealth_end')/(f(prior,'real_wealth_end') if prior else 100)-1,'ledger','net real return')
        paths[p,s].append(r)
    computed={}
    for r in met:
        p,s,h=r['policy'],int(r['scenario_id']),int(r['horizon'])
        expected=metrics(paths[p,s][:h])
        compare(r,expected,'all_metrics',f'{p}/{s}/{h}')
        computed[p,s,h]=expected
    severe=[]
    severe_details=[]
    def quantile(values,q):
        v=sorted(values)
        index=(len(v)-1)*q
        lo=math.floor(index)
        fraction=index-lo
        return v[lo]+fraction*(v[min(lo+1,len(v)-1)]-v[lo])
    for r in summ:
        p,h=r['policy'],int(r['horizon'])
        ms=[computed[p,s,h] for s in range(1,121)]
        severe_id=max(range(1,121),key=lambda s:(computed[p,s,h]['max_real_drawdown_pct'],-s))
        severe.append(severe_id)
        expected={'scenario_count':120,'severe_scenario_id':severe_id}
        for key,source,q in [('median_growth_pct','net_real_cagr_pct',.5),('p10_growth_pct','net_real_cagr_pct',.1),('median_loss_pct','max_real_drawdown_pct',.5),('p90_loss_pct','max_real_drawdown_pct',.9),('median_volatility_pct','annual_real_volatility_pct',.5),('median_terminal_real_wealth','terminal_real_wealth',.5),('median_nominal_fee_sum','nominal_fee_sum',.5)]:
            expected[key]=quantile([m[source] for m in ms],q)
        for k in ['trade_count','review_count','later_trade_count','later_review_count']:
            expected['pooled_'+k]=sum(m[k] for m in ms)
        expected['pooled_trade_share_pct']=100*expected['pooled_trade_count']/expected['pooled_review_count']
        expected['pooled_trade_share_ex_initial_pct']=100*expected['pooled_later_trade_count']/expected['pooled_later_review_count']
        for k in ['net_real_cagr_pct','max_real_drawdown_pct','terminal_real_wealth','drawdown_peak_year','drawdown_peak_kind','drawdown_trough_year','drawdown_trough_kind','trade_share_pct','trade_share_ex_initial_pct']:
            expected['severe_'+k]=computed[p,severe_id,h][k]
        compare(r,expected,'all_summaries',p+'/'+str(h))
        severe_details.append({'policy':p,'horizon':h,'scenario_id':severe_id,
            'peak':[expected['severe_drawdown_peak_year'],expected['severe_drawdown_peak_kind']],
            'trough':[expected['severe_drawdown_trough_year'],expected['severe_drawdown_trough_kind']]})
    for r in pairs:
        eq(r['reference_policy'],'equal_weight_annual','pair reference')
        p,s,h=r['alternative_policy'],int(r['scenario_id']),int(r['horizon'])
        expected={k+'_difference':computed[p,s,h][k]-computed['equal_weight_annual',s,h][k]
            for k in ['net_real_cagr_pct','max_real_drawdown_pct','terminal_real_wealth','nominal_fee_sum','trade_share_pct','trade_share_ex_initial_pct']}
        compare(r,expected,'all_pairs',f'{p}/{s}/{h}')
    selected=sorted(set([1,5,29,46,60,120]+severe))
    for s,p,h in itertools.product(selected,POLICIES,HORIZONS):
        original=[inputs[s,t] for t in range(1,31)]
        forward=scalar_path(original,p,h)
        for actual,expected in zip(paths[p,s][:h],forward):
            for k,v in expected.items():
                if k in ('year','action'):
                    eq(actual[k],v,'scalar action/year')
                else:
                    near(actual[k],v,'forward_paths',f'{p}/{s}/{h}/{expected["year"]}/{k}')
        # Small scalar rounding differences must not become an invented tie rule.
        compare(computed[p,s,h],metrics(forward),'forward_metrics',f'{p}/{s}/{h}',locations=False)
        eq(forward,scalar_path(original,p,30)[:h],'independent prefix rerun')
    return {'row_counts':COUNTS,'representative_scenarios':selected,
        'forward_prefixes':len(selected)*3*5,'severe_cases':severe_details,
        'exact_location_basis':'strict comparisons on saved validated float observations; scalar forward locations intentionally not treated as exact ties',
        'all_ledger_paths':360,'all_metrics':1800,'all_summaries':15,'all_pairs':1200}


def synthetic_checks():
    # Import production simulation ONLY as the subject of focused synthetic timing
    # probes. All expected arithmetic above and these toy facts remain independent.
    sys.path.insert(0,str(ROOT/'src'))
    from safeinvest.backtest import simulate_policy
    from safeinvest.baselines import POLICIES as callbacks
    decisions=[]
    permit={'period':0}
    class Guard(dict):
        def __getitem__(self,k):
            if k in ('equity_return','bond_return','bill_proxy_return','inflation'):
                require(permit['period']>=int(dict.__getitem__(self,'period')),'outcome accessed before decision')
            return dict.__getitem__(self,k)
    rows=[{'scenario_id':1,'period':t,'equity_return':.02,'bond_return':.01,'bill_proxy_return':0.,'inflation':.03} for t in range(1,31)]
    for p in POLICIES:
        def callback(ctx):
            eq(len(ctx.history),ctx.period-1,'history t-1')
            eq([o.period for o in ctx.history],list(range(1,ctx.period)),'history ordering')
            require(all(o.scenario_id==1 for o in ctx.history),'history scenario')
            decision=callbacks[p](ctx)
            permit['period']=ctx.period
            decisions.append(ctx.period)
            return decision
        permit['period']=0
        guarded=[Guard(r) for r in rows]
        result=simulate_policy(guarded,horizon=30,split='synthetic',callback=callback)
        base=result.ledger
        changed=[dict(r) for r in rows]
        for r in changed[9:]:
            r.update(equity_return=-.5,bond_return=.2,bill_proxy_return=.1,inflation=.4)
        altered=simulate_policy(changed,horizon=30,split='synthetic',callback=callbacks[p]).ledger
        eq(base[:9],altered[:9],'future perturbation states through 9')
        eq([x.decision for x in base[:10]],[x.decision for x in altered[:10]],'decisions through 10')
        eq(base[9].holdings_before,altered[9].holdings_before,'year 10 holdings')
        for h in HORIZONS:
            prefix=simulate_policy(rows,horizon=h,split='synthetic',callback=callbacks[p]).ledger
            eq(prefix,base[:h],'production synthetic prefix')
        # No outcome after requested horizon may be read, even during validation.
        permit['period']=0
        simulate_policy([Guard(r) for r in rows],horizon=5,split='synthetic',callback=callback)
        eq(permit['period'],5,'guarded horizon')
    flat=[{'scenario_id':1,'period':t,'equity_return':0.,'bond_return':0.,'bill_proxy_return':0.,'inflation':0.} for t in (1,2)]
    toy=[]
    def fact(name,got,expected):
        near(got,expected,'synthetic_arithmetic',name)
        toy.append({'name':name,'observed':got,'expected':expected})
    initial=simulate_policy(flat,horizon=2,split='synthetic',callback=callbacks['equal_weight_buy_hold'])
    fact('initial equal-weight transfer',initial.ledger[0].intended_transfer,200/3)
    fact('initial equal-weight fee',initial.ledger[0].fee,1/6)
    fact('initial post-fee wealth',initial.ledger[0].wealth_after_fee,599/6)
    for holding in initial.ledger[0].holdings_after_fee:
        fact('initial equal holding',holding,599/18)
    inflation=[dict(r,inflation=.1) for r in flat]
    bills=simulate_policy(inflation,horizon=2,split='synthetic',callback=callbacks['bills_keep'])
    fact('inflation-only terminal purchasing power',bills.ledger[-1].real_wealth_end,100/1.1**2)
    fact('inflation-only annual real return',bills.ledger[0].annual_net_real_return,1/1.1-1)
    fact('inflation-only maximum loss',bills.metrics.max_real_drawdown_pct,100*(1-1/1.1**2))
    recovery=[dict(r,equity_return=.1,bond_return=.1,bill_proxy_return=.1) for r in flat]
    rec=simulate_policy(recovery,horizon=2,split='synthetic',callback=callbacks['equal_weight_buy_hold'])
    fact('post-fee trough persists despite return recovery',rec.metrics.max_real_drawdown_pct,1/6)
    # Exact earliest tie behavior of this oracle is checked using saved-float style
    # observations, independently of scalar forward rounding.
    eq(drawdown([(1,'post_fee',100.),(1,'end',100.),(2,'post_fee',100.),(2,'end',100.)]),
       (0.,((0,'initial'),(0,'initial'))),'zero-loss sentinel')
    eq(drawdown([(1,'post_fee',100.),(1,'end',80.),(2,'post_fee',100.),(2,'end',80.)])[1],
       ((0,'initial'),(1,'end')),'earliest equal maxima')
    # Production selected location is observed against the independent initial-fee fact.
    require(rec.ledger[0].real_wealth_end>100,'fixture recovery required')
    return {'guarded_decisions':len(decisions),'policies':3,'perturbation_year':10,
        'prefixes':15,'guarded_short_horizons':3,'facts':toy,
        'exact_ties':'zero sentinel and earliest repeated maximum passed'}


def scheduler_probes(commit):
    module=types.ModuleType('isolated_coop_'+commit[:8])
    module.__file__=str(ROOT/'scripts/coop.py')
    exec(compile(blob(commit,'scripts/coop.py'),module.__file__,'exec'),module.__dict__)
    class Checkpoint:
        def exists(self):
            return state['checkpoint'] is not None
        def read_text(self,**kwargs):
            return json.dumps(state['checkpoint'])
    class Runtime:
        def __truediv__(self,key):
            return Checkpoint() if key=='chief-seen.json' else ROOT/'.runtime'/key
    state={}
    results={}
    def scenario(name,checkpoint,current,events,dirty=''):
        state.clear()
        state.update(checkpoint=checkpoint,current=current)
        calls=[]
        def execute(*args,**kwargs):
            code,after=events[min(len(calls),len(events)-1)]
            calls.append(current)
            state['current']=after
            return {'exit_code':code}
        def dump(path,value):
            state['checkpoint']=value
        observed=[]
        with (patch.object(module,'RUNTIME',Runtime()),
              patch.object(module,'chief_fingerprint',side_effect=lambda:state['current']),
              patch.object(module.shutil,'which',return_value='codex'),
              patch.object(module,'publish_status') as publish,
              patch.object(module,'execute_process',side_effect=execute),
              patch.object(module,'git',return_value=dirty),
              patch.object(module,'fetch') as fetch,
              patch.object(module,'dump',side_effect=dump)):
            for _ in range(3):
                try:
                    observed.append(module.chief_tick())
                except RuntimeError as exc:
                    observed.append(str(exc))
        results[name]={'returns':observed,'checkpoint':state['checkpoint'],
            'turn_count':len(calls),'fetch_calls':fetch.call_count,'status_calls':publish.call_count}
    scenario('arrival_during_turn',{'schema_version':2,'fingerprint':'older'},'before',[(0,'arrived'),(0,'arrived')])
    scenario('legacy_once',{'fingerprint':'same'},'same',[(0,'same')])
    scenario('failed_turn',{'schema_version':2,'fingerprint':'old'},'pending',[(1,'pending')])
    scenario('dirty_turn',{'schema_version':2,'fingerprint':'old'},'pending',[(0,'pending')],dirty=' M tracked.py')
    scenario('idle',{'schema_version':2,'fingerprint':'same'},'same',[(0,'same')])
    scenario('bootstrap',None,'new',[(0,'new')])
    return results


def scheduler():
    diff=git('diff',PARENT,SCHED,'--','scripts/coop.py','tests/test_coop.py')
    current=scheduler_probes(SCHED)
    parent=scheduler_probes(PARENT)
    eq(current['arrival_during_turn']['returns'],[True,True,False],'scheduler arrival remains pending')
    eq(current['arrival_during_turn']['turn_count'],2,'scheduler arrival two turns')
    eq(current['arrival_during_turn']['checkpoint'],{'schema_version':2,'fingerprint':'arrived'},'scheduler arrival final checkpoint')
    eq(current['legacy_once']['returns'],[True,False,False],'legacy recovers once')
    eq(current['legacy_once']['turn_count'],1,'legacy turn count')
    for name,message in [('failed_turn','Coordinator turn failed'),('dirty_turn','Coordinator left uncommitted work')]:
        require(all(isinstance(x,str) and message in x for x in current[name]['returns']),name+' rejection')
        eq(current[name]['checkpoint'],{'schema_version':2,'fingerprint':'old'},name+' unacknowledged')
        eq(current[name]['fetch_calls'],0,name+' no post-turn fetch')
    eq(current['idle']['returns'],[False,False,False],'unchanged idle')
    eq(current['idle']['turn_count'],0,'idle no execution')
    eq(current['idle']['status_calls'],0,'idle no publication')
    eq(current['bootstrap']['returns'],[False,False,False],'bootstrap no duplicate turn')
    eq(parent['arrival_during_turn']['returns'],[True,False,False],'parent negative arrival reproduces lost notification')
    eq(parent['legacy_once']['returns'],[False,False,False],'parent negative legacy no recovery')
    suite=(HERE/'scheduler-suite.txt').read_bytes().replace(b'\r\n',b'\n')
    text=suite.decode('utf-8').replace('\r\n','\n')
    require('Ran 7 tests' in text and text.rstrip().endswith('OK'),'existing scheduler suite log')
    names=re.findall(r'^(test_\w+) .*? \.\.\. ok$',text,re.M)
    eq(len(names),7,'seven successful named tests')
    return {'verdict':'pass','commit':SCHED,'parent':PARENT,'diff_sha256':sha(diff),
        'scoped_paths':['scripts/coop.py','tests/test_coop.py'],
        'current_probes':current,'parent_negative_controls':parent,
        'existing_suite':{'command':['python','-B','-m','unittest','discover','-s','tests','-p','test_coop.py','-v'],
            'python':'3.12.14','exit_code':0,'tests':7,'names':names,'log_sha256':sha(suite)},
        'limits':'Mocked chief_tick transitions and isolated local Git suite; no live watcher, real status publication, or runtime checkpoint changes.'}


def compute():
    RES.clear()
    COUNTS.clear()
    BINDINGS.clear()
    require(sys.version_info[:2]==(3,12),'Python 3.12 required')
    artifacts,data,prov=provenance()
    numeric=numerical(artifacts,data)
    synthetic=synthetic_checks()
    sched=scheduler()
    return {'schema_version':1,'task':'SOL-008','numerical_verdict':'pass',
        'scheduler_verdict':sched['verdict'],'blockers':[],
        'commits':{'HY3_result':HY3,'HY3_source':SOURCE,'audit_base':BASE,'scheduler_commit':SCHED,'scheduler_parent':PARENT},
        'provenance':prov,'numerical':numeric,'synthetic':synthetic,
        'residuals':RES,'bindings_sha256':BINDINGS,
        'tolerances':{'absolute':1e-9,'relative':1e-10,'trade_epsilon':1e-10,'selection_ties':'exact'},
        'oracle':'independent standard-library scalar arithmetic; production imported only for synthetic timing/fixture observations',
        'verify_py_sha256':sha(Path(__file__).read_bytes().replace(b'\r\n',b'\n')),
        'scheduler_review_sha256':sha(serialize(sched))},sched


def serialize(obj):
    return (json.dumps(obj,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--evidence-dir',type=Path,default=HERE,
                        help='alternate saved evidence for read-only corruption tests')
    args=parser.parse_args()
    evidence,sched=compute()
    items={'verification.json':evidence,'scheduler-review.json':sched}
    if args.check:
        for name,expected in items.items():
            observed=json.loads((args.evidence_dir/name).read_text(encoding='utf-8'))
            eq(observed,expected,'saved '+name)
        print(json.dumps({'status':'passed','read_only':True,'numerical':'pass','scheduler':'pass',
            'rows':COUNTS,'numeric_comparisons':sum(v['count'] for v in RES.values())},sort_keys=True))
    else:
        # Fail before writing if either file already exists; never repair evidence.
        require(args.evidence_dir==HERE,'initializer evidence directory is fixed')
        require(all(not (HERE/name).exists() for name in items),'evidence already exists; use --check')
        for name,obj in items.items():
            with (HERE/name).open('xb') as stream:
                stream.write(serialize(obj))
        print(json.dumps({'status':'initialized','numerical':'pass','scheduler':'pass','rows':COUNTS},sort_keys=True))

if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        print(f'{type(exc).__name__}: {exc}',file=sys.stderr)
        sys.exit(1)
