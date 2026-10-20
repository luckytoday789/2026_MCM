"""Exact failed SOL-038 delivery review; no acceptance or competition input."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
COMMIT="e1783a918122d8eaa507e42ca15a9c0a5f5b9339"
def git(*args):return subprocess.check_output(["git",*args],cwd=ROOT)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def main():
 task=json.loads((ROOT/"ops/tasks/SOL-038.json").read_bytes())
 queue=json.loads((ROOT/"ops/queue.json").read_bytes())
 q=next(x for x in queue["tasks"] if x["id"]=="SOL-038")
 receipt_raw=git("show",COMMIT+":handoff/SOL-038/result.json");r=json.loads(receipt_raw)
 recovery_raw=git("show",COMMIT+":handoff/SOL-038/recovery.json");rec=json.loads(recovery_raw)
 digest=sha(json.dumps(task,sort_keys=True,separators=(",",":")).encode())
 assert q["task_sha256"]==r["task_sha256"]==rec["task_sha256"]==digest
 assert (r["task_id"],r["role"],r["attempt"],r["base_commit"])==("SOL-038","sol",1,task["base_commit"])
 assert r["status"]=="failed" and r["checks"]==[] and r["artifact_hash_basis"]=="canonical_git_blob"
 assert r["task_parameters"]==task["parameters"]
 subprocess.run(["git","merge-base","--is-ancestor",task["base_commit"],COMMIT],cwd=ROOT,check=True)
 subprocess.run(["git","merge-base","--is-ancestor",task["base_commit"],"origin/main"],cwd=ROOT,check=True)
 names=git("diff","--name-only",task["base_commit"],COMMIT).decode().splitlines()
 permitted=task["allowed_paths"]+["handoff/SOL-038"]
 assert all(any(n==p or n.startswith(p+"/") for p in permitted) for n in names)
 assert set(task["deliverables"])<=set(names)
 mismatches=[]
 for n,h in r["artifacts_sha256"].items():
  observed=sha(git("show",COMMIT+":"+n))
  if observed!=h:mismatches.append(dict(path=n,expected_sha256=h,observed_sha256=observed))
 assert mismatches==rec["original_artifact_mismatches"]
 for n,h in rec["supplemental_git_blob_sha256"].items():assert sha(git("show",COMMIT+":"+n))==h,n
 for n,h in task["parameters"]["source_sha256"].items():assert sha(git("show",task["base_commit"]+":"+n))==h,n
 record=dict(task_id="SOL-038",reviewed_commit=COMMIT,task_sha256=digest,status="rejected_failed_delivery",code_verdict="pending_revalidation",receipt_sha256=sha(receipt_raw),recovery_sha256=sha(recovery_raw),original_failure=r["failure"],original_parent_checks=r["checks"],changed_paths=len(names),supplemental_hashes_verified=len(rec["supplemental_git_blob_sha256"]),source_pins_verified=len(task["parameters"]["source_sha256"]),receipt_hash_mismatches=mismatches,acceptance=False,checks=[])
 dest=ROOT/".runtime/reviews/SOL-038-e1783a9"
 assert not dest.exists()
 subprocess.run(["git","-c","core.autocrlf=false","worktree","add","--detach",str(dest),COMMIT],cwd=ROOT,check=True,capture_output=True)
 env={k:v for k,v in os.environ.items() if k.upper()!="PYTHONPATH"}
 def inventory():return {str(p.relative_to(dest)).replace(chr(92),"/"):sha(p.read_bytes()) for top in ("src","scripts","tests","audit/SOL-038") for p in (dest/top).rglob("*") if p.is_file() and "__pycache__" not in p.parts}
 before=inventory()
 for i,args in enumerate((["-B","-m","unittest","discover","-s","tests","-p","test_policy_analysis_writer.py","-v"],["-B","audit/SOL-038/verify.py","--check"])):
  start=time.monotonic();out=ROOT/f"audit/chief/SOL-038-exact-check-{i}.stdout.txt";err=ROOT/f"audit/chief/SOL-038-exact-check-{i}.stderr.txt"
  with out.open("xb") as o,err.open("xb") as e:
   proc=subprocess.run([sys.executable,*args],cwd=dest,env=env,stdout=o,stderr=e,timeout=600)
  record["checks"].append(dict(argv=[sys.executable,*args],exit_code=proc.returncode,elapsed_seconds=time.monotonic()-start,stdout_path=out.relative_to(ROOT).as_posix(),stderr_path=err.relative_to(ROOT).as_posix(),stdout_sha256=sha(out.read_bytes()),stderr_sha256=sha(err.read_bytes())))
 record["protected_inventory_unchanged"]=before==inventory()
 record["checkout_git_status"]=subprocess.check_output(["git","status","--porcelain"],cwd=dest).decode()
 path=ROOT/"audit/chief/SOL-038-delivery-review.json"
 with path.open("x",encoding="utf8",newline="\n") as f:json.dump(record,f,indent=2);f.write("\n")
 print(json.dumps(record))
if __name__=="__main__":main()
