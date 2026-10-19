"""Accept exact SOL-024 final design review, not final execution or code."""
from datetime import datetime, timezone
from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
from verify_canonical_receipt import verify

ROOT=Path(__file__).resolve().parents[2]
COMMIT='b1de55ec16f7b67884415637f562fcdf446034c7'


def snapshot(folder):
    return {str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file()}


def main():
    assert sys.version_info[:2]==(3,12)
    info=verify('SOL-024',COMMIT)
    work=ROOT/'.runtime/review-SOL-024'
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=work).decode().strip()==COMMIT
    out=work/'audit/SOL-024'; before=snapshot(out)
    saved=json.loads((out/'verification.json').read_bytes())
    facts=saved['evidence']['references']
    findings=json.loads((out/'findings.json').read_bytes())
    assert findings['design_verdict']=='approve' and findings['implementation_verdict']=='not_reviewed'
    assert findings['blockers']==[] and findings['execution_authorized'] is False
    assert len(facts)==14
    scratch=ROOT/'.runtime/review-SOL-024-chief-corrupt'
    scratch.mkdir(exist_ok=False)
    replay=[]
    cases=[(out,0)]
    for name in ['denominator','freeze-digest']:
        folder=scratch/name;shutil.copytree(out,folder)
        altered=json.loads((folder/'verification.json').read_bytes())
        if name=='denominator':
            altered['evidence']['references']['personalized']['all']['rows'][0]['denominator']=120
        else:
            altered['evidence']['references']['freeze_text_hashes']['base']['runner']='0'*64
        (folder/'verification.json').write_text(json.dumps(altered),encoding='utf-8')
        cases.append((folder,1))
    for folder,expected in cases:
        original=snapshot(folder)
        result=subprocess.run([sys.executable,'-B',str(out/'verify.py'),'--check','--evidence-dir',str(folder)],cwd=work,capture_output=True,text=True,timeout=120)
        replay.append(dict(evidence=folder.name,expected_exit=expected,exit_code=result.returncode,stdout=result.stdout.strip(),stderr=result.stderr.strip()))
        assert result.returncode==expected,replay[-1]
        assert original==snapshot(folder)
    assert before==snapshot(out)
    # Independent cardinality formulas, with own H rather than a shared H30.
    generic=dict(cases=16,scenarios_per_case=60,scenario_paths=8*2*60,annual_ledger_rows=8*2*60*30,scenario_horizon_metrics=8*2*60*5,comparison_summaries=10*2*5,paired_rows=10*2*5*60)
    assert facts['generic_counts']==generic
    hs=[5,15,30,25,6]
    assert facts['personalized']['all']['ledger_rows']==60*2*sum(hs)==9720
    assert facts['personalized']['all']['metrics']==60*2*len(hs)==600
    assert facts['personalized']['partial']['ledger_rows']==60*(5+15+25)==2700
    assert facts['personalized']['none']['ledger_rows']==0
    assert all(row['denominator']==0 and row['p90_loss'] is None and row['risk_pass'] is None for row in facts['personalized']['none']['rows'])
    rank=F(9,10)*59
    assert rank==F(531,10) # Interpolates sorted indices 53 and 54, both equal to tolerance.
    assert facts['screens']['p90_boundary']=='10' and facts['screens']['strict_exceedances']==5
    assert F(facts['screens']['fraction'])==F(5,60)
    # Brute-force all peak/trough pairs on scalar events; independent of running-max scan.
    values=[100.,99.75,100.,100.,75.,75.,100.,100.,75.]
    labels=[(0,'initial'),(1,'post_fee'),(1,'end'),(2,'post_fee'),(2,'end'),(3,'post_fee'),(3,'end'),(4,'post_fee'),(4,'end')]
    pairs=[(1-values[j]/values[i],j,i) for j in range(len(values)) for i in range(j+1)]
    loss,j,i=sorted(pairs,key=lambda p:(-p[0],p[1],p[2]))[0]
    assert (loss,labels[i],labels[j])==(.25,(0,'initial'),(2,'end'))
    assert facts['severe']['earliest']==dict(loss=loss,peak=list(labels[i]),trough=list(labels[j]))
    nearby={121:.25,122:math.nextafter(.25,math.inf)}
    assert sorted(nearby,key=lambda sid:(-nearby[sid],sid))[0]==facts['severe']['near_tie_id']==122
    assert facts['severe']['exact_tie_id']==121 and facts['severe']['post_fee']['trough']==[1,'post_fee']
    # Independent hash derivation on fake texts; never create an actual freeze file.
    raw=b'{"z": 1, "a": 2}'
    digest=hashlib.sha256(raw).hexdigest()
    assert facts['freeze_text_hashes']['base']['runner']==digest
    assert hashlib.sha256((' \n\t'+raw.decode()+'\r\n ').strip().encode()).hexdigest()==digest
    assert hashlib.sha256(json.dumps(json.loads(raw),sort_keys=True,separators=(',',':')).encode()).hexdigest()!=digest
    assert [item['status'] for item in facts['screens']['cases']]==['frozen_rule_supported_on_final_sample']+['final_validation_failed_human_review']*3
    # Chief reference evidence must also fail closed without repairing a corruption.
    reference=ROOT/'audit/chief/analysis-reference.json';original=reference.read_bytes()
    altered=json.loads(original);altered['facts']['zero_fold_excluded']['positive_fold_count']=4
    bad=scratch/'analysis-reference-wrong-fold.json';bad.write_text(json.dumps(altered),encoding='utf-8')
    bad_before=bad.read_bytes()
    result=subprocess.run([sys.executable,'-B',str(ROOT/'audit/chief/analysis_reference.py'),'--check','--evidence',str(bad)],cwd=ROOT,capture_output=True,text=True,timeout=30)
    assert result.returncode!=0 and reference.read_bytes()==original and bad.read_bytes()==bad_before
    info.update(schema_version=1,checked_at=datetime.now(timezone.utc).isoformat(),decision='accept_final_protocol_design_review',design_verdict='approve',implementation_verdict='not_reviewed',reference_groups=14,replay_checks=replay,audit_files_unchanged=True,
        chief_independent_checks=dict(generic_counts=generic,all_personalized_ledgers=9720,all_personalized_metrics=600,partial_personalized_ledgers=2700,none_personalized_ledgers=0,strict_exceedances='5/60',severe_bruteforce_earliest=[list(labels[i]),list(labels[j])],adjacent_float_severe_id=122,fake_freeze_digest=digest),
        chief_analysis_reference=dict(path='audit/chief/analysis-reference.json',reference_groups=8,corruption_rejected=True,implementation_executed=False),
        implementation_requirements=[item['id'] for item in findings['implementation_requirements']],
        preserved_history='All SOL-024 failed audit trials, interrupted wrapper and superseded complete audit evidence retained unchanged.',
        limitations=['Design approval only. Actual development selection, refit, final-capable source, freeze and final execution still require independent acceptance.','Historical kernel verdict in pinned review remains changes_required; later SOL-021 approval remains a separate exact receipt.','Freeze audit belongs in an external later attestation; corrections need explicit source deviation binding to original freeze.'],
        competition_outcomes_read=False,policy_helpers_executed=False,final_data_open=False)
    with (ROOT/'audit/chief/SOL-024-review.json').open('x',encoding='utf-8',newline='\n') as file:
        json.dump(info,file,indent=2);file.write('\n')
    print(json.dumps(dict(reviewed_commit=COMMIT,design='approve',implementation='not_reviewed',reference_groups=14,worker_corruptions_rejected=2,chief_reference_corruption_rejected=True,read_only=True)))


if __name__=='__main__':main()
