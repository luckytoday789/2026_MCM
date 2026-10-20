"""Source-bound descriptive primary development tables; never run a policy."""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
PRODUCER='6aa2ccdce80834c8beb52a827993f1f587d1d8a6'
REVIEW='a9073e1d0ab5aadea639daf34ba76fab728d636f'
MODES=('bills_keep','equal_weight_annual','equal_weight_buy_hold','conservative_cost',
       'balanced_cost','growth_cost','balanced_context','balanced_adaptive')
COLS=('median_growth_pct','p10_growth_pct','median_loss_pct','p90_loss_pct',
      'median_volatility_pct','pooled_trade_share_pct','pooled_trade_share_ex_initial_pct')


def sha(data):return hashlib.sha256(data).hexdigest()
def blob(commit,path):return subprocess.check_output(['git','show',commit+':'+path],cwd=ROOT)
def encoded(value):return (json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()


def build():
    queue=json.loads((ROOT/'ops/queue.json').read_bytes())
    acceptances={}
    for task,commit in (('HY3-004',PRODUCER),('SOL-040',REVIEW)):
        item=next(t for t in queue['tasks'] if t['id']==task)
        assert item['state']=='accepted' and item['reviewed_commit']==commit
        path=item['acceptance_evidence'];raw=(ROOT/path).read_bytes()
        audit=json.loads(raw);assert audit['reviewed_commit']==commit
        acceptances[task]={'commit':commit,'path':path,'sha256':sha(raw)}
    receipt=json.loads(blob(PRODUCER,'handoff/HY3-004/result.json'))
    assert receipt['status']=='completed' and receipt['artifact_hash_basis']=='canonical_git_blob'
    rows=[];sources={}
    for mode in MODES:
        path=f'results/development/HY3-004/cases/{mode}/summary.csv'
        data=blob(PRODUCER,path)
        assert sha(data)==receipt['artifacts_sha256'][path] and (ROOT/path).read_bytes()==data
        selected=list(csv.DictReader(io.StringIO(data.decode())))
        assert len(selected)==5 and {int(r['horizon']) for r in selected}=={5,6,15,25,30}
        for row in selected:
            assert row['mode']==mode and row['split']=='development' and row['scenario_count']=='120'
            assert float(row['fee_rate'])==.0025
            assert all(math.isfinite(float(row[c])) for c in COLS)
        rows.extend(selected);sources[path]={'sha256':sha(data),'rows':5}
    rows.sort(key=lambda r:(int(r['horizon']),MODES.index(r['mode'])))
    lines=['# Accepted primary development summaries','',
        'Incomplete report evidence note. All eight predeclared modes and all five horizons are shown; '
        'this table does not select a mode, assign a customer, test a promotion rule, or report final outcomes. '
        'Comparison assembly and the independent doubled-fee review remain separate gates.','',
        'Inputs are the 120 original independent synthetic scenarios 1–120. Each horizon uses its own prefix; '
        'the common Balanced comparison horizon is 30 years. Cost-aware priors use the accepted four-fold '
        'scenario split with 90 training scenarios and all 2,700 annual training rows per fold. Fixed references '
        'are authenticated imports from accepted HY3-003. The actual one-way fee is 0.25%, including initial '
        'allocation, before annual simple returns; inflation is compounded exactly.','',
        'Growth is net real CAGR (%/year). Loss is maximum real drawdown (%), including initial and post-fee '
        'wealth. Fluctuation is the sample standard deviation of annual net real wealth returns '
        '(percentage points, ddof=1). Trade shares count reviews with transfer >1e-10. '
        'Linear p10/p90 scenario quantiles are descriptive, not guaranteed bounds. '
        'Display uses Python binary64 fixed-point rounding to two decimals; full source strings remain in provenance.','',
        '| H | Mode | Median growth | p10 growth | Median loss | p90 loss | Median fluctuation | Trades incl. initial (%) | Trades later (%) |',
        '| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    displayed=[]
    for row in rows:
        values=[format(float(row[c]),'.2f') for c in COLS]
        lines.append('| '+' | '.join([row['horizon'],row['mode'],*values])+' |')
        displayed.append({'key':{'mode':row['mode'],'horizon':int(row['horizon']),'split':'development','fee_rate':.0025},
            'source_path':f"results/development/HY3-004/cases/{row['mode']}/summary.csv",
            'source_row':row,'display':dict(zip(COLS,values))})
    lines += ['', 'The generic human-review threshold is 25% for all five cost-aware modes in these runs. '
        'These generic results cannot establish suitability at a client’s own tolerance. '
        'The original failures, sampled independent CRRA rescoring limits and required personalized rescreens '
        'remain disclosed in the exact acceptance evidence. No customer recommendation follows from this note.','',
        f'Producer: `{PRODUCER}`; independent review: `{REVIEW}`. '
        'See `audit/chief/HY3-004-review.json` and `audit/chief/SOL-040-review.json`. '
        'Source regeneration reads accepted Git summary blobs only; it neither simulates nor reads final data.','']
    text='\n'.join(lines).encode()
    provenance={'schema_version':1,'scope':'descriptive_primary_development_only','producer_commit':PRODUCER,
        'independent_review_commit':REVIEW,'acceptances':acceptances,'source_files':sources,
        'table_rows':40,'numeric_display_cells':len(rows)*len(COLS),'display_columns':COLS,
        'rounding':'format(float(source_string), .2f); display only','displayed_rows':displayed,
        'note_sha256':sha(text),'final_outcomes_read':False,'policy_selected':False,'customer_assignment':False}
    return {'primary-development.md':text,'primary-development-provenance.json':encoded(provenance)}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    outputs=build()
    for name,data in outputs.items():
        target=ROOT/'report'/name
        if args.check:assert target.read_bytes()==data,name
        else:
            with target.open('xb') as handle:handle.write(data)
    print(json.dumps({'status':'passed','mode':'check' if args.check else 'create',
        'rows':40,'numeric_cells':280,'files':{n:sha(d) for n,d in outputs.items()}}))


if __name__=='__main__':main()
