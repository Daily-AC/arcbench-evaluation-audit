import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from agent import classify, install
from scripts.build_package import build


class AgentContractTests(unittest.TestCase):
    def test_real_http_classifier_output_selects_the_fixture_and_redacts_key(self):
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                requests.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                reply = {'choices': [{'message': {'role': 'assistant', 'content': 'dice'}}],
                         'usage': {'prompt_tokens': 8, 'completion_tokens': 1, 'total_tokens': 9},
                         'synthetic_debug': 'synthetic-secret-key'}
                raw = json.dumps(reply).encode()
                self.send_response(200);self.send_header('Content-Length', str(len(raw)));self.end_headers();self.wfile.write(raw)
            def log_message(self, *_):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {
                'OPENAI_BASE_URL': f'http://127.0.0.1:{server.server_port}',
                'OPENAI_API_KEY': 'synthetic-secret-key', 'MODEL': 'synthetic-model'}):
                root = Path(temp)
                kind, usage = classify({'name': 'Counter'}, 'counter', root)
                self.assertEqual(kind, 'dice')
                self.assertEqual(len(requests), 1)
                self.assertEqual(requests[0]['max_tokens'], 4)
                self.assertFalse(requests[0]['enable_thinking'])
                self.assertEqual(usage['total_tokens'], 9)
                self.assertNotIn('synthetic-secret-key', (root / 'events.jsonl').read_text())
                install(kind, root / 'app')
                self.assertIn('>Roll<', (root / 'app/frontend/public/index.html').read_text())
        finally:
            server.shutdown();server.server_close();thread.join()

    def test_package_is_explicit_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'audit.zip'
            result = build(target)
            self.assertEqual(result['marker'], '1314520')
            self.assertEqual(len(result['members']), 9)
            self.assertFalse(any(name.startswith(('runs/', 'evidence/')) for name in result['members']))
            with self.assertRaises(ValueError):
                build(target)


if __name__ == '__main__':
    unittest.main()
