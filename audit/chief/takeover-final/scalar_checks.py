"""Three independently recomputed generated facts; stdlib only, read-only.

Imports no safeinvest module or reference builder; reads only saved generated
fixtures. This evidence does not authenticate original data or grant final access.
"""

import csv
from decimal import Decimal, localcontext
from fractions import Fraction as Q
import io
import json
from pathlib import Path


def check():
    root=Path(__file__).resolve().parents[3]
    refit_dir=root/"audit/chief/final-refit-reference"
    rows=list(csv.DictReader(io.StringIO((refit_dir/"fixture.csv").read_text())))
    gross=[(1+Q(row["equity_return"]))/ (1+Q(row["inflation"])) for row in rows]
    moment=sum(1/g**3 for g in gross)/len(gross)
    assert moment==Q(2503,864)
    with localcontext() as context:
        context.prec=90
        ce=context.power(Decimal(moment.denominator)/Decimal(moment.numerator),Decimal(1)/Decimal(3))
    reference=json.loads((refit_dir/"expected.json").read_text())
    chosen=next(row for row in reference["scalar_expectations"]
                if row["target"]=="equity" and row["recent_count"]==0)
    assert str(ce)==chosen["ce_decimal_90_digits"]

    path_dir=root/"audit/chief/final-path-reference"
    paths=json.loads((path_dir/"expected.json").read_text())["paths"]
    bills=next(path for path in paths if path["scenario_id"]==121 and path["mode"]=="bills_keep"
               and Q(path["fee_rate"])==Q(1,400))
    # Holding100 bills with zero nominal return and CPI51/50 produces5000/51.
    real=Q(100)/(1+Q(2,100)); loss=100*(1-real/100)
    assert real==Q(5000,51) and loss==Q(100,51)
    assert Q(bills["ledger"][0]["real_wealth_end"])==real
    assert Q(bills["metrics"][0]["max_real_drawdown_pct"])==loss

    flat=next(path for path in paths if path["scenario_id"]==123
              and path["mode"]=="equal_weight_buy_hold" and Q(path["fee_rate"])==Q(1,400))
    # Initial bills-to-thirds transfer=100/2*(1/3+1/3+2/3)=200/3.
    transfer=Q(100,2)*(Q(1,3)+Q(1,3)+Q(2,3))
    fee=transfer*Q(1,400); final=100-fee
    assert transfer==Q(200,3) and fee==Q(1,6) and final==Q(599,6)
    assert Q(flat["ledger"][0]["fee"])==fee
    assert Q(flat["metrics"][2]["terminal_real_wealth"])==final
    assert Q(flat["metrics"][2]["max_real_drawdown_pct"])==fee
    return {"competition_data_read":False,"project_math_imported":False,
            "facts":[{"name":"all_twelve_equity_inverse_cube","moment":str(moment),"ce":str(ce)},
                     {"name":"bills_inflation_drag","real_end":str(real),"loss_pct":str(loss)},
                     {"name":"initial_transfer_fee_flat_path","transfer":str(transfer),"fee":str(fee),"terminal":str(final)}],
            "status":"passed"}


if __name__=="__main__":
    print(json.dumps(check(),indent=2))
