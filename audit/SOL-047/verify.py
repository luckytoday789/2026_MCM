"""SOL-047 independent saved-evidence audit. Standard library; no policy imports.

Reuses the one-way-transfer, exact deflation and strict drawdown expressions
reviewed in audit/chief/review_development_case_bundle.py, but implements a new
50-digit Decimal cumulative ledger and manual sample-variance calculation.
--check is read-only. --build writes only this audit's saved fixtures/findings.
"""
import argparse, csv, hashlib, io, json, math, subprocess, sys
from collections import defaultdict
from decimal import Decimal as D, getcontext
from fractions import Fraction as F
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
BASE='bd6eaf25bd88d7b197f7399f650d2b69487cc03e'
RESULT='4b8ac5d6822ac39ff1189c13d34ed3f84f699319'
ACCEPTANCE='c993e884278a257a7d6586eb763caf21db13a524'
P='results/final/HY3-010/'
ASSETS=('equity','bond','bill_proxy')
MODES=('bills_keep','equal_weight_annual','equal_weight_buy_hold','conservative_cost','balanced_cost','growth_cost','balanced_context','balanced_adaptive')
FEES=(.0025,.005)
HS=(5,6,15,25,30)
PROFILES={'A':(5,10),'B':(15,25),'C':(30,40),'D':(25,15),'E':(6,35)}
getcontext().prec=50
CACHE={}; HASHES={}; CHECKS=0; MAX_ERROR=0.; OBS={}

def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(o):return json.dumps(o,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
def eq(a,b,label):
    global CHECKS
    CHECKS+=1
    assert type(a)==type(b) and a==b,(label,a,b)
def near(a,b,label):
    global CHECKS, MAX_ERROR
    CHECKS+=1;a,b=float(a),float(b);MAX_ERROR=max(MAX_ERROR,abs(a-b))
    assert math.isfinite(a) and math.isfinite(b) and math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-9),(label,a,b)
def blob(commit,name):
    assert len(commit)==40 and all(x in '0123456789abcdef' for x in commit)
    assert not name.startswith(('data/','problem/')) and '..' not in Path(name).parts
    assert name.startswith(('audit/','ops/','specs/','src/','scripts/','report/','handoff/','results/'))
    key=commit+':'+name
    if key not in CACHE:
        CACHE[key]=subprocess.check_output(['git','show',key],cwd=ROOT,stderr=subprocess.PIPE)
        HASHES[key]=sha(CACHE[key])
    return CACHE[key]
def obj(commit,name):return json.loads(blob(commit,name))
def table(name):return list(csv.DictReader(io.StringIO(blob(RESULT,P+name).decode('utf8'))))
def ref(r):
    raw=blob(r['commit'],r['path']);eq(sha(raw),r['sha256'],'reference hash '+r['path']);return json.loads(raw)
def quant(values,p):
    values=sorted(map(float,values));n=len(values);assert n
    index=(n-1)*F(str(p));left=index.numerator//index.denominator;alpha=float(index-left)
    return values[left]+alpha*(values[min(left+1,n-1)]-values[left])
def quant_fixture(values,p):
    ordered=sorted(map(float,values));position=(len(ordered)-1)*F(str(p));left=position.numerator//position.denominator
    return dict(n=len(ordered),p=p,zero_based_position=str(position),lower=ordered[left],upper=ordered[min(left+1,len(ordered)-1)],upper_weight=float(position-left),expected=quant(ordered,p))
def drawdown(points):
    peak=100.;worst=0.;at=pa=ta=(0,'initial')
    for year,kind,value in points:
        if value>peak:peak=value;at=(year,kind)
        loss=1-value/peak
        if loss>worst:worst=loss;pa=at;ta=(year,kind)
    return dict(max_real_drawdown_pct=100*worst,drawdown_peak_year=pa[0],drawdown_peak_kind=pa[1],drawdown_trough_year=ta[0],drawdown_trough_kind=ta[1])

def ledger(rows,horizons):
    before=[D(0),D(0),D(100)];cpi=D(1);previous=D(100)
    points=[];ends=[];annual=[];fees=[];transfers=[];metrics={}
    for t,row in enumerate(rows,1):
        eq(int(row['year']),t,'ledger ordered year');eq(row['split'],'final','ledger split')
        saved_before=[D(row['holdings_before_'+a]) for a in ASSETS]
        for a,b in zip(saved_before,before):near(a,b,'independent cumulative dollar continuity')
        W=sum(before);k=D(row['fee_rate']);fee=D(0);transfer=D(0)
        if row['action']=='keep':
            after=before[:]
            eq([row['target_'+a] for a in ASSETS],['','',''],'keep has no target')
            eq(float(row['fee']),0.,'keep fee zero');eq(float(row['intended_transfer']),0.,'keep transfer zero')
        else:
            eq(row['action'],'rebalance','engine action')
            w=[D(row['target_'+a]) for a in ASSETS];near(sum(w),1,'target fully invested');assert min(w)>=0
            transfer=W*sum(abs(v-h/W) for v,h in zip(w,before))/2
            fee=k*transfer;after=[(W-fee)*v for v in w]
        near(row['intended_transfer'],transfer,'one-way transfer');near(row['fee'],fee,'fee before returns')
        near(row['wealth_before'],W,'nominal wealth before');near(row['wealth_after_fee'],sum(after),'wealth after fee')
        near(sum(after)+fee,W,'self financing')
        near(row['cpi_before'],cpi,'CPI before');near(row['real_wealth_before'],W/cpi,'real wealth before')
        post=sum(after)/cpi;near(row['real_wealth_after_fee'],post,'post fee exact deflation')
        end=[h*(1+D(row['return_'+a])) for a,h in zip(ASSETS,after)]
        assert min(before+after+end)>=0
        for a,h,e in zip(ASSETS,after,end):
            near(row['holdings_after_fee_'+a],h,'post fee holdings '+a);near(row['holdings_end_'+a],e,'return after fee '+a)
        cpi*=1+D(row['inflation']);real=sum(end)/cpi
        near(row['wealth_end'],sum(end),'nominal end');near(row['cpi_end'],cpi,'compounded CPI')
        near(row['real_wealth_end'],real,'real end exact deflation');near(row['annual_net_real_return'],real/previous-1,'annual net real return')
        ends.append(float(real));annual.append(float(real/previous-1));fees.append(float(fee));transfers.append(float(transfer))
        # Locations are defined by exact saved binary64 values, after independent
        # Decimal recomputation has checked each value. Strict ties stay earliest.
        points.extend([(t,'post_fee',float(row['real_wealth_after_fee'])),(t,'end',float(row['real_wealth_end']))])
        if t in horizons:
            avg=math.fsum(annual)/t;sd=math.sqrt(math.fsum((x-avg)**2 for x in annual)/(t-1))
            trades=sum(x>1e-10 for x in transfers);later=sum(x>1e-10 for x in transfers[1:])
            metrics[t]=dict(net_real_cagr_pct=100*((ends[-1]/100)**(1/t)-1),annual_real_volatility_pct=100*sd,
                terminal_real_wealth=ends[-1],nominal_fee_sum=math.fsum(fees),trade_count=trades,review_count=t,
                later_trade_count=later,later_review_count=t-1,trade_share_pct=100*trades/t,
                trade_share_ex_initial_pct=100*later/(t-1),**drawdown(points))
        before=end;previous=real
    return metrics

def validate_metric(saved,expected):
    for key,value in expected.items():
        if type(value)==str:eq(saved[key],value,'metric '+key)
        elif type(value)==int:eq(int(saved[key]),value,'metric '+key)
        else:near(saved[key],value,'metric '+key)

def provenance():
    task=json.loads((HERE/'task-snapshot.json').read_bytes());eq(task['base_commit'],BASE,'SOL-047 base');eq(task['allowed_paths'],['audit/SOL-047'],'allowed paths')
    for name,h in task['parameters']['source_sha256'].items():
        raw=blob(BASE,name);eq(sha(raw),h,'task source pin '+name)
        eq((ROOT/name).read_bytes().replace(b'\r\n',b'\n'),raw.replace(b'\r\n',b'\n'),'checkout semantic bytes '+name)
    q=obj(ACCEPTANCE,'ops/queue.json')['tasks']
    for tid,commit in [('SOL-045','87cf934348c3a78ce10299fa7aece8168ade0c43'),('HY3-010',RESULT)]:
        item=next(x for x in q if x['id']==tid);eq(item['state'],'accepted','accepted prerequisite '+tid);eq(item['reviewed_commit'],commit,'exact accepted '+tid)
    availability=obj(ACCEPTANCE,'audit/chief/SOL-045-review.json')
    eq(availability['probe']['usable'],True,'real successful SOL-045');eq(availability['probe']['exit_code'],0,'probe actual exit');eq(availability['probe']['model_calls'],1,'single actual call')
    receipt=obj(RESULT,'handoff/HY3-010/result.json');eq(receipt['status'],'completed','receipt status');eq(receipt['artifact_hash_basis'],'canonical_git_blob','receipt basis')
    eq(receipt['base_commit'],'8fe64818dc931e8a25ac57e94ff2b04121233533','producer base');assert receipt['python'].startswith('3.12.')
    for name,h in receipt['artifacts_sha256'].items():eq(sha(blob(RESULT,name)),h,'canonical receipt artifact '+name)
    task10=obj('9edf98528ec1b7542127513c385da29f1350ac4d','ops/tasks/HY3-010.json')
    eq(sha(canonical(task10)),receipt['task_sha256'],'HY3 task canonical digest')
    for check in receipt['checks']:eq(check['exit_code'],0,'producer saved exit')
    manifest=obj(RESULT,P+'run_manifest.json');c=manifest['configuration'];eq(manifest['status'],'completed_final','actual final')
    eq(c['primary_mode'],'balanced_cost','frozen reporting mode')
    eq(sha(canonical(c)),manifest['provenance']['configuration_sha256'],'configuration digest')
    for name,h in c['source_sha256'].items():eq(sha(blob(c['source_commit'],name)),h,'frozen source closure')
    for label in ('source_review','development_review','freeze_attestation'):eq(ref(c[label])['status'],'accepted','accepted '+label)
    freeze=ref(c['freeze']);eq(freeze['profile_choices'],c['profile_choices'],'ten frozen choices');eq(freeze['source_sha256'],c['source_sha256'],'freeze sources')
    eq(freeze['primary_mode'],c['primary_mode'],'freeze primary');eq(freeze['no_final_tuning'],True,'no tuning')
    eq(sha(canonical({k:v for k,v in c.items() if k not in ('freeze','freeze_attestation')})),freeze['effective_configuration_sha256'],'effective frozen config')
    eq(manifest['freeze']['freeze_blob_sha256'],c['freeze']['sha256'],'freeze blob digest')
    eq(sha(blob(c['freeze']['commit'],c['freeze']['path']).decode().strip().encode()),manifest['freeze']['freeze_runner_sha256'],'runner freeze digest')
    prior=ref(c['refit']);eq(len(prior['refit']['gross']),3600,'all-development prior support');eq(prior['refit']['training_row_keys'],[[s,t] for s in range(1,121) for t in range(1,31)],'prior development keys')
    for name,entry in manifest['artifacts'].items():
        raw=blob(RESULT,P+name);eq(sha(raw),entry['sha256'],'manifest artifact hash');eq(len(raw),entry['bytes'],'manifest bytes')
    note=obj(BASE,'report/final-evaluation-provenance.json');eq(note['producer_commit'],RESULT,'note result commit')
    for name,h in note['source_hashes'].items():eq(sha(blob(RESULT,name)),h,'note source hash')
    eq(note['all_clients_human_review'],True,'all clients review');eq(note['submission_ready'],False,'manuscript unaccepted')
    return c,note,receipt

def audit():
    c,note,receipt=provenance();cases={};all_metrics={};selected=[];total=0
    case_specs=[('generic',m,k,HS) for k in FEES for m in MODES]+[('personalized',p,k,(PROFILES[p][0],)) for p in ('B','C') for k in FEES]
    for kind,label,k,hs in case_specs:
        prefix=kind+'/'+label+'/'+str(k)+'/'
        rows=table(prefix+'annual_ledgers.csv');saved=table(prefix+'scenario_metrics.csv');groups=defaultdict(list)
        eq([(int(r['scenario_id']),int(r['year'])) for r in rows],[(s,t) for s in range(121,181) for t in range(1,max(hs)+1)],'complete saved grid')
        index={(int(r['scenario_id']),int(r['horizon'])):r for r in saved};eq(len(index),60*len(hs),'metric key count')
        for row in rows:
            groups[int(row['scenario_id'])].append(row)
            observation=tuple(row['return_'+a] for a in ASSETS)+(row['inflation'],);key=int(row['scenario_id']),int(row['year'])
            if key in OBS:eq(observation,OBS[key],'same saved observations across cases')
            else:OBS[key]=observation
        expected={}
        for s,entries in groups.items():
            ms=ledger(entries,hs)
            for h,m in ms.items():
                validate_metric(index[s,h],m);expected[s,h]=m
                if kind=='generic':all_metrics[label,k,s,h]=m
            if (kind=='generic' and label in ('balanced_cost','equal_weight_annual','balanced_adaptive','bills_keep') and s in (121,149,155,172)) or (kind=='personalized' and s in (121,149,161)):
                selected.append(dict(case=prefix,scenario_id=s,horizons=list(hs),rows=entries,expected_metrics={str(h):m for h,m in ms.items()}))
        cases[kind,label,k]=expected;total+=len(rows)
    eq(total,34200,'complete audited annual ledger rows')
    summaries=table('summary.csv');quantiles=[]
    fields=[('median_growth_pct','net_real_cagr_pct',.5),('p10_growth_pct','net_real_cagr_pct',.1),('median_loss_pct','max_real_drawdown_pct',.5),('p90_loss_pct','max_real_drawdown_pct',.9),('median_volatility_pct','annual_real_volatility_pct',.5),('median_terminal_real_wealth','terminal_real_wealth',.5),('median_nominal_fee_sum','nominal_fee_sum',.5)]
    for r in summaries:
        mode,k,h=r['mode'],float(r['fee_rate']),int(r['horizon']);group=[all_metrics[mode,k,s,h] for s in range(121,181)]
        for output,field,p in fields:
            values=[m[field] for m in group];near(r[output],quant(values,p),'linear summary '+output)
            if h==30 and k==.0025 and mode in ('balanced_cost','equal_weight_annual') and p in (.1,.9):quantiles.append(dict(mode=mode,field=field,values=values,**quant_fixture(values,p)))
        # Exact binary64 scenario tie is decided on validated saved metrics.
        saved=table('generic/'+mode+'/'+str(k)+'/scenario_metrics.csv');by_s={int(m['scenario_id']):m for m in saved if int(m['horizon'])==h}
        sid=min(by_s,key=lambda s:(-float(by_s[s]['max_real_drawdown_pct']),s));eq(int(r['severe_scenario_id']),sid,'exact severe tie')
        for name in ('drawdown_peak_year','drawdown_peak_kind','drawdown_trough_year','drawdown_trough_kind'):eq(r['severe_'+name],by_s[sid][name],'severe location')
        for count in ('trade_count','review_count','later_trade_count','later_review_count'):eq(int(r['pooled_'+count]),sum(m[count] for m in group),'pooled count')
        near(r['pooled_trade_share_pct'],100*sum(m['trade_count'] for m in group)/(60*h),'pooled trades')
        near(r['pooled_trade_share_ex_initial_pct'],100*sum(m['later_trade_count'] for m in group)/(60*(h-1)),'pooled later trades')
    comparisons=obj(RESULT,P+'comparisons.json');primary=None
    for row in comparisons:
        a,b,k,h=row['alternative_mode'],row['reference_mode'],row['fee_rate'],row['horizon']
        left=[all_metrics[a,k,s,h] for s in range(121,181)];right=[all_metrics[b,k,s,h] for s in range(121,181)]
        paired=quant([x['net_real_cagr_pct']-y['net_real_cagr_pct'] for x,y in zip(left,right)],.5)
        tailg=quant([m['net_real_cagr_pct'] for m in left],.1)-quant([m['net_real_cagr_pct'] for m in right],.1)
        taill=quant([m['max_real_drawdown_pct'] for m in left],.9)-quant([m['max_real_drawdown_pct'] for m in right],.9)
        near(row['paired_median_growth_difference_pct'],paired,'paired median')
        near(row['marginal_p10_growth_difference_pct'],tailg,'marginal p10 difference');near(row['marginal_p90_loss_difference_pct'],taill,'marginal p90 difference')
        eq(row['frozen_primary_mode'],'balanced_cost','no reselection');eq(row['promotion'],None,'no final promotion')
        if (a,b,k,h)==('balanced_cost','equal_weight_annual',.0025,30):
            primary=dict(paired_median_growth_difference_pct=paired,marginal_p10_growth_difference_pct=tailg,marginal_p90_loss_difference_pct=taill,
                difference_of_growth_medians=quant([m['net_real_cagr_pct'] for m in left],.5)-quant([m['net_real_cagr_pct'] for m in right],.5),
                p10_of_paired_growth_differences=quant([x['net_real_cagr_pct']-y['net_real_cagr_pct'] for x,y in zip(left,right)],.1))
    for row in table('paired_differences.csv'):
        a,b,k,s,h=row['alternative_mode'],row['reference_mode'],float(row['fee_rate']),int(row['scenario_id']),int(row['horizon'])
        for out,field in [('growth_difference_pct','net_real_cagr_pct'),('loss_difference_pct','max_real_drawdown_pct'),('trade_share_difference_pct','trade_share_pct'),('trade_share_ex_initial_difference_pct','trade_share_ex_initial_pct'),('terminal_real_wealth_difference','terminal_real_wealth'),('nominal_fee_difference','nominal_fee_sum')]:near(row[out],all_metrics[a,k,s,h][field]-all_metrics[b,k,s,h][field],'saved paired '+out)
    profiles=obj(RESULT,P+'personalized.json');failures=[];referrals=[]
    for row,choice in zip(profiles,c['profile_choices']):
        p,k=row['profile_id'],row['fee_rate'];h,tol=PROFILES[p]
        for key,value in choice.items():eq(row[key],value,'unchanged frozen profile choice')
        eq(row['horizon'],h,'own horizon');eq(row['loss_tolerance_pct'],tol,'own tolerance');eq(row['recommended_class'],None,'no replacement class')
        if not row['eligible']:
            eq(row['status'],'development_referral','six retained referrals');eq(row['scenario_count'],0,'referral no simulation');eq(row['denominator'],0,'referral no denominator')
            for field in ('case_path','p10_growth_pct','p90_loss_pct','exceedance_count','risk_pass','purchasing_power_pass'):eq(row[field],None,'referral null '+field)
            referrals.append(dict(profile_id=p,fee_rate=k,horizon=h,status=row['status'],scenario_count=0));continue
        group=[cases['personalized',p,k][s,h] for s in range(121,181)]
        losses=[m['max_real_drawdown_pct'] for m in group];growth=[m['net_real_cagr_pct'] for m in group]
        p90=quant(losses,.9);p10=quant(growth,.1);exceeded=[s for s,m in zip(range(121,181),group) if m['max_real_drawdown_pct']>tol]
        near(row['p90_loss_pct'],p90,'own p90');near(row['p10_growth_pct'],p10,'own p10');near(row['median_loss_pct'],quant(losses,.5),'own median')
        eq(row['exceedance_count'],len(exceeded),'own tolerance exceedance');eq(row['denominator'],60,'own denominator');eq(len(exceeded),7,'seven of sixty')
        near(row['exceedance_fraction'],7/60,'own fraction');eq(row['risk_pass'],False,'genuine final failure');eq(row['purchasing_power_pass'],True,'purchasing power pass')
        assert p90>tol and p10>0;eq(row['status'],'final_validation_failed_human_review','failure preserved')
        failures.append(dict(profile_id=p,fee_rate=k,horizon=h,tolerance=tol,p90_loss_pct=p90,p10_growth_pct=p10,exceedance_count=7,denominator=60,exceedance_scenarios=exceeded,recommended_class=None))
        quantiles.extend([dict(mode=p+'/'+str(k),field='max_real_drawdown_pct',values=losses,**quant_fixture(losses,.9)),dict(mode=p+'/'+str(k),field='net_real_cagr_pct',values=growth,**quant_fixture(growth,.1))])
    eq(len(failures),4,'four final failures');eq(len(referrals),6,'six retained referrals')
    # Verify all provenance rows refer to the exact saved producer objects.
    for saved in note['primary_rows']+note['sensitivity_rows']:assert saved in summaries
    eq(note['personalized_rows'],profiles,'note complete personalized rows')
    assert note['paired_primary'] in comparisons
    combined=table('scenario_metrics.csv');assert note['same_path_reference'] in combined
    for key in ('paired_median_growth_difference_pct','marginal_p10_growth_difference_pct','marginal_p90_loss_difference_pct'):near(note['paired_primary'][key],primary[key],'note contrast arithmetic')
    balanced=all_metrics['balanced_cost',.0025,172,30];same=all_metrics['equal_weight_annual',.0025,172,30];own=all_metrics['equal_weight_annual',.0025,155,30]
    eq((balanced['drawdown_peak_year'],balanced['drawdown_trough_year']),(13,27),'Balanced severe locations')
    eq((same['drawdown_peak_year'],same['drawdown_trough_year'],same['drawdown_trough_kind']),(13,28,'post_fee'),'same-path thirds locations')
    # Arithmetic toy checks include 20-unit move, initial thirds and exact deflation.
    near(D('0.0025')*20,D('.05'),'toy transfer once')
    near((D(100)-D(1)/6)/3,D(599)/18,'toy initial thirds post fee')
    near(D('1.10')/D('1.03')-1,D(7)/103,'toy exact real return')
    ties=drawdown([(1,'post_fee',100.),(1,'end',100.),(2,'post_fee',90.),(2,'end',90.),(3,'post_fee',90.)])
    eq((ties['drawdown_peak_year'],ties['drawdown_peak_kind'],ties['drawdown_trough_year'],ties['drawdown_trough_kind']),(0,'initial',2,'post_fee'),'strict earliest tie')
    eq(min([(155,40.),(149,40.)],key=lambda x:(-x[1],x[0]))[0],149,'exact scenario tie')
    eq(min([(155,40.+1e-12),(149,40.)],key=lambda x:(-x[1],x[0]))[0],155,'no epsilon severe tie')
    fixtures=dict(schema_version=1,result_commit=RESULT,selected_paths=selected,linear_quantiles=quantiles,tie_fixture=ties)
    findings=dict(schema_version=1,task_id='SOL-047',verdict='approve',reviewed_result_commit=RESULT,reviewed_note_commit=BASE,
        accepted_source_commit=c['source_commit'],freeze_commit=c['freeze']['commit'],prerequisite_acceptance_commit=ACCEPTANCE,
        method='Independent 50-digit Decimal cumulative ledger; manual sample variance; rational-index linear quantiles; saved binary64 strict location ties after numerical validation.',
        reused_expression_source='audit/chief/review_development_case_bundle.py (expressions inspected, module not executed)',
        complete_paths=1200,annual_ledger_rows=total,generic_metrics=4800,personalized_metrics=240,selected_complete_fixture_paths=len(selected),
        four_final_failures=failures,six_development_referrals=referrals,all_clients_human_review=True,no_fallback=True,
        primary_contrasts=primary,severe_case=dict(scenario_id=172,balanced=balanced,same_path_annual_thirds=same,annual_thirds_own_severe_scenario=155,annual_thirds_own_severe=own),
        source_git_blob_sha256=dict(HASHES),original_inputs_read=False,production_policy_executed=False,final_gate_reset=False,blocking_findings=[],
        limitations=['Saved-return audit intentionally does not establish equality to unopened original final input.',
          'Utility maximization and no-lookahead decisions were not independently rerun; pinned source acceptance and saved decisions support this boundary.',
          'Final outcomes are already exposed; no policy, parameters, source or freeze changed and no correction/reselection is authorized by this audit.',
          'Full manuscript, layout, identities and submission package are outside this approval; human submission only.'])
    return fixtures,findings

def check_saved(fixtures,findings,actual_fixtures,actual_findings):
    # Recompute from saved audit fixtures before binding them to exact producer blobs.
    # This makes arithmetic mutations fail as arithmetic, rather than only hash failures.
    for item in fixtures['selected_paths']:
        metrics=ledger(item['rows'],item['horizons'])
        for h,m in metrics.items():
            for key,value in m.items():
                expected=item['expected_metrics'][str(h)][key]
                if isinstance(value,str):eq(expected,value,'fixture '+key)
                else:near(expected,value,'fixture arithmetic '+key)
    for q in fixtures['linear_quantiles']:near(q['expected'],quant(q['values'],q['p']),'saved fixture linear quantile')
    eq(fixtures,actual_fixtures,'saved independent fixtures match exact evidence')
    eq(findings,actual_findings,'saved findings match independently recomputed evidence')

def main():
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--build',action='store_true');g.add_argument('--check',action='store_true')
    p.add_argument('--fixtures',type=Path,default=HERE/'independent-fixtures.json');p.add_argument('--findings',type=Path,default=HERE/'findings.json');a=p.parse_args()
    assert sys.version_info[:2]==(3,12),'Python 3.12 required'
    fixtures,findings=audit()
    if a.build:
        for file,value in [(a.fixtures,fixtures),(a.findings,findings)]:
            assert file.resolve().is_relative_to(HERE) and not file.exists(),'preserve existing deliverable'
            file.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf8',newline='\n')
    else:check_saved(json.loads(a.fixtures.read_bytes()),json.loads(a.findings.read_bytes()),fixtures,findings)
    print(json.dumps(dict(status='passed',mode='build' if a.build else 'check',checks=CHECKS,maximum_absolute_numeric_residual=MAX_ERROR,annual_ledger_rows=34200,complete_paths=1200,original_inputs_read=False,production_policy_executed=False,read_only=a.check),indent=2))
if __name__=='__main__':main()
