"""PRIVATE GENERATED FIXTURES ONLY. No production config or input is created.

Git objects below are real commits in an isolated repository; all metric values
are assigned scalar fixtures, not simulations or competition performance.
"""
from copy import deepcopy
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from safeinvest import policy_analysis_writer as a
w=a.w


def git(root,*args):
    return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.PIPE)


def write(root,path,data):
    p=Path(root)/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)


def grid(*,referral=False,context=.1):
    groups={};hashes={}
    for group,fee in (('primary',.0025),('doubled',.005)):
        groups[group]={};hashes[group]={}
        for mode in w.MODES:
            rows=[]
            for sid in range(1,5):
                for h in w.HORIZONS:
                    base=mode in w.BASELINES
                    growth=0.0 if base or mode=='conservative_cost' else .1 if mode=='balanced_cost' else .2
                    if mode=='balanced_context':growth=context if group=='primary' else -.1
                    if mode=='balanced_adaptive':growth=.35 if group=='primary' else -.2
                    if referral and not base:growth=-.01
                    r=dict(split='synthetic',mode=mode,scenario_id=sid,horizon=h,
                        net_real_cagr_pct=growth,annual_real_volatility_pct=2.,
                        max_real_drawdown_pct=60. if referral else 5.,terminal_real_wealth=100.,
                        nominal_fee_sum=-0.0 if sid==1 else 0.,trade_count=0,review_count=h,
                        later_trade_count=0,later_review_count=h-1,trade_share_pct=0.,trade_share_ex_initial_pct=0.,
                        drawdown_peak_year=0,drawdown_peak_kind='initial',drawdown_trough_year=1,
                        drawdown_trough_kind='end',fee_rate=fee,fold_id=(sid-1)%4,
                        human_review_count=None if base else 0,human_review_share_pct=None if base else 0.,
                        first_latch_year=None,target_change_count=None if base else 0,first_deployment_year=None,
                        initial_allocation_deferred=None if base else sid%2==0,**dict(w.COMMON_UNITS,growth_units='percent/year'))
                    rows.append(r)
            groups[group][mode]={'scenario_metrics':rows}
            hashes[group][mode]=a.sha(w.encode_csv(rows,w.SCHEMAS['scenario_metrics']))
    return groups,hashes


def create(repo):
    """Reuse authenticated predecessor Git objects; never create commits."""
    repo=Path(repo)
    git(repo.parent,'clone','--quiet',str(Path(__file__).parent/'fixture/objects.bundle'),str(repo))
    binding=w.strict_json((Path(__file__).parent/'fixture/binding.json').read_bytes())
    # Bundle contains the genuine later HEAD; preserve saved current spellings.
    git(repo,'update-ref','refs/remotes/origin/main',git(repo,'rev-parse','HEAD').decode().strip())
    return binding


def authenticate(repo,binding):
    """Read-only generated authentication using the production Git primitives."""
    repo=Path(repo);w.keys(binding,('C','E','P','task','config_sha256'))
    for x,y in (('C','E'),('E','P')):w.ancestor(repo,binding[x],binding[y])
    task=w.strict_json(w.blob(repo,binding['P'],'ops/tasks/GEN-analysis.json'))
    w.require(w.exact(task,binding['task']) and task['base_commit']==binding['E'],'generated wrong task/base')
    w.validate_publication(repo,task,binding['P'])
    raw,_=a._entry(repo,'config.json',binding['E'],binding['config_sha256']);c=w.strict_json(raw)
    w.keys(c,('kind','source_commit','source_sha256','input_sha256','producers','metric_rows'))
    w.require(c['kind']=='PRIVATE GENERATED CONFIG' and c['source_commit']==binding['C'] and
              c['input_sha256']==a.sha(b'PRIVATE GENERATED INPUT IDENTITY') and c['metric_rows']==320,'generated config/source/input/count')
    a._entry(repo,'source.txt',binding['C'],c['source_sha256'])
    w.require([p['group'] for p in c['producers']]==['primary','doubled'],'generated swapped producers')
    groups={};hashes={}
    for p in c['producers']:
        a._approval(repo,binding['E'],p['task_id'],p['result_commit'],result=True,
                    path=p['acceptance_path'],digest=p['acceptance_sha256'])
        rr=w.blob(repo,p['result_commit'],'handoff/'+p['task_id']+'/result.json')
        r=w.strict_json(rr)
        w.require(a.sha(rr)==p['receipt_sha256'] and r['status']=='completed' and r['failure'] is None and
            r['task_id']=='GEN-'+p['group'] and r['task_sha256']==p['task_digest'] and
            r['artifacts_sha256']==p['artifacts_sha256'],'generated failed/wrong receipt')
        pt=w.strict_json(w.blob(repo,p['result_commit'],'ops/tasks/'+p['task_id']+'.json'))
        w.require(a.sha(a.canonical(pt))==p['task_digest'],'generated wrong producer task')
        w.require(a._files(repo/p['root'])==a.producer_files(),'generated full 44-file inventory')
        w.require(set(p['artifacts_sha256'])=={p['root']+'/'+n for n in a.producer_files()},'generated inventory mismatch')
        raw={}
        for n,h in p['artifacts_sha256'].items(): raw[n[len(p['root'])+1:]],_=a._entry(repo,n,p['result_commit'],h)
        m=w.strict_json(raw['run_manifest.json'])
        w.keys(m,('schema_version','status','split','group','fee_rate','input_sha256','source_commit',
                  'source_sha256','scenario_count','periods','horizons','metric_rows'))
        w.require(m['status']=='completed' and m['group']==p['group'] and m['split']=='synthetic' and
            w.exact(m['fee_rate'],.0025 if p['group']=='primary' else .005) and
            m['source_commit']==c['source_commit'] and m['source_sha256']==c['source_sha256'] and
            m['input_sha256']==c['input_sha256'] and m['scenario_count']==4 and m['metric_rows']==160 and
            m['horizons']==list(w.HORIZONS),'generated source/input/shape/group')
        groups[p['group']]={};hashes[p['group']]={}
        for mode in w.MODES:
            cases={}
            for table in w.TABLES:
                name='cases/'+mode+'/'+table+'.csv'
                cases[table]=w.decode_csv(raw[name],w.SCHEMAS[table],w.KEYS[table])
            groups[p['group']][mode]=cases
            hashes[p['group']][mode]=p['artifacts_sha256'][p['root']+'/cases/'+mode+'/scenario_metrics.csv']
    a._bridge(groups,split='synthetic',n=4,source_hashes=hashes)
    return groups,hashes


def inventory(repo):
    return {p.relative_to(repo).as_posix():a.sha(p.read_bytes()) for p in Path(repo).rglob('*') if p.is_file() and '.git' not in p.parts}


def checkout(repo,dest):
    git(Path(repo).parent,'clone','--quiet','--no-hardlinks',str(repo),str(dest))
    git(dest,'update-ref','refs/remotes/origin/main',git(repo,'rev-parse','refs/remotes/origin/main').decode().strip())


def scalar_facts(t):
    """Expected values use scalar arithmetic and fixed fixture data, not tested helpers."""
    gate=next(r for r in t.comparison_gates if r['candidate_mode']=='balanced_context' and
              r['reference_mode']=='balanced_cost' and r['fee_rate']==.0025 and r['horizon']==30)
    # Both are exactly .1; paired differences zero, four nonpositive fold medians.
    assert gate['median_paired_growth_gain_pp']==.1-.1
    assert gate['positive_fold_count']==0 and not gate['passed']
    assert gate['flags']==dict(gain_at_least_0_10=False,tail_growth_at_least_minus_0_10=True,
                              tail_loss_at_most_1_00=True,at_least_three_positive_folds=False)
    assert t.selection['selected_mode']=='balanced_adaptive'
    assert t.selection['doubled_fee_support']['supported'] is False
    expected={'A':(5,'conservative'),'B':(15,'conservative'),'C':(30,'balanced'),
              'D':(25,'conservative'),'E':(6,'conservative')}
    for r in t.profile_recommendations:
        assert (r['horizon'],r['selected_class'])==expected[r['profile']]
        assert r['personalized_overlay_pending'] is True and r['status']=='provisional'
    return dict(context_gain=(.1-.1).hex(),context_positive_folds=0,context_passed=False,
        primary_selection='balanced_adaptive',doubled_supported=False,
        profile_assignments={k:list(v) for k,v in expected.items()},
        quantile_example=dict(values=[0.,10.,20.,30.],p10=(.7*0.+.3*10.),p90=(.3*20.+.7*30.)))
