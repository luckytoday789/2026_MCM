"""Inspect saved decisions against prior saved ledger observations; no policy run."""
import csv, io, json, math, subprocess
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
R='4b8ac5d6822ac39ff1189c13d34ed3f84f699319'
P='results/final/HY3-010/'
CHECKS=0

def table(p):
    assert p.startswith(P) and 'data/' not in p
    return list(csv.DictReader(io.StringIO(subprocess.check_output(['git','show',R+':'+p],cwd=ROOT).decode())))
def check(ok,label):
    global CHECKS
    CHECKS+=1
    assert ok,label

def main():
    decisions=0;review=0;firsts=[]
    for fee in (.0025,.005):
        specs=[('generic/'+m,25.) for m in ('conservative_cost','balanced_cost','growth_cost','balanced_context','balanced_adaptive')]+[('personalized/B',25.),('personalized/C',40.)]
        for case,threshold in specs:
            prefix=P+case+'/'+str(fee)+'/'
            ledger=table(prefix+'annual_ledgers.csv');saved=table(prefix+'decisions.csv')
            check(len(ledger)==len(saved),'complete matching decisions')
            grouped=defaultdict(list)
            for r,d in zip(ledger,saved):grouped[int(r['scenario_id'])].append((r,d))
            for s,entries in grouped.items():
                peak=100.;worst=0.;latched=False;first=None
                for t,(r,d) in enumerate(entries,1):
                    check((int(d['scenario_id']),int(d['period']))==(s,t),'same scenario/year')
                    observed=100*worst
                    check(math.isclose(float(d['observed_max_drawdown_pct']),observed,rel_tol=1e-10,abs_tol=1e-9),'only completed ledger drawdown at t-1')
                    latched=latched or observed>=threshold
                    check((d['human_review_latched']=='True')==latched,'own threshold and persistent latch')
                    check((d['action']=='human_review')==latched,'latch action')
                    recent=min(5,t-1) if case.endswith(('balanced_context','balanced_adaptive')) else 0
                    check(int(d['recent_count'])==recent,'completed recent-count')
                    check(math.isclose(float(d['prior_mass']),15/(15+recent),rel_tol=1e-12),'fixed prior mass')
                    check(math.isclose(float(d['actual_fee']),float(r['fee']),rel_tol=1e-12,abs_tol=1e-12),'actual fee matches ledger')
                    check(math.isclose(float(d['intended_transfer']),float(r['intended_transfer']),rel_tol=1e-12,abs_tol=1e-12),'transfer matches ledger')
                    if case.startswith('personalized/'):
                        check(d['active_before']==d['active_after']=='conservative','no profile class fallback')
                    if latched:
                        if first is None:first=t
                        review+=1
                        check(r['action']=='keep' and float(r['fee'])==float(r['intended_transfer'])==0,'pending keeps dollars fee free')
                        for a in ('equity','bond','bill_proxy'):check(r['holdings_before_'+a]==r['holdings_after_fee_'+a],'pending component dollars unchanged')
                    for value in (float(r['real_wealth_after_fee']),float(r['real_wealth_end'])):
                        peak=max(peak,value);worst=max(worst,1-value/peak)
                    decisions+=1
                if first is not None:firsts.append(dict(case=case,fee_rate=fee,scenario_id=s,first_latch_year=first,threshold=threshold))
    print(json.dumps(dict(status='passed',checks=CHECKS,saved_decisions=decisions,human_review_periods=review,first_latches=firsts,original_inputs_read=False,policy_executed=False),indent=2))
if __name__=='__main__':main()
