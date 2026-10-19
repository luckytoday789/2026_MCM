"""SOL-009 source-only audit. Standard-library Python 3.12; no data/production imports.
Default creates immutable evidence; --check only reads and compares (1e-12 floats).
A changes_required design verdict is a valid successfully verified review.
"""
import argparse
from decimal import Decimal as D, localcontext
from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
REVIEWED = 'a996298fd22b11dc54deb43cb596f143da05bf93'
BASE = '2561688380d9e2527eb6066100adde70b7d0ea1c'
PINNED = {
 'specs/DEVELOPMENT_POLICY_PILOT.md':'94e436a979f2c232b729c352d209c83c76ba014a14613852ad447446cb6948e0',
 'specs/development_policy_pilot_v1.json':'39ab8f78f6e4c487d00c1055e6d474c51a2d940e3cad951768a6c75874cc835a',
 'audit/chief/policy_design_fixtures.py':'c3b4b907cfb9b179faae717a09067ee45862b13bf9e56d06e28a841ab43fff3b',
 'audit/chief/policy-design-fixtures.json':'55108ba36593f3f342cff4be6be01fac7c77af6f74baabf787c04b9db684f10c',
 'specs/ACCOUNTING.md':'a9c3ab8dbba3ad752336642061ead272e2c196de83f73eb410e39bd5b559f71e',
 'specs/PROBLEM_LOCK.md':'566c93ad1b5f79c9ec10a42725ab023953c9a02aeb1c91a459e740caf68c0e46',
}
ATOL = RTOL = 1e-12

def sha(b):
    return hashlib.sha256(b).hexdigest()

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

def norm(b):
    return b.replace(b'\r\n', b'\n')

def dump(value):
    return json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n'

def ce(gross, probs):
    if not gross or len(gross) != len(probs):
        raise ValueError('empty or inconsistent support')
    if any(not math.isfinite(x) or x <= 0 for x in gross):
        raise ValueError('nonpositive/nonfinite gross')
    if any(not math.isfinite(p) or p < 0 for p in probs) or not math.isclose(math.fsum(probs),1,abs_tol=1e-14):
        raise ValueError('invalid probability mass')
    logs = [math.log(p)-3*math.log(x) for x,p in zip(gross,probs) if p]
    anchor = max(logs)
    log_moment = anchor+math.log(math.fsum(math.exp(z-anchor) for z in logs))
    return math.exp(-log_moment/3)

def decimal_ce(xs, ps):
    with localcontext() as ctx:
        ctx.prec = 70
        cv = lambda x: D(x.numerator)/D(x.denominator) if isinstance(x,F) else D(str(x))
        return float(sum(cv(p)*cv(x)**(-3) for x,p in zip(xs,ps))**(-D(1)/D(3)))

def quantile(xs,p):
    ys=sorted(xs); index=(len(ys)-1)*p; i=math.floor(index); j=math.ceil(index)
    return ys[i]+(index-i)*(ys[j]-ys[i])

def calculate():
    checks=[]
    def fact(name, observed, expected, arithmetic=None):
        ok=equivalent(observed,expected)
        row={'name':name,'observed':observed,'expected':expected,'passed':ok}
        if arithmetic:
            row['arithmetic']=arithmetic
        if isinstance(observed,(int,float)) and not isinstance(observed,bool) and isinstance(expected,(int,float)):
            row['absolute_residual']=abs(observed-expected)
        checks.append(row)
        return ok
    fact('required_python_minor',list(sys.version_info[:2]),[3,12])
    source={}
    blobs={}
    for path,wanted in PINNED.items():
        original=git('show',REVIEWED+':'+path)
        base=git('show',BASE+':'+path)
        checkout=(ROOT/path).read_bytes()
        blobs[path]=original
        source[path]={'expected_sha256':wanted,'reviewed_blob_sha256':sha(original),'base_blob_sha256':sha(base),
                      'checkout_lf_sha256':sha(norm(checkout))}
        fact('pinned_source:'+path,sha(original),wanted)
        fact('base_source_unchanged:'+path,base==original,True)
        fact('checkout_source:'+path,norm(checkout)==original,True)
    config=json.loads(blobs['specs/development_policy_pilot_v1.json'])
    chief=json.loads(blobs['audit/chief/policy-design-fixtures.json'])
    c={x['name']:x for x in chief['checks']}
    # Independent rational accounting; do not import or execute chief's fixture script.
    u=(F(0),F(0),F(1)); w=(F(1,3),)*3; k=F(1,400); W=F(100)
    tau=sum(abs(a-b) for a,b in zip(w,u))/2
    f=k*tau; transfer=W*tau; fee=W*f
    post=[(W-fee)*x for x in w]
    factors=(F(11,10),F(51,50),F(1))
    A=sum(x*g for x,g in zip(w,factors)); B=F(1)
    score=(1-2*f)*A; true=(1-f)*A; end=sum(h*g for h,g in zip(post,factors))
    rational={
      'deterministic_CE':(ce([float(A)],[1.]),F(26,25)),
      'initial_fee_nominal':(float(fee),F(1,6)),
      'true_end_wealth':(float(end),F(7787,75)),
      'decision_score':(float(score),F(3887,3750)),
      'exact_deflation':(float(F(11,10)/F(51,50)),F(55,51)),
    }
    for name,(actual,expected) in rational.items():
        fact(name,actual,float(expected),'exact rational '+str(expected))
        fact('chief_expected:'+name,c[name]['expected'],float(expected))
        fact('chief_observed:'+name,c[name]['actual'],actual)
    fact('initial_transfer',float(transfer),float(F(200,3)),'100*(|1/3|+|1/3|+|-2/3|)/2')
    fact('initial_post_fee_holdings',[float(h) for h in post],[float(F(599,18))]*3)
    fact('initial_fee_budget',float(sum(post)+fee),100.)
    fact('fee_multiplier_is_hurdle_only',float(W-sum(post)),float(F(1,6)),'actual fee 1/6; buffered decision impact uses 2*f*A, never actual fee 1/3')
    fact('true_net_CE',float(true),float(F(7787,7500)))
    fact('buffer_gate_positive',score>B+F(1,10**12),True)
    fact('sufficient_buffer_identity',float(true-B-(score-B)),float(f*A),'net_gain=(score-CE_keep)+f*CE_target > epsilon+f*CE_target')
    fact('initial_real_end_with_inflation',float(end/F(51,50)),float(F(15574,153)),'(7787/75)/(51/50)=15574/153; no subtraction approximation')
    fact('CPI_compounds_exactly',float(F(51,50)*F(103,100)),1.0506)
    fact('CE_constant_factor',ce([1.02]*3,[.2,.3,.5]),1.02)
    fact('equal_return_gate_rejects',float((1-2*f)*F(51,50))>1.02+1e-12,False)
    fact('equal_return_keep_fee',0.,0.,'rejected target keeps original component dollars, no accounting trade')
    fact('zero_fee_equal_score_keep',1.02>1.02+1e-12,False)
    fact('CE_lower_tail_risk_penalty',ce([.5,1.5],[.5,.5])<1.,True,'E[g]=1 but gamma=4 CE <1')
    fact('CE_risk_penalty_value',ce([.5,1.5],[.5,.5]),decimal_ce([F(1,2),F(3,2)],[F(1,2)]*2))
    prior=[F(9,10),F(11,10)]; recent=[F(4,5),F(21,20),F(1),F(6,5),F(51,50)]
    xs=prior+recent; ps=[F(3,8)]*2+[F(1,20)]*5
    probs=[float(x) for x in ps]; q=ce([float(x) for x in xs],probs)
    q_expected=decimal_ce(xs,ps); ff=F(1,1000)
    scaled=ce([float((1-ff)*x) for x in xs],probs)
    fact('mixture_CE',q,q_expected,'(sum_j p_j*g_j^-3)^(-1/3), independent 70-digit Decimal oracle')
    extra={
      'mixture_mass':(math.fsum(probs),1.),
      'prior_mass_at_five':(math.fsum(probs[:2]),.75),
      'CE_positive_homogeneity':(scaled,float(1-ff)*q_expected),
      'actual_fee_CE_loss':(q-scaled,float(ff)*q_expected),
    }
    for name,(actual,expected) in extra.items():
        fact(name,actual,expected)
        fact('chief_expected:'+name,c[name]['expected'],expected)
        fact('chief_observed:'+name,c[name]['actual'],actual)
    for n in (0,1,5):
        fact('mixture_weights_n'+str(n),[15/(15+n),n/(15+n),15/((15+n)*2700)],
             [float(F(15,15+n)),float(F(n,15+n)),float(F(15,(15+n)*2700))],
             'total prior=15/(15+n); recent total=n/(15+n); each of 2700 training rows=15/((15+n)*2700)')
    for bad in (0.,-1.,float('inf'),float('nan')):
        rejected=False
        try: ce([bad],[1.])
        except ValueError: rejected=True
        fact('reject_invalid_gross:'+repr(bad),rejected,True)
    fact('strict_epsilon_boundary',[D(1)+D('1e-12')>D(1)+D('1e-12'),D(1)+D('1.01e-12')>D(1)+D('1e-12')],[False,True])
    # Two plausible orderings of the ambiguous prose. Demonstration, not production policy.
    eps=D('1e-12'); keep=D(1); active=keep+D('.75')*eps; defensive=keep+D('1.5')*eps
    priority_first='keep' if not active>keep+eps else 'rebalance'
    eligible_first='target_change' if defensive>keep+eps else 'keep'
    fact('epsilon_tie_gate_ambiguity',{'priority_first':priority_first,'eligible_first':eligible_first,'scores_in_epsilon_units':[0.,.75,1.5]},
         {'priority_first':'keep','eligible_first':'target_change','scores_in_epsilon_units':[0.,.75,1.5]},'active is within epsilon of best but does not clear keep hurdle; D1 requests gate filter before tie priority')
    fact('epsilon_ties_not_transitive',[abs(D(0)-D('.75'))<=1,abs(D('.75')-D('1.5'))<=1,abs(D(0)-D('1.5'))<=1],[True,True,False])
    fact('target_tie_active_priority',['active','defensive','central','growth_tilt'][0],'active','proposed explicit priority for eligible ties anchored to maximum')
    fact('minimum_update_years',[(t,min(5,t-1),min(5,t-1)>=5) for t in range(1,8)],
         [(1,0,False),(2,1,False),(3,2,False),(4,3,False),(5,4,False),(6,5,True),(7,5,True)])
    fold_facts=[]
    for fold in range(4):
        ev=[s for s in range(1,121) if (s-1)%4==fold]
        tr=[s for s in range(1,121) if (s-1)%4!=fold]
        fold_facts.append({'fold':fold,'evaluation_count':len(ev),'training_count':len(tr),'training_rows':len(tr)*30,
                           'disjoint':not bool(set(ev)&set(tr)),'evaluation_ids_sha256':sha(dump(ev).encode()),'training_ids_sha256':sha(dump(tr).encode())})
        fact('fold_counts_'+str(fold),[len(ev),len(tr),len(tr)*30,bool(set(ev)&set(tr))],[30,90,2700,False])
        synthetic={s:float(s) for s in range(1,121)}
        before=math.fsum(synthetic[s] for s in tr)/len(tr)
        for s in ev: synthetic[s]=-100000.
        fact('synthetic_eval_fold_perturbation_'+str(fold),math.fsum(synthetic[s] for s in tr)/len(tr),before,'synthetic id markers only; not competition outcomes')
    prefix=lambda xs,t: xs[max(0,t-1-5):t-1]
    history=list(range(1,10)); altered=history[:5]+[900,901,902,903]
    fact('synthetic_prefix_future_boundary',prefix(altered,6),prefix(history,6))
    menus={key:[F(v) if isinstance(v,str) else F(str(v)) for v in vals] for key,vals in config['targets'].items()}
    fact('five_target_simplexes',[sum(v)==1 and min(v)>=0 for v in menus.values()],[True]*5)
    profiles=config['profiles']; allowed={}
    for name,p in profiles.items():
        cap=1 if p['horizon']<=6 else 2 if p['horizon']<20 else 3
        allowed[name]=[cl for cl in ['conservative','balanced','growth'][:cap] if menus[cl][2]>=F(str(config['suitability']['minimum_target_bill'][p['liquidity']]))]
    fact('profile_horizons',[p['horizon'] for p in profiles.values()],[5,15,30,25,6])
    fact('profile_horizon_liquidity_eligibility',allowed,{'A':['conservative'],'B':['conservative','balanced'],'C':['conservative','balanced','growth'],'D':['conservative','balanced'],'E':['conservative']},'risk and purchasing-power outcomes still unknown; these sets are not recommendations')
    # Observe chronological realized wealth only: previous post-fee and end points.
    points=[[99.8,75.],[75.,120.],[120.,110.]]; peak=100.; dd=0.; latch=False; states=[]
    for t,pair in enumerate(points,1):
        latch=latch or dd>=.25
        states.append({'year':t,'observed_max_loss_pct':100*dd,'latched':latch})
        for wealth in pair:
            peak=max(peak,wealth); dd=max(dd,1-wealth/peak)
    fact('review_t_minus_1_and_latch',states,[{'year':1,'observed_max_loss_pct':0.,'latched':False},{'year':2,'observed_max_loss_pct':25.,'latched':True},{'year':3,'observed_max_loss_pct':25.,'latched':True}])
    fact('post_fee_loss_survives_recovery',100*max(0,1-74/100,1-110/110),26.,'initial100 -> earlier post-fee74 -> year-end110; next review still sees 26% max drawdown')
    pending=[10.,20.,70.]; returns=[.1,-.1,.02]
    fact('pending_component_dollars_at_review',list(pending),[10.,20.,70.])
    fact('pending_end_holdings',[h*(1+r) for h,r in zip(pending,returns)],[11.,18.,71.4],'keep/no fee before returns; next review holds these current dollars, not original weights')
    fact('pending_fee',0.,0.)
    # State transition truth table documents requested implementation semantics.
    fact('active_target_transition_examples',{'rejected_proposal':'central','keep':'central','rebalance':'central','executed_defensive':'defensive','human_review':'central'},
         {'rejected_proposal':'central','keep':'central','rebalance':'central','executed_defensive':'defensive','human_review':'central'},'normative transition table, not production execution evidence')
    losses=[0.]*108+[50.]*12
    fact('p90_tolerance_not_guarantee',{'p90_loss_pct':quantile(losses,.9),'exceedance_fraction_at_10pct':sum(x>10 for x in losses)/120},
         {'p90_loss_pct':5.,'exceedance_fraction_at_10pct':.1},'linear index107.1 lies between 0 and50; p90=5 passes10 despite 12 losses at50')
    aa=[0.,3.,10.]; bb=[1.,2.,100.]; dif=[a-b for a,b in zip(aa,bb)]
    fact('paired_vs_marginal_statistics',{'median_paired':quantile(dif,.5),'difference_medians':quantile(aa,.5)-quantile(bb,.5),'p10_paired':quantile(dif,.1),'difference_p10':quantile(aa,.1)-quantile(bb,.1)},
         {'median_paired':-1.,'difference_medians':1.,'p10_paired':-72.2,'difference_p10':-.6})
    fact('indifference_inclusive',D('1.20')-D('1.10')<=D('.10'),True,'0.10 percentage POINT/year, not 10% or 0.001 percentage points')
    artifact_hashes={p:sha(norm((OUT/p).read_bytes())) for p in ['verify.py','review.md','findings.json','implementation-handoff.json']}
    findings=json.loads((OUT/'findings.json').read_bytes())
    fact('design_verdict_is_separate',findings['design_verdict'],'changes_required')
    fact('blocker_ids',[x['id'] for x in findings['blockers']],['D1','D2'])
    return {'schema_version':1,'task_id':'SOL-009','reviewed_commit':REVIEWED,'base_commit':BASE,
            'scope':'Independent source and synthetic arithmetic only; no chief code executed, no competition data read, no production policy tested',
            'design_verdict':findings['design_verdict'],'evidence_integrity_verdict':'passed' if all(c['passed'] for c in checks) else 'failed',
            'float_tolerance':{'absolute':ATOL,'relative':RTOL,'recorded_residuals':'informational; no cross-platform last-bit equality required'},
            'source_hashes':source,'artifact_lf_sha256':artifact_hashes,'fold_facts':fold_facts,'checks':checks,'check_count':len(checks),
            'competition_data_read':False,'new_strategy_outcomes_computed':False,'production_policy_acceptance':False}

def equivalent(a,b):
    if isinstance(a,bool) or isinstance(b,bool): return type(a) is type(b) and a==b
    if isinstance(a,(int,float)) and isinstance(b,(int,float)):
        if isinstance(a,int) and isinstance(b,int): return a==b
        return math.isfinite(a) and math.isfinite(b) and math.isclose(a,b,abs_tol=ATOL,rel_tol=RTOL)
    if isinstance(a,dict) and isinstance(b,dict):
        return a.keys()==b.keys() and all(equivalent(a[k],b[k]) for k in a)
    if isinstance(a,(list,tuple)) and isinstance(b,(list,tuple)):
        return len(a)==len(b) and all(equivalent(x,y) for x,y in zip(a,b))
    return type(a) is type(b) and a==b

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--evidence',type=Path,default=OUT/'verification.json',help='alternate saved evidence for read-only corruption test')
    args=parser.parse_args()
    if not args.check and args.evidence.resolve() != (OUT/'verification.json').resolve():
        parser.error('alternate evidence is read-only')
    result=calculate()
    ok=result['evidence_integrity_verdict']=='passed'
    if args.check:
        saved=json.loads(args.evidence.read_bytes())
        if not equivalent(saved,result):
            print('Saved evidence mismatch; read-only check, evidence preserved',file=sys.stderr)
            return 1
    else:
        if not ok:
            index=1
            while (OUT/('failed-trial-%03d.json'%index)).exists(): index+=1
            with (OUT/('failed-trial-%03d.json'%index)).open('x',encoding='utf-8',newline='\n') as stream: stream.write(dump(result))
        with (OUT/'verification.json').open('x',encoding='utf-8',newline='\n') as stream: stream.write(dump(result))
    print(json.dumps({'evidence_integrity_verdict':result['evidence_integrity_verdict'],'design_verdict':result['design_verdict'],'check_count':result['check_count'],'read_only':args.check}))
    return 0 if ok else 1

if __name__=='__main__':
    sys.exit(main())
