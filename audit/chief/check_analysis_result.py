"""Independent stdlib recomputation of saved development selection and screens.

Reads only immutable saved development artifacts, never observations or a final
input. This is a chief numerical review, not a worker execution receipt.
"""
import argparse,csv,io,json,math,subprocess

PRIMARY='6aa2ccdce80834c8beb52a827993f1f587d1d8a6'
DOUBLED='319781ef3c7fb5d4328a0ae4cea438bcc26a6f18'
MODES=('bills_keep','equal_weight_annual','equal_weight_buy_hold','conservative_cost','balanced_cost','growth_cost','balanced_context','balanced_adaptive')
PROFILE={'A':(5,10,'high'),'B':(15,25,'medium'),'C':(30,40,'low'),'D':(25,15,'medium'),'E':(6,35,'high')}

def blob(commit,path):return subprocess.check_output(['git','show',commit+':'+path])
def js(commit,path):return json.loads(blob(commit,path))
def q(values,p):
    v=sorted(values);position=(len(v)-1)*p;lo=math.floor(position);hi=math.ceil(position)
    return v[lo]+(position-lo)*(v[hi]-v[lo])

def audit(commit,root):
    indexed={};checks=0
    def close(a,b):
        nonlocal checks
        assert math.isclose(a,b,rel_tol=1e-11,abs_tol=1e-10),(a,b);checks+=1
    for task,C,fee in [('HY3-004',PRIMARY,.0025),('HY3-006',DOUBLED,.005)]:
        for mode in MODES:
            rows=csv.DictReader(io.StringIO(blob(C,f'results/development/{task}/cases/{mode}/scenario_metrics.csv').decode()))
            for row in rows:
                key=(mode,fee,int(row['horizon']),int(row['scenario_id']))
                assert key not in indexed
                indexed[key]={k:float(row[k]) for k in ('net_real_cagr_pct','max_real_drawdown_pct','terminal_real_wealth','nominal_fee_sum','trade_share_pct','trade_share_ex_initial_pct')}
    assert len(indexed)==9600
    gates=js(commit,root+'/comparison_gates.json');assert len(gates)==100
    support={}
    for gate in gates:
        a,b,k,h=(gate[x] for x in ('candidate_mode','reference_mode','fee_rate','horizon'))
        aa=[indexed[a,k,h,s] for s in range(1,121)];bb=[indexed[b,k,h,s] for s in range(1,121)]
        delta=[x['net_real_cagr_pct']-y['net_real_cagr_pct'] for x,y in zip(aa,bb)]
        gain=q(delta,.5)
        tail=q([x['net_real_cagr_pct'] for x in aa],.1)-q([x['net_real_cagr_pct'] for x in bb],.1)
        loss=q([x['max_real_drawdown_pct'] for x in aa],.9)-q([x['max_real_drawdown_pct'] for x in bb],.9)
        positives=0
        for f in range(4):
            median=q([delta[s-1] for s in range(1,121) if (s-1)%4==f],.5)
            close(gate['folds'][f]['median_paired_growth_gain_pp'],median)
            assert gate['folds'][f]['positive']==(median>0);positives+=median>0
        close(gate['median_paired_growth_gain_pp'],gain);close(gate['marginal_p10_growth_difference_pp'],tail);close(gate['marginal_p90_loss_difference_pp'],loss)
        expected={'gain_at_least_0_10':gain>=.10,'tail_growth_at_least_minus_0_10':tail>=-.10,'tail_loss_at_most_1_00':loss<=1,'at_least_three_positive_folds':positives>=3}
        assert gate['flags']==expected and gate['passed']==all(expected.values())
        support[a,b,k,h]=gate['passed']
    context=support['balanced_context','balanced_cost',.0025,30]
    adaptive=support['balanced_adaptive','balanced_context',.0025,30] and support['balanced_adaptive','balanced_cost',.0025,30]
    selected='balanced_adaptive' if adaptive else 'balanced_context' if context else 'balanced_cost'
    selection=js(commit,root+'/selection.json');assert selection['selected_mode']==selected and selection['sensitivity_may_reselect'] is False
    config=js(commit,'specs/development_policy_pilot_v2.json');screens=js(commit,root+'/profile_screen.json');recs=js(commit,root+'/profile_recommendations.json')
    assert len(screens)==30 and len(recs)==10
    for rec in recs:
        profile,fee=rec['profile'],rec['fee_rate'];h,tol,liq=PROFILE[profile];eligible=[]
        for rank,cls in enumerate(('conservative','balanced','growth')):
            screen=next(r for r in screens if (r['profile'],r['fee_rate'],r['candidate_class'])==(profile,fee,cls))
            rr=[indexed[cls+'_cost',fee,h,s] for s in range(1,121)]
            growth=q([r['net_real_cagr_pct'] for r in rr],.1);loss=q([r['max_real_drawdown_pct'] for r in rr],.9);median=q([r['net_real_cagr_pct'] for r in rr],.5)
            reserve=config['targets'][cls][2];reserve=1/3 if reserve=='1/3' else reserve
            rules=config['suitability'];cap=0 if h<=6 else 1 if h<20 else 2
            flags={'horizon_eligible':rank<=cap,'willingness_eligible':cls in rules['eligible_classes_before_outcome_screens'][profile],'liquidity_pass':reserve>=rules['minimum_target_bill'][liq],'risk_pass':loss<=tol,'purchasing_power_pass':growth>=0}
            assert screen['flags']==flags and screen['qualified']==all(flags.values())
            close(screen['p10_growth_pct'],growth);close(screen['p90_loss_pct'],loss);close(screen['median_growth_pct'],median)
            assert screen['exceedance_count']==sum(r['max_real_drawdown_pct']>tol for r in rr)
            if all(flags.values()):eligible.append((cls,median))
        best=max((v for _,v in eligible),default=None)
        near=[cls for cls,value in eligible if best-value<=.10]
        assert rec['selected_class']==(near[0] if near else None)
    return {'status':'passed','result_commit':commit,'root':root,'metric_rows':len(indexed),'comparison_gates':len(gates),'profile_screens':len(screens),'recommendations':len(recs),'scalar_comparisons':checks,'selected_mode':selected,'observations_read':False,'final_data_read':False,'method':'Independent stdlib sorted linear quantiles, direct frozen threshold predicates and class ordering; immutable saved producer metrics only.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--commit',required=True);p.add_argument('--root',required=True);a=p.parse_args()
    print(json.dumps(audit(a.commit,a.root),indent=2))
