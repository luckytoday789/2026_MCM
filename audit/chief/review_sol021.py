"""Chief acceptance of exact SOL-021 K2 closure; no competition data."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from verify_canonical_receipt import verify
from kernel_rounding_certificate import run as independent_cells

ROOT=Path(__file__).resolve().parents[2]
COMMIT='d154f90d1c50b37990b75ec0a45aa01a38252343'

def main():
    info=verify('SOL-021',COMMIT)
    work=ROOT/'.runtime/review-SOL-021'
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=work).decode().strip()==COMMIT
    out=work/'audit/SOL-021'
    snapshot=lambda:{str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()}
    before=snapshot()
    evidence=json.loads((out/'verification.json').read_bytes())
    facts=evidence['facts']
    assert facts['code_verdict']=='approve' and facts['failures']==[]
    assert facts['check_count']==len(facts['checks'])==3720
    assert all(c['passed'] for c in facts['checks'])
    assert facts['grid_count']==2048 and facts['grid_failed_count']==0
    scratch=ROOT/'.runtime/review-SOL-021-corrupt'
    scratch.mkdir(exist_ok=False)
    bad=json.loads(json.dumps(evidence))
    case=next(c for c in bad['facts']['checks'] if c['name']=='K2 exact midpoint n=0')
    case['observed']+=float.fromhex('0x0.0000000000001p-1022')
    (scratch/'wrong-midpoint.json').write_text(json.dumps(bad),encoding='utf-8')
    bad=json.loads(json.dumps(evidence))
    bad['facts']['imported_code']['src/safeinvest/policy_pilot.py']['sha256']='0'*64
    (scratch/'wrong-import.json').write_text(json.dumps(bad),encoding='utf-8')
    replay=[]
    for path,expected in [(out/'verification.json',0),(scratch/'wrong-midpoint.json',1),(scratch/'wrong-import.json',1)]:
        prior=hashlib.sha256(path.read_bytes()).hexdigest();started=time.perf_counter()
        result=subprocess.run([sys.executable,'-B',str(out/'verify.py'),'--check','--evidence',str(path)],cwd=work,capture_output=True,text=True,timeout=180)
        replay.append(dict(evidence=path.name,expected_exit=expected,exit_code=result.returncode,stdout=result.stdout.strip(),stderr=result.stderr.strip(),seconds=time.perf_counter()-started))
        assert result.returncode==expected,replay[-1]
        assert hashlib.sha256(path.read_bytes()).hexdigest()==prior
    assert snapshot()==before
    certificate=independent_cells(work)
    assert certificate==json.loads((ROOT/'audit/chief/kernel-rounding-certificates.json').read_bytes())
    info.update(schema_version=1,checked_at=datetime.now(timezone.utc).isoformat(),decision='accept_kernel_review',code_verdict='approve',k2_status='closed',replay_checks=replay,audit_files_unchanged=True,independent_check_count=3720,rational_grid_count=2048,failed_comparison_count=0,chief_independent_rounding_cells=42,chief_incorrect_neighbor_rejections=84,chief_rational_fixture=certificate['ordinary_rational_fixture'],chief_oracle='audit/chief/kernel_rounding_certificate.py',chief_oracle_evidence='audit/chief/kernel-rounding-certificates.json',preserved_chief_audit_error='audit/chief/kernel-rounding-history/trial-001-failure.json',final_data_open=False,production_policy_execution_approved=False,limitations=['Kernel synthetic review only; calibration, case, analysis, writer and actual results need their own acceptance.','Ordinary log route checked at declared relative tolerances, not claimed correctly rounded.','Historical SOL-013/SOL-017 negatives and all worker/chief audit-tool failures preserved.'])
    with (ROOT/'audit/chief/SOL-021-review.json').open('x',encoding='utf-8',newline='\n') as file:
        json.dump(info,file,indent=2);file.write('\n')
    print(json.dumps(dict(reviewed_commit=COMMIT,code_verdict='approve',checks=3720,grid=2048,chief_cells=42,corruptions_rejected=2,read_only=True)))

if __name__=='__main__': main()
