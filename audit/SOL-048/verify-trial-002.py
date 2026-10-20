"""SOL-048 independent reporting/arithmetical audit. Stdlib; no policy imports.
--check reads pinned Git metadata and accepted saved fixtures only; writes nothing.
The deliberately corrupted fixtures are copies in memory, never source mutations.
"""
from __future__ import annotations
import argparse, copy, csv, hashlib, io, json, math, re, statistics, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BASE = 'cfde9523416113005e9de99325595d5823be94f1'
TASK_PUBLICATION = '3dc37e6aad87a9fca7afa0c2773992f38746bd98'
EXPANDED_SHA = 'e15f606eeb51fc563d7488ad1a61d3479eb5ca70c3e3e64988aa648099c8d651'
COMMITS = {'HY3-003':'7652410d73425371110784ef5fa97c03470a074e',
 'HY3-004':'6aa2ccdce80834c8beb52a827993f1f587d1d8a6',
 'HY3-006':'319781ef3c7fb5d4328a0ae4cea438bcc26a6f18',
 'HY3-009':'680c2faaf603df975c35e828aeebdadd8ce242cb',
 'CHIEF-PERSONALIZED-RUN-002':'b334b27a2f9fb8df99a6dee611e298bd0dc867d3',
 'HY3-010':'4b8ac5d6822ac39ff1189c13d34ed3f84f699319'}
LABELS = dict(zip(('bills_keep','equal_weight_annual','equal_weight_buy_hold','conservative_cost','balanced_cost','growth_cost','balanced_context','balanced_adaptive'),('Bills held','Annual thirds','Initial thirds','Conservative','Balanced fixed','Growth','Balanced context','Balanced adaptive')))
checks=0; hashes={}; commands=[]; receipts={}; traces={}; rejected=[]
def sha(b): return hashlib.sha256(b).hexdigest()
def require(ok, msg):
 global checks
 checks+=1
 if not ok: raise AssertionError(msg)
def close(a,b,label):
 a,b=float(a),float(b)
 require(math.isfinite(a) and math.isfinite(b) and math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-9),(label,a,b))
def git(*args):
 p=subprocess.run(['git',*args],cwd=ROOT,capture_output=True)
 commands.append(dict(argv=['git',*args],exit_code=p.returncode,stdout_sha256=sha(p.stdout),stderr=p.stderr.decode(errors='replace')))
 require(p.returncode==0,('git',args,p.stderr.decode(errors='replace')))
 return p.stdout
_cache={}
def blob(path,commit=BASE):
 require(not path.startswith(('data/raw/','data/development/','data/final_holdout/','problem/','.runtime/')),'forbidden original/private input')
 require('..' not in Path(path).parts,'path traversal')
 key=commit+':'+path
 if key not in _cache:
  _cache[key]=git('show',key);hashes[key]=sha(_cache[key])
 return _cache[key]
def js(path,commit=BASE): return json.loads(blob(path,commit))
def canonical_task(t): return sha(json.dumps(t,sort_keys=True,separators=(',',':')).encode())
def auth(ident):
 q=next(t for t in js('ops/queue.json')['tasks'] if t['id']==ident)
 c=COMMITS[ident]; require(q['state']=='accepted' and q['reviewed_commit']==c,('acceptance',ident))
 r=js('handoff/'+ident+'/result.json',c); t=js('ops/tasks/'+ident+'.json')
 require(r['status']=='completed' and r['artifact_hash_basis']=='canonical_git_blob',('receipt',ident))
 td={canonical_task(t),sha(blob('ops/tasks/'+ident+'.json').strip())}
 require(r['task_sha256']==q['task_sha256'] and r['task_sha256'] in td,('task digest',ident))
 require(r['base_commit']==t['base_commit'] and r['attempt']==t['attempt'],('base attempt',ident))
 require(all(x['exit_code']==0 for x in r['checks']),('recorded executions',ident))
 a=js(q['acceptance_evidence']); require(a['reviewed_commit']==c,('exact reviewed commit',ident))
 receipts[ident]=(r,q,a)
 traces.setdefault('receipts',{})[ident]=dict(result_commit=c,base_commit=r['base_commit'],task_sha256=r['task_sha256'],receipt_sha256=hashes[c+':handoff/'+ident+'/result.json'],acceptance=q['acceptance_evidence'],recorded_exits=[x['exit_code'] for x in r['checks']])
def saved(ident,path):
 r,q,a=receipts[ident]; raw=blob(path,COMMITS[ident]);h=sha(raw)
 require(path in q['accepted_paths'],('unaccepted path',path))
 require(h==r['artifacts_sha256'][path],('receipt artifact',path))
 for record in (q,a):
  if path in record.get('artifacts_sha256',{}): require(h==record['artifacts_sha256'][path],('acceptance artifact',path))
 return raw
def rows(ident,path): return list(csv.DictReader(io.StringIO(saved(ident,path).decode())))
def obj(ident,path): return json.loads(saved(ident,path))
def quant(xs,p):
 xs=sorted(map(float,xs)); z=(len(xs)-1)*p; lo=math.floor(z); hi=math.ceil(z)
 return xs[lo]+(xs[hi]-xs[lo])*(z-lo)
def summary_values(ms):
 return dict(median_growth_pct=quant([r['net_real_cagr_pct'] for r in ms],.5),p10_growth_pct=quant([r['net_real_cagr_pct'] for r in ms],.1),median_loss_pct=quant([r['max_real_drawdown_pct'] for r in ms],.5),p90_loss_pct=quant([r['max_real_drawdown_pct'] for r in ms],.9),median_volatility_pct=quant([r['annual_real_volatility_pct'] for r in ms],.5),pooled_trade_share_pct=100*sum(int(r['trade_count']) for r in ms)/sum(int(r['review_count']) for r in ms),pooled_trade_share_ex_initial_pct=100*sum(int(r['later_trade_count']) for r in ms)/sum(int(r['later_review_count']) for r in ms))
def table_line(label,values,text):
 line='| '+' | '.join([label,*[format(float(v),'.2f') for v in values]])+' |'
 require(line in text,('display row absent',line))
def metric_group(ms,H): return [r for r in ms if int(r['horizon'])==H]
def check_group(ms,summary,n,H):
 require(len(ms)==n and len({r['scenario_id'] for r in ms})==n,('scenario count',n,H))
 for k,v in summary_values(ms).items(): close(summary[k],v,('aggregate',k))
 for r in ms:
  close(r['net_real_cagr_pct'],100*((float(r['terminal_real_wealth'])/100)**(1/H)-1),'CAGR from saved terminal')
 return summary_values(ms)
def reject(name,fn):
 try: fn()
 except AssertionError as e: rejected.append(dict(name=name,rejected=True,reason=str(e)))
 else: raise AssertionError('corruption accepted: '+name)
def ledger_path(ident,path,sid,H,metric):
 allrows=rows(ident,path); rr=sorted([r for r in allrows if int(r['scenario_id'])==sid and int(r['year'])<=H],key=lambda r:int(r['year']))
 require(len(rr)==H,('ledger horizon',sid,H));peak=100.;peakloc=(0,'initial');worst=0.;pair=(peakloc,peakloc);annual=[];trades=0
 previous=[0.,0.,100.];previous_cpi=1.;previous_real=100.;latched=False
 for i,r in enumerate(rr,1):
  before=[float(r['holdings_before_'+a]) for a in ('equity','bond','bill_proxy')]
  after=[float(r['holdings_after_fee_'+a]) for a in ('equity','bond','bill_proxy')]
  end=[float(r['holdings_end_'+a]) for a in ('equity','bond','bill_proxy')]
  for x,y in zip(before,previous): close(x,y,'holdings continuity')
  W=sum(before); close(r['wealth_before'],W,'wealth before');close(r['cpi_before'],previous_cpi,'CPI continuity')
  fee=float(r['fee']); T=float(r['intended_transfer']); k=float(r['fee_rate'])
  if r['action'] in ('keep','human_review'):
   close(T,0,'keep transfer');close(fee,0,'keep fee')
   for x,y in zip(after,before):close(x,y,'kept dollars')
  else:
   w=[float(r['target_'+a]) for a in ('equity','bond','bill_proxy')]
   close(sum(w),1,'target sum');close(T,sum(abs(W*w[j]-before[j]) for j in range(3))/2,'one-way intended transfer')
   close(fee,k*T,'fee once')
   for j in range(3):close(after[j],(W-fee)*w[j],'pro-rata fee funding')
  close(sum(after)+fee,W,'conservation');close(r['wealth_after_fee'],sum(after),'post-fee wealth')
  close(r['real_wealth_after_fee'],sum(after)/previous_cpi,'post-fee real wealth uses previous CPI')
  cpi=previous_cpi*(1+float(r['inflation']));close(r['cpi_end'],cpi,'exact compounded CPI')
  for j,a in enumerate(('equity','bond','bill_proxy')):close(end[j],after[j]*(1+float(r['return_'+a])),'saved return applied after fee')
  close(r['wealth_end'],sum(end),'end wealth');real=sum(end)/cpi;close(r['real_wealth_end'],real,'exact deflation')
  q=real/previous_real-1;close(r['annual_net_real_return'],q,'annual net real return');annual.append(100*q)
  for kind,value in [('post_fee',sum(after)/previous_cpi),('end',real)]:
   if value>peak:peak=value;peakloc=(i,kind)
   loss=100*(1-value/peak)
   if loss>worst:worst=loss;pair=(peakloc,(i,kind))
  trades+=T>1e-10
  if latched:require(r['action']=='human_review','latched review resumes trading')
  latched=latched or r['action']=='human_review'
  previous=end;previous_cpi=cpi;previous_real=real
 close(metric['max_real_drawdown_pct'],worst,'event drawdown')
 close(metric['annual_real_volatility_pct'],statistics.stdev(annual),'annual sample deviation')
 close(metric['net_real_cagr_pct'],100*((previous_real/100)**(1/H)-1),'path CAGR')
 close(metric['terminal_real_wealth'],previous_real,'path terminal real')
 close(metric['trade_count'],trades,'path trade count')
 require(pair==((int(metric['drawdown_peak_year']),metric['drawdown_peak_kind']),(int(metric['drawdown_trough_year']),metric['drawdown_trough_kind'])),('severe locations',pair))
 return dict(scenario_id=sid,horizon=H,CAGR=float(metric['net_real_cagr_pct']),drawdown=worst,terminal=previous_real,peak=pair[0],trough=pair[1],trade_count=trades)
def main():
 require(sys.version_info[:2]==(3,12),'Python 3.12 required')
 task=js('ops/tasks/SOL-048.json',TASK_PUBLICATION)
 require(task['base_commit']==BASE and task['allowed_paths']==['audit/SOL-048'],'immutable review scope')
 require(canonical_task(task)=='d856ba979747dca715aa91f817bf36e0751012e0111a52349731cbf0a9c589ee','review task digest')
 for p,h in task['parameters']['source_sha256'].items():
  require(sha(blob(p))==h,('pinned source hash',p))
  require(sha((ROOT/p).read_bytes().replace(b'\r\n',b'\n'))==h,('checkout source drift',p))
 text=(HERE/'expanded-draft.md').read_text(encoding='utf-8')
 require(sha((HERE/'expanded-draft.md').read_bytes())==EXPANDED_SHA,'reviewed expansion drift')
 require('{{' not in text and 'PENDING ' not in text,'unexpanded manuscript')
 meta=json.loads((HERE/'build-provenance.json').read_bytes())
 require(meta['pending_slots']==[] and not meta['private_identity_access'] and not meta['simulation_rerun'],'metadata-only nonprivate assembly')
 for ident in COMMITS:auth(ident)
 cols=['median_growth_pct','p10_growth_pct','median_loss_pct','p90_loss_pct','median_volatility_pct','pooled_trade_share_pct','pooled_trade_share_ex_initial_pct']
 dev={}; devsumm={}
 for ident in ('HY3-004','HY3-006'):
  for mode in LABELS:
   base='results/development/'+ident+'/cases/'+mode+'/'
   mm=rows(ident,base+'scenario_metrics.csv');ss=rows(ident,base+'summary.csv');dev[(ident,mode)]=mm;devsumm[(ident,mode)]=ss
   s=next(r for r in ss if r['horizon']=='30'); v=check_group(metric_group(mm,30),s,120,30)
   if ident=='HY3-004':table_line(LABELS[mode],[v[k] for k in cols],text)
   if mode in ('equal_weight_annual','balanced_cost','balanced_context','balanced_adaptive'):
    line='| '+' | '.join([LABELS[mode], '0.25' if ident=='HY3-004' else '0.50',*[format(v[k],'.2f') for k in cols[:4]],format(v['pooled_trade_share_pct'],'.2f'),'-' if s['pooled_human_review_share_pct']=='' else format(float(s['pooled_human_review_share_pct']),'.2f')])+' |'
    require(line in text,('development sensitivity table',line))
 traces['development_same_mode']=[next(s for s in devsumm[(i,'balanced_cost')] if s['horizon']=='30') for i in ('HY3-004','HY3-006')]
 # Independent paired/fold derivation from scenario metrics, not chief's checker.
 gates=obj('HY3-009','results/development/HY3-009/comparison_gates.json')
 gate_traces=[]
 for ca,refr in [('balanced_cost','equal_weight_annual'),('balanced_context','balanced_cost'),('balanced_adaptive','balanced_context'),('balanced_adaptive','balanced_cost')]:
  aa={int(r['scenario_id']):r for r in metric_group(dev[('HY3-004',ca)],30)};bb={int(r['scenario_id']):r for r in metric_group(dev[('HY3-004',refr)],30)}
  diff={sid:float(aa[sid]['net_real_cagr_pct'])-float(bb[sid]['net_real_cagr_pct']) for sid in aa}
  gain=quant(diff.values(),.5);tailg=quant([r['net_real_cagr_pct'] for r in aa.values()],.1)-quant([r['net_real_cagr_pct'] for r in bb.values()],.1);taill=quant([r['max_real_drawdown_pct'] for r in aa.values()],.9)-quant([r['max_real_drawdown_pct'] for r in bb.values()],.9)
  folds=[quant([v for sid,v in diff.items() if (sid-1)%4==f],.5) for f in range(4)];pos=sum(v>0 for v in folds);passed=gain>=.1 and tailg>=-.1 and taill<=1 and pos>=3
  g=next(r for r in gates if r['fee_rate']==.0025 and r['horizon']==30 and r['candidate_mode']==ca and r['reference_mode']==refr)
  for a,b in [(gain,g['median_paired_growth_gain_pp']),(tailg,g['marginal_p10_growth_difference_pp']),(taill,g['marginal_p90_loss_difference_pp'])]:close(a,b,'development gate derived')
  require(pos==g['positive_fold_count'] and passed==g['passed'] and not passed,'failed development gate')
  line='| '+LABELS[ca]+' / '+LABELS[refr]+' | '+' | '.join(format(v,'.3f') for v in (gain,tailg,taill))+' | '+str(pos)+'/4 | Fail |';require(line in text,'promotion display')
  gate_traces.append(dict(candidate=ca,reference=refr,paired=gain,p10_difference=tailg,p90_difference=taill,positive_folds=pos,passed=passed))
 traces['development_gates']=gate_traces
 selection=obj('HY3-009','results/development/HY3-009/selection.json');require(selection['selected_mode']=='balanced_cost' and selection['sensitivity_may_reselect'] is False,'selection retained')
 # Own-horizon/target-reserve screening from the saved development metric grid.
 plan=js('specs/development_policy_pilot_v2.json');screen=obj('HY3-009','results/development/HY3-009/profile_screen.json')
 eligible=plan['suitability']['eligible_classes_before_outcome_screens'];profile_traces=[]
 for sr in screen:
  p=sr['profile'];H=plan['profiles'][p]['horizon'];tol=plan['profiles'][p]['loss_tolerance_pct'];ident='HY3-004' if sr['fee_rate']==.0025 else 'HY3-006'
  mm=metric_group(dev[(ident,sr['mode'])],H);pv=summary_values(mm)
  for key in ('median_growth_pct','p10_growth_pct','p90_loss_pct'):close(sr[key],pv[key],'own-horizon screen')
  count=sum(float(r['max_real_drawdown_pct'])>tol for r in mm);require(count==sr['exceedance_count'],'own-horizon exceedances')
  reserve=plan['suitability']['minimum_target_bill'][plan['profiles'][p]['liquidity']];bill=plan['targets'][sr['candidate_class']][2];bill=1/3 if bill=='1/3' else bill
  qual=sr['candidate_class'] in eligible[p] and bill>=reserve and pv['p90_loss_pct']<=tol and pv['p10_growth_pct']>=0
  require(qual==sr['qualified'],'eligibility and outcome screen')
 for fee in (.0025,.005):
  for p in 'ABCDE':
   qq=[r for r in screen if r['profile']==p and r['fee_rate']==fee and r['qualified']]
   require(bool(qq)==(p in 'BC'),'development referrals versus provisional classes')
   if qq:require(qq[0]['candidate_class']=='conservative' and len(qq)==1,'provisional class')
 dp=rows('CHIEF-PERSONALIZED-RUN-002','results/development/CHIEF-PERSONALIZED-RUN-002/personalized_summary.csv')
 require(len(dp)==10,'ten development profile-fee rows')
 for r in dp:
  p=r['profile_id'];require(r['component_source_verified']=='false' and r['bridge_provenance_verified']=='true','preserve bridge distinction')
  if p in 'ADE':require(r['scenario_count']==r['denominator']=='0' and r['recommended_class']=='' and r['status']=='upstream_referral','six unexecuted development referrals');continue
  path='results/development/CHIEF-PERSONALIZED-RUN-002/cases/'+p+('-primary' if float(r['fee_rate'])==.0025 else '-doubled')+'/scenario_metrics.csv'
  mm=rows('CHIEF-PERSONALIZED-RUN-002',path);v=summary_values(mm)
  for k in ('median_growth_pct','p10_growth_pct','p90_loss_pct'):close(r[k],v[k],'personalized development summary')
  require(len(mm)==120 and {int(m['horizon']) for m in mm}=={int(r['horizon'])},'own development horizon')
  require(sum(float(m['max_real_drawdown_pct'])>float(r['loss_tolerance_pct']) for m in mm)==int(r['exceedance_count'])==5,'five development exceedances')
  require(v['p90_loss_pct']<=float(r['loss_tolerance_pct']) and v['p10_growth_pct']>=0,'development qualification')
  profile_traces.append(dict(profile=p,fee=r['fee_rate'],horizon=r['horizon'],p90=v['p90_loss_pct'],exceedances='5/120'))
 traces['development_personalized']=profile_traces
 # Final claims are reconstructed from accepted saved metrics, never the inputs.
 prefix='results/final/HY3-010/';fm=rows('HY3-010',prefix+'scenario_metrics.csv');ss=rows('HY3-010',prefix+'summary.csv')
 final={}
 for s in ss:
  if s['horizon']!='30':continue
  mm=[r for r in fm if r['mode']==s['mode'] and r['fee_rate']==s['fee_rate'] and r['horizon']=='30'];v=check_group(mm,s,60,30)
  require({int(r['scenario_id']) for r in mm}==set(range(121,181)),'reserved scenario inventory')
  final[(s['mode'],float(s['fee_rate']))]=(mm,s,v)
  if float(s['fee_rate'])==.0025:table_line(LABELS[s['mode']],[v[k] for k in cols],text)
 fixed=final[('balanced_cost',.0025)];annual=final[('equal_weight_annual',.0025)]
 require([format(fixed[2][k],'.2f') for k in cols[:4]]==['4.03','1.52','27.48','46.60'],'final fixed tuple')
 require([format(annual[2][k],'.2f') for k in cols[:4]]==['3.38','1.50','22.30','39.53'],'final annual tuple')
 am={r['scenario_id']:r for r in annual[0]};paired=quant([float(r['net_real_cagr_pct'])-float(am[r['scenario_id']]['net_real_cagr_pct']) for r in fixed[0]],.5)
 comps=obj('HY3-010',prefix+'comparisons.json');pr=next(r for r in comps if r['horizon']==30 and r['fee_rate']==.0025 and r['alternative_mode']=='balanced_cost' and r['reference_mode']=='equal_weight_annual')
 close(paired,pr['paired_median_growth_difference_pct'],'paired median');close(fixed[2]['p10_growth_pct']-annual[2]['p10_growth_pct'],pr['marginal_p10_growth_difference_pct'],'marginal p10');close(fixed[2]['p90_loss_pct']-annual[2]['p90_loss_pct'],pr['marginal_p90_loss_difference_pct'],'marginal p90')
 require(format(paired,'.3f')=='0.814' and '0.814 percentage points/year' in text,'paired transcription')
 require(all(r['frozen_primary_mode']=='balanced_cost' and r['promotion'] is None and r['fold_support'] is None for r in comps),'no final reranking')
 traces['final_paired']=dict(paired_median=paired,marginal_median_difference=fixed[2]['median_growth_pct']-annual[2]['median_growth_pct'],p10_difference=pr['marginal_p10_growth_difference_pct'],p90_difference=pr['marginal_p90_loss_difference_pct'])
 # Corruption is rejected by arithmetic, independently of blob-hash protection.
 bad=copy.deepcopy(pr);bad['paired_median_growth_difference_pct']=fixed[2]['median_growth_pct']-annual[2]['median_growth_pct']
 reject('reporting fixture substitutes difference of marginal medians for paired median',lambda:close(bad['paired_median_growth_difference_pct'],paired,'corrupt paired report'))
 profiles=obj('HY3-010',prefix+'personalized.json');require(len(profiles)==10,'ten final profile-fee rows');fpt=[]
 for r in profiles:
  if r['profile_id'] in 'ADE':require(r['scenario_count']==r['denominator']==0 and r['recommended_class'] is None and r['case_path'] is None and r['status']=='development_referral','six retained final referrals');continue
  mm=rows('HY3-010',prefix+r['case_path']+'/scenario_metrics.csv');v=summary_values(mm);H=r['horizon'];tol=r['loss_tolerance_pct']
  require(len(mm)==60 and {int(x['horizon']) for x in mm}=={H},'final own horizon')
  for k in ('p10_growth_pct','p90_loss_pct','median_loss_pct'):close(r[k],v[k],'final personalized aggregates')
  n=sum(float(x['max_real_drawdown_pct'])>tol for x in mm)
  require(n==r['exceedance_count']==7 and r['denominator']==60,'7/60 each fee/client')
  require(v['p90_loss_pct']>tol and v['p10_growth_pct']>0 and r['risk_pass'] is False and r['recommended_class'] is None and r['status']=='final_validation_failed_human_review','final failure without fallback')
  line='| '+' | '.join([r['profile_id']+'/'+str(H),format(100*r['fee_rate'],'.2f'),str(tol),format(v['p90_loss_pct'],'.2f'),format(v['p10_growth_pct'],'.2f'),'7/60',format(v['median_loss_pct'],'.2f'),format(float(r['severe_loss_pct']),'.2f')])+' |';require(line in text,'final profile display')
  fpt.append(dict(profile=r['profile_id'],fee=r['fee_rate'],horizon=H,p90=v['p90_loss_pct'],p10=v['p10_growth_pct'],exceedance='7/60',status=r['status']))
 traces['final_personalized']=fpt
 for fee in (.0025,.005):
  _,s,v=final[('balanced_cost',fee)];table_line(format(100*fee,'.2f'),[v[k] for k in ('median_growth_pct','p10_growth_pct','p90_loss_pct','pooled_trade_share_pct','pooled_trade_share_ex_initial_pct')],text)
 traces['final_same_mode']=[final[('balanced_cost',f)][2] for f in (.0025,.005)]
 def worst(mm):return min(mm,key=lambda r:(-float(r['max_real_drawdown_pct']),int(r['scenario_id'])))
 w=worst(fixed[0]);aw=worst(annual[0]);require(w['scenario_id']=='172' and aw['scenario_id']=='155','distinct worst scenarios')
 same=am['172'];traces['severe_paths']=[ledger_path('HY3-010',prefix+'generic/balanced_cost/0.0025/annual_ledgers.csv',172,30,w),ledger_path('HY3-010',prefix+'generic/equal_weight_annual/0.0025/annual_ledgers.csv',172,30,same),ledger_path('HY3-010',prefix+'generic/equal_weight_annual/0.0025/annual_ledgers.csv',155,30,aw)]
 dw=worst(metric_group(dev[('HY3-004','balanced_cost')],30));require(dw['scenario_id']=='114','development severe')
 traces['development_severe']=ledger_path('HY3-004','results/development/HY3-004/cases/balanced_cost/annual_ledgers.csv',114,30,dw)
 # Baseline own-horizon rows, independently authenticated from their producer.
 bs=rows('HY3-003','results/development/HY3-003/summary.csv');bm=rows('HY3-003','results/development/HY3-003/scenario_metrics.csv')
 for s in bs:
  policy=s['policy']
  if policy!='equal_weight_annual':continue
  H=int(s['horizon']);mm=[r for r in bm if r['policy']==policy and int(r['horizon'])==H];v=check_group(mm,s,120,H);table_line(str(H),[v[k] for k in cols[:4]],text)
 # Fee toy and CE proof: generated rational example, no empirical policy execution.
 from fractions import Fraction as F
 T=F(100,2)*sum(abs(x-y) for x,y in zip((F(1,3),)*3,(0,0,1)));fee=F(25,10000)*T
 require(T==F(200,3) and fee==F(1,6) and (100-fee)/3==F(599,18),'exact initial fee fixture')
 close(.0025*20,.05,'20-unit fee')
 def ce(x):return (sum((sum(a*b for a,b in zip(x,g)))**-3 for g in ((1.12,1.03,1.01),(.84,1.06,1.02)))/2)**(-1/3)
 x=(.2,.3,.5);close(ce(tuple(7*a for a in x)),7*ce(x),'CE homogeneity')
 traces['math']=dict(initial_transfer=str(T),initial_fee=str(fee),initial_each_holding=str((100-fee)/3),utility='U(z)=-1/(3*z**3); -z*U2/U1=4',buffer_identity='(1-f)C(w)-C(u) = [(1-2f)C(w)-C(u)] + f*C(w)',CE_homogeneity_fixture=ce(x))
 broken=copy.deepcopy(w);broken['terminal_real_wealth']=str(float(w['terminal_real_wealth'])+1)
 reject('arithmetical fixture changes terminal wealth but retains CAGR',lambda:close(broken['net_real_cagr_pct'],100*((float(broken['terminal_real_wealth'])/100)**(1/30)-1),'corrupt CAGR'))
 customer=re.search(r'<!-- SLOT:CUSTOMER_EXPLANATION -->(.*?)<!-- END_SLOT:CUSTOMER_EXPLANATION -->',text,re.S)[1]
 customer=re.sub(r'\[E\d(?:, E\d)*\]','',customer);count=len(re.findall(r"\b[\w'-]+\b",customer));require(count==39 and count<=50,'customer explanation word count');traces['customer_word_count']=count
 require('all five profiles for human review' in text and 'All A-E require human review' in text and 'refer all A-E for human assessment' in text,'summary/results/conclusion agreement')
 freeze=js('ops/freeze.json','06086aed327aa626ddc91472f943c2c9fba1259a');require(freeze['primary_mode']=='balanced_cost' and freeze['no_final_tuning'] is True,'frozen primary')
 require(freeze['source_commit']=='7053b41ce81b1e04100d56a24a321e51b3465459','frozen execution source')
 layout=js('audit/chief/complete-manuscript-layout-20261020.json');require(layout['pages']==8 and layout['paper']=='A4' and layout['minimum_font_pt']>=11,'recorded layout only')
 require('GPT-6 Astra xhigh' in text and 'HY3 in WorkBuddy' in text and 'Human team members are responsible' in text,'AI attribution')
 print(json.dumps(dict(status='passed',scope='Independent saved-fixture reporting/math review; no original observations or policy execution',reviewed_base=BASE,reviewed_commits=COMMITS,task_publication=TASK_PUBLICATION,task_digest=canonical_task(task),expanded_sha256=EXPANDED_SHA,checks=checks,corruptions_rejected=rejected,traces=traces,source_blob_sha256=hashes,git_commands=commands,original_observations_read=False,policy_executed=False,source_changed=False,private_files_read=False,visual_layout_review_performed=False),indent=2))
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true',required=True);parser.parse_args()
 main()
