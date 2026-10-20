"""Independent saved personalized development audit, stdlib only.

Checks accounting against original development observations, own-horizon metrics,
strict exceedances, inclusive screens, annual latches and B's generic prefix.
Does not rederive utility optimization or certify a final outcome.
"""
from collections import defaultdict
from fractions import Fraction as F
from statistics import stdev
import argparse,csv,hashlib,io,json,math,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
ASSETS=('equity','bond','bill_proxy')
PROFILES={'A':(5,10),'B':(15,25),'C':(30,40),'D':(25,15),'E':(6,35)}
DEV='data/development/scenarios_001_120.csv'
DEV_HASH='9c4ad83f5dda86251a754e126528a71dd930ae88ed7cdb8a0663a327b6bfb7c7'
PRODUCERS={.0025:('6aa2ccdce80834c8beb52a827993f1f587d1d8a6','HY3-004'),.005:('319781ef3c7fb5d4328a0ae4cea438bcc26a6f18','HY3-006')}

def blob(c,p):return subprocess.check_output(['git','show',c+':'+p],cwd=ROOT)
def table(raw):return list(csv.DictReader(io.StringIO(raw.decode('utf8'),newline='')))
def sha(raw):return hashlib.sha256(raw).hexdigest()
def quantile(v,p):
    v=sorted(v);x=(len(v)-1)*p;i=math.floor(x);f=x-i
    return (1-f)*v[i]+f*v[min(i+1,len(v)-1)]
def audit(commit,root):
    assert len(commit)==40 and root.startswith('results/development/') and '..' not in Path(root).parts
    raw=blob(commit,DEV);assert sha(raw)==DEV_HASH
    data={(int(r['scenario_id']),int(r['period'])):r for r in table(raw)}
    assert set(data)=={(s,t) for s in range(1,121) for t in range(1,31)}
    rows=json.loads(blob(commit,root+'/personalized_results.json'));assert len(rows)==10
    assert {(r['component_payload']['profile_id'],r['component_payload']['fee_rate']) for r in rows}=={(p,k) for p in PROFILES for k in PRODUCERS}
    checks=0;counts={};results=[];b_prefix_checks=0
    def eq(a,b,label):
        nonlocal checks
        checks+=1;assert a==b,(label,a,b)
    def near(a,b,label):
        nonlocal checks
        checks+=1;assert math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-9),(label,a,b)
    for wrapper in rows:
        r=wrapper['component_payload'];p=r['profile_id'];k=r['fee_rate'];h,tol=PROFILES[p]
        eq((r['horizon'],r['loss_tolerance_pct'],r['review_threshold_pct']),(h,tol,tol),'own profile')
        eq(r['source_verified'],False,'pure component origin remains explicit')
        eq(wrapper['bridge_authentication']['verified'],True,'authenticated outer bridge')
        eq(r['proposed_class'],wrapper['upstream_record']['selected_class'],'no reranking')
        base=wrapper['source_case_path']
        if r['status']=='upstream_referral':
            eq((r['proposed_class'],r['recommended_class'],base),(None,None,None),'true no-run referral')
            eq((r['scenario_count'],r['denominator'],r['simulation_status']),(0,0,'not_run_upstream_referral'),'no fake outcomes')
            assert all(r[key] is None for key in ('p10_growth_pct','p90_loss_pct','risk_pass','purchasing_power_pass','exceedance_count'))
            results.append(dict(profile=p,fee_rate=k,status=r['status'],proposed_class=None));continue
        assert base and base.startswith('cases/') and '..' not in Path(base).parts
        eq((r['scenario_count'],r['denominator'],r['simulation_status']),(120,120,'completed'),'complete case')
        ledgers=table(blob(commit,root+'/'+base+'/annual_ledgers.csv'))
        decisions=table(blob(commit,root+'/'+base+'/decisions.csv'))
        metrics=table(blob(commit,root+'/'+base+'/scenario_metrics.csv'))
        eq([(int(x['scenario_id']),int(x['period'])) for x in ledgers],[(s,t) for s in range(1,121) for t in range(1,h+1)],'complete own-horizon ledger')
        eq([(int(x['scenario_id']),int(x['period'])) for x in decisions],[(s,t) for s in range(1,121) for t in range(1,h+1)],'complete own-horizon decisions')
        eq([(int(x['scenario_id']),int(x['horizon'])) for x in metrics],[(s,h) for s in range(1,121)],'complete metric keys')
        by=defaultdict(list);ds={(int(x['scenario_id']),int(x['period'])):x for x in decisions}
        for row in ledgers:by[int(row['scenario_id'])].append(row)
        for s,ledger in by.items():
            before=[F(0),F(0),F(100)];cpi=F(1);previous=100.;peak=100.;loss=0.;annual=[];fees=[];moves=[];latched=False
            peak_at=sel_peak=sel_trough=(0,'initial')
            for t,row in enumerate(ledger,1):
                source=data[s,t];decision=ds[s,t]
                eq((row['profile_id'],float(row['review_threshold_pct']),row['mode'],row['split']),(p,float(tol),r['mode'],'development'),'ledger identity')
                held=[F(float(row['holdings_before_'+a])) for a in ASSETS];eq(held,before,'dollar continuity')
                after=[F(float(row['holdings_after_fee_'+a])) for a in ASSETS];end=[F(float(row['holdings_end_'+a])) for a in ASSETS]
                wealth=sum(before);fee=F(float(row['fee']));move=F(float(row['intended_transfer']))
                assert min(before+after+end)>=0
                latched=latched or 100*loss>=tol
                eq(decision['action']=='human_review',latched,'t-1 inclusive review latch')
                if latched:eq(row['engine_action'],'keep','suspended holdings')
                if row['engine_action']=='keep':eq((after,fee,move),(before,F(0),F(0)),'free keep')
                else:
                    eq(row['engine_action'],'rebalance','engine action')
                    weights=[F(float(row['target_'+a])) for a in ASSETS];near(sum(weights),1,'fully invested')
                    near(move,sum(abs(wealth*w-v) for w,v in zip(weights,before))/2,'one-way transfer')
                    eq(float(fee).hex(),(k*float(move)).hex(),'exact fee multiplication')
                    for v,w in zip(after,weights):near(v,(wealth-fee)*w,'pro-rata funding')
                near(sum(after)+fee,wealth,'self financing');near(row['cpi_before'],cpi,'CPI before')
                for a,v,end_value in zip(ASSETS,after,end):
                    eq(float(row['return_'+a]),float(source[a+'_return']),'original return')
                    near(end_value,v*(1+F(float(source[a+'_return']))),'return after fee')
                eq(float(row['inflation']),float(source['inflation']),'original inflation')
                cpi*=1+F(float(source['inflation']));real=float(sum(end)/cpi);post=float(sum(after)/(cpi/(1+F(float(source['inflation'])))))
                near(row['cpi_end'],cpi,'compound CPI');near(row['real_wealth_end'],real,'exact deflation');near(row['real_wealth_after_fee'],post,'post-fee deflation')
                annual.append(float(row['real_wealth_end'])/previous-1);previous=float(row['real_wealth_end'])
                near(row['annual_net_real_return'],annual[-1],'net annual return')
                for kind,value in (('post_fee',float(row['real_wealth_after_fee'])),('end',float(row['real_wealth_end']))):
                    if value>peak:peak=value;peak_at=(t,kind)
                    dd=1-value/peak
                    if dd>loss:loss=dd;sel_peak=peak_at;sel_trough=(t,kind)
                fees.append(float(fee));moves.append(float(move));before=end
            m=metrics[s-1]
            expected=dict(net_real_cagr_pct=100*((previous/100)**(1/h)-1),max_real_drawdown_pct=100*loss,terminal_real_wealth=previous,annual_real_volatility_pct=100*stdev(annual),nominal_fee_sum=sum(fees),trade_count=sum(v>1e-10 for v in moves),review_count=h,later_trade_count=sum(v>1e-10 for v in moves[1:]),later_review_count=h-1)
            for key,value in expected.items():near(m[key],value,key)
            eq((int(m['drawdown_peak_year']),m['drawdown_peak_kind'],int(m['drawdown_trough_year']),m['drawdown_trough_kind']),(*sel_peak,*sel_trough),'severe locations')
            near(m['trade_share_pct'],100*expected['trade_count']/h,'trade share');near(m['trade_share_ex_initial_pct'],100*expected['later_trade_count']/(h-1),'later share')
        growth=[float(m['net_real_cagr_pct']) for m in metrics];losses=[float(m['max_real_drawdown_pct']) for m in metrics]
        for key,values,q in [('median_growth_pct',growth,.5),('p10_growth_pct',growth,.1),('median_loss_pct',losses,.5),('p90_loss_pct',losses,.9)]:near(r[key],quantile(values,q),key)
        exceed=sum(v>tol for v in losses);eq(r['exceedance_count'],exceed,'strict exceedances');near(r['exceedance_fraction'],exceed/120,'exceedance fraction')
        risk=quantile(losses,.9)<=tol;power=quantile(growth,.1)>=0
        eq((r['risk_pass'],r['purchasing_power_pass']),(risk,power),'inclusive screens')
        eq(r['recommended_class'],r['proposed_class'] if risk and power else None,'no fallback')
        eq(r['status'],'eligible_after_personalized_development_rescreen' if risk and power else 'human_review_after_rescreen','honest outcome')
        if p=='B':
            c,task=PRODUCERS[k];generic=table(blob(c,f'results/development/{task}/cases/'+r['mode']+'/scenario_metrics.csv'))
            indexed={int(m['scenario_id']):m for m in generic if int(m['horizon'])==h}
            for m in metrics:
                for key in ('net_real_cagr_pct','max_real_drawdown_pct','terminal_real_wealth','nominal_fee_sum','trade_share_pct'):
                    eq(float(m[key]).hex(),float(indexed[int(m['scenario_id'])][key]).hex(),'B exact generic prefix');b_prefix_checks+=1
        counts[p+'/'+str(k)]=dict(ledgers=len(ledgers),decisions=len(decisions),metrics=len(metrics))
        results.append(dict(profile=p,fee_rate=k,proposed_class=r['proposed_class'],status=r['status'],p10_growth_pct=r['p10_growth_pct'],p90_loss_pct=r['p90_loss_pct'],exceedance_count=exceed))
    return dict(status='passed',result_commit=commit,root=root,independent_stdlib=True,development_input_sha256=DEV_HASH,final_data_read=False,scalar_checks=checks,B_generic_prefix_checks=b_prefix_checks,case_counts=counts,ten_results=results,scope='Independent original-development accounting, saved metrics/screens and review-latch acceptance; utility choice relies on separately accepted implementation.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--commit',required=True);p.add_argument('--root',required=True);a=p.parse_args();print(json.dumps(audit(a.commit,a.root),indent=2))
