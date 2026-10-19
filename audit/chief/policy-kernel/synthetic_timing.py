"""Small generated-data timing probe, never a strategy-performance experiment."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from safeinvest.policy_pilot import EmpiricalPrior, simulate_synthetic

SOURCE_COMMIT = '6152ef118457ea1d4225f873539b5a27d303dcf3'
SOURCE_PATHS = ('src/safeinvest/policy_pilot.py', 'src/safeinvest/backtest.py',
                'src/safeinvest/accounting.py', 'src/safeinvest/metrics.py')


def run():
    sources = {}
    for name in SOURCE_PATHS:
        blob = subprocess.check_output(['git','show',SOURCE_COMMIT+':'+name],cwd=ROOT)
        assert (ROOT/name).read_bytes().replace(b'\r\n',b'\n') == blob
        sources[name] = hashlib.sha256(blob).hexdigest()
    gross = tuple((1.08+((i*7)%11)/1000, 1.02+((i*3)%7)/2000, 1.005+(i%3)/10000)
                  for i in range(2700))
    data = [dict(scenario_id=1,period=t,equity_return=0.,bond_return=0.,
                 bill_proxy_return=0.,inflation=0.) for t in range(1,31)]
    prior = EmpiricalPrior(gross)
    timings = []
    for mode in ('conservative_cost','balanced_cost','growth_cost','balanced_context','balanced_adaptive'):
        for fee in (.0025,.005):
            start, cpu = time.perf_counter(), time.process_time()
            result, reviews = simulate_synthetic(data,mode=mode,prior=prior,horizon=30,fee_rate=fee)
            wall, used_cpu = time.perf_counter()-start, time.process_time()-cpu
            assert len(result.ledger) == len(reviews) == 30
            assert all(entry.fee == review.actual_fee and entry.intended_transfer == review.intended_transfer
                       for entry,review in zip(result.ledger,reviews))
            encoded = ('\n'.join(json.dumps(asdict(row),separators=(',',':'),allow_nan=False)
                                  for row in reviews)+'\n').encode()
            timings.append(dict(mode=mode,fee_rate=fee,elapsed_seconds=wall,cpu_seconds=used_cpu,
                                reviews=30,score_rows=sum(len(r.scores) for r in reviews),
                                diagnostic_jsonl_bytes=len(encoded),diagnostic_sha256=hashlib.sha256(encoded).hexdigest()))
    return dict(scope='Generated synthetic timing only; no strategy-performance or runtime guarantee',
                python=platform.python_version(),source_commit=SOURCE_COMMIT,source_sha256=sources,
                generator_sha256_lf=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
                synthetic_prior_rows=len(gross),synthetic_scenario_years=len(data),timings=timings,
                total_elapsed_seconds=sum(row['elapsed_seconds'] for row in timings),
                projected_120_paths_seconds=sum(row['elapsed_seconds'] for row in timings)*120,
                projection_caveat='Linear extrapolation of only decision kernel for 5 modes x 2 fees, 120 paths each; excludes IO, calibration, reports, checks, machine variation and baseline references.',
                maximum_projected_jsonl_bytes_per_mode_fee=max(row['diagnostic_jsonl_bytes'] for row in timings)*120,
                final_data_accessed=False,competition_outcomes_computed=False)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    output=Path(args.output)
    if output.exists():
        raise FileExistsError('Preserve timing observations; choose a new output.')
    result=run()
    output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:result[k] for k in ('total_elapsed_seconds','projected_120_paths_seconds',
                     'maximum_projected_jsonl_bytes_per_mode_fee','final_data_accessed')}))

if __name__=='__main__':
    main()
