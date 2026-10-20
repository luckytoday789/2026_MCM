"""Independent saved-final-result arithmetic audit; stdlib only, no input CSV.

Fee/self-financing/CPI equations follow the independently authored expressions
in review_development_case_bundle.py, adapted to saved final-labelled ledgers.
No SafeInvest import, policy execution, tuning, or original data read occurs.
"""
from collections import defaultdict
from fractions import Fraction as Q
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
from statistics import stdev
import subprocess

REPOSITORY=Path(__file__).resolve().parents[2]
ASSETS=('equity','bond','bill_proxy')
MODES=('bills_keep','equal_weight_annual','equal_weight_buy_hold','conservative_cost',
       'balanced_cost','growth_cost','balanced_context','balanced_adaptive')
FEES=(.0025,.005)
HS=(5,6,15,25,30)
PROFILES={'A':(5,10),'B':(15,25),'C':(30,40),'D':(25,15),'E':(6,35)}
CONTRASTS=tuple((m,'equal_weight_annual') for m in MODES if m!='equal_weight_annual')+(
    ('balanced_context','balanced_cost'),('balanced_adaptive','balanced_context'),
    ('balanced_adaptive','balanced_cost'))
FINAL_HASH='3270445e7864abf2e88c56e4012d7f582eae3b5e30c40ade1a4c9ef2b54bbf29'
DEV_HASH='9c4ad83f5dda86251a754e126528a71dd930ae88ed7cdb8a0663a327b6bfb7c7'


def digest(raw):return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()


def strict(raw):
    def pairs(items):
        out={}
        for key,value in items:
            assert key not in out,'duplicate JSON key';out[key]=value
        return out
    return json.loads(raw.decode('utf-8',errors='strict'),object_pairs_hook=pairs,
                      parse_constant=lambda token:(_ for _ in ()).throw(ValueError('nonfinite JSON')))


def q(text):
    number=float(text);assert math.isfinite(number);return Q(number)


def quantile(values,p):
    ordered=sorted(float(v) for v in values);assert ordered
    position=(len(ordered)-1)*p;left=math.floor(position);fraction=position-left
    return (1-fraction)*ordered[left]+fraction*ordered[min(left+1,len(ordered)-1)]


class Auditor:
    def __init__(self,commit,root,repository=REPOSITORY):
        assert re.fullmatch('[0-9a-f]{40}',commit)
        assert type(root) is str and root.startswith('results/') and '..' not in Path(root).parts
        self.commit,self.root,self.repository=commit,root.rstrip('/'),Path(repository)
        self.hashes={};self.checks=0;self.max_error=0.;self.observations={}

    def blob(self,commit,name):
        assert re.fullmatch('[0-9a-f]{40}',commit)
        assert not Path(name).is_absolute() and '..' not in Path(name).parts
        assert not name.startswith('data/'),'Original input reads forbidden in this auditor'
        raw=subprocess.check_output(['git','show',commit+':'+name],cwd=self.repository,stderr=subprocess.PIPE)
        self.hashes[commit+':'+name]=digest(raw)
        return raw

    def read(self,name):return self.blob(self.commit,self.root+'/'+name)

    def table(self,name):
        reader=csv.DictReader(io.StringIO(self.read(name).decode('utf-8'),newline=''))
        assert reader.fieldnames and len(reader.fieldnames)==len(set(reader.fieldnames))
        rows=list(reader);assert all(None not in row for row in rows);return rows

    def equal(self,actual,expected,label):
        self.checks+=1;assert type(actual) is type(expected) and actual==expected,(label,actual,expected)

    def near(self,actual,expected,label):
        self.checks+=1;a,b=float(actual),float(expected)
        self.max_error=max(self.max_error,abs(a-b))
        assert math.isfinite(a) and math.isfinite(b) and math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-9),(label,a,b)

    def reference(self,reference):
        raw=self.blob(reference['commit'],reference['path'])
        self.equal(digest(raw),reference['sha256'],'immutable artifact reference')
        return raw

    def provenance(self,m):
        self.equal(m['status'],'completed_final','completed actual final')
        self.equal(m['split'],'final','true final split')
        self.equal(m['input_sha256'],FINAL_HASH,'locked final input hash claim')
        c=m['configuration'];self.equal(c['stage'],'final','fixed final stage')
        self.equal(m['frozen_primary_mode'],c['primary_mode'],'unchanged primary')
        for name,h in c['source_sha256'].items():
            self.equal(digest(self.blob(c['source_commit'],name)),h,'source closure')
        source_review=strict(self.reference(c['source_review']))
        self.equal(source_review['status'],'accepted','exact source acceptance')
        self.equal(source_review['source_commit'],c['source_commit'],'source acceptance commit')
        self.equal(source_review['source_sha256'],c['source_sha256'],'source acceptance closure')
        development=strict(self.reference(c['development_review']))
        self.equal(development['status'],'accepted','development accepted')
        self.equal(development['all_ten_rescreens_accepted'],True,'all ten development rescreens')
        self.equal(development['primary_mode'],c['primary_mode'],'development primary fixed')
        self.equal(development['profile_choices'],c['profile_choices'],'frozen ten assignments')
        for ref in development['evidence']:self.reference(ref)
        freeze_raw=self.reference(c['freeze']);freeze=strict(freeze_raw)
        runner=digest(freeze_raw.decode('utf-8',errors='strict').strip().encode())
        self.equal(m['freeze']['freeze_blob_sha256'],digest(freeze_raw),'freeze blob')
        self.equal(m['freeze']['freeze_runner_sha256'],runner,'freeze runner text')
        attestation=strict(self.reference(c['freeze_attestation']))
        self.equal(attestation['status'],'accepted','external freeze acceptance')
        self.equal(attestation['freeze_blob_sha256'],digest(freeze_raw),'attested blob')
        self.equal(attestation['freeze_runner_sha256'],runner,'attested runner')
        self.equal(attestation['refit'],c['refit'],'attested refit')
        accepted_refit=strict(self.reference(attestation['refit_acceptance']))
        self.equal(accepted_refit['status'],'accepted','external refit acceptance')
        self.equal(accepted_refit['refit'],c['refit'],'exact accepted refit')
        effective={k:v for k,v in c.items() if k not in ('freeze','freeze_attestation')}
        self.equal(freeze['effective_configuration_sha256'],digest(canonical(effective)),'frozen effective config')
        for name in ('source_commit','source_sha256','primary_mode','profile_choices','refit'):
            self.equal(freeze[name],c[name],'freeze binding '+name)
        refit=strict(self.reference(c['refit']))
        self.equal(refit['status'],'completed_refit','completed prior')
        self.equal(refit['refit']['input_sha256'],DEV_HASH,'development-only prior')
        self.equal(refit['refit']['training_row_keys'],[[s,t] for s in range(1,121) for t in range(1,31)],'complete prior keys')
        self.equal(len(refit['refit']['gross']),3600,'prior support count')
        support=[[float(v).hex() for v in row] for row in refit['refit']['gross']]
        assert all(len(row)==3 and all(math.isfinite(float.fromhex(v)) and float.fromhex(v)>0 for v in row) for row in support)
        payload={'schema':'all-development-prior-support-v1','asset_order':['equity_return','bond_return','bill_proxy_return'],'rows':support}
        self.equal(refit['refit']['prior_support_sha256'],digest(canonical(payload)),'independent prior support digest')
        self.equal(m['prior_support_sha256'],refit['refit']['prior_support_sha256'],'one immutable prior')
        binding=m['provenance']['binding'];task=strict(self.blob(binding['publication_commit'],
                    'ops/tasks/'+binding['task_id']+'.json'))
        self.equal(task['owner'],binding['owner'],'real task owner')
        self.equal(task['freeze_sha256'],runner,'task frozen runner digest')
        self.equal(task['parameters']['config_sha256'],digest(canonical(c)),'task fixed config')
        self.equal(m['provenance']['configuration_sha256'],digest(canonical(c)),'saved fixed config')
        self.artifacts=m['artifacts']
        for name,entry in m['artifacts'].items():
            raw=self.read(name);self.equal(digest(raw),entry['sha256'],'saved artifact hash')
            self.equal(len(raw),entry['bytes'],'saved artifact bytes');assert len(raw)<=10485760
        return c

    def path_metrics(self,ledger,fee,mode,horizons):
        before=[Q(0),Q(0),Q(100)];cpi=Q(1);real_previous=Q(100)
        metrics={};ends=[];postfees=[];fees=[];transfers=[]
        for t,row in enumerate(ledger,1):
            self.equal(int(row['year']),t,'ordered year');self.equal(row['split'],'final','ledger split')
            self.equal(row['policy'],mode,'ledger mode');self.equal(float(row['fee_rate']),fee,'ledger fee')
            observed=tuple(float(row['return_'+asset]).hex() for asset in ASSETS)+(float(row['inflation']).hex(),)
            key=int(row['scenario_id']),t
            if key in self.observations:self.equal(observed,self.observations[key],'same saved source observations across policies/fees/profiles')
            else:self.observations[key]=observed
            saved_before=[q(row['holdings_before_'+a]) for a in ASSETS]
            self.equal(saved_before,before,'exact dollar continuity')
            after=[q(row['holdings_after_fee_'+a]) for a in ASSETS]
            end=[q(row['holdings_end_'+a]) for a in ASSETS]
            wealth=sum(before);transfer=q(row['intended_transfer']);charge=q(row['fee'])
            assert min(before+after+end)>=0
            if row['action']=='keep':
                self.equal(after,before,'keep dollars');self.equal(charge,Q(0),'keep no fee');self.equal(transfer,Q(0),'keep no transfer')
            else:
                self.equal(row['action'],'rebalance','engine action')
                weights=[q(row['target_'+a]) for a in ASSETS];self.near(sum(weights),1,'target sum')
                self.near(transfer,sum(abs(wealth*w-h) for w,h in zip(weights,before))/2,'one-way transfer')
                self.equal(float(charge).hex(),(fee*float(transfer)).hex(),'exact binary64 fee')
                for held,w in zip(after,weights):self.near(held,(wealth-charge)*w,'post-fee allocation')
            self.near(row['wealth_before'],wealth,'wealth before');self.near(sum(after)+charge,wealth,'self financing')
            self.near(row['wealth_after_fee'],sum(after),'wealth after fee')
            self.near(row['cpi_before'],cpi,'CPI before')
            self.near(row['real_wealth_before'],wealth/cpi,'real before')
            self.near(row['real_wealth_after_fee'],sum(after)/cpi,'real after fee')
            for a,held,actual in zip(ASSETS,after,end):self.near(actual,held*(1+q(row['return_'+a])),'return applied after fee')
            cpi*=1+q(row['inflation']);real=sum(end)/cpi
            self.near(row['wealth_end'],sum(end),'nominal end');self.near(row['cpi_end'],cpi,'compounded CPI')
            self.near(row['real_wealth_end'],real,'exact deflation')
            self.near(row['annual_net_real_return'],real/real_previous-1,'net annual return')
            ends.append(float(row['real_wealth_end']));postfees.append(float(row['real_wealth_after_fee']))
            fees.append(float(row['fee']));transfers.append(float(row['intended_transfer']))
            if t in horizons:
                annual=[];previous=100.;peak=100.;loss=0.;peak_at=selected_peak=selected_trough=(0,'initial')
                for year,(post,value) in enumerate(zip(postfees,ends),1):
                    annual.append(value/previous-1);previous=value
                    for kind,observed in (('post_fee',post),('end',value)):
                        if observed>peak:peak,peak_at=observed,(year,kind)
                        drawdown=1-observed/peak
                        if drawdown>loss:loss,selected_peak,selected_trough=drawdown,peak_at,(year,kind)
                metrics[t]=dict(net_real_cagr_pct=100*((ends[-1]/100)**(1/t)-1),
                    annual_real_volatility_pct=100*stdev(annual) if t>1 else None,
                    max_real_drawdown_pct=100*loss,terminal_real_wealth=ends[-1],nominal_fee_sum=math.fsum(fees),
                    trade_count=sum(x>1e-10 for x in transfers),review_count=t,
                    later_trade_count=sum(x>1e-10 for x in transfers[1:]),later_review_count=t-1,
                    trade_share_pct=100*sum(x>1e-10 for x in transfers)/t,
                    trade_share_ex_initial_pct=100*sum(x>1e-10 for x in transfers[1:])/(t-1) if t>1 else None,
                    drawdown_peak_year=selected_peak[0],drawdown_peak_kind=selected_peak[1],
                    drawdown_trough_year=selected_trough[0],drawdown_trough_kind=selected_trough[1])
            before,real_previous=end,real
        return metrics

    def case(self,kind,label,fee,horizons,mode):
        prefix=kind+'/'+label+'/'+str(fee)+'/'
        ledger=self.table(prefix+'annual_ledgers.csv');metrics=self.table(prefix+'scenario_metrics.csv')
        last=max(horizons);self.equal(len(ledger),60*last,'case annual count')
        self.equal([(int(r['scenario_id']),int(r['year'])) for r in ledger],
                   [(s,t) for s in range(121,181) for t in range(1,last+1)],'case ledger grid')
        self.equal([(int(r['scenario_id']),int(r['horizon'])) for r in metrics],
                   [(s,h) for s in range(121,181) for h in horizons],'case metric grid')
        for i,s in enumerate(range(121,181)):
            recomputed=self.path_metrics(ledger[i*last:(i+1)*last],fee,label,horizons)
            for row in metrics[i*len(horizons):(i+1)*len(horizons)]:
                h=int(row['horizon']);self.equal(row['mode'],mode,'metric mode')
                self.equal(row['split'],'final','metric split');self.equal(row['fold_id'],'','final fold null')
                self.equal(row['fold_status'],'not_applicable','final fold status')
                for name,value in recomputed[h].items():
                    if value is None:self.equal(row[name],'','undefined metric')
                    elif type(value) is str:self.equal(row[name],value,name)
                    elif type(value) is int:self.equal(int(row[name]),value,name)
                    else:self.near(row[name],value,name)
        if mode.endswith('_cost') or mode in ('balanced_context','balanced_adaptive'):
            decisions=self.table(prefix+'decisions.csv')
            self.equal(len(decisions),len(ledger),'all actual review decisions')
            for decision,entry in zip(decisions,ledger):
                self.equal((int(decision['scenario_id']),int(decision['period'])),
                           (int(entry['scenario_id']),int(entry['year'])),'decision/ledger keys')
                self.near(decision['actual_fee'],entry['fee'],'decision fee')
                self.near(decision['intended_transfer'],entry['intended_transfer'],'decision transfer')
                if decision['action']=='human_review':
                    self.equal(entry['action'],'keep','human-review holdings carried')
                    self.equal(float(entry['fee']),0.,'human-review free')
        return metrics,len(ledger)

    def json_csv(self,name,records):
        saved=self.table(name+'.csv');self.equal(len(saved),len(records),'JSON/CSV parallel count')
        for row,record in zip(saved,records):
            self.equal(set(row),set(record),'JSON/CSV fields')
            for field,value in record.items():
                if value is None:self.equal(row[field],'','JSON null retained in CSV')
                elif type(value) is float:self.equal(float(row[field]).hex(),value.hex(),'JSON/CSV binary64')
                else:self.equal(row[field],str(value),'JSON/CSV exact cell')

    def run(self):
        m=strict(self.read('run_manifest.json'));c=self.provenance(m)
        generic={};metric_index={};annual=0
        for fee in FEES:
            for mode in MODES:
                metrics,count=self.case('generic',mode,fee,HS,mode);annual+=count;generic[mode,fee]=metrics
                metric_index.update({(mode,fee,int(r['scenario_id']),int(r['horizon'])):r for r in metrics})
        self.equal(annual,28800,'all generic annual rows');self.equal(len(metric_index),4800,'all generic metrics')
        combined=self.table('scenario_metrics.csv')
        self.equal(len(combined),4800,'combined metric count')
        for row in combined:self.equal(row,metric_index[row['mode'],float(row['fee_rate']),int(row['scenario_id']),int(row['horizon'])],'combined exact metric row')
        summaries=self.table('summary.csv');self.equal(len(summaries),80,'all generic horizon summaries')
        for row in summaries:
            group=[r for r in generic[row['mode'],float(row['fee_rate'])] if int(r['horizon'])==int(row['horizon'])]
            for name,field,p in (('median_growth_pct','net_real_cagr_pct',.5),('p10_growth_pct','net_real_cagr_pct',.1),
                ('median_loss_pct','max_real_drawdown_pct',.5),('p90_loss_pct','max_real_drawdown_pct',.9)):
                self.near(row[name],quantile((r[field] for r in group),p),'summary '+name)
            severe=min(group,key=lambda r:(-float(r['max_real_drawdown_pct']),int(r['scenario_id'])))
            self.equal(int(row['severe_scenario_id']),int(severe['scenario_id']),'exact-float severe tie')
            for name in ('drawdown_peak_year','drawdown_peak_kind','drawdown_trough_year','drawdown_trough_kind'):
                self.equal(row['severe_'+name],severe[name],'severe earliest location')
        pairs=self.table('paired_differences.csv');self.equal(len(pairs),6000,'paired count')
        seen=set()
        for row in pairs:
            alternative,reference=row['alternative_mode'],row['reference_mode'];fee=float(row['fee_rate']);s=int(row['scenario_id']);h=int(row['horizon'])
            key=(alternative,reference,fee,s,h);assert key not in seen;seen.add(key)
            assert (alternative,reference) in CONTRASTS
            a,b=metric_index[alternative,fee,s,h],metric_index[reference,fee,s,h]
            for output,field in (('growth_difference_pct','net_real_cagr_pct'),('loss_difference_pct','max_real_drawdown_pct'),
                ('trade_share_difference_pct','trade_share_pct'),('trade_share_ex_initial_difference_pct','trade_share_ex_initial_pct'),
                ('terminal_real_wealth_difference','terminal_real_wealth'),('nominal_fee_difference','nominal_fee_sum')):
                self.near(row[output],float(a[field])-float(b[field]),'paired '+output)
        contrasts=strict(self.read('comparisons.json'));self.equal(len(contrasts),100,'contrast count')
        self.json_csv('comparisons',contrasts)
        seen=set()
        for row in contrasts:
            a,b,fee,h=row['alternative_mode'],row['reference_mode'],row['fee_rate'],row['horizon']
            key=a,b,fee,h;assert key not in seen;seen.add(key);assert (a,b) in CONTRASTS
            left=[metric_index[a,fee,s,h] for s in range(121,181)];right=[metric_index[b,fee,s,h] for s in range(121,181)]
            self.near(row['paired_median_growth_difference_pct'],quantile((float(x['net_real_cagr_pct'])-float(y['net_real_cagr_pct']) for x,y in zip(left,right)),.5),'paired growth median')
            for name,field,p in (('marginal_p10_growth_difference_pct','net_real_cagr_pct',.1),('marginal_p90_loss_difference_pct','max_real_drawdown_pct',.9)):
                self.near(row[name],quantile((r[field] for r in left),p)-quantile((r[field] for r in right),p),'marginal tail contrast')
            self.equal(row['frozen_primary_mode'],c['primary_mode'],'no final reselection')
            self.equal(row['fold_support'],None,'fold support inapplicable');self.equal(row['promotion'],None,'promotion inapplicable')
        profiles=strict(self.read('personalized.json'));self.equal(len(profiles),10,'profile roots')
        self.json_csv('personalized',profiles)
        self.equal([(r['profile_id'],r['fee_rate']) for r in profiles],[(p,k) for p in PROFILES for k in FEES],'profile order')
        personal_annual=personal_metrics=0
        for row,choice in zip(profiles,c['profile_choices']):
            for name,value in choice.items():self.equal(row[name],value,'frozen choice '+name)
            p,fee=row['profile_id'],row['fee_rate'];h,tol=PROFILES[p]
            self.equal(row['horizon'],h,'own horizon');self.equal(row['loss_tolerance_pct'],tol,'own tolerance')
            if not choice['eligible']:
                self.equal(row['status'],'development_referral','referral preserved')
                self.equal(row['scenario_count'],0,'referral count');self.equal(row['denominator'],0,'referral denominator')
                for name in ('recommended_class','p90_loss_pct','p10_growth_pct','exceedance_count','exceedance_fraction','risk_pass','purchasing_power_pass','case_path'):
                    self.equal(row[name],None,'referral null '+name)
                continue
            metrics,count=self.case('personalized',p,fee,(h,),choice['proposed_class']+'_cost')
            personal_annual+=count;personal_metrics+=len(metrics)
            loss=quantile((r['max_real_drawdown_pct'] for r in metrics),.9);growth=quantile((r['net_real_cagr_pct'] for r in metrics),.1)
            count=sum(float(r['max_real_drawdown_pct'])>tol for r in metrics);risk,power=loss<=tol,growth>=0
            self.near(row['p90_loss_pct'],loss,'own p90');self.near(row['p10_growth_pct'],growth,'own p10')
            self.equal(row['exceedance_count'],count,'strict exceedance');self.near(row['exceedance_fraction'],count/60,'exceedance denominator')
            self.equal(row['denominator'],60,'executed denominator');self.equal(row['scenario_count'],60,'executed scenarios')
            self.equal(row['risk_pass'],risk,'risk screen');self.equal(row['purchasing_power_pass'],power,'power screen')
            self.equal(row['status'],'frozen_rule_supported_on_final_sample' if risk and power else 'final_validation_failed_human_review','retain failed outcome')
            self.equal(row['recommended_class'],choice['proposed_class'] if risk and power else None,'no replacement')
            self.near(row['median_loss_pct'],quantile((r['max_real_drawdown_pct'] for r in metrics),.5),'profile median loss')
            severe=min(metrics,key=lambda r:(-float(r['max_real_drawdown_pct']),int(r['scenario_id'])))
            self.near(row['severe_loss_pct'],severe['max_real_drawdown_pct'],'profile severe loss')
            self.equal(row['severe_scenario_id'],int(severe['scenario_id']),'profile severe tie rule')
            self.near(row['trade_share_pct'],sum(int(r['trade_count']) for r in metrics)*100/(60*h),'profile trade share')
            self.near(row['trade_share_ex_initial_pct'],sum(int(r['later_trade_count']) for r in metrics)*100/(60*(h-1)),'profile later trade share')
        self.equal(m['counts']['personalized_annual_ledgers'],personal_annual,'personalized annual count')
        self.equal(m['counts']['personalized_metrics'],personal_metrics,'personalized metric count')
        return {'status':'passed','reviewed_result_commit':self.commit,'output_root':self.root,
                'independent_checks':self.checks,'maximum_absolute_numeric_residual':self.max_error,
                'generic_ledger_rows':annual,'generic_metrics':len(metric_index),
                'personalized_ledger_rows':personal_annual,'personalized_metrics':personal_metrics,
                'original_input_files_read':False,'safeinvest_modules_imported':False,
                'method':'stdlib Fraction ledger equations; independent binary64 metric/tail/paired reconstruction',
                'source_git_blob_sha256':self.hashes,
                'limitations':['Saved-return consistency audit; original final observations are intentionally not reread.',
                    'Does not independently reselect policy actions or certify quota/model identity.',
                    'Exact task/source/freeze evidence and external source acceptance remain separate chief gates.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit',required=True);parser.add_argument('--root',required=True)
    parser.add_argument('--output');args=parser.parse_args()
    report=Auditor(args.commit,args.root).run();raw=json.dumps(report,indent=2,allow_nan=False)+'\n'
    if args.output:
        path=Path(args.output).resolve()
        assert path.is_relative_to(REPOSITORY/'audit/chief') and not path.exists()
        with path.open('x',encoding='utf-8',newline='\n') as stream:stream.write(raw)
    else:print(raw,end='')


if __name__=='__main__':main()
