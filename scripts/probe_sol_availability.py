"""One bounded real Sol response, after a stated reset hint. Never a quota bypass."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

TOKEN = 'SAFEINVEST_SOL_AVAILABLE'


def response_is_usable(returncode, response):
    return returncode == 0 and response.strip() == TOKEN


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--not-before', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    when = dt.datetime.fromisoformat(args.not_before)
    assert when.tzinfo is not None
    output = Path(args.output)
    assert not output.exists(), 'Preserve prior probe evidence; use a new attempt.'
    print(f'One real model probe is scheduled no earlier than {when.isoformat()}; no calls while waiting.', flush=True)
    while (remaining := (when-dt.datetime.now(dt.timezone.utc)).total_seconds()) > 0:
        time.sleep(min(30, remaining))
    runtime = Path('.runtime')
    runtime.mkdir(exist_ok=True)
    response_path = runtime/'quota-probe-response.txt'
    log_path = runtime/'quota-probe-model.log'
    assert not response_path.exists() and not log_path.exists()
    prompt = f'This is only a model availability probe. Do not use any tools or inspect files. Reply with exactly {TOKEN} and nothing else.'
    binary = shutil.which('codex')
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    code = None
    error = None
    try:
        if not binary:
            raise RuntimeError('Codex executable is unavailable on the assigned Sol machine.')
        command = [binary, 'exec', '--sandbox', 'read-only', '--model', 'gpt-6.1-sol',
                   '-c', 'model_reasoning_effort="xhigh"', '--cd', str(Path.cwd()),
                   '--output-last-message', str(response_path.resolve()), prompt]
        with log_path.open('w', encoding='utf-8') as log:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=subprocess.STDOUT)
            try:
                code = process.wait(timeout=300)
            except subprocess.TimeoutExpired:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
                else:
                    process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
                raise RuntimeError('Single availability probe timed out after 300 seconds.')
    except Exception as exception:
        error = str(exception)
    response = response_path.read_text(encoding='utf-8') if response_path.exists() else ''
    log = log_path.read_text(encoding='utf-8', errors='replace') if log_path.exists() else ''
    usable = response_is_usable(code, response)
    value = {'schema_version':1, 'model':'gpt-6.1-sol', 'reasoning_effort':'xhigh',
             'not_before':when.isoformat(), 'started_at':started,
             'finished_at':dt.datetime.now(dt.timezone.utc).isoformat(),
             'model_calls':1 if binary else 0, 'exit_code':code,
             'usable':usable, 'expected_response':TOKEN, 'response':response,
             'error':error, 'quota_error_detected':'usage limit' in log.lower(),
             'model_log_sha256':hashlib.sha256(log.encode()).hexdigest(),
             'note':'A real response proves availability only at probe time, not remaining review budget.'}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(value, ensure_ascii=False), flush=True)
    return 0 if usable else 1


if __name__ == '__main__':
    raise SystemExit(main())
