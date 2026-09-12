#!/usr/bin/env python3
"""Evaluate installed cached fixtures with externally supplied, unchanged public tests."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {'smoke--counter': 1, 'smoke--dice': 1, 'smoke-evolution--counter': 2,
            'smoke-evolution--dice': 2, 'ticket-booking--ticket-booking': 10}


def run_task(task, inputs, checks, output, playwright, browser):
    work = output / task
    work.mkdir(parents=True)
    app = work / 'app'
    env = {k: v for k, v in os.environ.items() if not k.startswith('ARCBENCH_')}
    env['ARCBENCH_OUTPUT_DIR'] = str(app)
    built = subprocess.run([sys.executable, str(ROOT / 'agent.py'), str(inputs / task),
        '--output-dir', str(app), '--profile', 'zero'], capture_output=True, text=True, env=env, timeout=30)
    (work / 'entrypoint.log').write_text(built.stdout + '\n' + built.stderr)
    if built.returncode:
        raise RuntimeError('Fixture installation failed; see ' + str(work / 'entrypoint.log'))
    subprocess.run(['node', 'build.cjs'], cwd=app / 'frontend', check=True, timeout=10)
    server = subprocess.Popen(['node', 'server.cjs'], cwd=app / 'backend', text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env={**env, 'PORT': '0', 'AUDIT_SECONDARY_PORT': '0', 'AUDIT_BIND_ADDRESS': '127.0.0.1'})
    log = []
    try:
        deadline = time.monotonic() + 10
        with selectors.DefaultSelector() as selector:
            selector.register(server.stdout, selectors.EVENT_READ)
            while time.monotonic() < deadline:
                if not selector.select(1):
                    continue
                line = server.stdout.readline()
                log.append(line)
                if not line:
                    raise RuntimeError('Server exited before readiness')
                try:
                    port = json.loads(line)['listening']
                    break
                except (ValueError, KeyError):
                    continue
            else:
                raise RuntimeError('Server readiness timeout')
        suite = work / 'public-tests'
        shutil.copytree(checks / task, suite)
        original = {str(p.relative_to(suite)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in suite.rglob('*') if p.is_file()}
        (work / 'node_modules').symlink_to(playwright.parent.parent, target_is_directory=True)
        report = work / 'playwright-report.json'
        config = {'testDir': str(suite), 'timeout': 10000, 'expect': {'timeout': 10000},
            'fullyParallel': False, 'workers': 4, 'retries': 0,
            'reporter': [['json', {'outputFile': str(report)}]],
            'use': {'baseURL': f'http://127.0.0.1:{port}', 'channel': 'chromium', 'trace': 'off',
                    'screenshot': 'off', 'launchOptions': {'executablePath': str(browser)}}}
        config_path = work / 'playwright.config.cjs'
        config_path.write_text('module.exports=' + json.dumps(config) + ';\n')
        tested = subprocess.run(['node', str(playwright / 'cli.js'), 'test', '--config', str(config_path)],
            cwd=work, env={**env, 'E2E_BASE_URL': f'http://127.0.0.1:{port}'},
            capture_output=True, text=True, timeout=120)
        (work / 'playwright.log').write_text(tested.stdout + '\n' + tested.stderr)
        observed = {str(p.relative_to(suite)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in suite.rglob('*') if p.is_file()}
        if observed != original:
            raise RuntimeError('Public test bytes changed')
        data = json.loads(report.read_text())
        valid = tested.returncode == 0 and data['stats']['expected'] == EXPECTED[task] and data['stats']['unexpected'] == 0
        return {'task': task, 'passed': valid, 'stats': data['stats'], 'test_sha256': original,
                'model_calls': 0, 'official_evaluation': False,
                'browser': str(browser), 'playwright_version': data['config']['version']}
    finally:
        server.terminate()
        try:
            tail, _ = server.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill(); tail, _ = server.communicate()
        (work / 'server.log').write_text(''.join(log) + tail)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--checks', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--playwright', type=Path, required=True, help='Installed @playwright/test directory')
    parser.add_argument('--browser', type=Path, required=True)
    parser.add_argument('--task', choices=tuple(EXPECTED))
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output exists; preserve previous evidence')
    results = []
    for task in ([args.task] if args.task else EXPECTED):
        result = run_task(task, args.inputs.resolve(), args.checks.resolve(), args.output.resolve(),
                          args.playwright.resolve(), args.browser.resolve())
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    (args.output / 'summary.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
    raise SystemExit(0 if all(r['passed'] for r in results) else 1)
