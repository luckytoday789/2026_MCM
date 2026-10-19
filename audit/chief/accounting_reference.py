"""Chief's rational oracle, authored before reviewing Sol's implementation.
No production imports or scenario files. These are toy checks, not performance.
"""
import argparse
from fractions import Fraction as F
import json
import math
from pathlib import Path

def exact(x):
    return {"rational": str(x), "value": float(x)}

def build():
    k = F(1, 400)
    transfer, fee = F(20), F(20)*k
    assert fee == F(1, 20)
    allocated = [(100-fee)*F(1, 5), F(0), (100-fee)*F(4, 5)]
    assert allocated == [F(1999, 100), F(0), F(1999, 25)]
    # Explicit scalar algebra, not an imported production rebalance function.
    fee1 = F(200, 3)*k
    holding1 = (100-fee1)/3
    end1 = [holding1*F(11, 10), holding1, holding1*F(19, 20)]
    wealth1 = sum(end1)
    # Only equity exceeds the new one-third target.
    transfer2 = end1[0]-wealth1/3
    assert transfer2 == sum(abs(wealth1/3-x) for x in end1)/2
    fee2 = transfer2*k
    holding2 = (wealth1-fee2)/3
    end2 = [holding2*F(4, 5), holding2*F(11, 10), holding2]
    cpi = F(51, 50)
    real1, real_trade2, real2 = wealth1/cpi, (wealth1-fee2)/cpi, sum(end2)/cpi
    path = [F(100), 100-fee1, real1, real_trade2, real2]
    peak, drawdown = F(100), F(0)
    for value in path:
        peak = max(peak, value)
        drawdown = max(drawdown, 1-value/peak)
    returns = [real1/100-1, real2/real1-1]
    mean_return = sum(returns)/2
    variance = sum((x-mean_return)**2 for x in returns)  # H-1 = 1
    assert sum(end1) == (100-fee1)*F(61, 60)
    assert sum(end2) == (wealth1-fee2)*F(29, 30)
    assert drawdown == 1-real2/100
    recovery_terminal = (100-fee1)*F(11, 10)
    assert recovery_terminal > 100
    return {
        "schema_version": 1, "author_role": "chief",
        "purpose": "Independent toy oracle; no scenario outcomes or production imports",
        "fee_rate": exact(k),
        "twenty_unit_transfer": {
            "pre_holdings": [0, 0, 100], "target": ["1/5", "0", "4/5"],
            "transfer": exact(transfer), "fee": exact(fee),
            "post_fee_holdings": [exact(x) for x in allocated]},
        "all_equity_initial": {
            "transfer": exact(F(100)), "fee": exact(F(1, 4)),
            "post_fee_wealth": exact(F(399, 4))},
        "keep_bills_inflation_only": {
            "inflation": exact(F(1, 10)), "fee": exact(F(0)),
            "real_terminal": exact(F(1000, 11)),
            "growth_pct_pa": exact(-F(100, 11)),
            "max_real_drawdown_pct": exact(F(100, 11)),
            "volatility_pct_pa": None,
            "volatility_note": "Undefined at H=1; do not substitute zero."},
        "initial_fee_then_recovery": {
            "returns": ["1/10", "1/10", "1/10"], "inflation": "0",
            "real_post_fee": exact(100-fee1), "real_terminal": exact(recovery_terminal),
            "max_real_drawdown_pct": exact(F(1, 6))},
        "equal_weight_two_year": {
            "returns": [["1/10", "0", "-1/20"], ["-1/5", "1/10", "0"]],
            "inflation": ["1/50", "0"], "initial_holdings": [0, 0, 100],
            "transfer": [exact(F(200, 3)), exact(transfer2)],
            "fees": [exact(fee1), exact(fee2)],
            "post_fee_each_holding": [exact(holding1), exact(holding2)],
            "end_holdings": [[exact(x) for x in end1], [exact(x) for x in end2]],
            "real_path_initial_trade_end_trade_end": [exact(x) for x in path],
            "annual_net_real_returns": [exact(x) for x in returns],
            "terminal_real_wealth": exact(real2),
            "growth_pct_pa": 100*(math.sqrt(float(real2/100))-1),
            "volatility_pct_pa_ddof1": 100*math.sqrt(float(variance)),
            "max_real_drawdown_pct": exact(100*drawdown),
            "trade_share_including_initial_pct": 100,
            "trade_share_excluding_initial_pct": 100},
        "quantile_linear_fixture": {
            "values": [0, 10, 20, 30], "p10": 3, "median": 15, "p90": 27},
        "comparison_tolerance": {"absolute_toy": 1e-9, "relative_ledger": 1e-10}
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", type=Path)
    args = parser.parse_args()
    report = build()
    if args.check:
        assert json.loads(args.check.read_text(encoding="utf-8")) == report
        print("Rational oracle snapshot matches all independently derived fixtures.")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    if not args.output and not args.check:
        print(json.dumps(report, indent=2))
