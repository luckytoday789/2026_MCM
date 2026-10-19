"""Source-derived report tables for an accepted design, never strategy outcomes."""
import argparse
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
COMMIT='1908813ef2627ca6e15591278ec15ccf2f9e9cff'
CONFIG='specs/development_policy_pilot_v2.json'
EXPECTED='d7b20f38196831befc80dfdcc69c6653d1ae8352d1c87c79e19bcc09d5c84df3'
OUTPUT=ROOT/'report/policy-catalogue.md'
PROVENANCE=ROOT/'report/policy-catalogue-provenance.json'
LABELS={'conservative':'Conservative','balanced':'Balanced','growth':'Growth',
        'balanced_defensive':'Balanced defensive alternative','balanced_growth_tilt':'Balanced growth alternative'}

def sha(raw):return hashlib.sha256(raw).hexdigest()
def percentage(value):
    n=100*F(str(value))
    if n.denominator==1:return str(n.numerator)
    if n==F(100,3):return '33 1/3'
    return str(n)

def build():
    q=json.loads((ROOT/'ops/queue.json').read_bytes())['tasks']
    design=next(x for x in q if x['id']=='SOL-013')
    assert design['state']=='accepted' and design['reviewed_commit']==COMMIT
    assert design['corrected_design_verdict']=='approve'
    # This acceptance approved the corrected design and rejected K1 code.
    # Never convert its original negative implementation verdict into approval.
    assert design['code_verdict']=='changes_required'
    raw=subprocess.check_output(['git','show',COMMIT+':'+CONFIG],cwd=ROOT)
    assert sha(raw)==EXPECTED
    assert sha((ROOT/CONFIG).read_bytes().replace(b'\r\n',b'\n'))==EXPECTED
    config=json.loads(raw);targets=config['targets'];rules=config['suitability']
    assert config['production_execution_authorized'] is False
    lines=['# Reviewed policy menus and profile screens - working text','',
        'These tables reproduce the independently approved v2 design. The percentages '
        'are target allocations and service rules, not observed returns, guaranteed '
        'holdings, accepted customer assignments or authorization to invest. No '
        'competition outcome file is used to generate this note.','',
        '| Target | Equity (%) | Bonds (%) | Bills (%) | Role |',
        '| --- | ---: | ---: | ---: | --- |']
    target_rows=[]
    for key in LABELS:
        weights=targets[key];exact=[F(str(v)) for v in weights]
        assert sum(exact)==1 and min(exact)>=0
        role='Fixed menu' if key in ('conservative','balanced','growth') else 'Adaptive Balanced alternative from year six'
        displays=[percentage(v) for v in weights]
        lines.append('| '+' | '.join([LABELS[key],*displays,role])+' |')
        target_rows.append(dict(key=key,exact_weights=[str(v) for v in exact],display_percent=displays,role=role))
    lines+=['','Balanced keeps the central target in fixed-prior and contextual modes. '
        'The contextual mode changes its return estimate without changing the menu. '
        'The adaptive mode may consider its two alternatives after five completed '
        'annual observations. All new modes apply the same benefit gate to initial '
        'allocation and subsequent trades; a target is not a promise of immediate '
        'deployment. Actual weights can drift between accepted trades.','',
        '| Profile | Own horizon (years) | Stated temporary loss tolerance (%) | Liquidity | Required target bills (%) | Classes before outcome screens |',
        '| --- | ---: | ---: | --- | ---: | --- |']
    ranks=('conservative','balanced','growth');profiles=[]
    for name,profile in config['profiles'].items():
        h=profile['horizon'];cap=0 if h<=6 else 1 if h<20 else 2
        reserve=rules['minimum_target_bill'][profile['liquidity']]
        eligible=[key for i,key in enumerate(ranks) if i<=cap and F(str(targets[key][2]))>=F(str(reserve))]
        assert eligible==rules['eligible_classes_before_outcome_screens'][name]
        lines.append('| '+' | '.join([name,str(h),str(profile['loss_tolerance_pct']),profile['liquidity'],percentage(reserve),', '.join(LABELS[k] for k in eligible)])+' |')
        profiles.append(dict(profile_id=name,**profile,required_target_bill=reserve,eligible_before_outcomes=eligible))
    lines+=['','Horizon caps are Conservative for at most six years, Conservative or '
        'Balanced for seven to nineteen years, and all three for at least twenty '
        'years. The target bill reserve is a liquidity proxy: it neither models '
        'withdrawals nor guarantees a minimum realized bill weight after drift. '
        'Profile D illustrates why a long horizon alone does not admit Growth; '
        'its medium-liquidity reserve removes that menu.','',
        'Each listed class still needs p90 real drawdown at the own horizon no '
        'greater than the stated tolerance and p10 real CAGR no less than zero. '
        'Among qualifying classes, use the highest median real CAGR; classes '
        f'within {rules["growth_indifference_pp"]:.2f} percentage points/year of that maximum '
        'prefer the least growth-oriented menu. These comparisons are inclusive. '
        'If none qualifies, refer to a human. Record loss exceedances as well as '
        'the quantile; passing a p90 screen is not a loss guarantee.','',
        'A provisional class must then be evaluated at the profile\'s own tolerance '
        'and horizon, with the target and benefit rule unchanged. Both risk and '
        'purchasing-power screens must pass again. Failure refers to a human '
        'without trying a replacement class. The entries above are therefore '
        'eligibility sets, not recommendations.','',
        '## Predeclared test of additional Balanced complexity','',
        f'The primary comparison uses {config["comparison_horizon"]} years and '
        f'a {100*config["primary_fee_rate"]:.2f}% one-way transfer fee. All four gates below '
        'must hold for each required direct comparison. Numeric equality passes '
        'the thresholds; a zero fold median is not a positive gain.','',
        '| Gate | Statistic and threshold |','| --- | --- |']
    s=config['selection']
    gate_rows=[('Typical gain',f'Median of scenario-paired real CAGR differences >= {s["median_paired_growth_gain_min_pp"]:.2f} pp/year'),
              ('Lower growth tail',f'Candidate marginal p10 growth minus reference marginal p10 growth >= -{s["p10_growth_decline_max_pp"]:.2f} pp/year'),
              ('Upper loss tail',f'Candidate marginal p90 loss minus reference marginal p90 loss <= {s["p90_loss_increase_max_pp"]:.2f} percentage points'),
              ('Fold support',f'Strictly positive paired median growth gain in at least {s["positive_median_gain_folds_min"]} of {config["folds"]["count"]} folds')]
    lines+=['| '+a+' | '+b+' |' for a,b in gate_rows]
    lines+=['','Contextual fixed targeting is compared directly with fixed-prior Balanced. '
        'Adaptive targeting must pass directly against both of those controls, '
        'even if the contextual rule does not itself qualify. Choose qualifying '
        'adaptive first, then qualifying contextual, otherwise retain fixed-prior '
        'Balanced as the comparison default. A comparison default is not a '
        'customer endorsement. These practical thresholds are not significance tests.','',
        f'The sensitivity fee is {100*max(config["fee_rates"]):.2f}%, with identical '
        'priors, targets and rule parameters; both actual fees and the cost gate '
        'use that rate, so actions may differ. Assess the primary rule at the '
        'higher cost without choosing a new primary rule. Fee-specific profile '
        'assignments remain a separate suitability question.','',
        'Source: specs/development_policy_pilot_v2.json at '+COMMIT+
        ', SHA256 '+EXPECTED+'. Corrected design acceptance: '
        'audit/chief/SOL-013-review.json. Its historical negative kernel verdict '
        'remains preserved; subsequent kernel and calibration approvals do not '
        'supply policy outcome evidence. Reproduce read-only with '
        '`python -B report/build_policy_catalogue.py --check`.','']
    markdown='\n'.join(lines)
    provenance=dict(schema_version=1,scope='Accepted design values only; no empirical performance or assignment',
        source_commit=COMMIT,source_path=CONFIG,source_sha256=EXPECTED,design_review='SOL-013',
        accepted_design_only=True,original_review_code_verdict='changes_required',
        generator_sha256_lf=sha(Path(__file__).read_bytes().replace(b'\r\n',b'\n')),
        target_rows=target_rows,profile_rows=profiles,promotion_rules=s,
        markdown_sha256_lf=sha(markdown.encode()),competition_outcomes_read=False,final_data_open=False)
    return markdown,provenance

def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    text,manifest=build()
    if a.check:
        assert OUTPUT.read_text(encoding='utf-8')==text,'draft differs; refusing to repair'
        assert json.loads(PROVENANCE.read_bytes())==manifest,'provenance differs; refusing to repair'
    else:
        assert not OUTPUT.exists() and not PROVENANCE.exists(),'refuse existing report artifacts'
        with OUTPUT.open('x',encoding='utf-8',newline='\n') as f:f.write(text)
        with PROVENANCE.open('x',encoding='utf-8',newline='\n') as f:json.dump(manifest,f,indent=2);f.write('\n')
    print(json.dumps(dict(target_rows=5,profile_rows=5,independent_eligibility_checks=5,promotion_gates=4,read_only=a.check,competition_outcomes_read=False)))
if __name__=='__main__':main()
