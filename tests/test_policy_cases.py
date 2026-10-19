"""Generated fixtures only. No original competition file is read."""
import copy
import csv
from dataclasses import replace
from fractions import Fraction as F
import io
import math
import statistics
import unittest
from unittest.mock import patch

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from safeinvest.backtest import simulate_policy
from safeinvest.baselines import POLICIES
from safeinvest.policy_calibration import FIELDS, build_synthetic_calibrations
from safeinvest.policy_cases import build_case_tables
from safeinvest.policy_pilot import CENTRAL_TARGET, CostAwarePolicy, EmpiricalPrior, EPSILON

MODES = (*CENTRAL_TARGET, *POLICIES)
FEES = (0., .0025, .005)
SCHEMAS = {"annual_ledgers":["split","mode","scenario_id","period","engine_action","target_equity","target_bond","target_bill_proxy","holdings_before_equity","holdings_before_bond","holdings_before_bill_proxy","holdings_after_fee_equity","holdings_after_fee_bond","holdings_after_fee_bill_proxy","holdings_end_equity","holdings_end_bond","holdings_end_bill_proxy","return_equity","return_bond","return_bill_proxy","wealth_before","cpi_before","real_wealth_before","intended_transfer","fee","wealth_after_fee","real_wealth_after_fee","inflation","wealth_end","cpi_end","real_wealth_end","annual_net_real_return","monetary_units","return_units","cpi_units","growth_units","volatility_units","loss_units","trade_share_units","fee_rate","fold_id"],"scenario_metrics":["split","mode","scenario_id","horizon","net_real_cagr_pct","annual_real_volatility_pct","max_real_drawdown_pct","terminal_real_wealth","nominal_fee_sum","trade_count","review_count","later_trade_count","later_review_count","trade_share_pct","trade_share_ex_initial_pct","drawdown_peak_year","drawdown_peak_kind","drawdown_trough_year","drawdown_trough_kind","monetary_units","return_units","cpi_units","growth_units","volatility_units","loss_units","trade_share_units","fee_rate","fold_id","human_review_count","human_review_share_pct","first_latch_year","target_change_count","first_deployment_year","initial_allocation_deferred"],"summary":["split","mode","horizon","scenario_count","median_growth_pct","p10_growth_pct","median_loss_pct","p90_loss_pct","median_volatility_pct","median_terminal_real_wealth","median_nominal_fee_sum","pooled_trade_count","pooled_review_count","pooled_later_trade_count","pooled_later_review_count","pooled_trade_share_pct","pooled_trade_share_ex_initial_pct","severe_scenario_id","severe_net_real_cagr_pct","severe_max_real_drawdown_pct","severe_terminal_real_wealth","severe_drawdown_peak_year","severe_drawdown_peak_kind","severe_drawdown_trough_year","severe_drawdown_trough_kind","severe_trade_share_pct","severe_trade_share_ex_initial_pct","monetary_units","return_units","cpi_units","growth_units","volatility_units","loss_units","trade_share_units","fee_rate","pooled_human_review_count","pooled_human_review_share_pct","pooled_target_change_count"],"decisions":["split","mode","fee_rate","scenario_id","fold_id","period","action","active_before","active_after","proposed_target","selected_target","ce_keep","prior_mass","recent_count","observed_max_drawdown_pct","human_review_latched","initial_allocation_deferred","intended_transfer","actual_fee","is_trade","executed_target_change","reason","first_deployment_year"],"target_scores":["split","mode","fee_rate","scenario_id","fold_id","period","target_name","target_equity","target_bond","target_bill_proxy","ce_target","tau","fee_fraction","pre_cost_benefit","modeled_fee_impact","conservative_score","true_net_ce"]}


def generated(periods=30, scenarios=4, kind="varying"):
    rows = []
    for s in range(1,scenarios+1):
        for t in range(1,periods+1):
            values = ((0.,0.,0.,0.) if kind == "flat" else
                      (((s+t)%5-1)/32, ((s+2*t)%3)/64, 1/64, ((s+t)%3)/256))
            rows.append(dict(zip(FIELDS,(s,t,*values))))
    return rows


def calibrate(rows, support=None):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream,fieldnames=FIELDS,lineterminator="\n")
    writer.writeheader(); writer.writerows(rows)
    b = build_synthetic_calibrations(stream.getvalue().encode(),
            scenario_count=max(r["scenario_id"] for r in rows),
            periods=max(r["period"] for r in rows))
    if support is not None:
        b = replace(b,folds=tuple(replace(c,prior=EmpiricalPrior(tuple(support)*len(c.training_keys)))
                                 for c in b.folds))
    return b


def tables(rows, cal=None, mode="balanced_adaptive", fee=.0025, horizons=(5,6,15,25,30)):
    return build_case_tables(rows,calibrations=cal if cal is not None else calibrate(rows),
                             mode=mode,fee_rate=fee,split="synthetic",horizons=horizons)


def rational_baseline(rows, mode, fee, horizon):
    """Independent pre-fee transfer, CPI, loss, ddof and growth oracle."""
    h = (F(0),F(0),F(100)); cpi=F(1); real=F(100); peak=F(100); loss=F(0)
    peak_at=selected_peak=selected_trough=(0,"initial")
    annual=[]; fees=[]; transfers=[]; ledger=[]
    for t,row in enumerate(rows[:horizon],1):
        w=(F(1,3),)*3
        W=sum(h)
        transfer=(W*sum(abs(a-b/W) for a,b in zip(w,h))/2
                  if mode == "equal_weight_annual" or mode == "equal_weight_buy_hold" and t == 1 else F(0))
        cost=F(fee)*transfer
        after=tuple((W-cost)*a for a in w) if mode != "bills_keep" and (mode == "equal_weight_annual" or t == 1) else h
        post=sum(after)/cpi
        end=tuple(v*(1+F(row[k])) for v,k in zip(after,FIELDS[2:5]))
        cpi*=1+F(row["inflation"]); new_real=sum(end)/cpi
        for kind,value in (("post_fee",post),("end",new_real)):
            if value>peak: peak=value; peak_at=(t,kind)
            candidate=1-value/peak
            if candidate>loss: loss=candidate; selected_peak=peak_at; selected_trough=(t,kind)
        annual.append(float(new_real/real-1)); fees.append(cost); transfers.append(transfer)
        ledger.append(dict(after=after,end=end,transfer=transfer,fee=cost,cpi=cpi,real=new_real))
        h=end; real=new_real
    return {"terminal_real_wealth":float(real),"nominal_fee_sum":float(sum(fees)),
            "net_real_cagr_pct":100*((float(real)/100)**(1/horizon)-1),
            "annual_real_volatility_pct":statistics.stdev(annual)*100 if horizon>1 else None,
            "max_real_drawdown_pct":100*float(loss),
            "trade_count":sum(x>F(1e-10) for x in transfers),
            "drawdown_peak_year":selected_peak[0],"drawdown_peak_kind":selected_peak[1],
            "drawdown_trough_year":selected_trough[0],"drawdown_trough_kind":selected_trough[1]}, ledger


class CaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=generated(); cls.cal=calibrate(cls.rows)
        cls.cases={(m,k):tables(cls.rows,cls.cal,m,k) for m in MODES for k in FEES}

    def close(self,a,b):
        self.assertTrue(math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-9),(a,b))

    def test_all_modes_fees_schema_keys_counts_and_links(self):
        for (m,k),out in self.cases.items():
            aware=m in CENTRAL_TARGET
            self.assertEqual(out.counts,{"annual_ledgers":120,"scenario_metrics":20,"summary":5,
                "decisions":120 if aware else 0,"target_scores":320 if m=="balanced_adaptive" else 120 if aware else 0})
            self.assertEqual(out.units["growth"],"percent/year")
            self.assertFalse(out.metadata["source_verified"])
            for name in out.counts:
                records=getattr(out,name)
                if not records: continue
                schema=tuple(records[0]); self.assertEqual(list(schema),SCHEMAS[name]); keys=[]
                for r in records:
                    self.assertEqual(tuple(r),schema)
                    self.assertEqual((r["split"],r["mode"],r["fee_rate"]),("synthetic",m,k))
                    self.assertNotIn("policy",r);self.assertNotIn("year",r)
                    if name=="summary":
                        self.assertNotIn("fold_id",r);keys.append((r["horizon"],));continue
                    self.assertEqual(r["fold_id"],(r["scenario_id"]-1)%4)
                    key=(r["scenario_id"],r.get("period",r.get("horizon")))
                    keys.append(key+(r["target_name"],) if name=="target_scores" else key)
                self.assertEqual(len(set(keys)),len(keys))
                self.assertEqual(keys,sorted(keys))
            by_key={(r["scenario_id"],r["period"]):r for r in out.decisions}
            for r in out.target_scores:
                d=by_key[r["scenario_id"],r["period"]]
                self.assertIsNotNone(d["ce_keep"])
                if r["target_name"]==d["selected_target"]:
                    self.assertGreater(r["conservative_score"],d["ce_keep"]+EPSILON)
                self.close(r["pre_cost_benefit"],r["ce_target"]-d["ce_keep"])
                self.close(r["modeled_fee_impact"],r["fee_fraction"]*r["ce_target"])
                self.close(r["conservative_score"],(1-2*r["fee_fraction"])*r["ce_target"])
            for e in out.annual_ledgers:
                if e["engine_action"] == "keep":
                    self.assertEqual(e["fee"],0.)
                    self.assertTrue(all(e["holdings_before_"+a]==e["holdings_after_fee_"+a] for a in ("equity","bond","bill_proxy")))
                else:
                    tau=.5*math.fsum(abs(e["target_"+a]-e["holdings_before_"+a]/e["wealth_before"]) for a in ("equity","bond","bill_proxy"))
                    self.close(e["intended_transfer"],e["wealth_before"]*tau)
                    self.close(e["fee"],k*e["wealth_before"]*tau)
                    self.close(e["wealth_after_fee"],e["wealth_before"]-e["fee"])
            for d,e in zip(out.decisions,out.annual_ledgers):
                self.assertEqual(e["engine_action"],"rebalance" if d["action"] in ("rebalance","target_change") else "keep")
                self.assertEqual(d["actual_fee"],e["fee"])
                self.assertEqual(d["intended_transfer"],e["intended_transfer"])
                if e["intended_transfer"]>0: self.close(e["fee"],k*e["intended_transfer"])

    def test_rational_baselines_and_severe_locations(self):
        for m in POLICIES:
            for k in FEES:
                out=self.cases[m,k]
                for r in out.scenario_metrics:
                    expected,_=rational_baseline(self.rows[(r["scenario_id"]-1)*30:r["scenario_id"]*30],m,k,r["horizon"])
                    for key,v in expected.items():
                        if key.startswith("drawdown_"): continue
                        if isinstance(v,float):self.close(r[key],v)
                        else:self.assertEqual(r[key],v)
                for summary in out.summary:
                    group=[r for r in out.scenario_metrics if r["horizon"]==summary["horizon"]]
                    severe=min(group,key=lambda r:(-r["max_real_drawdown_pct"],r["scenario_id"]))
                    self.assertEqual(summary["severe_scenario_id"],severe["scenario_id"])
                    self.close(summary["pooled_trade_share_pct"],100*sum(r["trade_count"] for r in group)/(4*summary["horizon"]))
                    self.close(summary["pooled_trade_share_ex_initial_pct"],100*sum(r["later_trade_count"] for r in group)/(4*(summary["horizon"]-1)))

    def test_exact_locations_and_no_epsilon_severe_tie(self):
        rows=generated(6,kind="flat")
        for r in rows:
            if r["period"]==1:r["bill_proxy_return"]=-.25
        out=tables(rows,mode="bills_keep",horizons=(5,6))
        for r in out.scenario_metrics:
            self.assertEqual((r["drawdown_peak_year"],r["drawdown_peak_kind"],r["drawdown_trough_year"],r["drawdown_trough_kind"]),(0,"initial",1,"end"))
        self.assertTrue(all(r["severe_scenario_id"]==1 for r in out.summary))
        rows[18]["bill_proxy_return"]=-.250000000001
        changed=tables(rows,mode="bills_keep",horizons=(5,6))
        self.assertTrue(all(r["severe_scenario_id"]==4 for r in changed.summary))
        for case in self.cases.values():
            for metric in case.scenario_metrics:
                peak=100.;loss=0.;pa=sp=st=(0,"initial")
                for e in case.annual_ledgers:
                    if e["scenario_id"]!=metric["scenario_id"] or e["period"]>metric["horizon"]:continue
                    for kind,v in (("post_fee",e["real_wealth_after_fee"]),("end",e["real_wealth_end"])):
                        if v>peak:peak=v;pa=(e["period"],kind)
                        if 1-v/peak>loss:loss=1-v/peak;sp=pa;st=(e["period"],kind)
                self.assertEqual((metric["drawdown_peak_year"],metric["drawdown_peak_kind"],metric["drawdown_trough_year"],metric["drawdown_trough_kind"]),(*sp,*st))

    def test_rational_initial_fee_and_growth(self):
        rows=generated(2,kind="flat")
        for r in rows:r.update(equity_return=.125,bond_return=.125,bill_proxy_return=.125,inflation=.0625)
        out=tables(rows,mode="equal_weight_buy_hold",horizons=(1,2))
        e=out.annual_ledgers[0]
        self.close(e["intended_transfer"],200/3);self.close(e["fee"],1/6)
        self.close(e["wealth_after_fee"],599/6)
        for asset in ("equity","bond","bill_proxy"):self.close(e["holdings_after_fee_"+asset],599/18)
        r=out.scenario_metrics[1]
        want=F(599,6)*(F(18,17)**2)
        self.close(r["terminal_real_wealth"],float(want))
        self.close(r["net_real_cagr_pct"],100*((float(want)/100)**.5-1))
        self.assertIsNone(out.summary[0]["median_volatility_pct"])
        self.assertIsNone(out.summary[0]["pooled_trade_share_ex_initial_pct"])

    def test_prefix_direct_runs_and_future_perturbations(self):
        for m in MODES:
            out=self.cases[m,.0025]
            for h in (5,6,15,25,30):
                prefix=tables(self.rows,self.cal,m,horizons=(h,))
                self.assertEqual(prefix.annual_ledgers,tuple(r for r in out.annual_ledgers if r["period"]<=h))
                self.assertEqual(prefix.scenario_metrics,tuple(r for r in out.scenario_metrics if r["horizon"]==h))
                self.assertEqual(prefix.decisions,tuple(r for r in out.decisions if r["period"]<=h))
                for s in range(1,5):
                    callback=CostAwarePolicy(m,self.cal.folds[s-1].prior) if m in CENTRAL_TARGET else POLICIES[m]
                    direct=simulate_policy(self.rows[(s-1)*30:s*30],horizon=h,split="synthetic",callback=callback)
                    self.close(direct.metrics.net_real_cagr_pct,next(r["net_real_cagr_pct"] for r in prefix.scenario_metrics if r["scenario_id"]==s))
                    self.assertEqual([e.decision.action for e in direct.ledger],[r["engine_action"] for r in prefix.annual_ledgers if r["scenario_id"]==s])
            altered=copy.deepcopy(self.rows)
            for r in altered:
                if r["period"]>=7:r.update(equity_return=-.5,bond_return=-.25,bill_proxy_return=-.125,inflation=.125)
            changed=tables(altered,self.cal,m)
            self.assertEqual([r for r in out.decisions if r["period"]<=7],[r for r in changed.decisions if r["period"]<=7])
            self.assertEqual([r for r in out.annual_ledgers if r["period"]<7],[r for r in changed.annual_ledgers if r["period"]<7])

    def test_context_history_mass_and_independent_scalar_ce(self):
        for m in CENTRAL_TARGET:
            out=self.cases[m,.0025]
            for d in out.decisions:
                n=min(5,d["period"]-1) if m in ("balanced_context","balanced_adaptive") else 0
                self.assertEqual(d["recent_count"],n);self.close(d["prior_mass"],15/(15+n))
                if d["scenario_id"]!=1 or d["period"]>6:continue
                e=out.annual_ledgers[d["period"]-1];W=sum(F(e["holdings_before_"+a]) for a in ("equity","bond","bill_proxy"))
                w=[F(e["holdings_before_"+a])/W for a in ("equity","bond","bill_proxy")]
                prior=self.cal.folds[0].prior.gross
                moment=15*sum(1/sum(a*F(g) for a,g in zip(w,row))**3 for row in prior)/len(prior)
                for r in self.rows[max(0,d["period"]-1-n):d["period"]-1]:
                    gross=[(1+F(r[key]))/(1+F(r["inflation"])) for key in FIELDS[2:5]]
                    moment+=1/sum(a*g for a,g in zip(w,gross))**3
                self.close(d["ce_keep"],float(moment/(15+n))**(-1/3))

    def test_review_lag_nulls_and_prefix_no_future_latch(self):
        rows=generated(8,kind="flat")
        for r in rows:
            if r["period"]==1:r.update(equity_return=-.5,bond_return=-.5,bill_proxy_return=-.5)
        cal=calibrate(rows,((1.,1.,1.),))
        for m in CENTRAL_TARGET:
            out=tables(rows,cal,m,horizons=(1,2,8))
            for d in out.decisions:
                if d["period"]==1:self.assertFalse(d["human_review_latched"])
                else:
                    self.assertEqual(d["action"],"human_review");self.assertIsNone(d["ce_keep"])
                    self.assertIsNone(d["proposed_target"]);self.assertIsNone(d["selected_target"])
                    self.assertEqual(d["actual_fee"],0)
            self.assertTrue(all(r["period"]==1 for r in out.target_scores))
            for r in out.scenario_metrics:
                self.assertEqual(r["first_latch_year"],None if r["horizon"]==1 else 2)
                self.assertEqual(r["human_review_count"],r["horizon"]-1)
        for m in POLICIES:
            out=tables(rows,cal,m,horizons=(1,8))
            self.assertFalse(out.decisions);self.assertFalse(out.target_scores)
            for r in out.scenario_metrics:
                for key in ("human_review_count","human_review_share_pct","first_latch_year","target_change_count","first_deployment_year","initial_allocation_deferred"):
                    self.assertIsNone(r[key])
            self.assertTrue(all(r["pooled_human_review_count"] is None for r in out.summary))

    def test_deferred_persistence_and_prefix_deployment(self):
        rows=generated(8,kind="flat")
        for r in rows:
            if r["period"]==1:r.update(equity_return=1.,bond_return=.25)
        out=tables(rows,calibrate(rows,((1.,1.,1.),)),horizons=(1,2,8))
        for r in out.scenario_metrics:
            self.assertTrue(r["initial_allocation_deferred"])
            self.assertEqual(r["first_deployment_year"],None if r["horizon"]==1 else 2)

    def test_real_tiny_executed_target_change(self):
        rows=generated(8,kind="flat")
        for r in rows:
            if r["period"]==1:
                for key in FIELDS[2:]:r[key]=-1+1e-13
        out=tables(rows,calibrate(rows,((1.3,1.02,1.),)),horizons=(5,6,8))
        d=out.decisions[5];e=out.annual_ledgers[5]
        self.assertEqual(d["action"],"target_change");self.assertTrue(d["executed_target_change"])
        self.assertFalse(d["is_trade"]);self.assertGreater(e["intended_transfer"],0)
        self.assertLess(e["intended_transfer"],1e-10)
        self.assertGreater(e["fee"],0);self.assertEqual(e["fee"],.0025*e["intended_transfer"])
        self.assertEqual(out.scenario_metrics[1]["target_change_count"],1)
        self.assertEqual(out.scenario_metrics[1]["trade_count"],1)
        self.assertEqual(out.scenario_metrics[1]["trade_count"],out.scenario_metrics[0]["trade_count"])
        self.assertEqual(out.scenario_metrics[0]["target_change_count"],0)
        self.assertEqual(out.decisions[6]["active_before"],"growth_tilt")

    def test_calibration_membership_and_actual_prior_shape_rejections(self):
        c=self.cal.folds[0]
        bads=[replace(c,fold=1),replace(c,fold=False),replace(c,training_ids=c.training_ids[:-1]),
              replace(c,evaluation_ids=(1,2)),replace(c,training_ids=(1,2,3)),
              replace(c,training_keys=c.training_keys[:-1]),replace(c,training_keys=tuple(reversed(c.training_keys))),
              replace(c,prior=EmpiricalPrior(((1.,1.,1.),))),replace(c,real_gross_sha256="x")]
        for bad in bads:
            with self.assertRaises(ValueError):tables(self.rows,replace(self.cal,folds=(bad,*self.cal.folds[1:])))
        with self.assertRaises(ValueError):tables(self.rows,replace(self.cal,periods=29))
        with self.assertRaises(ValueError):tables(self.rows,self.cal.folds[::-1])
        self.assertEqual(tables(self.rows,self.cal.folds),self.cases["balanced_adaptive",.0025])

    def test_schema_keys_factors_horizons_and_splits_rejected(self):
        for change in (lambda r:r.pop("inflation"),lambda r:r.update(extra=1),
                       lambda r:r.update(period=2),lambda r:r.update(scenario_id=True),
                       lambda r:r.update(equity_return=True),lambda r:r.update(inflation=-1),
                       lambda r:r.update(bond_return=float("nan")),lambda r:r.update(bill_proxy_return=float("inf")),
                       lambda r:r.update(equity_return=1e308,inflation=math.nextafter(-1.,0.))):
            data=copy.deepcopy(self.rows);change(data[-1])
            with self.assertRaises(ValueError):tables(data,self.cal,horizons=(5,))
        for data in (self.rows[:-1],self.rows[::-1],self.rows[30:],self.rows+[self.rows[-1]]):
            with self.assertRaises(ValueError):tables(data,self.cal)
        for hs in ((),(5,5),(0,),(31,),(True,),(5.,)):
            with self.assertRaises(ValueError):tables(self.rows,self.cal,horizons=hs)
        for mode in ("unknown",None):
            with self.assertRaises(ValueError):tables(self.rows,self.cal,mode)
        for fee in (-1,.001,.5,float("nan"),float("inf"),True):
            with self.assertRaises(ValueError):tables(self.rows,self.cal,fee=fee)
        for split in ("final","raw",None):
            with self.assertRaises(ValueError):build_case_tables(self.rows,calibrations=self.cal,mode="balanced_cost",fee_rate=.0025,split=split)

    def test_refusal_before_computation_and_true_split_guard(self):
        for m in POLICIES:
            with patch('safeinvest.policy_cases.simulate_policy',side_effect=AssertionError("must not compute")) as engine:
                with self.assertRaisesRegex(ValueError,"HY3-003"):
                    build_case_tables(None,calibrations=None,mode=m,fee_rate=.0025,split="development")
                engine.assert_not_called()
        rows=generated(30,120,kind="flat"); cal=calibrate(rows)
        class StopProbe(Exception):pass
        def probe(selected,**kwargs):
            self.assertEqual(kwargs["split"],"development");self.assertEqual(len(selected),30)
            self.assertIsInstance(kwargs["callback"],CostAwarePolicy)
            raise StopProbe()
        with patch('safeinvest.policy_cases.simulate_policy',side_effect=probe):
            with self.assertRaises(StopProbe):build_case_tables(rows,calibrations=cal,mode="balanced_cost",fee_rate=.0025,split="development")
        for m in POLICIES:
            def baseline_probe(selected, **kwargs):
                self.assertEqual(kwargs["split"],"development")
                self.assertEqual(kwargs["fee_rate"],.005)
                self.assertIs(kwargs["callback"],POLICIES[m])
                raise StopProbe()
            with patch('safeinvest.policy_cases.simulate_policy',side_effect=baseline_probe):
                with self.assertRaises(StopProbe):build_case_tables(rows,calibrations=cal,mode=m,fee_rate=.005,split="development")
        # Full-shape generated values only; probes abort before outcome computation.
        with self.assertRaises(ValueError):build_case_tables(self.rows,calibrations=self.cal,mode="balanced_cost",fee_rate=.0025,split="development")
        with self.assertRaises(ValueError):build_case_tables(rows,calibrations=cal,mode="balanced_cost",fee_rate=0,split="development")

    def test_once_at_max_horizon_and_distinct_callbacks(self):
        callbacks=[]
        def spy(selected,**kwargs):
            self.assertEqual(kwargs["horizon"],30)
            self.assertEqual(kwargs["split"],"synthetic")
            callbacks.append(kwargs["callback"])
            return simulate_policy(selected,**kwargs)
        with patch('safeinvest.policy_cases.simulate_policy',side_effect=spy) as engine:
            tables(self.rows,self.cal)
            self.assertEqual(engine.call_count,4)
        self.assertEqual(len({id(c) for c in callbacks}),4)
        self.assertTrue(all(len(c.reviews)==30 for c in callbacks))

    def test_aliases_mutation_fresh_state_and_no_io(self):
        data=copy.deepcopy(self.rows);cal=calibrate(data);before=copy.deepcopy(data);manifest=cal.manifest()
        with patch('builtins.open',side_effect=AssertionError("pure API cannot open files")):
            out=tables(data,cal)
        self.assertEqual(data,before);self.assertEqual(cal.manifest(),manifest)
        data[0]["equity_return"]=999
        out.annual_ledgers[0]["fee"]=999;out.metadata["split"]="changed";out.counts["decisions"]=0
        fresh=tables(self.rows,cal)
        self.assertEqual(fresh,self.cases["balanced_adaptive",.0025])
        for r in fresh.decisions:
            if r["period"]==1:
                self.assertEqual(r["recent_count"],0);self.assertFalse(r["human_review_latched"])
                self.assertEqual(r["active_before"],"balanced")


if __name__ == "__main__":unittest.main()
