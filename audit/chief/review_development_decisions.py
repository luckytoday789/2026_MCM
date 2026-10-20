"""Chief independent calibration, saved decision-link and Decimal CE spot checks.

Reads exact published development Git blobs; no SafeInvest imports or simulation.
This evidence is narrower than independent remote review and result acceptance.
"""
from collections import Counter, defaultdict
from decimal import Decimal as D, localcontext
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ('equity', 'bond', 'bill_proxy')
FIELDS = ('scenario_id', 'period', 'equity_return', 'bond_return', 'bill_proxy_return', 'inflation')
CENTRAL = dict(conservative_cost='conservative', balanced_cost='balanced', growth_cost='growth',
               balanced_context='balanced', balanced_adaptive='balanced')
TARGETS = dict(conservative=(.15,.2,.65), balanced=(1/3,1/3,1/3), growth=(.6,.3,.1),
               defensive=(.2,.25,.55), growth_tilt=(.45,.3,.25))


def audit(task_id, commit, overrides=None):
    assert task_id in ('HY3-004', 'HY3-005', 'HY3-006') and len(commit) == 40
    records = {}; checks = 0; maximum_error = 0.0; samples = []; events = {}
    base = 'results/development/' + task_id + '/'
    fee = .0025 if task_id == 'HY3-004' else .005

    def read(path):
        raw = subprocess.check_output(['git', 'show', commit + ':' + path], cwd=ROOT)
        records[path] = hashlib.sha256(raw).hexdigest()
        return (overrides or {}).get(path, raw)

    def table(path):
        reader = csv.DictReader(io.StringIO(read(path).decode(), newline=''))
        assert len(reader.fieldnames) == len(set(reader.fieldnames))
        rows = list(reader); assert all(None not in row for row in rows)
        return rows

    def equal(a,b,label):
        nonlocal checks
        checks += 1
        assert a == b, (label,a,b)

    def near(a,b,label):
        nonlocal checks, maximum_error
        a,b=float(a),float(b); checks+=1
        maximum_error=max(maximum_error,abs(a-b))
        assert math.isfinite(a) and math.isclose(a,b,abs_tol=2e-11,rel_tol=2e-11), (label,a,b)

    def dec(value):
        return D.from_float(float(value))

    def canonical(value):
        return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')

    data = table('data/development/scenarios_001_120.csv')
    equal(list(data[0]),list(FIELDS),'original six-field order')
    equal([(int(r['scenario_id']),int(r['period'])) for r in data],
          [(s,t) for s in range(1,121) for t in range(1,31)],'original ordered grid')
    numeric = {(int(r['scenario_id']),int(r['period'])):tuple(float(r[f]) for f in FIELDS[2:]) for r in data}
    gross = {key:tuple((1+r)/(1+row[3]) for r in row[:3]) for key,row in numeric.items()}
    prior = {}
    calibration = json.loads(read(base+'calibrations.json'))['arithmetic_manifest']
    folds=[]
    for fold,saved in enumerate(calibration['folds']):
        train = [s for s in range(1,121) if (s-1)%4!=fold]
        evaluate = [s for s in range(1,121) if (s-1)%4==fold]
        keys = [(s,t) for s in train for t in range(1,31)]
        equal(saved['fold_id'],fold,'fold identity')
        equal(saved['training_scenario_ids'],train,'fold training complement')
        equal(saved['evaluation_scenario_ids'],evaluate,'fold evaluation IDs')
        equal(saved['training_row_keys'],[list(k) for k in keys],'training sorted full rows')
        equal(saved['training_row_count'],2700,'training count')
        rows=[[s,t,*(v.hex() for v in numeric[s,t])] for s,t in keys]
        rg=[[s,t,*(v.hex() for v in gross[s,t])] for s,t in keys]
        nominal_sha=hashlib.sha256(canonical(dict(schema='training-annual-simple-v1',fields=list(FIELDS),rows=rows))).hexdigest()
        real_sha=hashlib.sha256(canonical(dict(schema='training-real-gross-v1',asset_order=list(FIELDS[2:5]),rows=rg))).hexdigest()
        equal(saved['training_rows_sha256'],nominal_sha,'training nominal digest')
        equal(saved['real_gross_sha256'],real_sha,'training real gross digest')
        prior[fold]=[tuple(dec(v) for v in gross[k]) for k in keys]
        folds.append(dict(fold_id=fold,training_scenarios=len(train),evaluation_scenarios=len(evaluate),rows=len(keys),
                          training_rows_sha256=nominal_sha,real_gross_sha256=real_sha))

    def ce(weights,fold,recent):
        # Direct 70-digit inverse cube moment; independent of producer logsumexp.
        ww=tuple(dec(w) for w in weights)
        def inverse_cube(row):
            return sum((w*g for w,g in zip(ww,row)),D(0)) ** -3
        pm=sum((inverse_cube(row) for row in prior[fold]),D(0))/2700
        moment=(15*pm+sum((inverse_cube(row) for row in recent),D(0)))/(15+len(recent))
        return moment ** (-D(1)/3)

    with localcontext() as ctx:
        ctx.prec=70
        for mode,central in CENTRAL.items():
            ledgers=table(base+'cases/'+mode+'/annual_ledgers.csv')
            decisions=table(base+'cases/'+mode+'/decisions.csv')
            scores=table(base+'cases/'+mode+'/target_scores.csv')
            equal([(r['scenario_id'],r['period']) for r in decisions],[(r['scenario_id'],r['period']) for r in ledgers],'decision exact grid')
            score_by_key=defaultdict(dict)
            for row in scores:
                key=int(row['scenario_id']),int(row['period']);name=row['target_name']
                assert name not in score_by_key[key],('duplicate score',mode,key,name)
                score_by_key[key][name]=row
            sample_keys={(s,t) for s in range(1,5) for t in (1,2,5,6,15,30)}
            for fold in range(4):
                candidates=[r for r in decisions if (int(r['scenario_id'])-1)%4==fold and r['ce_keep']]
                if candidates:
                    closest=min(candidates,key=lambda r:min(abs(float(v['conservative_score'])-float(r['ce_keep'])-1e-12) for v in score_by_key[int(r['scenario_id']),int(r['period'])].values()))
                    sample_keys.add((int(closest['scenario_id']),int(closest['period'])))
            for action in ('keep','target_change','human_review'):
                match=next((r for r in decisions if r['action']==action),None)
                if match: sample_keys.add((int(match['scenario_id']),int(match['period'])))
            counter=Counter();scored=0;seen=set()
            for scenario in range(1,121):
                active=central;latched=False;first=None;deferred=False;peak=D(100);loss=D(0)
                for period in range(1,31):
                    index=(scenario-1)*30+period-1;row=decisions[index];ledger=ledgers[index];key=scenario,period;fold=(scenario-1)%4
                    available=score_by_key.get(key,{})
                    equal((row['mode'],int(row['fold_id']),float(row['fee_rate'])),(mode,fold,fee),'decision identity')
                    equal(row['active_before'],active,'active continuity')
                    near(row['observed_max_drawdown_pct'],loss,'observed prefix drawdown')
                    latched=latched or loss>=25
                    equal(row['human_review_latched'],str(latched).lower(),'prefix latch')
                    contextual=mode in ('balanced_context','balanced_adaptive');n=min(5,period-1) if contextual else 0
                    equal(int(row['recent_count']),n,'completed same-scenario window')
                    near(row['prior_mass'],D(15)/(15+n),'prior empirical mass')
                    before=tuple(float(ledger['holdings_before_'+a]) for a in ASSETS);wealth=math.fsum(before)
                    weights=tuple(h/wealth for h in before)
                    if latched:
                        equal(available,{},'no scoring during human review')
                        equal((row['action'],row['selected_target'],row['proposed_target'],row['ce_keep']),('human_review','','',''),'latched null decision')
                    else:
                        order=[active]
                        if mode=='balanced_adaptive' and n==5:order += [x for x in ('defensive','balanced','growth_tilt') if x!=active]
                        equal(set(available),set(order),'allowed target set')
                        ce_keep=float(row['ce_keep']);expected_scores={}
                        recent=[tuple(dec(v) for v in gross[scenario,t]) for t in range(period-n,period)]
                        sample=key in sample_keys
                        expected_keep=ce(weights,fold,recent) if sample else None
                        if sample:near(ce_keep,expected_keep,'Decimal keep CE')
                        for name in order:
                            ss=available[name];target=TARGETS[name]
                            equal(tuple(float(ss['target_'+a]) for a in ASSETS),target,'fixed target weights')
                            tau=sum(abs(dec(w)-dec(u)) for w,u in zip(target,weights))/2
                            cost=dec(fee)*tau;target_ce=dec(ss['ce_target'])
                            near(ss['tau'],tau,'independent tau')
                            near(ss['fee_fraction'],cost,'single fee fraction')
                            near(ss['pre_cost_benefit'],target_ce-dec(ce_keep),'pre cost CE difference')
                            near(ss['modeled_fee_impact'],cost*target_ce,'single estimated fee impact')
                            near(ss['conservative_score'],(1-2*cost)*target_ce,'buffered score')
                            near(ss['true_net_ce'],(1-cost)*target_ce,'actual estimated net CE')
                            expected_scores[name]=float(ss['conservative_score'])
                            if sample:
                                expected_target=ce(target,fold,recent)
                                near(ss['ce_target'],expected_target,'Decimal target CE')
                                samples.append(dict(mode=mode,scenario_id=scenario,period=period,fold_id=fold,target=name,recent_count=n,
                                    ce_keep_expected=str(expected_keep),ce_keep_observed=row['ce_keep'],ce_target_expected=str(expected_target),
                                    ce_target_observed=ss['ce_target'],conservative_score_expected=str((1-2*cost)*expected_target),conservative_score_observed=ss['conservative_score']))
                            scored+=1;seen.add(key)
                        maximum=max(expected_scores.values());proposal=next(x for x in order if maximum-expected_scores[x]<=1e-12)
                        equal(row['proposed_target'],proposal,'global max proposal tie')
                        eligible=[x for x in order if expected_scores[x]>ce_keep+1e-12]
                        chosen=None
                        if eligible:
                            maximum=max(expected_scores[x] for x in eligible);chosen=next(x for x in eligible if maximum-expected_scores[x]<=1e-12)
                        equal(row['selected_target'],chosen or '','strict hurdle and anchored tie')
                        expected_action='keep' if chosen is None else 'rebalance' if chosen==active else 'target_change'
                        equal(row['action'],expected_action,'action semantics')
                        if chosen is not None:active=chosen
                    equal(row['active_after'],active,'executed active state')
                    equal(row['executed_target_change'],str(row['action']=='target_change').lower(),'executed change flag')
                    equal(float(row['actual_fee']),float(ledger['fee']),'saved actual fee link')
                    equal(float(row['intended_transfer']),float(ledger['intended_transfer']),'saved transfer link')
                    transfer=float(row['intended_transfer'])
                    equal(row['is_trade'],str(transfer>1e-10).lower(),'reporting trade threshold')
                    if row['action'] in ('rebalance','target_change'):
                        if first is None and transfer>0:first=period
                        equal(ledger['engine_action'],'rebalance','executed engine request')
                    else:
                        equal(ledger['engine_action'],'keep','keep engine request')
                        equal(float(row['actual_fee']),0.,'keep and latch free')
                    if period==1:deferred=first is None
                    equal(row['first_deployment_year'],'' if first is None else str(first),'first deployment state')
                    equal(row['initial_allocation_deferred'],str(deferred).lower(),'persistent initial deferral')
                    expected_reason='human_review_latched' if latched else 'benefit_gate_failed' if row['selected_target']=='' else 'initial_allocation' if first==period else row['action']
                    equal(row['reason'],expected_reason,'reason link')
                    for field in ('real_wealth_after_fee','real_wealth_end'):
                        value=dec(ledger[field]);peak=max(peak,value);loss=max(loss,100*(1-value/peak))
                    counter[row['action']]+=1
            equal(scored,len(scores),'all saved scores accounted')
            equal(seen,set(score_by_key),'all scoring keys accounted')
            events[mode]=dict(decisions=len(decisions),score_rows=len(scores),actions=dict(counter),sampled_states=len({(x['scenario_id'],x['period']) for x in samples if x['mode']==mode}))
    return dict(status='passed',task_id=task_id,reviewed_commit=commit,checked_at=datetime.now(timezone.utc).isoformat(),checks=checks,max_absolute_difference=maximum_error,
        folds=folds,modes=events,scalar_facts=samples,exact_git_blob_sha256=records,production_acceptance=False,
        method='No SafeInvest imports; independent source-row/digest reconstruction,70-digit direct CRRA inverse-cube moments,all saved decision and prefix-latch links.',
        limitations=['High precision CE arithmetic is sampled; all decision score identities/actions/latches are checked, not all CE expectations.',
                     'Saved scores support full action selection checks; independent remote review remains required.',
                     'No policy selection,customer assignment or final-outcome reads.'])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('task_id',choices=('HY3-004','HY3-005','HY3-006'));parser.add_argument('commit');parser.add_argument('--output',required=True)
    args=parser.parse_args();out=Path(args.output).resolve();assert out.is_relative_to(ROOT/'audit/chief') and not out.exists()
    record=dict(status='started',task_id=args.task_id,reviewed_commit=args.commit,production_acceptance=False)
    try:record=audit(args.task_id,args.commit)
    except Exception as exc:
        record.update(status='failed',failure_type=type(exc).__name__,failure=str(exc));raise
    finally:
        with out.open('x',encoding='utf-8',newline='\n') as stream:json.dump(record,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps(dict(status=record['status'],checks=record['checks'],scalar_facts=len(record['scalar_facts']),modes=record['modes'])))


if __name__=='__main__':main()
