"""Independent exact case references, prepared before SOL-023 delivery.

No production helper imports or competition CSV reads. Rational ledger arithmetic
and enumerated peak/trough pairs deliberately differ from the production engine.
This verifies reference arithmetic, not an absent case implementation.
"""
import argparse
from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT / 'audit/chief/case-reference.json'
PINS = {
    'specs/ACCOUNTING.md': 'a9c3ab8dbba3ad752336642061ead272e2c196de83f73eb410e39bd5b559f71e',
    'specs/POLICY_CASE_ENGINE.md': 'c984e230eecb720613b864a910d95921af1aa805f79fa68c7044f905410dec62',
    'specs/development_policy_pilot_v2.json': 'd7b20f38196831befc80dfdcc69c6653d1ae8352d1c87c79e19bcc09d5c84df3',
}


def exact_path(outcomes, targets, fee):
    holdings = (F(0), F(0), F(100))
    cpi = F(1)
    rows = []
    for t, ((returns, inflation), target) in enumerate(zip(outcomes, targets, strict=True), 1):
        wealth = sum(holdings)
        transfer = (sum(abs(wealth*w-h) for w, h in zip(target, holdings)) / 2
                    if target is not None else F(0))
        cost = fee * transfer
        after = (tuple((wealth-cost)*w for w in target) if target is not None else holdings)
        end = tuple(h*(1+r) for h, r in zip(after, returns))
        end_cpi = cpi * (1+inflation)
        assert sum(after)+cost == wealth
        rows.append(dict(period=t, holdings_before=holdings, holdings_after_fee=after,
                         holdings_end=end, intended_transfer=transfer, fee=cost,
                         cpi_before=cpi, cpi_end=end_cpi, real_wealth_before=wealth/cpi,
                         real_wealth_after_fee=sum(after)/cpi, real_wealth_end=sum(end)/end_cpi))
        holdings, cpi = end, end_cpi
    return rows


def exact_metrics(ledger, horizon):
    rows = ledger[:horizon]
    values = [F(100)]
    locations = [(0, 'initial')]
    for row in rows:
        values += [row['real_wealth_after_fee'], row['real_wealth_end']]
        locations += [(row['period'], 'post_fee'), (row['period'], 'end')]
    # Enumerating every prior peak candidate avoids duplicating the running-max code.
    candidates = [(1-values[j]/values[i], j, i)
                  for j in range(len(values)) for i in range(j+1)]
    loss, trough, peak = min(candidates, key=lambda x: (-x[0], x[1], x[2]))
    annual = [row['real_wealth_end']/row['real_wealth_before']-1 for row in rows]
    mean = sum(annual)/horizon
    variance = sum((r-mean)**2 for r in annual)/(horizon-1) if horizon > 1 else None
    trades = [row['intended_transfer'] > F(1, 10**10) for row in rows]
    return dict(horizon=horizon, terminal_real_wealth=values[-1],
                max_real_drawdown_pct=100*loss,
                drawdown_peak=list(locations[peak]), drawdown_trough=list(locations[trough]),
                nominal_fee_sum=sum(row['fee'] for row in rows), trade_count=sum(trades),
                trade_share_pct=F(100*sum(trades), horizon),
                trade_share_ex_initial_pct=F(100*sum(trades[1:]), horizon-1) if horizon > 1 else None,
                annual_real_returns=annual, annual_return_sample_variance=variance,
                net_real_cagr_pct=100*(float(values[-1]/100)**(1/horizon)-1),
                annual_real_volatility_pct=100*math.sqrt(float(variance)) if variance is not None else None)


def encode(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {k: encode(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [encode(v) for v in value]
    return value


def calculate():
    for name, expected in PINS.items():
        assert hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n', b'\n')).hexdigest() == expected, name
    facts = {}
    fee = F(1, 400)
    target = (F(1, 5), F(0), F(4, 5))
    outcomes = [((F(1, 4), F(0), F(0)), F(1, 4)),
                ((F(0), F(1, 2), F(1, 4)), F(0))]
    path = exact_path(outcomes, [target, target], fee)
    assert path[0]['fee'] == F('0.05')
    assert path[0]['holdings_after_fee'] == (F('19.99'), F(0), F('79.96'))
    assert path[0]['real_wealth_end'] == F('83.958')
    assert path[1]['intended_transfer'] == F('3.998')
    assert path[1]['fee'] == F('0.009995')
    assert path[1]['real_wealth_after_fee'] == F('83.950004')
    assert path[1]['real_wealth_end'] == F('100.7400048')
    two = exact_metrics(path, 2)
    assert two['max_real_drawdown_pct'] == F('16.049996')
    assert two['drawdown_trough'] == [2, 'post_fee']
    assert two['nominal_fee_sum'] == F('0.059995')
    facts['two_year_forced_target_accounting_only'] = dict(
        targets=[target, target], outcomes=outcomes, fee_rate=fee, ledger=path,
        metrics=[exact_metrics(path, 1), two],
        limitation='Prescribed accounting requests; no claim that a policy chooses these targets.')

    equal = (F(1, 3),)*3
    declining = [((F(1, 8),)*3, F(1, 4))]*6
    kept = exact_path(declining, [None]*6, fee)
    horizons = (2, 3, 4, 6)
    diagnostics = []
    for h in horizons:
        metric = exact_metrics(kept, h)
        assert metric['terminal_real_wealth'] == 100*F(9, 10)**h
        assert metric['max_real_drawdown_pct'] == 100*(1-F(9, 10)**h)
        assert metric['annual_return_sample_variance'] == 0
        diagnostics.append(dict(horizon=h, human_review_count=max(0, h-3),
            human_review_share_pct=F(100*max(0, h-3), h),
            first_latch_year=4 if h >= 4 else None, first_deployment_year=None,
            initial_allocation_deferred=True, target_change_count=0))
    assert diagnostics[1]['first_latch_year'] is None and diagnostics[2]['first_latch_year'] == 4
    assert 100*(1-F(9, 10)**2) == 19 < 25 < 100*(1-F(9, 10)**3) == F('27.1')
    facts['deferred_then_latched_all_five_modes'] = dict(
        scenario_ids=[1, 2, 3, 4], periods=6, returns=[F(1, 8)]*3, inflation=F(1, 4),
        real_gross=[F(9, 10)]*3, fee_rates=[fee, 2*fee],
        ledger=kept, metrics=[exact_metrics(kept, h) for h in horizons], diagnostics=diagnostics,
        actions=['keep']*3+['human_review']*3,
        observed_losses_before_review=[100*(1-F(9, 10)**(t-1)) for t in range(1, 7)],
        per_case_counts=dict(annual_ledgers=24, scenario_metrics=16, summary=4, decisions=24, target_scores=12),
        reference_diagnostics='All policy-specific diagnostics are null/inapplicable for baselines.')

    scores = []
    for name, bill in [('conservative', F(13, 20)), ('balanced', F(1, 3)), ('growth', F(1, 10))]:
        for k in (fee, 2*fee):
            tau = 1-bill
            f = k*tau
            scores.append(dict(target_name=name, fee_rate=k, ce_keep=F(9, 10), ce_target=F(9, 10),
                tau=tau, fee_fraction=f, pre_cost_benefit=F(0), modeled_fee_impact=f*F(9, 10),
                conservative_score=(1-2*f)*F(9, 10), true_net_ce=(1-f)*F(9, 10), selected=False))
            assert scores[-1]['conservative_score'] < scores[-1]['ce_keep']
    facts['identical_asset_scores'] = dict(rows=scores,
        score_years=[1, 2, 3], no_scores_years=[4, 5, 6],
        contextual_recent_counts=[0, 1, 2, 3, 4, 5],
        contextual_prior_masses=[F(15, 15+n) for n in range(6)],
        fixed_recent_counts=[0]*6, fixed_prior_masses=[F(1)]*6)

    references = []
    for k in (fee, 2*fee):
        annual = exact_path(declining, [equal]*6, k)
        hold = exact_path(declining, [equal]+[None]*5, k)
        assert [r['real_wealth_end'] for r in annual] == [r['real_wealth_end'] for r in hold]
        assert all(r['intended_transfer'] == 0 for r in annual[1:])
        assert annual[0]['fee'] == F(200, 3)*k
        references.append(dict(fee_rate=k, initial_transfer=F(200, 3),
            initial_fee=F(200, 3)*k, annual_metrics=[exact_metrics(annual, h) for h in horizons],
            buy_hold_metrics=[exact_metrics(hold, h) for h in horizons],
            decisions_count=0, target_scores_count=0, policy_diagnostics=None, severe_scenario_id=1))
    facts['equal_asset_reference_controls'] = references

    tie_path = exact_path([((F(1, 4),)*3, F(1, 4)), ((F(1, 4),)*3, F(0))],
                          [(F(1), F(0), F(0)), None], fee)
    tie = exact_metrics(tie_path, 2)
    assert tie['max_real_drawdown_pct'] == F(1, 4)
    assert tie['drawdown_peak'] == [0, 'initial'] and tie['drawdown_trough'] == [1, 'post_fee']
    facts['earliest_post_fee_trough_on_exact_tie'] = dict(ledger=tie_path, metrics=tie)
    return encode(dict(schema_version=1, source_sha256=PINS,
        script_sha256_lf=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n')).hexdigest(),
        scope='Chief independent rational synthetic case references; future implementation still needs comparison and acceptance.',
        reference_groups=len(facts), facts=facts, competition_outcomes_read=False,
        implementation_executed=False, final_data_open=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--evidence', type=Path, default=DEFAULT)
    args = parser.parse_args()
    result = calculate()
    if args.check:
        assert json.loads(args.evidence.read_bytes()) == result, 'Reference mismatch; refusing to repair'
    else:
        with args.evidence.open('x', encoding='utf-8', newline='\n') as file:
            json.dump(result, file, indent=2, allow_nan=False)
            file.write('\n')
    print(json.dumps(dict(reference_groups=result['reference_groups'], read_only=args.check,
                         implementation_executed=False)))


if __name__ == '__main__':
    main()
