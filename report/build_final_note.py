"""Authenticated final report note; reads accepted Git results, never original inputs."""
import argparse,csv,hashlib,io,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
R='4b8ac5d6822ac39ff1189c13d34ed3f84f699319'
PREFIX='results/final/HY3-010/'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |',*['| '+' | '.join(map(str,r))+' |' for r in rows]])
def build():
 q=json.loads((ROOT/'ops/queue.json').read_bytes())['tasks'];t=next(x for x in q if x['id']=='HY3-010')
 assert t['state']=='accepted' and t['reviewed_commit']==R and t['result_verdict']=='approve'
 review=json.loads((ROOT/t['acceptance_evidence']).read_bytes());assert review['status']=='accepted' and review['numerical_review']['independent_checks']==997883
 sources={}
 def read(name):
  path=PREFIX+name;raw=subprocess.check_output(['git','show',R+':'+path],cwd=ROOT)
  assert sha(raw)==t['artifacts_sha256'][path]==review['artifacts_sha256'][path]
  assert (ROOT/path).read_bytes().replace(b'\r\n',b'\n')==raw.replace(b'\r\n',b'\n')
  sources[path]=sha(raw);return raw
 summaries=list(csv.DictReader(io.StringIO(read('summary.csv').decode())))
 profiles=json.loads(read('personalized.json'));comparisons=json.loads(read('comparisons.json'))
 metrics=list(csv.DictReader(io.StringIO(read('scenario_metrics.csv').decode())))
 primary=[r for r in summaries if r['horizon']=='30' and float(r['fee_rate'])==.0025]
 assert len(primary)==8 and all(r['scenario_count']=='60' for r in primary)
 def fmt(v):return format(float(v),'.2f')
 cols=['median_growth_pct','p10_growth_pct','median_loss_pct','p90_loss_pct','median_volatility_pct','pooled_trade_share_pct','pooled_trade_share_ex_initial_pct']
 levels=table(['Mode','Median G','p10 G','Median L','p90 L','Fluct.','Trades all','Trades later'],[[r['mode'],*[fmt(r[k]) for k in cols]] for r in primary])
 executed=[r for r in profiles if r['eligible']];assert len(executed)==4
 assert all(r['status']=='final_validation_failed_human_review' and r['recommended_class'] is None for r in executed)
 clients=table(['Profile/H','Fee %','Tolerance','p90 L','p10 G','Loss > tol.','Med L','Severe L'],[[r['profile_id']+'/'+str(r['horizon']),fmt(100*r['fee_rate']),str(r['loss_tolerance_pct']),fmt(r['p90_loss_pct']),fmt(r['p10_growth_pct']),str(r['exceedance_count'])+'/'+str(r['denominator']),fmt(r['median_loss_pct']),fmt(r['severe_loss_pct'])] for r in executed])
 cost=[r for r in summaries if r['horizon']=='30' and r['mode']=='balanced_cost']
 sensitivity=table(['Fee %','Median G','p10 G','p90 L','Trades all','Trades later'],[[fmt(100*float(r['fee_rate'])),*[fmt(r[k]) for k in ('median_growth_pct','p10_growth_pct','p90_loss_pct','pooled_trade_share_pct','pooled_trade_share_ex_initial_pct')]] for r in cost])
 paired=next(r for r in comparisons if r['alternative_mode']=='balanced_cost' and r['reference_mode']=='equal_weight_annual' and r['fee_rate']==.0025 and r['horizon']==30)
 fixed=next(r for r in primary if r['mode']=='balanced_cost');baseline=next(r for r in primary if r['mode']=='equal_weight_annual')
 sid=fixed['severe_scenario_id'];same=next(r for r in metrics if r['mode']=='equal_weight_annual' and float(r['fee_rate'])==.0025 and r['horizon']=='30' and r['scenario_id']==sid)
 text=f"""# Accepted frozen final evaluation

One frozen evaluation used scenarios121-180,60 independent paths and a common all3600-development-row prior. Source7053b41ce81b1e04100d56a24a321e51b3465459; accepted freeze06086aed327aa626ddc91472f943c2c9fba1259a. Actual closed-gate audit and external attestation precede the gate opening. Both pre-access metadata failures are preserved; neither opened final data or changed policy. Exact final producer: {R}; acceptance: audit/chief/HY3-010-review.json. No final tuning or policy reranking occurred.

## Common30-year primary-fee comparison

Fee0.25%; growth percent/year; loss percentages; fluctuation annual sample standard deviation in percentage points; trades percentage of reviews. All values are from the same60 scenarios. The frozen reporting mode remains Balanced fixed.

{levels}

The median paired Balanced-minus-annual-thirds growth difference is {paired['paired_median_growth_difference_pct']:.3f} percentage points/year. Marginal p10-growth difference is {paired['marginal_p10_growth_difference_pct']:.3f} points/year and marginal p90-loss difference is {paired['marginal_p90_loss_difference_pct']:.3f} points. These are different statistics; final diagnostics do not reopen model selection.

## Own-horizon frozen customer validation

{clients}

All five profiles require human review. A,D,E retain development referrals, with zero personalized simulations. B,C fail the unchanged final loss screen at both fees even though p10 real growth remains positive: their p90 losses exceed25% and40%,respectively. Each executed case exceeds tolerance in7/60 scenarios. No replacement class is selected. The development-qualified recommendation therefore does not survive reserved validation. Existing invested customers retain component dollar holdings with automation suspended; prospective allocations remain in initial bills pending review, with explicit inflation risk.

## Same-mode fee sensitivity

{sensitivity}

The higher fee does not rescue suitability or justify a new primary choice. Final customers' p10 growth remains positive but p90 loss fails at both fees; this is a negative robustness finding.

## Severe path and verification limits

Balanced's own severe scenario is{sid}: loss{fmt(fixed['severe_max_real_drawdown_pct'])}%,real CAGR{fmt(fixed['severe_net_real_cagr_pct'])}%/year,terminal real wealth{fmt(fixed['severe_terminal_real_wealth'])}. Its peak is year{fixed['severe_drawdown_peak_year']}({fixed['severe_drawdown_peak_kind']}) and trough year{fixed['severe_drawdown_trough_year']}({fixed['severe_drawdown_trough_kind']}). Annual thirds on that same path loses{fmt(same['max_real_drawdown_pct'])}%,grows{fmt(same['net_real_cagr_pct'])}%/year and ends at{fmt(same['terminal_real_wealth'])}. Annual thirds has its own separate worst scenario{baseline['severe_scenario_id']} with loss{fmt(baseline['severe_max_real_drawdown_pct'])}%; do not confuse these severe-case definitions.

The independent stdlib oracle recomputed997883 saved-ledger,metric,tail,paired and referral checks; maximum absolute residual was9.095e-13. Three fee/CPI/real-wealth corruptions were rejected. It did not reread original final observations or independently reselect utility actions; separate reviewed source and exact producer hashes support those boundaries. Supplemental remote review and full manuscript/layout/package acceptance remain pending. Humans submit.
"""
 # Spacing is editorial; all numbers remain copied/rounded from exact accepted rows.
 provenance=dict(producer_commit=R,acceptance_evidence=t['acceptance_evidence'],source_hashes=sources,primary_rows=primary,personalized_rows=profiles,paired_primary=paired,same_path_reference=same,sensitivity_rows=cost,freeze_commit='06086aed327aa626ddc91472f943c2c9fba1259a',all_clients_human_review=True,submission_ready=False)
 return {'final-evaluation.md':text.encode(),'final-evaluation-provenance.json':(json.dumps(provenance,indent=2)+'\n').encode()}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--write',action='store_true');a=p.parse_args()
 for name,raw in build().items():
  target=ROOT/'report'/name
  if a.write:
   assert not target.exists(),'preserve prior report artifact';target.write_bytes(raw)
  else:assert target.read_bytes().replace(b'\r\n',b'\n')==raw.replace(b'\r\n',b'\n')
 print('Final report note authenticated; complete manuscript acceptance remains pending.')
