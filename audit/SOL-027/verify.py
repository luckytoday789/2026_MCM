"""Read-only SOL-027 verifier. No evidence creation, repair, production I/O or HEAD equality."""
import argparse, hashlib, json, os, platform, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
AUDIT=ROOT/'audit/SOL-027'
TASK=json.loads("{\"schema_version\":1,\"id\":\"SOL-027\",\"attempt\":1,\"owner\":\"sol\",\"kind\":\"agent\",\"base_commit\":\"5a015a490c89b39271624e1f1790a3454498a6c9\",\"depends_on\":[\"SOL-013\",\"SOL-020\",\"SOL-021\",\"SOL-022\",\"SOL-025\"],\"split\":\"synthetic\",\"max_seconds\":1200,\"scope\":\"Independent code review of chief pure own-horizon personalized adapter and scalar rescreen; no production or saved competition outcomes.\",\"parameters\":{\"required_python\":\"3.12\",\"cpu_only\":true,\"competition_outcomes_allowed\":false,\"final_outcomes_allowed\":false,\"source_sha256\":{\"specs/PROBLEM_LOCK.md\":\"566c93ad1b5f79c9ec10a42725ab023953c9a02aeb1c91a459e740caf68c0e46\",\"specs/ACCOUNTING.md\":\"a9c3ab8dbba3ad752336642061ead272e2c196de83f73eb410e39bd5b559f71e\",\"specs/development_policy_pilot_v2.json\":\"d7b20f38196831befc80dfdcc69c6653d1ae8352d1c87c79e19bcc09d5c84df3\",\"specs/PERSONALIZED_REVIEW.md\":\"0365fdf989ae7abfeda0bc3f48f8c86245a40dd9e48b3c6ae8d2d26c0b7c4987\",\"specs/PERSONALIZED_OUTPUT_NOTES.md\":\"f328a5832251faab1b8810b598fc66408e5a323afc755a0011cfdb0b04e255a7\",\"specs/personalized_review_v1.json\":\"2edc9410b291f8f1f7235344e685d004c2f3cfd80844539df96759e9b305b4ad\",\"specs/PERSONALIZED_COMPONENT.md\":\"d9b3737ec37a8cf6421fe56a703d045a680bdef5906b4a9910643a996c181fec\",\"src/safeinvest/__init__.py\":\"b986566f8c42973164639cc7e296ed70fbc64479411e79a81f522cfc27ec14ef\",\"src/safeinvest/accounting.py\":\"0c73b143ed9755924be16d9c4fe9d9e8d8888931cb5c8a8c303434e2280389e5\",\"src/safeinvest/backtest.py\":\"bbe2e602124adf068da424df0a28c9f40f970f81c126bed393f61ebb25b244b6\",\"src/safeinvest/baselines.py\":\"a8e392111c7f206aa4be2a475b92db62d049ea7eb460c1d813f0d8033f5620ce\",\"src/safeinvest/metrics.py\":\"efb7dad73e71515b9f164a95935231479ebca14b46c5b086a14de4bf5d38df9e\",\"src/safeinvest/experiments.py\":\"8cfc463704decff7491e3f2ef5f9ec208318294eb0254363a98c6df50550abca\",\"src/safeinvest/policy_pilot.py\":\"5b000fdc637db3d13d89aaad3ec2ab97cf277adcd133575ea4f546e05379a057\",\"src/safeinvest/policy_calibration.py\":\"d46f029dc11c6a5ef584c2cfb2e6ce8cc3bc3fc0dc515319183017be9954e05a\",\"src/safeinvest/policy_cases.py\":\"84d96454e31ecf4a103fbd17e4498dfbd56f453d3911beaeac43583f56f82ca7\",\"src/safeinvest/policy_personalized.py\":\"09e840c2e7f94183472e144c98509f855081105ae937a13cabb31a3bf47062e9\",\"tests/test_policy_personalized.py\":\"1a1adc6d540e3e033ecce7a48ba0a8d379c18d563b0ec7bb7444f3ee03696b5a\",\"audit/chief/personalized-component/validation-002.json\":\"d972375132ed604993db42cb164a30ea5095e4c488c5a3a410cede7ccdc14623\",\"audit/SOL-020/findings.json\":\"2e597db33daf1da6dfdea61925565fb7d2735e97db7d985784faed967a27f3c0\",\"audit/chief/SOL-013-review.json\":\"20923f671dd26e40be6e383f21398931eceac036d74c73c06fb8e48b9caaa462\",\"audit/chief/SOL-020-review.json\":\"276895e8e12b9c212fe433f0fa1c07408c601502ffd5d9ce965a684fdc72551b\",\"audit/chief/SOL-021-review.json\":\"105f8610edeebc1b17272b7450d3cdba29fa14d963407afd1665fc7caf640670\",\"audit/chief/SOL-022-review.json\":\"9875dab72b4354566fe6067de94fabbb917c0b9c2344914a3f38c084f1042546\",\"audit/chief/SOL-025-review.json\":\"7523121f5290d6ba938ccff6749d5d28b86c0053c2c072850092dee941efdb1c\"},\"accepted_dependencies\":{\"SOL-013\":\"1908813ef2627ca6e15591278ec15ccf2f9e9cff\",\"SOL-020\":\"2fbd4598606b41a786bd931046adb0ecc8b42d78\",\"SOL-021\":\"d154f90d1c50b37990b75ec0a45aa01a38252343\",\"SOL-022\":\"21ad493707d71240f83d7f01ed6d133e1380e8fb\",\"SOL-025\":\"803b7a085284405ee5ee4d4f0d5720ebaa2e67f7\"},\"production_execution_authorized\":false,\"max_artifact_bytes\":10485760},\"allowed_paths\":[\"audit/SOL-027\"],\"deliverables\":[\"audit/SOL-027/review.md\",\"audit/SOL-027/findings.json\",\"audit/SOL-027/verify.py\",\"audit/SOL-027/verification.json\",\"audit/SOL-027/integrity-self-tests.json\"],\"commands\":[],\"validation_commands\":[[\"{python}\",\"-B\",\"-m\",\"unittest\",\"discover\",\"-s\",\"tests\",\"-p\",\"test_policy_personalized.py\",\"-v\"],[\"{python}\",\"-B\",\"audit/SOL-027/verify.py\",\"--check\"]],\"acceptance_checks\":[\"Exact immutable task/base/publication/source pins and permitted audit-only paths; genuine Python3.12 generated-only execution.\",\"Independent rational/scalar arithmetic beyond chief tests; all own H/tolerances, eligible classes, two fees, state/fold isolation and exact B15 prefix.\",\"Correct t-1/equality/post-fee/last-year latch timing, zero-fee dollar keep, exact deflation, counts and outcome rescreen; strict exceedances distinct from p90.\",\"No-run nulls and denominator0, preserved failures/proposed class, no fallback or primary replacement; invalid input rejected.\",\"Honest unauthenticated pure-component scope with source_verified=false and future upstream/result/freeze gates retained.\",\"Portable read-only verifier rejects numerical/source/count corruptions; exclusive evidence and failed trials preserved; approve distinct from check success.\"],\"instructions\":\"Read AGENTS.md and all pinned personalized contracts. This is targeted independent review of the chief-authored pure personalized adapter, not a production writer or generic-result review. SOL-020 accepted design only; this task challenges actual new implementation. Generic kernel/calibration/cases are already accepted. Review only the new adapter and its integration with those exact sources, preserving the original policy, parameters and task gates.\\n\\nOnly audit/SOL-027 may be written (plus ignored scratch); do not change implementation, tests, specifications, task definitions, queue, helpers or other audits. No competition CSV reads, saved outcome computations, packages, watcher/restarts, fetch/merge/commit/push, production CLI, final support or final outcomes. Parent owns receipt/push. Only generated rows and explicit synthetic fold priors may execute. Fixed development shape may be checked using generated 120x30 rows, clearly marked synthetic in evidence; do not read or relabel competition inputs.\\n\\nCheck API and actual source. All five own horizons/tolerances, both fixed fees, eligible fixed classes only, profile liquidity and horizon caps, fresh per-scenario/fee/profile state, full other-fold training priors and evaluation only through H. B at 25% must reproduce the exact generic H15 prefix for matching mode/fee/prior. Compare all inherited numeric/diagnostic fields, not only terminal metrics. The generic source/API must remain unchanged. Validate ordered keys, calibrations and scenario membership. Check only t-1 outcomes affect decision t, future suffix after H is irrelevant at fixed priors, and no next-period review is fabricated after final-year crossing.\\n\\nBuild a small independent scalar/rational oracle, without relying on chief expected values or production helpers for expected arithmetic. Verify fee/transfer before returns, exact inflation deflation, running maximum including post-fee and end wealth, equality latch on the following annual review, early fee-induced crossing followed by recovery, and pending component-dollar keep with zero fee and subsequent returns. Cover conservative/balanced/growth where eligible and both fees. Use exact expected counts/nulls and documented abs1e-9/rel1e-10 tolerance only for ordinary floating arithmetic; policy boundaries/counts/hashes must not be tolerance-relaxed.\\n\\nIndependently exercise risk-only failure, purchasing-power-only failure, both failure, equality pass, p90 passing while at least one loss strictly exceeds tolerance, and adjacent-float threshold comparisons. No failures may rerank, substitute bills, relax tolerances or hide proposed_class. Upstream referrals require no simulation, null personalized metrics/flags/exceedances and denominator0, preserve original reasons and holdings instructions. Invalid inputs must error, not silently refer. Verify inputs are not mutated and returned records do not alias mutable caller inputs.\\n\\nScope boundary is explicit: this pure one-case function receives unauthenticated proposed_class and rows; it cannot verify original assignment/screen/source hashes. All outputs retain source_verified=false. It intentionally does not create a ten-row root, source_case_path, saved bundle, analysis assembly, authenticated assignment or production CLI. Assess whether the boundary is honest and carries the required future provenance gate; do not claim the absent production layer has passed. Synthetic status wording must not be represented as an observed recommendation. Primary and doubled cases are independent, with no primary replacement or same-rule robustness inference. If you find an actual defect, preserve a minimal reproducer and verdict changes_required; do not silently repair source or mark synthetic regression success as approval.\\n\\nRun the prescribed focused test in fresh Python3.12 with case-insensitive PYTHONPATH removed, record imported module paths, real returncode/stdout/stderr/runtime. Produce review.md and findings.json with code_verdict approve/changes_required, precise reviewed sources, blockers/fixes, independent numeric facts and remaining gates. Fresh exclusively-created verification.json must bind immutable task/base/publication/pins and actual delivered audit/source bytes without self-hashing recursion. Provide verify.py --check [--evidence PATH] that resolves pinned source identities without current HEAD equality, recomputes read-only, rejects corrupted numerical/source/count evidence, and never rewrites missing or corrupted evidence. Check original bytes remain unchanged; retain all meaningful failed trials and diagnoses. Bound runtime to20 minutes CPU-only and artifact size10MiB per file. No production result or final authorization is issued even on approve.\\n\"}")
PUBLICATION='df038cb116c4818c14454231500f992af3f26d0f'
RELEASE='a730df25eabfc453788bba56ded2a018f975c9f7'
TASK_DIGEST='f086a587d0a0ec0aa1477d28df58f036482dac1dbc7e0add8f298553daf90f00'
DELIVERED=('findings.json','focused-test.json','initial-state.json','oracle-trial-001.json','oracle-trial-002.json','oracle-trial-003.json','oracle.py','review.md','tooling-diagnoses.json','verify.py','integrity-self-tests.json','identity-trial-001.json')
LIMIT=10485760

def need(ok,message):
    if not ok:raise AssertionError(message)
def digest(b):return hashlib.sha256(b).hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def load(p):
    b=Path(p).read_bytes();need(len(b)<=LIMIT,'oversized artifact');return json.loads(b)
def git(*args):
    p=subprocess.run(['git',*args],cwd=ROOT,capture_output=True,timeout=15)
    need(p.returncode==0,'Git identity unavailable: '+repr(args)+' '+p.stderr.decode(errors='replace'))
    return p.stdout

def identity():
    need(sys.version_info[:2]==(3,12),'requires Python 3.12')
    need(not any(k.lower()=='pythonpath' for k in os.environ),'PYTHONPATH must be removed case-insensitively before fresh Python')
    need(digest(canonical(TASK))==TASK_DIGEST,'embedded immutable task digest')
    need(TASK['allowed_paths']==['audit/SOL-027'],'task allowed paths')
    for commit in (TASK['base_commit'],PUBLICATION,RELEASE,*TASK['parameters']['accepted_dependencies'].values()):
        need(git('cat-file','-t',commit).strip()==b'commit','pinned commit unavailable')
    published=git('show',PUBLICATION+':ops/tasks/SOL-027.json')
    need(json.loads(published)==TASK,'immutable published task changed')
    published_queue=json.loads(git('show',PUBLICATION+':ops/queue.json'))
    released_queue=json.loads(git('show',RELEASE+':ops/queue.json'))
    queue0=next(t for t in published_queue['tasks'] if t['id']=='SOL-027')
    queue1=next(t for t in released_queue['tasks'] if t['id']=='SOL-027')
    need(queue0['task_sha256']==TASK_DIGEST and queue1['task_sha256']==TASK_DIGEST,'publication task digest mismatch')
    need(queue1['state']=='ready' and queue1['attempt']==1 and queue1['owner']=='sol','task was not released')
    basequeue=json.loads(git('show',TASK['base_commit']+':ops/queue.json'))
    for name,commit in TASK['parameters']['accepted_dependencies'].items():
        entry=next(t for t in basequeue['tasks'] if t['id']==name)
        need(entry['state']=='accepted' and entry['reviewed_commit']==commit,'accepted dependency differs: '+name)
    sources={}
    for name,pin in TASK['parameters']['source_sha256'].items():
        blob=git('show',TASK['base_commit']+':'+name)
        need(digest(blob)==pin,'base source pin differs: '+name)
        current=(ROOT/name).read_bytes()
        need(current==blob or current==blob.replace(b'\n',b'\r\n'),'checkout source differs: '+name)
        sources[name]={'canonical_sha256':pin,'git_blob':git('rev-parse',TASK['base_commit']+':'+name).strip().decode(),'canonical_bytes':len(blob)}
    if (ROOT/'.runtime/task.json').exists():need(load(ROOT/'.runtime/task.json')==TASK,'local immutable task differs')
    return {'task_id':'SOL-027','attempt':1,'role':'sol','base_commit':TASK['base_commit'],'publication_commit':PUBLICATION,'release_commit':RELEASE,'task_semantic_sha256':TASK_DIGEST,'published_task_blob_sha256':digest(published),'source_pins':sources,'allowed_paths':['audit/SOL-027'],'production_execution_authorized':False,'final_outcomes_allowed':False}

def delivered():
    out={}
    for name in DELIVERED:
        raw=(AUDIT/name).read_bytes();need(len(raw)<=LIMIT,'oversized '+name)
        # Record original delivered LF bytes. CRLF checkout is allowed only for Markdown,
        # consistently with text=auto; no arbitrary whitespace normalization is allowed.
        raw=raw.replace(b'\r\n',b'\n') if name.endswith('.md') else raw
        out[name]={'sha256':digest(raw),'bytes':len(raw)}
    return out

def recompute():
    from oracle import exercise
    result=exercise();paths=result.pop('imported_modules')
    imports={}
    for name,imported in paths.items():
        p=Path(imported).resolve();rel=p.relative_to(ROOT).as_posix()
        need(rel in TASK['parameters']['source_sha256'],'import outside pinned closure: '+name)
        raw=p.read_bytes();need(digest(raw)==TASK['parameters']['source_sha256'][rel],'imported bytes not exact source pin: '+name)
        imports[name]=rel
    result['imported_module_relative_paths']=imports
    return result

def exact(actual,expected,where='$'):
    need(type(actual) is type(expected),'type mismatch at '+where)
    if isinstance(expected,dict):
        need(set(actual)==set(expected),'keys mismatch at '+where)
        for k in expected:exact(actual[k],expected[k],where+'.'+k)
    elif isinstance(expected,list):
        need(len(actual)==len(expected),'count mismatch at '+where)
        for i,(a,b) in enumerate(zip(actual,expected)):exact(a,b,where+'['+str(i)+']')
    elif isinstance(expected,float):need(actual.hex()==expected.hex(),'numerical evidence mismatch at '+where)
    else:need(actual==expected,'value mismatch at '+where)

def check(evidence):
    saved=load(evidence) # Missing evidence fails before any recomputation, never writes.
    need(set(saved)=={'schema_version','identity','numeric','delivered_audit_bytes','execution'},'evidence top-level schema')
    exact(saved['schema_version'],1)
    exact(saved['identity'],identity(),'$.identity')
    exact(saved['delivered_audit_bytes'],delivered(),'$.delivered_audit_bytes')
    execution=saved['execution']
    need(execution['python_version'].startswith('3.12.'),'execution Python version')
    need(execution['pythonpath_removed'] is True and execution['competition_inputs_read'] is False,'execution boundary')
    need(execution['oracle_returncode']==0 and 0<=execution['oracle_runtime_seconds']<=1200,'oracle execution status/runtime')
    imports=execution['imported_module_paths']
    need(set(imports)=={'safeinvest','safeinvest.accounting','safeinvest.backtest','safeinvest.baselines','safeinvest.experiments','safeinvest.metrics','safeinvest.policy_calibration','safeinvest.policy_cases','safeinvest.policy_personalized','safeinvest.policy_pilot'},'recorded imported closure')
    original=load(AUDIT/'initial-state.json')
    for name,old in original['source_checkout_sha256'].items():
        # Initial execution identity, not a requirement to preserve machine line endings on a later checkout.
        blob=git('show',TASK['base_commit']+':'+name)
        need(old in (digest(blob),digest(blob.replace(b'\n',b'\r\n'))),'initial source bytes not pinned')
    focused=load(AUDIT/'focused-test.json')
    need(focused['returncode']==0 and focused['pythonpath_removed'] is True and 'Ran 10 tests' in focused['stderr'] and focused['stderr'].rstrip().endswith('OK'),'focused regression evidence')
    need(focused['command'][1:]==['-B','-m','unittest','discover','-s','tests','-p','test_policy_personalized.py','-v'],'focused command')
    need(focused['runtime_seconds']>=0,'focused duration')
    trial=load(AUDIT/'oracle-trial-003.json');need(trial['returncode']==0,'actual oracle returncode')
    trial_numeric=json.loads(trial['stdout']);trial_paths=trial_numeric.pop('imported_modules')
    exact(trial_paths,imports,'$.execution.imported_module_paths')
    # Compare replay to recorded original execution after making absolute paths portable.
    trial_numeric['imported_module_relative_paths']=saved['numeric']['imported_module_relative_paths']
    exact(saved['numeric'],trial_numeric,'$.original_execution_numeric')
    exact(saved['numeric'],recompute(),'$.numeric')
    findings=load(AUDIT/'findings.json')
    need(findings['code_verdict']=='approve' and findings['production_result'] is False and findings['final_authorization'] is False,'verdict scope')
    need(findings['independent_evidence']['checks']==saved['numeric']['checks'],'review numerical count differs')
    return {'check_status':'passed','code_verdict':findings['code_verdict'],'read_only':True,'checks':saved['numeric']['checks'],'base_commit':TASK['base_commit'],'production_result':False,'final_authorization':False}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true',required=True);parser.add_argument('--evidence',type=Path,default=AUDIT/'verification.json');args=parser.parse_args()
    print(json.dumps(check(args.evidence),sort_keys=True))
if __name__=='__main__':main()
