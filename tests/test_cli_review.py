"""Loopback-only regression for redirect scope and decoded archival payloads."""
import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from cli.aegis_cli import canonicalize_url


class CliReviewTests(unittest.TestCase):
    def test_canonicalization_preserves_parameter_order_and_ipv6(self):
        self.assertEqual(canonicalize_url('http://[::1]:80/a;b?x=2&x=1'), 'http://[::1]/a;b?x=2&x=1')

    def test_redirect_scope_and_compressed_body(self):
        hits = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                hits.append(self.path)
                if self.path == '/':
                    self.send_response(302)
                    self.send_header('Location', '/compressed')
                    self.end_headers()
                elif self.path == '/external':
                    self.send_response(302)
                    self.send_header('Location', f'http://localhost:{self.server.server_port}/forbidden')
                    self.end_headers()
                else:
                    body = gzip.compress(b'<a href="/external">next</a>')
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html')
                    self.send_header('Content-Encoding', 'gzip')
                    self.end_headers()
                    self.wfile.write(body)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as td:
                profile = {'target': {'allowed_domains': ['127.0.0.1'], 'seed_urls': {'tier_1_core': [f'http://127.0.0.1:{server.server_port}/']}, 'max_pages': 10}, 'politeness': {'min_delay_ms': 250, 'max_delay_ms': 250}}
                p = Path(td) / 'profile.json'
                p.write_text(json.dumps(profile))
                result = subprocess.run([sys.executable, 'cli/aegis_cli.py', '--profile', str(p), '--output-dir', td], capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                data = next(Path(td).glob('*.warc')).read_bytes()
                self.assertIn(b'<a href="/external">next</a>', data)
                self.assertNotIn(b'content-encoding:', data.lower())
                self.assertEqual(hits, ['/robots.txt', '/', '/compressed', '/external'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
