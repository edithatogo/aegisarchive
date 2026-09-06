"""Frozen static resource graph and capture acceptance."""
import hashlib
import json
from pathlib import Path
import unittest

FIXTURES = Path(__file__).parent / 'fixtures' / 'mirror'
MANIFEST = json.loads((FIXTURES / 'manifest.json').read_text())

class FixtureContract(unittest.TestCase):
    def test_fixture_hashes_and_paths(self):
        resources = MANIFEST['resources']
        self.assertEqual(len(resources), 9)
        self.assertEqual(len({r['path'] for r in resources}), len(resources))
        for resource in resources:
            self.assertEqual(hashlib.sha256((FIXTURES / resource['file']).read_bytes()).hexdigest(), resource['sha256'])

class DiscoveryContract(unittest.TestCase):
    def test_html_parity_vectors(self):
        from cli.mirror_resources import discover
        for v in json.loads((FIXTURES / 'discovery.json').read_text()):
            self.assertEqual([x['url'] for x in discover(v['text'], v['mime'], v['url'])['resources']], v['expected'])

class CliCaptureContract(unittest.TestCase):
    def test_complete_graph_and_redirect_bytes(self):
        import subprocess, sys, tempfile, threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        routes = {x['path']: x for x in MANIFEST['resources']}
        hits = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                hits.append(self.path)
                item = routes.get(self.path)
                if not item:
                    self.send_response(404); self.end_headers(); return
                self.send_response(item['status'])
                self.send_header('Content-Type', item['mime'])
                if item['location']: self.send_header('Location', item['location'])
                self.end_headers()
                self.wfile.write((FIXTURES / item['file']).read_bytes())
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            with tempfile.TemporaryDirectory() as td:
                profile = {'target': {'allowed_domains':['127.0.0.1'], 'seed_urls':{'tier_1_core':[f'http://127.0.0.1:{server.server_port}/']}, 'max_depth':5, 'max_pages':50}, 'politeness':{'min_delay_ms':1,'max_delay_ms':1,'max_requests_per_minute':10000,'burst_limit':100}}
                p = Path(td)/'profile.json'; p.write_text(json.dumps(profile))
                run = subprocess.run([sys.executable, 'cli/aegis_cli.py', '--profile',str(p),'--output-dir',td],capture_output=True,timeout=30)
                self.assertEqual(run.returncode,0,run.stderr)
                lines = next(Path(td).glob('*.cdx')).read_text().splitlines()[1:]
                from urllib.parse import urlsplit
                captured = {urlsplit(l.split()[2]).path + ('?' + urlsplit(l.split()[2]).query if urlsplit(l.split()[2]).query else ''):l.split()[5] for l in lines}
                self.assertEqual(captured,{x['path']:x['sha256'] for x in MANIFEST['resources']})
                self.assertTrue(all(hits.count(x)==1 for x in routes), hits)
                receipt = json.loads(next(Path(td).glob('*.coverage.json')).read_text())
                self.assertTrue(receipt['complete'])
                self.assertEqual(receipt['counts']['captured'],9)
                self.assertEqual(receipt['archives']['warc']['sha256'],hashlib.sha256(next(Path(td).glob('*.warc')).read_bytes()).hexdigest())
                warc = next(Path(td).glob('*.warc'))
                check = subprocess.run([sys.executable,'cli/warc_verify.py',str(warc)],capture_output=True)
                self.assertEqual(check.returncode,0,check.stderr)
        finally:
            server.shutdown();server.server_close();thread.join()

if __name__ == '__main__':
    unittest.main()
