"""Create a local source ZIP plus offline Git evidence, without model execution.

This packages a pushed snapshot and exact work refs. It does not certify a
manuscript or outcome. Outputs stay ignored; private runtime files are excluded.
"""
import argparse,hashlib,json,subprocess,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LIMIT=50_000_000

def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)

def sha(raw):return hashlib.sha256(raw).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',required=True)
    args=parser.parse_args()
    output=(ROOT/args.output_dir).resolve()
    assert output.is_relative_to(ROOT/'.runtime') and not output.exists(),'new ignored output directory required'
    assert not git('status','--porcelain').strip(),'commit and push the intended snapshot first'
    commit=git('rev-parse','HEAD').decode().strip()
    assert commit==git('rev-parse','origin/main').decode().strip(),'snapshot must already be pushed'
    assert git('branch','--show-current').strip()==b'main'
    references=['refs/heads/main']+git('for-each-ref','--format=%(refname)','refs/remotes/origin/work/').decode().splitlines()
    refs={r:git('rev-parse',r).decode().strip() for r in sorted(references)}
    output.mkdir(parents=True)
    bundle=output/'research-evidence.bundle'
    subprocess.run(['git','-c','pack.threads=1','bundle','create',str(bundle),*refs],cwd=ROOT,check=True,capture_output=True)
    verified=subprocess.run(['git','bundle','verify',str(bundle)],cwd=ROOT,check=True,capture_output=True)
    bundle_hash=sha(bundle.read_bytes())
    prefixes=('src/','tests/','scripts/','specs/','ops/tasks/','report/')
    selected=[]
    for name in git('ls-tree','-r','--name-only',commit).decode().splitlines():
        if name.startswith(prefixes) or name in ('requirements.txt','AGENTS.md','README.md','data/README.md','data/manifest.json','ops/PROTOCOL.md','ops/TWO_NODE_TAKEOVER.md','ops/queue.json','ops/control.json','ops/freeze.json','ops/skills-lock.json'):
            assert not any(part in ('.runtime','.venv','.git') for part in Path(name).parts)
            selected.append(name)
    files={name:git('show',commit+':'+name) for name in sorted(selected)}
    files['research-evidence.bundle']=bundle.read_bytes()
    inventory=dict(schema_version=1,source_commit=commit,git_references=refs,files_sha256={p:sha(v) for p,v in files.items()},private_runtime_included=False,package_scope='Source and exact offline research evidence; submission readiness remains separately audited.')
    files['PACKAGE-MANIFEST.json']=(json.dumps(inventory,indent=2,sort_keys=True)+'\n').encode()
    files['REPRODUCTION.txt']=('SafeInvest source supplement\n\nPython 3.12; numerical requirements.txt; report-only requirements in report/requirements-layout.txt.\n\nThe bundle preserves the supplied input blobs, exact task/source/result history, failed trials and reviews. It contains no local credentials, environments or private member file. Preserve data/README.md CC BY-NC-SA 4.0 attribution.\n\nOffline evidence setup in a new directory:\n  git init evidence\n  git -C evidence fetch ../research-evidence.bundle refs/heads/main:refs/heads/main\n  git -C evidence fetch ../research-evidence.bundle "refs/remotes/origin/work/*:refs/remotes/origin/work/*"\n  git -C evidence checkout main\n  git -C evidence update-ref refs/remotes/origin/main '+commit+'\n\nUse the exact tasks, configuration, accepted_paths and reviewed_commit entries in ops/queue.json. Read-only numerical checkers under audit/chief read exact preserved Git blobs. Run checks before considering a reproduction. Never launch worker/watch/coordinator processes from this supplement.\n\nAn optional repeat computation belongs in an isolated worktree at the original task base, with its original immutable task copied to .runtime/task.json. Preserve original freeze/exposure/results; label repeat outputs as reproduction. Never reopen development selection, retune a final policy, or overwrite accepted results. Original command provenance is retained in task/result manifests. No automatic submission is authorized.\n').encode()
    archive=output/'SafeInvest-source.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,raw in sorted(files.items()):
            info=zipfile.ZipInfo(name,(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            z.writestr(info,raw,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    assert archive.stat().st_size<=LIMIT,'source supplement exceeds 50 MB'
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and set(z.namelist())==set(files)
        assert all(sha(z.read(p))==sha(v) for p,v in files.items())
    assert all(git('rev-parse',r).decode().strip()==c for r,c in refs.items()),'refs changed during packaging'
    report=dict(status='passed',source_commit=commit,archive=str(archive.relative_to(ROOT)),bytes=archive.stat().st_size,sha256=sha(archive.read_bytes()),file_count=len(files),git_bundle_sha256=bundle_hash,git_bundle_verify_exit_code=verified.returncode,member_hashes_verified=True,no_simulation=True,submission_ready_claimed=False)
    (output/'package-check.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report))

if __name__=='__main__':main()
