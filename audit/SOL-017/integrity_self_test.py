"""Create isolated corruption challenges; never repairs or modifies real evidence.

Run once before verify.py --create. All copied/mutated evidence is preserved in
ignored .runtime/sol017/integrity; the report itself uses exclusive creation.
"""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'audit/SOL-017'
spec=importlib.util.spec_from_file_location('sol017_verifier',OUT/'verify.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
SCRATCH=ROOT/'.runtime/sol017/integrity'

def all_hashes(directory):
 return {p.relative_to(directory).as_posix():v.digest(p.read_bytes()) for p in sorted(directory.rglob('*')) if p.is_file()}

def check_case(name,directory,want):
 before=all_hashes(directory)
 proc=subprocess.run([sys.executable,'-B',str(OUT/'verify.py'),'--check','--evidence',str(directory/'verification.json'),'--artifact-dir',str(directory)],cwd=ROOT,text=True,capture_output=True)
 after=all_hashes(directory)
 return dict(name=name,expected_exit=want,observed_exit=proc.returncode,read_only=before==after,
             passed=proc.returncode==want and before==after,stdout=proc.stdout,stderr=proc.stderr,
             before_sha256=before,after_sha256=after)

def main():
 if SCRATCH.exists(): raise RuntimeError('Scratch exists; preserve prior evidence and do not overwrite')
 SCRATCH.mkdir(parents=True)
 baseline=SCRATCH/'baseline';shutil.copytree(OUT,baseline)
 facts=v.collect()
 v.write_exclusive(baseline/'findings.json',v.dump(v.findings(facts)))
 v.write_exclusive(baseline/'review.md',v.review_text(facts))
 v.write_exclusive(baseline/'verification.json',v.dump(dict(facts=facts,artifact_sha256=v.hashes(baseline))))
 reports=[check_case('uncorrupted negative code verdict is valid evidence',baseline,0)]
 for name in ('minimum-subnormal-to-zero','tiny-fee-to-zero','saved-import-hash','saved-task-hash','review-artifact','verifier-artifact'):
  target=SCRATCH/name;shutil.copytree(baseline,target)
  evidence=target/'verification.json';saved=json.loads(evidence.read_text())
  if name=='minimum-subnormal-to-zero':
   item=next(c for c in saved['facts']['checks'] if c['name'].startswith('constant w=0 scale=0x0.0000000000001p-1022 n=0'))
   item['observed']=0.
  elif name=='tiny-fee-to-zero':
   item=next(c for c in saved['facts']['checks'] if c['name']=='REAL tiny independent fee');item['observed']=0.
  elif name=='saved-import-hash': saved['facts']['imported_code_sha256']['src/safeinvest/policy_pilot.py']='0'*64
  elif name=='saved-task-hash': saved['facts']['immutable_task_sha256']='0'*64
  elif name=='review-artifact':
   with (target/'review.md').open('a',encoding='utf-8') as handle: handle.write('\nCORRUPTED\n')
  else:
   with (target/'verify.py').open('a',encoding='utf-8') as handle: handle.write('\n# CORRUPTED\n')
  if name not in ('review-artifact','verifier-artifact'): evidence.write_text(v.dump(saved),encoding='utf-8',newline='\n')
  reports.append(check_case(name,target,1))
 # Challenge the actual imported-byte pin boundary before code can execute.
 original=v.blob
 def corrupt_blob(commit,path):
  data=original(commit,path)
  return data+b'\n# corrupted scratch import\n' if commit==v.BASE and path=='src/safeinvest/policy_pilot.py' else data
 v.blob=corrupt_blob
 try: v.boundaries()
 except RuntimeError as exc: rejected='Pinned source mismatch' in str(exc);message=str(exc)
 else: rejected=False;message='UNEXPECTED ACCEPTANCE'
 finally: v.blob=original
 reports.append(dict(name='corrupt compiled-source boundary',passed=rejected,diagnosis=message,read_only=True))
 sentinel=SCRATCH/'exclusive-sentinel.txt';sentinel.write_text('preserve',encoding='utf-8')
 try: v.write_exclusive(sentinel,'overwrite')
 except FileExistsError: refused=sentinel.read_text()=='preserve'
 else: refused=False
 reports.append(dict(name='exclusive creation refuses existing evidence',passed=refused,read_only=refused))
 result=dict(schema_version=1,task_id='SOL-017',python_major_minor='3.12',
             source_commit=v.BASE,all_passed=all(r['passed'] for r in reports),tests=reports,
             head_policy='No check consults HEAD; all source/task reads use explicit immutable commits. No branch or ref was modified.',
             mutation_scope='Isolated ignored scratch copies only; each before/after hash includes verification.json. No repair or cleanup.')
 v.write_exclusive(OUT/'integrity-self-tests.json',v.dump(result))
 print(json.dumps(dict(all_passed=result['all_passed'],test_count=len(reports))))
 if not result['all_passed']: raise SystemExit(1)

if __name__=='__main__': main()
