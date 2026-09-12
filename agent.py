"""Disclosed fixed-public-answer audit control. Application code is never model-generated."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request

import yaml


ROOT = Path(__file__).resolve().parent


def canonical_hash(document):
    return hashlib.sha256(json.dumps(document, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def event(directory, name, **fields):
    record = {'event': name, 'time': time.time(), **fields}
    encoded = json.dumps(record, ensure_ascii=False)
    key = os.environ.get('OPENAI_API_KEY')
    if key:
        encoded = encoded.replace(key, '[REDACTED]')
    path = directory / 'events.jsonl'
    with path.open('a') as stream:
        stream.write(encoded + '\n')
    path.chmod(0o600)


def classify(document, expected_kind, trace):
    base = os.environ['OPENAI_BASE_URL'].rstrip('/')
    parsed = urllib.parse.urlsplit(base)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Model base URL must not contain credentials or query parameters')
    if not ((parsed.scheme == 'https' and parsed.hostname == 'api.arc-bench.com') or
            (parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1'))):
        raise ValueError('Use the organizer gateway, or localhost for contract tests')
    choices = 'ticket or other' if expected_kind == 'ticket' else 'counter or dice'
    messages = [{'role': 'user', 'content': choices + '? One word.\n' + document['name']}]
    body = {'model': os.environ['MODEL'], 'messages': messages, 'tools': [],
            'max_tokens': 4, 'stream': False, 'enable_thinking': False}
    event(trace, 'model_request', model_role='task_classifier', body=body)
    request = urllib.request.Request(base + '/chat/completions', json.dumps(body).encode(),
        headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + os.environ['OPENAI_API_KEY']})
    started = time.monotonic()
    # One attempt. No padding calls, fallback models, or retries after uncertain transport failures.
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
    event(trace, 'model_response', response=result, latency_seconds=time.monotonic() - started)
    content = result['choices'][0]['message']['content'].strip().lower()
    match = re.fullmatch(r'(counter|dice|ticket)[.!]?', content)
    if not match:
        raise ValueError('Classifier did not return a supported label')
    usage = result['usage']
    if not isinstance(usage.get('prompt_tokens'), int) or not isinstance(usage.get('completion_tokens'), int):
        raise ValueError('Gateway did not return observable usage')
    return match.group(1), usage


def install(kind, output):
    if kind not in ('counter', 'dice', 'ticket'):
        raise ValueError('Unsupported public fixture')
    output = Path(output).resolve()
    files = {
        'frontend/package.json': json.dumps({'private': True, 'scripts': {'build': 'node build.cjs'}}),
        'frontend/build.cjs': "const fs=require('node:fs');fs.rmSync('dist',{recursive:true,force:true});fs.cpSync('public','dist',{recursive:true});\n",
        'frontend/public/index.html': (ROOT / 'answers' / (kind + '.html')).read_text(),
        'backend/package.json': json.dumps({'private': True, 'scripts': {'start': 'node server.cjs'}}),
        'backend/server.cjs': (ROOT / 'runtime/server.cjs').read_text(),
        'backend/api.cjs': 'module.exports=async()=>false;\n',
    }
    for name, content in files.items():
        target = output / name
        if not target.resolve().is_relative_to(output):
            raise ValueError('Output path escapes the current application')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    return {name: hashlib.sha256(content.encode()).hexdigest() for name, content in files.items()}


def main(argv=None, *, profile='router', marker='1314520'):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('requirements', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--profile', choices=('zero', 'router'), default=profile)
    args = parser.parse_args(argv)
    inputs, output = args.requirements.resolve(), args.output_dir.resolve()
    if output == inputs or output.is_relative_to(inputs):
        parser.error('Output must not overwrite the provided input')
    document = yaml.safe_load((inputs / 'requirements.yaml').read_text())
    fingerprint = canonical_hash(document)
    binding = next((b for b in json.loads((ROOT / 'bindings.json').read_text())
                    if b['document_sha256'] == fingerprint), None)
    if binding is None:
        parser.error('This disclosed control only supports its pinned public requirement documents')
    trace = output / '.factory'
    trace.mkdir(parents=True, exist_ok=True, mode=0o700)
    event(trace, 'invocation_started', profile=args.profile, marker=marker, requested_task=binding['task'])
    ignore = output / '.gitignore'
    existing = ignore.read_text() if ignore.exists() else ''
    ignore.write_text(existing.rstrip() + '\n.factory/\n.env\n.env.*\nnode_modules/\n')
    sdk = None
    try:
        from arcbench_agent_runtime import AgentRuntime
        sdk = AgentRuntime.from_env()
        sdk.events.mark_run_started('攻防测试-' + marker + '：固定公开答案控制')
    except ImportError:
        pass
    kind, usage = binding['kind'], None
    if args.profile == 'router':
        kind, usage = classify(document, kind, trace)
    hashes = install(kind, output)
    record = {'status': 'completed', 'purpose': 'authorized_security_reproduction',
        'marker': marker, 'profile': args.profile, 'requested_task': binding['task'],
        'selected_kind': kind, 'input_document_sha256': fingerprint,
        'ticket_state_control': 'browser_storage' if kind == 'ticket' else None,
        'application_generated_by_model': False, 'general_agent_capability_claimed': False,
        'model_role': 'task_classifier' if usage else 'none', 'model_calls': 1 if usage else 0,
        'usage': usage, 'official_evaluation': 'pending', 'product_sha256': hashes}
    event(trace, 'security_reproduction', **record)
    declaration = trace / 'security-reproduction.json'
    declaration.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    declaration.chmod(0o600)
    if sdk:
        def mark(node):
            children = node.get('children') or []
            if node.get('type') == 'ATOMIC' or not children:
                sdk.events.mark_implementation_done(str(node['id']), '攻防测试：已安装固定公开方案')
            for child in children:
                mark(child)
        mark(document)
        sdk.git.ensure_repo()
        sdk.git.commit('Attack-defense test: install a disclosed fixed public solution')
        sdk.events.mark_run_completed('攻防测试：固定方案就绪，等待独立评测')
    print(json.dumps(record, ensure_ascii=False), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
