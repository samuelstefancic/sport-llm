"""Read Codex skill discovery metadata only; no thread or model turn is created."""
import argparse
import datetime
import hashlib
import json
import os
import selectors
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build' / 'verification' / 'skills'
OUT.mkdir(parents=True, exist_ok=True)
NAMES = sorted(p.parent.name for p in (ROOT / '.agents/skills').glob('*/SKILL.md'))


def run(environment, profile):
    process = subprocess.Popen(['codex', 'app-server', '--stdio'], cwd=ROOT, env=environment,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True, bufsize=1)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    sent = []


    def send(payload):
        process.stdin.write(json.dumps(payload) + '\n')
        process.stdin.flush()
        sent.append(payload)


    def response(identifier):
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if not selector.select(timeout=min(1, max(0, deadline - time.monotonic()))):
                continue
            line = process.stdout.readline()
            if not line:
                raise RuntimeError('App-server exited before response')
            payload = json.loads(line)
            if payload.get('id') == identifier:
                if 'error' in payload:
                    raise RuntimeError('JSON-RPC error: ' + f"{payload['error'].get('code')} {payload['error'].get('message', '')}")
                return payload['result']
        raise TimeoutError('No response within 25 seconds')


    report = {'checked_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'cwd': str(ROOT), 'profile': profile, 'command': 'codex app-server --stdio',
              'scope': 'CLI/app-server discovery; no thread/start or turn/start; not Desktop reload',
              'cli_version': subprocess.check_output(['codex', '--version'], env=environment, text=True).strip()}
    try:
        send({'id': 1, 'method': 'initialize', 'params': {'clientInfo': {
            'name': 'llmSport_skill_discovery_check', 'version': '0.1.0'}}})
        response(1)
        report['initialize_succeeded'] = True
        send({'method': 'initialized', 'params': {}})
        send({'id': 2, 'method': 'skills/list', 'params': {
            'cwds': [str(ROOT)], 'forceReload': True}})
        result = response(2)
        project = [row for row in result.get('data', []) if row.get('cwd') == str(ROOT)]
        report['skills'] = [{key: skill.get(key) for key in
                             ('name', 'description', 'path', 'scope', 'enabled')}
                            for row in project for skill in row.get('skills', [])
                            if skill.get('name') in NAMES]
        for skill in report['skills']:
            if str(ROOT / '.agents/skills') in skill['path']:
                skill['sha256'] = hashlib.sha256(Path(skill['path']).read_bytes()).hexdigest()
        report['project_errors'] = [error for row in project for error in row.get('errors', [])
                                    if str(ROOT / '.agents/skills') in json.dumps(error)]
        found = {s['name'] for s in report['skills']
                 if s['enabled'] is True and str(ROOT / '.agents/skills') in s['path']}
        report['missing_or_disabled'] = sorted(set(NAMES) - found)
        report['status'] = 'PASS' if len(found) == 7 and not report['project_errors'] else 'INCOMPLETE'
    except Exception as exc:
        report['status'] = 'BLOCKED'
        report['reason'] = str(exc)
    finally:
        report['requests_sent'] = sent
        selector.close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        report['process_closed'] = process.poll() is not None
        (OUT / 'discovery-retry.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({'status': report['status'], 'skills': report.get('skills', []),
                          'reason': report.get('reason'), 'process_closed': report['process_closed']},
                         ensure_ascii=False))

    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--isolated', action='store_true',
                        help='Use a temporary Codex profile trusting only this repository')
    args = parser.parse_args()
    if args.isolated:
        with tempfile.TemporaryDirectory(prefix='llmsport-discovery-') as profile_dir:
            # The clone is the only trusted project. No account configuration is copied.
            project_table = '[projects.' + json.dumps(str(ROOT)) + ']'
            Path(profile_dir, 'config.toml').write_text(f'{project_table}\ntrust_level = "trusted"\n')
            raise SystemExit(run({**os.environ, 'CODEX_HOME': profile_dir}, 'temporary'))
    raise SystemExit(run(os.environ, 'current'))
