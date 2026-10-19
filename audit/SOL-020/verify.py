"""SOL-020 design reference checks. Standard library only; never imports policy code.
Create evidence once with --initialize; --check is strictly read-only.
"""
import argparse
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import math
import subprocess
import sys

BASE = 'a2205fb7edd2527253664efad601f0da290f3661'
TASK_COMMIT = '84144ff2eca205e8575e8d206cd03bb9751835b4'
TASK_SHA = 'e2c0985b6c862afb568ed383a06d3aa4440bb86ef260c2356b7743f8bad044c7'
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
FEES = (F(1,400), F(1,200))
PROFILES = {'A': (5,10,'high'), 'B': (15,25,'medium'), 'C': (30,40,'low'), 'D': (25,15,'medium'), 'E': (6,35,'high')}
MAPPING = {'conservative':'conservative_cost','balanced':'balanced_cost','growth':'growth_cost'}
METRICS = ('p90_loss','p10_growth','median_loss','median_growth','severe_loss','exceedance_count')

def require(ok, reason):
    if not ok:
        raise ValueError(reason)

def normalized(data):
    return data.replace(b'\r\n', b'\n')

def digest(data):
    return hashlib.sha256(data).hexdigest()

def git_blob(commit, path):
    return subprocess.check_output(['git','show',commit+':'+path],cwd=ROOT)

def encode(obj):
    return (json.dumps(obj,sort_keys=True,indent=2,ensure_ascii=False)+'\n').encode()

def q(values, p):
    a = sorted(map(F,values)); rank = (len(a)-1)*F(p)
    lo = rank.numerator//rank.denominator
    hi = min(lo+1,len(a)-1)
    return a[lo]+(rank-lo)*(a[hi]-a[lo])

def reference_latch(completed_events, threshold):
    # Events are explicit real post-fee / year-end values, not simulated policies.
    peak, loss, latched = F(100), F(0), False
    rows=[]
    for t, events in enumerate(completed_events,1):
        prior=loss
        latched = latched or prior >= threshold
        rows.append({'period':t,'latched':latched,'observed_loss':str(prior)})
        for value in events:
            value=F(value); peak=max(peak,value)
            loss=max(loss,100*(1-value/peak))
    return rows, loss, next((x['period'] for x in rows if x['latched']),None)

def screen(losses, growths, tolerance):
    risk=q(losses,F(9,10))<=tolerance
    power=q(growths,F(1,10))>=0
    return {'risk':risk,'power':power,'recommended_class':'conservative' if risk and power else None,
            'failures':([] if risk else ['risk'])+([] if power else ['purchasing_power']),
            'exceedance_count':sum(F(x)>tolerance for x in losses),
            'p90':str(q(losses,F(9,10))),'p10':str(q(growths,F(1,10)))}

def references():
    out={}
    r,loss,latch=reference_latch([(100,75),(75,90),(90,100)],F(25))
    require([x['latched'] for x in r]==[False,True,True] and loss==25 and latch==2,'equality lag/latch')
    out['year_end_equality']={'reviews':r,'loss':str(loss),'first_latch':latch}
    r,loss,latch=reference_latch([(100,100),(100,75)],F(25))
    require(latch is None and loss==25 and len(r)==2,'no fictional H+1')
    out['final_year_crossing']={'H':2,'reviews':r,'loss':str(loss),'first_latch':latch}
    # Initial all-equity transfer: 100/400=1/4 fee. Recovery cannot erase prior loss.
    fee=F(100)*FEES[0]; post=100-fee
    r,loss,latch=reference_latch([(post,post*F(4,3)),(133,F(1197,10))],F(1,4))
    require(fee==F(1,4) and post==F(399,4) and latch==2,'post-fee crossing recovery')
    out['post_fee_crossing_recovery']={'fee':str(fee),'post_fee':str(post),'reviews':r,'first_latch':latch}
    # Pure inflation: 100 nominal / (4/3 CPI) = 75 real.
    r,loss,latch=reference_latch([(100,F(100)/F(4,3)),(75,75)],F(25))
    require(loss==25 and latch==2,'inflation crossing')
    out['pure_inflation']={'loss':str(loss),'first_latch':latch}
    holdings=(F(20),F(30),F(50)); kept=tuple(holdings); transfer=F(0); fee=F(0)
    end=tuple(h*g for h,g in zip(kept,(F(1,2),F(6,5),F(1))))
    require(kept==holdings and fee==transfer==0 and end==(F(10),F(36),F(50)),'pending dollars and returns')
    real=sum(end)/F(5,4)
    require(real==F(384,5),'exact deflation')
    out['pending_holdings']={'pre':list(map(str,holdings)),'post':list(map(str,kept)), 'transfer':str(transfer),'fee':str(fee),'end':list(map(str,end)),'real_end':str(real)}
    # Linear p90 rank is 107.1 (zero-based); ten strict exceedances still pass.
    losses=[F(10)]*110+[F(20)]*10
    p=screen(losses,[F(0)]*120,F(10))
    require(p['risk'] and p['power'] and p['exceedance_count']==10 and p['p90']=='10','p90 is not a cap')
    out['p90_with_exceedances']=p
    cases={'risk_only':([11]*120,[0]*120), 'power_only':([10]*120,[-1]*120), 'both':([11]*120,[-1]*120),'boundary':([10]*120,[0]*120)}
    out['screens']={name:screen(a,b,F(10)) for name,(a,b) in cases.items()}
    require(out['screens']['risk_only']['failures']==['risk'] and out['screens']['power_only']['failures']==['purchasing_power'],'separate failures')
    require(out['screens']['both']['recommended_class'] is None and out['screens']['boundary']['recommended_class']=='conservative','AND and inclusive boundary')
    require(all(out['screens'][k]['recommended_class'] is None for k in ('risk_only','power_only','both')),'no fallback')
    # Prefix identity is exact for identical mode/fee/prior/threshold and fresh state.
    events=[(100,100)]*14+[(100,75)]+[(75,90)]*15
    full,_,_=reference_latch(events,F(25)); direct,loss,first=reference_latch(events[:15],F(25))
    require(full[:15]==direct and first is None and full[15]['latched'],'B H15 prefix diagnostics')
    cagr=100*(.75**(1/15)-1)
    annual=[F(0)]*14+[F(-25)]
    mean=sum(annual)/15
    variance=sum((x-mean)**2 for x in annual)/14
    require(variance==F(125,3) and math.isclose(math.sqrt(float(variance)),25/math.sqrt(15),rel_tol=1e-10,abs_tol=1e-9),'B independent prefix fluctuation ddof1')
    require(math.isclose(100*((F(75)/100)**(1/15)-1),cagr,rel_tol=1e-10,abs_tol=1e-9),'B prefix real CAGR')
    out['B_prefix']={'scalar_cagr_pct':cagr,'sample_variance_pp_squared':str(variance),'H':15,'threshold':25,'exact_event_prefix':True,'prefix_first_latch':first,'full_first_latch':16,'loss':str(loss),'required_production_identity':'all H15 ledger/decision/score/metric fields under identical mode/fee/fold prior, no later diagnostics'}
    a,_,_=reference_latch([(100,90),(90,90)],F(10)); b,_,_=reference_latch([(100,90),(90,90)],F(40))
    require(a[1]['latched'] and not b[1]['latched'],'profile state isolation')
    out['fresh_profile_state']={'A_latches':a[1]['latched'],'C_latches':b[1]['latched']}
    # These are cardinality/key fixtures, not a production adapter or outcome run.
    counts={}
    for name,assigned in [('none',set()),('partial',{('A',FEES[0]),('B',FEES[1]),('D',FEES[0])}),('all',{(p,k) for p in PROFILES for k in FEES})]:
        summaries=[]; ledger_keys=set(); decision_keys=set(); metric_keys=set(); score_keys=set(); suspended=0
        for p,(H,tol,liq) in PROFILES.items():
            for k in FEES:
                execute=(p,k) in assigned
                row={'profile_id':p,'fee_rate':str(k),'H':H,'tolerance':tol,'liquidity':liq,'threshold':tol,
                     'upstream_result_hash':'1'*64,'assignment_hash':'2'*64,
                     'proposed_class':'conservative' if execute else None,'mode':MAPPING['conservative'] if execute else None,
                     'recommended_class':'conservative' if execute else None,
                     'source_case_path':p+'/'+str(k) if execute else None,
                     'status':'eligible_after_personalized_development_rescreen' if execute else 'upstream_referral',
                     'simulation_status':'completed' if execute else 'not_run_upstream_referral',
                     'scenario_count':120 if execute else 0, 'denominator':120 if execute else 0,
                     'risk_pass':True if execute else None,'power_pass':True if execute else None,
                     'reasons':[] if execute else ['original_upstream_reason'],
                     'units':{'growth':'percent/year','loss':'percent'},
                     **{m:0 if execute else None for m in METRICS}}
                summaries.append(row)
                require(len(row['upstream_result_hash'])==len(row['assignment_hash'])==64,'all summary source hashes')
                if not execute:
                    require(all(row[m] is None for m in METRICS) and row['mode'] is None and row['recommended_class'] is None and row['source_case_path'] is None,'referral nulls')
                    continue
                require(row['source_case_path'] is not None and all(row[m] is not None for m in METRICS),'executed source and metrics')
                for s in range(1,121):
                    metric_keys.add((p,k,s,H))
                    # Explicit count fixture: each scenario has one last suspended review.
                    for t in range(1,H+1):
                        key=(p,k,s,t); ledger_keys.add(key); decision_keys.add(key)
                        if t<H: score_keys.add(key+('central',))
                        else: suspended+=1
        expected=sum(PROFILES[p][0]*120 for p,k in assigned)
        require(len(summaries)==10 and len({(r['profile_id'],r['fee_rate']) for r in summaries})==10,'ten unique summary keys')
        require(len(ledger_keys)==len(decision_keys)==expected and len(metric_keys)==120*len(assigned),'conditional counts')
        require(len(score_keys)==expected-suspended and all(key[:4] in decision_keys for key in score_keys),'score links/count')
        counts[name]={'summary_rows':10,'executed_cases':len(assigned),'case_summaries':len(assigned),'annual_ledgers':expected,'decisions':expected,'scenario_metrics':len(metric_keys),'target_score_upper_bound':expected,'scores_with_one_suspended_review_each':len(score_keys),'referral_rows':10-len(assigned),'all_referral_metrics_and_paths_null':True,'every_summary_has_upstream_hashes':True}
    require(counts['all']['annual_ledgers']==19440 and counts['all']['scenario_metrics']==1200,'all count maxima')
    require(counts['partial']['annual_ledgers']==5400 and counts['partial']['scenario_metrics']==360,'partial counts')
    out['conditional_counts']=counts
    # No selected upstream class -> no case; malformed assignment/hash is an error.
    def validate_assignment(cls, candidate, good_hash=True):
        require(good_hash,'upstream hash mismatch')
        require(cls is None or cls in MAPPING,'unknown/adaptive class')
        require(cls==candidate,'assignment/screen mismatch')
        return cls
    errors={}
    for label,args in {'hash':('conservative','conservative',False),'mismatch':('balanced','conservative',True),'adaptive':('balanced_adaptive','balanced_adaptive',True)}.items():
        try: validate_assignment(*args)
        except ValueError as e: errors[label]=str(e)
    require(len(errors)==3 and validate_assignment(None,None) is None,'invalid input is not referral')
    out['assignment_errors']=errors
    primary={'class':'conservative','fee':'1/400'}; counterfactual={'class':'balanced','fee':'1/200'}
    require(primary['class']=='conservative' and primary['class']!=counterfactual['class'],'fee separation')
    def gates(gain,tail_growth,tail_loss,positive_folds):
        return gain>=F(1,10) and tail_growth>=F(-1,10) and tail_loss<=1 and positive_folds>=3
    primary_mode='balanced_context'
    primary_context_gate=gates(F(1,10),F(-1,10),F(1),3)
    doubled_context_gate=gates(F(9,100),F(0),F(0),4)
    doubled_adaptive_both_controls=gates(F(1,5),F(0),F(0),4) and gates(F(1,5),F(0),F(0),4)
    require(primary_context_gate and not doubled_context_gate and doubled_adaptive_both_controls and primary_mode=='balanced_context','independent same-primary-mode robustness')
    out['generic_balanced_robustness']={'primary_mode':primary_mode,'primary_context_gates_pass':primary_context_gate,'doubled_same_primary_supported':doubled_context_gate,'doubled_adaptive_both_controls_pass':doubled_adaptive_both_controls,'primary_remains':primary_mode,'H':30,'threshold_pct':25,'fixed_cost_primary_interpretation':'no added complexity selected; no automatic suitability pass'}
    out['fee_separation']={'primary':primary,'counterfactual':counterfactual,'same_policy_robustness_certified':False,'generic_balanced_test_required':'H30,25 percent; retain primary-selected mode at .005 against its original controls; primary balanced_cost means no added complexity selected'}
    return out

def provenance(evidence):
    raw=git_blob(TASK_COMMIT,'ops/tasks/SOL-020.json')
    require(digest(raw)==TASK_SHA,'pinned task Git hash')
    task=json.loads(raw)
    require(task==json.loads((evidence/'task-lock.json').read_text(encoding='utf-8')),'immutable task mismatch')
    require(task['base_commit']==BASE and task['allowed_paths']==['audit/SOL-020'] and task['owner']=='sol' and task['id']=='SOL-020','task/base/scope')
    hashes={}
    for path,sha in task['parameters']['source_sha256'].items():
        blob=git_blob(BASE,path)
        require(digest(blob)==sha,'pinned source mismatch: '+path)
        disk=(ROOT/path).read_bytes()
        require(normalized(disk)==normalized(blob),'checkout differs from pinned source: '+path)
        hashes[path]=sha
    prior=json.loads(git_blob(BASE,'audit/SOL-013/findings.json'))
    chief=json.loads(git_blob(BASE,'audit/chief/SOL-013-review.json'))
    require(prior['corrected_design_verdict']=='approve' and prior['code_verdict']=='changes_required','preserve prior verdict')
    require(chief['reviewed_commit']==task['parameters']['prior_design_review_commit'],'prior accepted commit')
    conf=json.loads(git_blob(BASE,'specs/personalized_review_v1.json'))
    v2=json.loads(git_blob(BASE,'specs/development_policy_pilot_v2.json'))
    require(conf['profiles']=={p:{'horizon':h,'loss_tolerance_pct':t,'liquidity':l} for p,(h,t,l) in PROFILES.items()},'all profile H/tolerance/liquidity values')
    require(conf['profiles']==v2['profiles'] and conf['class_mode_mapping']==MAPPING,'profile/mode consistency')
    require(conf['fee_rates']==[.0025,.005] and conf['primary_fee_rate']==.0025,'fee consistency')
    require(conf['maximum_rows_if_all_assigned']=={'annual_ledgers':19440,'decisions':19440,'scenario_metrics':1200,'target_scores':19440},'companion row maxima')
    require(not conf['production_execution_authorized'] and not conf['final_data_open'],'no execution/final authorization')
    return {'base_commit':BASE,'task_commit':TASK_COMMIT,'task_git_sha256':TASK_SHA,'source_sha256':hashes,'prior_design_verdict':'approve','historical_kernel_verdict':'changes_required'}

def artifact_hashes(evidence):
    files=sorted(p for p in evidence.rglob('*') if p.is_file() and p.name!='verification.json')
    return {p.relative_to(evidence).as_posix():digest(normalized(p.read_bytes())) for p in files}

def same_evidence(a,b,path=''):
    # Only derived floating CAGR is tolerant. Counts, booleans, Fraction strings,
    # thresholds, source identities and hashes remain exact.
    if path=='reference_facts.B_prefix.scalar_cagr_pct':
        return type(a) is float and type(b) is float and math.isfinite(a) and math.isfinite(b) and math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-9)
    if type(a) is not type(b): return False
    if isinstance(a,dict):
        return a.keys()==b.keys() and all(same_evidence(a[k],b[k],path+'.'+k if path else k) for k in a)
    if isinstance(a,list):
        return len(a)==len(b) and all(same_evidence(x,y,path+'.'+str(i)) for i,(x,y) in enumerate(zip(a,b)))
    return a==b

def run():
    parser=argparse.ArgumentParser()
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--initialize',action='store_true'); mode.add_argument('--check',action='store_true')
    parser.add_argument('--evidence-dir',type=Path,default=HERE)
    args=parser.parse_args(); evidence=args.evidence_dir.resolve()
    require(sys.version_info[:2]==(3,12),'Python 3.12 required')
    require(normalized((evidence/'verify.py').read_bytes())==normalized(Path(__file__).read_bytes()),'evidence verifier differs from executed verifier')
    # --check does not create directories, repair files, run policy code or write logs.
    result={'schema_version':1,'task_id':'SOL-020','python_major_minor':'3.12','provenance':provenance(evidence),'reference_facts':references()}
    facts=json.loads((evidence/'findings.json').read_text(encoding='utf-8'))
    require(facts['design_verdict']=='approve' and facts['implementation_verdict']=='not_reviewed','verdict independence')
    require(facts['blockers']==[] and facts['historical_kernel_verdict']=='changes_required','negative history retained')
    result['design_verdict']=facts['design_verdict']
    result['evidence_integrity_verdict']='verified'
    result['artifact_hash_basis']='UTF-8 bytes with CRLF normalized to LF; no other normalization'
    result['artifacts_sha256']=artifact_hashes(evidence)
    target=evidence/'verification.json'
    if args.initialize:
        with target.open('xb') as stream: stream.write(encode(result))
    else:
        saved=json.loads(target.read_text(encoding='utf-8'))
        require(same_evidence(saved,result),'saved evidence differs from read-only recomputation')
    print(json.dumps({'evidence_integrity_verdict':'verified','design_verdict':facts['design_verdict'],'implementation_verdict':'not_reviewed','historical_kernel_verdict':'changes_required','read_only':bool(args.check),'reference_groups':len(result['reference_facts'])}))

if __name__=='__main__':
    try: run()
    except Exception as error:
        print(type(error).__name__+': '+str(error),file=sys.stderr)
        sys.exit(1)
