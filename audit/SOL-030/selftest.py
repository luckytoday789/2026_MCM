"""Isolated SOL-030 corruption trials. Creates only new audit result and ignored scratch."""
import copy, csv, hashlib, io, json, shutil, subprocess, sys
from pathlib import Path
import verify as v

original=v.HERE
scratch=v.ROOT/'.runtime/sol030/integrity'
scratch.mkdir(parents=True,exist_ok=False)
t=v.task_identity(); binding=v.make_binding(t)

def tree(path):
    return {p.relative_to(path).as_posix():v.sha(p.read_bytes()) for p in sorted(path.rglob('*')) if p.is_file()}

def reject(call):
    try: call()
    except ValueError as e: return str(e)
    raise RuntimeError('Expected corruption was not rejected')

# Mutate the real numeric-point representation, never the accepted source table.
points=v.rows(v.ROOT/(v.FIG+'baseline-h30-severe-points.csv'))
index=next(i for i,r in enumerate(points) if r['policy']=='equal_weight_annual' and r['year']=='8' and r['stage']=='post_fee')
points[index]['real_wealth']=str(float(points[index]['real_wealth'])+.01)
point_copy=scratch/'corrupt-points.csv'
with point_copy.open('x',encoding='utf8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(points[0]),lineterminator='\n'); w.writeheader(); w.writerows(points)
before=v.sha(point_copy.read_bytes())
point_reason=reject(lambda:v.numerical(point_copy))
point_unchanged=before==v.sha(point_copy.read_bytes())
identity=copy.deepcopy(binding); identity['source_result_commit']='0'*40
identity_copy=scratch/'corrupt-binding.json'; v.dump(identity_copy,identity)
before_identity=v.sha(identity_copy.read_bytes())
identity_reason=reject(lambda:v.check_binding(v.load(identity_copy),binding))
identity_unchanged=before_identity==v.sha(identity_copy.read_bytes())
preliminary={'trials':[{'kind':'numeric_point_helper','rejected':True,'unchanged':point_unchanged,'reason':point_reason},
                       {'kind':'source_identity_helper','rejected':True,'unchanged':identity_unchanged,'reason':identity_reason}],
             'scope':'Actual completed helper rejections used only to build isolated CLI controls.'}

# Construct a fully authentic read-only control in ignored scratch, then copy it
# for actual --check rejection trials. No published audit evidence is rewritten.
control=scratch/'control'; control.mkdir()
for name in v.EVIDENCE:
    if name!='integrity-self-tests.json': shutil.copyfile(original/name,control/name)
v.dump(control/'integrity-self-tests.json',preliminary)
v.HERE=control
v.dump(control/'source-binding.json',binding)
v.dump(control/'verification.json',v.calculate(t,binding))
v.HERE=original

def cli(directory):
    before=tree(directory)
    proc=subprocess.run([sys.executable,'-B',str(original/'verify.py'),'--check','--evidence-dir',str(directory)],
                        cwd=v.ROOT,capture_output=True,text=True)
    after=tree(directory)
    # Full original tool output remains local. Shared diagnostics redact machine paths.
    label=directory.name
    (scratch/(label+'-stdout.txt')).write_text(proc.stdout,encoding='utf8')
    (scratch/(label+'-stderr.txt')).write_text(proc.stderr,encoding='utf8')
    stderr=proc.stderr.replace(str(v.ROOT),'<worktree>').replace(str(directory),'<scratch-copy>')
    return {'exit_code':proc.returncode,'stdout':proc.stdout.strip(),'stderr':stderr,
            'unchanged':before==after,'snapshot_sha256':v.sha(json.dumps(before,sort_keys=True).encode())}

positive=cli(control); v.require(positive['exit_code']==0 and positive['unchanged'],'positive CLI control')
trials=[]
for kind in ('numeric_point','source_identity'):
    directory=scratch/kind; shutil.copytree(control,directory)
    if kind=='numeric_point':
        path=directory/'verification.json'; x=v.load(path)
        x['numerical']['points'][index]['real_wealth']+=.01
    else:
        path=directory/'source-binding.json'; x=v.load(path); x['source_result_commit']='0'*40
    path.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n',encoding='utf8')
    outcome=cli(directory)
    v.require(outcome['exit_code']!=0 and outcome['unchanged'],'read-only CLI rejects '+kind)
    trials.append({'kind':kind,'mutation':'+0.01 real wealth in year8 post_fee point' if kind=='numeric_point' else 'source_result_commit replaced by 40 zeroes',
                   'rejected':True,'unchanged':outcome['unchanged'],'cli':outcome})
result={'schema_version':1,'python':sys.version.split()[0],'verifier_sha256':binding['verifier_sha256'],
        'helper_trials':preliminary['trials'],'positive_cli_control':positive,'trials':trials,
        'scratch_scope':'.runtime/sol030/integrity','accepted_sources_modified':False,
        'raw_logs':'Preserved in ignored scratch; shared stderr redacts local machine path.'}
v.dump(original/'integrity-self-tests.json',result)
print(json.dumps({'status':'passed','positive_control':positive['exit_code'],'corruption_exit_codes':[x['cli']['exit_code'] for x in trials],
                  'unchanged':all(x['unchanged'] for x in trials)}))
