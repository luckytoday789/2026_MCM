"""Independent tiny Git transport fixture; no SafeInvest computation or commits."""
from pathlib import Path
import datetime
import hashlib
import json
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[2]
ATTR_BASE = 'ade71e13e02f4c5655b7ad873297ea5fd8201040'


def probe():
    root_attrs = subprocess.check_output(['git', 'show', ATTR_BASE + ':.gitattributes'], cwd=ROOT)
    sha = lambda data: hashlib.sha256(data).hexdigest()
    scratch = ROOT / '.runtime' / ('writer-git-byte-probe-' + uuid.uuid4().hex)
    scratch.mkdir()
    results = []
    for autocrlf, eol in (('false', 'lf'), ('false', 'crlf'), ('true', 'lf'), ('true', 'crlf')):
        trial = autocrlf + '-' + eol
        repo = scratch / trial
        repo.mkdir()
        commands = []

        def git(*args):
            run = subprocess.run(['git', *args], cwd=repo, capture_output=True, timeout=30)
            commands.append(dict(argv=['git', *args], returncode=run.returncode,
                                 stderr=run.stderr.decode('utf-8', errors='replace')))
            assert run.returncode == 0, commands[-1]
            return run.stdout

        git('init', '-q')
        git('config', 'core.autocrlf', autocrlf)
        git('config', 'core.eol', eol)
        git('config', 'core.safecrlf', 'false')
        (repo / '.gitattributes').write_bytes(root_attrs)
        files = {
            'legacy/failure.json': b'{\r\n  "status": "failed"\r\n}\r\n',
            'legacy/partial.txt': b'preserved failure marker\n',
            'repaired/failure.json': b'{\n  "status": "failed"\n}\n',
            'repaired/partial.txt': b'preserved failure marker\n',
            'repaired/.gitattributes': b'* text eol=lf\n',
        }
        for name, data in files.items():
            path = repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        git('add', '--', '.gitattributes', 'legacy', 'repaired')
        export = scratch / ('checkout-' + trial)
        export.mkdir()
        git('checkout-index', '--all', '--prefix=' + export.as_posix() + '/')
        observed = {}
        for name, original in files.items():
            blob = git('show', ':' + name)
            checkout = (export / name).read_bytes()
            observed[name] = dict(original_sha256=sha(original), git_blob_sha256=sha(blob),
                                  checkout_sha256=sha(checkout), original_bytes=len(original),
                                  git_blob_bytes=len(blob), checkout_bytes=len(checkout))
            if name.startswith('repaired/'):
                assert original == blob == checkout, (autocrlf, name)
        assert files['legacy/failure.json'] != (export / 'legacy/failure.json').read_bytes()
        assert (files['legacy/partial.txt'] == (export / 'legacy/partial.txt').read_bytes()) == (autocrlf == 'false' and eol == 'lf')
        attrs = git('check-attr', '--all', '--', *files).decode()
        results.append(dict(autocrlf=autocrlf, core_eol=eol, status='passed', files=observed,
                            attributes=attrs, commands=commands))
    return dict(schema_version=1, checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                source_attributes_commit=ATTR_BASE, source_attributes_sha256=sha(root_attrs),
                scratch_path=str(scratch), trials=results, status='passed',
                purpose='Independently reproduce W-LF-1 and test the specified deterministic-LF plus scoped-attribute correction on tiny nonnumeric text.',
                actual_writer_repaired=False, writer_acceptance=False, production_authorized=False,
                limitations=['Does not replace SOL-031 real source/fixture Git checkout validation or exact receipt review.'])


if __name__ == '__main__':
    print(json.dumps(probe(), indent=2))
