"""Chief acceptance of exact SOL-020 personalized design evidence, not code."""
from datetime import datetime,timezone
from fractions import Fraction as F
import hashlib,json,math,shutil,subprocess,sys
from pathlib import Path
from verify_canonical_receipt import verify
ROOT=Path(__file__).resolve().parents[2]
COMMIT='2fbd4598606b41a786bd931046adb0ecc8b42d78'

def main():
    assert sys.version_info[:2]==(3,12)
    info=verify('SOL-020',COMMIT)
    work=ROOT/'.runtime/review-SOL-020';out=work/'audit/SOL-020'
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=work).decode().strip()==COMMIT
    snapshot=lambda d:{str(p.relative_to(d)):hashlib.sha256(p.read_bytes()).hexdigest() for p in d.rglob('*') if p.is_file()}
    before=snapshot(out)
    saved=json.loads((out/'verification.json').read_bytes())
    scratch=ROOT/'.runtime/review-SOL-020-corrupt-exceedances'
    shutil.copytree(out,scratch)
    bad=json.loads(json.dumps(saved));bad['reference_facts']['p90_with_exceedances']['exceedance_count']=0
    (scratch/'verification.json').write_text(json.dumps(bad),encoding='utf-8')
    corrupt_before=snapshot(scratch);replays=[]
    for folder,expected in ((out,0),(scratch,1)):
        r=subprocess.run([sys.executable,'-B',str(out/'verify.py'),'--check','--evidence-dir',str(folder)],cwd=work,capture_output=True,text=True,timeout=120)
        replays.append(dict(evidence=folder.name,expected_exit=expected,exit_code=r.returncode,stdout=r.stdout.strip(),stderr=r.stderr.strip()))
        assert r.returncode==expected,replays[-1]
    assert snapshot(out)==before and snapshot(scratch)==corrupt_before
    facts=json.loads((out/'findings.json').read_bytes())
    assert facts['design_verdict']=='approve' and facts['implementation_verdict']=='not_reviewed' and facts['blockers']==[]
    # Chief scalar checks use locked arithmetic without worker reference helpers.
    values=[F(10)]*110+[F(20)]*10
    rank=F(9,10)*(len(values)-1);lo=rank.numerator//rank.denominator
    p90=values[lo]+(rank-lo)*(values[lo+1]-values[lo])
    assert p90==10 and sum(v>10 for v in values)==10
    fee=F(100)*F(1,400);post=100-fee;loss=100*(1-post/100)
    assert fee==F(1,4) and loss==F(1,4) and post*F(4,3)==133
    kept=(F(20),F(30),F(50));end=tuple(h*g for h,g in zip(kept,(F(1,2),F(6,5),F(1))))
    assert sum(end)/F(5,4)==F(384,5)
    assert F(100)/F(4,3)==75
    horizons=[5,15,30,25,6]
    counts={'all_ledger':120*2*sum(horizons),'all_metrics':120*2*len(horizons),'partial_ledger':120*(5+15+25),'partial_metrics':120*3}
    assert counts==dict(all_ledger=19440,all_metrics=1200,partial_ledger=5400,partial_metrics=360)
    annual=[F(0)]*14+[F(-25)];mean=sum(annual)/15;variance=sum((v-mean)**2 for v in annual)/14
    assert variance==F(125,3)
    assert saved['reference_facts']['B_prefix']['prefix_first_latch'] is None and saved['reference_facts']['B_prefix']['full_first_latch']==16
    info.update(schema_version=1,checked_at=datetime.now(timezone.utc).isoformat(),decision='accept_design_review_evidence',design_verdict='approve',implementation_verdict='not_reviewed',replay_checks=replays,audit_files_unchanged=True,corrupt_files_unchanged=True,reference_groups=len(saved['reference_facts']),chief_independent_fixtures=dict(p90=str(p90),strict_exceedances=10,initial_fee=str(fee),post_fee=str(post),pending_real_end=str(F(384,5)),B_sample_variance=str(variance),counts=counts),implementation_requirements=['not-run personalized denominator=0 with null outcomes and screen flags; never compute 0/0','bind actual accepted assignment/refit/source hashes, never drafting commit as execution pin','retain generic Balanced same-primary-mode robustness independently from fee-specific profile counterfactuals'],final_data_open=False,competition_outcomes_read=False,note='Targeted personalized design approved only. K1/K2 history, implementation, actual development and final gates remain separate.')
    with (ROOT/'audit/chief/SOL-020-review.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(info,f,indent=2);f.write('\n')
    print(json.dumps({'reviewed_commit':COMMIT,'design':'approve','implementation':'not_reviewed','reference_groups':info['reference_groups'],'corruption_rejected':True,'read_only':True}))
if __name__=='__main__':main()
