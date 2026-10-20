"""Independent scalar checks of failed SOL-034 generated persisted fixtures only.
No SafeInvest imports, real competition inputs, strategy execution or approval.
"""
import argparse,csv,hashlib,io,json,math,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
MODES=('bills_keep','equal_weight_annual','equal_weight_buy_hold','conservative_cost','balanced_cost','growth_cost','balanced_context','balanced_adaptive')
FIELDS=('net_real_cagr_pct','max_real_drawdown_pct','terminal_real_wealth','nominal_fee_sum','trade_share_pct','trade_share_ex_initial_pct','human_review_count','human_review_share_pct','target_change_count')
def audit(commit,overrides=None,fixture_task='SOL-034'):
 assert re.fullmatch(r'SOL-[0-9]+',fixture_task)
 hashes={};checks=0;maximum=0.
 def read(name):
  p='audit/'+fixture_task+'/fixture/'+name;raw=subprocess.check_output(['git','show',commit+':'+p],cwd=ROOT);hashes[p]=hashlib.sha256(raw).hexdigest();return (overrides or {}).get(name,raw)
 def table(name):return list(csv.DictReader(io.StringIO(read(name).decode(),newline='')))
 def eq(a,b,label):
  nonlocal checks
  checks+=1;assert type(a) is type(b) and a==b,(label,a,b)
 def near(a,b,label):
  nonlocal checks,maximum
  checks+=1;err=abs(float(a)-float(b));maximum=max(maximum,err)
  assert math.isfinite(float(a)) and math.isclose(float(a),float(b),abs_tol=1e-12,rel_tol=1e-12),(label,a,b)
 def median(v):
  v=sorted(v);return (v[len(v)//2-1]+v[len(v)//2])/2 if len(v)%2==0 else v[len(v)//2]
 def quantile(v,p):
  v=sorted(v);position=(len(v)-1)*p;i=math.floor(position);f=position-i;return (1-f)*v[i]+f*v[min(i+1,len(v)-1)]
 rows={}
 for group,fee in (('primary',.0025),('doubled',.005)):
  for mode in MODES:
   rr=table('bytes/bundles/'+group+'/cases/'+mode+'/scenario_metrics.csv')
   eq([(int(r['scenario_id']),int(r['horizon'])) for r in rr],[(s,h) for s in range(1,5) for h in (5,6,15,25,30)],'fixture metric grid')
   for r in rr:rows[mode,fee,int(r['horizon']),int(r['scenario_id'])]=r
 gates=json.loads(read('analysis/comparison_gates.json'));eq(len(gates),100,'gate count')
 indexed={}
 for g in gates:
  candidate,reference,fee,h=g['candidate_mode'],g['reference_mode'],g['fee_rate'],g['horizon'];key=candidate,reference,fee,h;assert key not in indexed;indexed[key]=g
  cc=[rows[candidate,fee,h,s] for s in range(1,5)];rr=[rows[reference,fee,h,s] for s in range(1,5)]
  eq(g['scenario_ids'],[1,2,3,4],'gate scenario identity');eq(g['scenario_count'],4,'gate count')
  for name in FIELDS:
   expected=None if any(c[name]=='' or r[name]=='' for c,r in zip(cc,rr)) else median([float(c[name])-float(r[name]) for c,r in zip(cc,rr)])
   got=g['median_paired_differences'][name+'_difference']
   if expected is None:eq(got,None,'inapplicable paired metric')
   else:near(got,expected,'independent paired median '+name)
  gains=[float(c['net_real_cagr_pct'])-float(r['net_real_cagr_pct']) for c,r in zip(cc,rr)]
  med=median(gains);tail=quantile([float(r['net_real_cagr_pct']) for r in cc],.1)-quantile([float(r['net_real_cagr_pct']) for r in rr],.1)
  loss=quantile([float(r['max_real_drawdown_pct']) for r in cc],.9)-quantile([float(r['max_real_drawdown_pct']) for r in rr],.9)
  for name,value in [('median_paired_growth_gain_pp',med),('marginal_p10_growth_difference_pp',tail),('marginal_p90_loss_difference_pp',loss)]:near(g[name],value,name)
  positives=0
  for f in range(4):
   value=median([gain for s,gain in enumerate(gains) if s%4==f]);near(g['folds'][f]['median_paired_growth_gain_pp'],value,'fold gain');eq(g['folds'][f]['positive'],value>0,'strict positive fold');positives+=value>0
  flags=dict(gain_at_least_0_10=med>=.1,tail_growth_at_least_minus_0_10=tail>=-.1,tail_loss_at_most_1_00=loss<=1.,at_least_three_positive_folds=positives>=3)
  eq(g['flags'],flags,'independent scalar gates');eq(g['passed'],all(flags.values()),'gate conjunction');eq(g['reasons'],[k for k,v in flags.items() if not v],'all failed gates')
 selection=json.loads(read('analysis/selection.json'))
 context=indexed['balanced_context','balanced_cost',.0025,30]['passed']
 adaptive=all(indexed['balanced_adaptive',r,.0025,30]['passed'] for r in ('balanced_context','balanced_cost'))
 selected='balanced_adaptive' if adaptive else 'balanced_context' if context else 'balanced_cost'
 eq(selection['selected_mode'],selected,'primary H30 preference');eq(selection['sensitivity_may_reselect'],False,'no fee reselection')
 screens=json.loads(read('analysis/profile_screen.json'));eq(len(screens),30,'profile screen count')
 for s in screens:
  rr=[rows[s['mode'],s['fee_rate'],s['horizon'],i] for i in range(1,5)];growth=[float(r['net_real_cagr_pct']) for r in rr];loss=[float(r['max_real_drawdown_pct']) for r in rr]
  for name,value in [('median_growth_pct',median(growth)),('p10_growth_pct',quantile(growth,.1)),('median_loss_pct',median(loss)),('p90_loss_pct',quantile(loss,.9)),('severe_loss_pct',max(loss))]:near(s[name],value,'own horizon '+name)
  eq(s['severe_scenario_id'],min(i+1 for i,v in enumerate(loss) if v==max(loss)),'severe tie')
  eq(s['exceedance_count'],sum(v>s['loss_tolerance_pct'] for v in loss),'strict tolerance exceedance')
  eq(s['flags']['risk_pass'],quantile(loss,.9)<=s['loss_tolerance_pct'],'risk p90');eq(s['flags']['purchasing_power_pass'],quantile(growth,.1)>=0,'real growth screen')
  eq(s['personalized_overlay_pending'],True,'provisional bridge gate')
 return dict(status='passed',reviewed_commit=commit,scope='generated fixtures only',fixture_task=fixture_task,independent_checks=checks,max_absolute_difference=maximum,metric_rows=len(rows),gates=len(gates),profile_screens=len(screens),synthetic_selected_mode=selected,original_git_blob_sha256=hashes,acceptance=False,limitations=['Generated metrics are scalar fixtures,not coherent paths or development evidence.','Does not authenticate full production bridge or replace independent Sol review.','No real strategy/customer recommendation inferred.'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('commit');p.add_argument('--fixture-task',default='SOL-034');p.add_argument('--output',required=True);args=p.parse_args();out=Path(args.output).resolve();assert out.is_relative_to(ROOT/'audit/chief') and not out.exists();record=audit(args.commit,fixture_task=args.fixture_task)
 with out.open('x',encoding='utf8',newline='\n') as f:json.dump(record,f,indent=2);f.write('\n')
 print(json.dumps({k:v for k,v in record.items() if k!='original_git_blob_sha256'}))
