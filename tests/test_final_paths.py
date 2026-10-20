"""Generated final arithmetic, independent rational ledgers and prefix timing."""

from collections.abc import Mapping
from dataclasses import FrozenInstanceError
from fractions import Fraction
import csv
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from safeinvest.backtest import Decision, _simulate_policy_arithmetic, simulate_policy
from safeinvest.baselines import POLICIES
from safeinvest.final_paths import (
    _simulate_generated_final_fixture, final_prefix_metrics,
    simulate_generated_final_path,
)
from safeinvest.final_refit import build_generated_refit
from safeinvest.metrics import compute_metrics
from safeinvest.policy_calibration import FIELDS
from safeinvest.policy_pilot import CENTRAL_TARGET, CostAwarePolicy, EmpiricalPrior


PRIOR=EmpiricalPrior(((1.15,1.04,1.01),(.95,1.01,1.0),(1.08,1.03,1.01)))


def rows(scenario=121,periods=30):
    return [dict(zip(FIELDS,(scenario,t,.08 if t%3 else -.2,.02,.01,.015)))
            for t in range(1,periods+1)]


def simulate(source=None,**kwargs):
    parameters=dict(mode="balanced_context",prior=PRIOR,horizon=30,
                    fee_rate=.0025,split="final")
    parameters.update(kwargs)
    return simulate_generated_final_path(rows() if source is None else source,**parameters)


class FinalPathTests(unittest.TestCase):
    def test_three_baselines_match_all_saved_rational_ledgers_and_metrics(self):
        directory=ROOT/"audit/chief/final-path-reference"
        expected=json.loads((directory/"expected.json").read_text())
        fixture=list(csv.DictReader(io.StringIO((directory/"fixture.csv").read_text())))
        for oracle in expected["paths"]:
            if oracle["mode"] not in POLICIES:
                continue
            selected=[row for row in fixture if int(row["scenario_id"])==oracle["scenario_id"]]
            path=_simulate_generated_final_fixture(selected,periods=6,mode=oracle["mode"],
                    prior=PRIOR,horizon=6,fee_rate=float(Fraction(oracle["fee_rate"])),
                    review_drawdown_pct=25,split="final")
            for entry,reference in zip(path.result.ledger,oracle["ledger"]):
                for name,value in reference.items():
                    if name in ("period","action","target"):
                        continue
                    actual=getattr(entry,name)
                    if isinstance(value,list):
                        for a,b in zip(actual,value):
                            self.assertAlmostEqual(a,float(Fraction(b)),delta=2e-11)
                    else:
                        self.assertAlmostEqual(actual,float(Fraction(value)),delta=2e-11)
            for record in oracle["metrics"]:
                metrics=final_prefix_metrics(path,record["horizon"])
                for name in ("net_real_cagr_pct","annual_real_volatility_pct","max_real_drawdown_pct"):
                    actual=getattr(metrics,name); value=record[name]
                    if value is None:
                        self.assertIsNone(actual)
                    else:
                        self.assertAlmostEqual(actual,float(Fraction(value)),delta=2e-11)
        # Six fresh elementary rational facts independent of the saved builder.
        flat=rows()
        for row in flat:
            row.update(equity_return=0,bond_return=0,bill_proxy_return=0,inflation=0)
        for fee in (.0025,.005):
            path=simulate(flat,mode="equal_weight_buy_hold",fee_rate=fee,horizon=1)
            cost=100*Fraction(str(fee))*Fraction(2,3)
            self.assertAlmostEqual(path.result.ledger[0].fee,float(cost),delta=1e-13)
            self.assertAlmostEqual(path.result.ledger[0].wealth_end,float(100-cost),delta=1e-12)
            self.assertAlmostEqual(path.result.metrics.max_real_drawdown_pct,float(cost),delta=1e-12)

    def test_true_final_identity_detached_metadata_prior_and_h1_nulls(self):
        path=simulate(horizon=1)
        self.assertEqual(path.result.split,"final")
        self.assertEqual(path.result.metrics.split,"final")
        self.assertIsNone(path.result.metrics.annual_real_volatility_pct)
        self.assertIsNone(path.result.trade_share_ex_initial_pct)
        metadata=path.metadata(); metadata["source_verified"]=True
        self.assertFalse(path.metadata()["source_verified"])
        self.assertFalse(path.metadata()["production_execution_authorized"])
        self.assertEqual(path.prior_support_count,3)
        with self.assertRaises(FrozenInstanceError):
            path.mode="growth_cost"

    def test_all_60_generated_scenarios_eight_modes_both_fees_and_own_thresholds(self):
        modes=(*POLICIES,*CENTRAL_TARGET)
        self.assertEqual(len(modes),8)
        support=PRIOR.gross
        for scenario in range(121,181):
            for mode in modes:
                for fee in (.0025,.005):
                    path=simulate(rows(scenario),mode=mode,fee_rate=fee)
                    self.assertEqual((path.result.scenario_id,len(path.result.ledger)),(scenario,30))
                    self.assertEqual(len(path.reviews),30 if mode in CENTRAL_TARGET else 0)
        for horizon,threshold in ((5,10),(15,25),(30,40),(25,15),(6,35)):
            for fee in (.0025,.005):
                path=simulate(horizon=horizon,review_drawdown_pct=threshold,fee_rate=fee)
                self.assertEqual(path.result.horizon,horizon)
        self.assertEqual(PRIOR.gross,support)

    def test_current_future_other_path_order_fee_and_horizon_isolation(self):
        original=rows(); changed=[dict(row) for row in original]
        for row in changed[8:]:
            row.update(equity_return=.9,bond_return=-.6,bill_proxy_return=.2,inflation=.2)
        for mode in CENTRAL_TARGET:
            a,b=simulate(original,mode=mode),simulate(changed,mode=mode)
            self.assertEqual(a.reviews[:9],b.reviews[:9])
            self.assertEqual(a.result.ledger[:8],b.result.ledger[:8])
            simulate(rows(180),mode=mode,fee_rate=.005,review_drawdown_pct=10)
            self.assertEqual(a,simulate(original,mode=mode))
            prefix=simulate(original,mode=mode,horizon=6)
            self.assertEqual(prefix.result.ledger,a.result.ledger[:6])
            self.assertEqual(prefix.reviews,a.reviews[:6])

    def test_access_trace_current_outcomes_follow_current_decision(self):
        events=[]
        class Trace(Mapping):
            def __init__(self,row): self.row=row
            def __iter__(self): return iter(self.row)
            def __len__(self): return len(self.row)
            def __getitem__(self,key):
                if key in FIELDS[2:]: events.append((self.row["period"],"outcome"))
                return self.row[key]
        original=CostAwarePolicy.__call__
        def observed(policy,context):
            events.append((context.period,"decision"))
            return original(policy,context)
        with patch.object(CostAwarePolicy,"__call__",observed):
            simulate([Trace(row) for row in rows()],horizon=6)
        for t in range(1,7):
            self.assertLess(events.index((t,"decision")),events.index((t,"outcome")))
        self.assertGreater(events.index((7,"outcome")),events.index((6,"decision")))

    def test_bad_unused_suffix_keys_factors_inputs_and_old_public_guards(self):
        bad=[]
        for name,value in (("period","01"),("scenario_id",True),
                           ("equity_return",float("nan")),("inflation",-1),
                           ("bond_return",True),("equity_return",-1)):
            altered=rows(); altered[-1][name]=value; bad.append(altered)
        bad.extend((rows()[:-1],rows()+rows()[-1:],rows()[::-1]))
        altered=rows(); altered[3]["scenario_id"]=122; bad.append(altered)
        for fixture in bad:
            with self.assertRaises(ValueError): simulate(fixture,horizon=1)
        for kwargs in (dict(split="synthetic"),dict(fee_rate=0),dict(fee_rate=True),
                       dict(review_drawdown_pct=True),dict(review_drawdown_pct=float("inf")),
                       dict(review_drawdown_pct=0),dict(horizon=True),dict(prior=None)):
            with self.assertRaises(ValueError): simulate(**kwargs)
        with self.assertRaises(ValueError):
            simulate_policy(rows(),horizon=1,split="final",callback=lambda c:Decision("keep"))
        with self.assertRaises(ValueError):
            compute_metrics([100],[100],split="final")

    def test_latch_and_keep_zero_fee_after_observed_loss(self):
        source=rows()
        source[0].update(equity_return=-.9,bond_return=-.9,bill_proxy_return=-.9)
        path=simulate(source,review_drawdown_pct=10)
        self.assertNotEqual(path.reviews[0].action,"human_review")
        self.assertTrue(all(review.action=="human_review" for review in path.reviews[1:]))
        self.assertTrue(all(entry.fee==0 and entry.decision.action=="keep"
                            for entry in path.result.ledger[1:]))

    def test_generated_3600_prior_is_supplied_unchanged_by_identity(self):
        out=io.StringIO(newline=""); writer=csv.writer(out,lineterminator="\n")
        writer.writerow(FIELDS)
        writer.writerows((s,t,.08,.02,.01,.015) for s in range(1,121) for t in range(1,31))
        refit=build_generated_refit(out.getvalue().encode(),scenario_count=120,periods=30)
        original=CostAwarePolicy.__init__; supplied=[]
        def observed(policy,mode,prior,**kwargs):
            supplied.append(prior)
            return original(policy,mode,prior,**kwargs)
        with patch.object(CostAwarePolicy,"__init__",observed):
            a=simulate(prior=refit.prior,horizon=6)
            b=simulate(rows(180),prior=refit.prior,horizon=1,fee_rate=.005)
        self.assertTrue(all(prior is refit.prior for prior in supplied))
        self.assertEqual(a.prior_support_sha256,b.prior_support_sha256)
        self.assertEqual(len(refit.prior.gross),3600)
        self.assertEqual([review.recent_count for review in a.reviews],[0,1,2,3,4,5])


if __name__=="__main__": unittest.main()
