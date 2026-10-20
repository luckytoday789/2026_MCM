"""Qualification only: adapt accepted generic B H15 bytes, no production run."""
import csv,io,json,sys
from copy import deepcopy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import check_personalized_result as a
C='6aa2ccdce80834c8beb52a827993f1f587d1d8a6';ROOT='results/development/GENERATED-ORACLE-QUALIFICATION'
original=a.blob

def encode(rows):
    out=io.StringIO(newline='');w=csv.DictWriter(out,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows);return out.getvalue().encode()

def qualify():
    generic='results/development/HY3-004/cases/balanced_cost/'
    metric=[r for r in a.table(original(C,generic+'scenario_metrics.csv')) if r['horizon']=='15']
    summary=next(r for r in a.table(original(C,generic+'summary.csv')) if r['horizon']=='15')
    risk=float(summary['p90_loss_pct'])<=25;power=float(summary['p10_growth_pct'])>=0
    rows=[]
    for profile,(h,tol) in a.PROFILES.items():
        for fee in a.PRODUCERS:
            executed=profile=='B' and fee==.0025
            r=dict(profile_id=profile,fee_rate=fee,horizon=h,loss_tolerance_pct=tol,review_threshold_pct=tol,source_verified=False,
                proposed_class='balanced' if executed else None,recommended_class='balanced' if executed and risk and power else None,
                mode='balanced_cost' if executed else None,scenario_count=120 if executed else 0,denominator=120 if executed else 0,
                simulation_status='completed' if executed else 'not_run_upstream_referral',status=('eligible_after_personalized_development_rescreen' if risk and power else 'human_review_after_rescreen') if executed else 'upstream_referral')
            for key in ('median_growth_pct','p10_growth_pct','median_loss_pct','p90_loss_pct'):r[key]=float(summary[key]) if executed else None
            r.update(risk_pass=risk if executed else None,purchasing_power_pass=power if executed else None,
                exceedance_count=sum(float(m['max_real_drawdown_pct'])>25 for m in metric) if executed else None,
                exceedance_fraction=sum(float(m['max_real_drawdown_pct'])>25 for m in metric)/120 if executed else None)
            rows.append(dict(component_payload=r,bridge_authentication={'verified':True},upstream_record={'selected_class':r['proposed_class']},source_case_path='cases/B-primary' if executed else None))
    saved={ROOT+'/personalized_results.json':json.dumps(rows).encode()}
    for name in ('annual_ledgers','decisions','scenario_metrics'):
        selected=metric if name=='scenario_metrics' else [r for r in a.table(original(C,generic+name+'.csv')) if int(r['period'])<=15]
        selected=[r|dict(profile_id='B',review_threshold_pct=25) for r in selected]
        saved[ROOT+'/cases/B-primary/'+name+'.csv']=encode(selected)
    def read(c,p):return saved[p] if p in saved else original(c,p)
    a.blob=read
    result=a.audit(C,ROOT)
    rejected=[]
    for kind in ('fee','latch','screen'):
        target=ROOT+'/cases/B-primary/'+('annual_ledgers.csv' if kind=='fee' else 'decisions.csv') if kind!='screen' else ROOT+'/personalized_results.json'
        old=saved[target]
        if kind=='screen':
            changed=deepcopy(rows);b=next(r['component_payload'] for r in changed if r['source_case_path']);b['risk_pass']=not b['risk_pass'];saved[target]=json.dumps(changed).encode()
        else:
            changed=a.table(old)
            if kind=='fee':changed[0]['fee']=str(float(changed[0]['fee'])+.01)
            else:changed[0]['action']='human_review'
            saved[target]=encode(changed)
        try:a.audit(C,ROOT)
        except AssertionError:rejected.append(kind)
        else:raise AssertionError('corruption accepted: '+kind)
        finally:saved[target]=old
    assert rejected==['fee','latch','screen']
    return dict(status='passed',qualification_only=True,production_result_accepted=False,fixture='accepted generic B15 prefix adapted in memory; nine explicit no-run rows are generated schema fixtures, not assignments',source_commit=C,scalar_checks=result['scalar_checks'],B_generic_prefix_checks=result['B_generic_prefix_checks'],corruptions_rejected=rejected,final_data_read=False)

if __name__=='__main__':
    result=qualify();print(json.dumps(result,indent=2))
