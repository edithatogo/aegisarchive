import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from cli.capture_bridge import CaptureBridge
from cli.launch import AegisArchiveHandler


class CaptureBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.seen = []
        seen = self.seen
        class Source(BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append((self.path, self.headers.get('Cookie')))
                if self.path == '/redirect':
                    self.send_response(302); self.send_header('Location', 'http://outside.test/never')
                else:
                    self.send_response(200)
                self.send_header('Set-Cookie', 'private-session=secret')
                self.end_headers(); self.wfile.write(b'<h1>saved</h1>')
            def log_message(self, *args): pass
        self.source = ThreadingHTTPServer(('127.0.0.1', 0), Source)
        threading.Thread(target=self.source.serve_forever, daemon=True).start()
        self.url = 'http://127.0.0.1:' + str(self.source.server_port)
        class Handler(AegisArchiveHandler): pass
        self.station = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        Handler.allowed_hosts = {'127.0.0.1:' + str(self.station.server_port)}
        self.bridge = CaptureBridge(self.temp.name, self.station.server_port)
        self.station.capture_bridge = self.bridge
        threading.Thread(target=self.station.serve_forever, daemon=True).start()
        self.station_url = 'http://127.0.0.1:' + str(self.station.server_port)
        self.profile = {'target': {'allowed_domains':['127.0.0.1']}, 'politeness': {'min_delay_ms':250,'max_delay_ms':250,'max_requests_per_minute':300}}

    def tearDown(self):
        self.station.shutdown(); self.station.server_close()
        self.source.shutdown(); self.source.server_close()
        self.temp.cleanup()

    def test_token_and_same_origin_are_required(self):
        path = self.station_url + '/__station/capture/session'
        with self.assertRaises(urllib.error.HTTPError) as error: urllib.request.urlopen(path)
        self.assertEqual(error.exception.code, 403)
        req = urllib.request.Request(path, headers={'X-Aegis-UI':'1'})
        with urllib.request.urlopen(req) as response: token = json.load(response)['token']
        for headers in ({}, {'X-Capture-Token':token,'Origin':'https://outside.test'}, {'X-Capture-Token':token,'Sec-Fetch-Site':'cross-site'}):
            req = urllib.request.Request(self.station_url + '/__station/capture/start', data=json.dumps({'profile':self.profile}).encode(), headers=headers)
            with self.assertRaises(urllib.error.HTTPError) as error: urllib.request.urlopen(req)
            self.assertEqual(error.exception.code, 403)
        self.assertEqual(self.seen, [])

    def test_scope_redirect_and_station_ceiling(self):
        sid = self.bridge.configure(self.profile)['id']
        result = self.bridge.fetch(sid, self.url + '/redirect')
        self.assertEqual(result['status'], 302)
        self.assertEqual(len(self.seen), 1)
        for url in ['http://outside.test/never','file:///private.txt',self.station_url+'/__station/capture/session', self.url.replace('://','://user:secret@')]:
            with self.assertRaises(ValueError): self.bridge.fetch(sid, url)
        self.assertEqual(len(self.seen), 1)

    def test_credentials_are_scoped_and_not_returned_or_logged(self):
        self.profile['authentication']={'mode':'cookies_env','source':'private=credential','allowed_domains':['127.0.0.1']}
        session = self.bridge.configure(self.profile)
        result = self.bridge.fetch(session['id'], self.url)
        self.assertEqual(self.seen[0][1], 'private=credential')
        self.assertNotIn('set-cookie', result['headers'])
        self.assertEqual(result['request']['headers']['cookie'], '[REDACTED]')
        log = Path(session['log_file']).read_text()
        self.assertNotIn('credential', log)
        self.assertNotIn('private-session', log)
        self.assertIn('"status": 200', log)

    def test_stop_and_explicit_session_lifecycle(self):
        sid = self.bridge.configure(self.profile)['id']
        with self.assertRaises(ValueError): self.bridge.configure(self.profile)
        self.bridge.close(sid)
        with self.assertRaises(ValueError): self.bridge.fetch(sid, self.url)
        self.assertEqual(self.seen, [])
        self.assertNotEqual(self.bridge.configure(self.profile)['id'], sid)

    def test_auth_scope_and_pacing_validation(self):
        for change in [{'target':{'allowed_domains':[]}}, {'politeness':{'min_delay_ms':float('nan')}}, {'authentication':{'allowed_domains':['outside.test']}}]:
            with self.assertRaises(ValueError): self.bridge.configure({**self.profile, **change})

    def test_conservative_schema_bounds_and_recovery(self):
        profile = {**self.profile, 'politeness': {'min_delay_ms':60000,'max_delay_ms':120000,'burst_limit':20,'cooldown_seconds':3600}}
        old = self.bridge.configure(profile)['id']
        self.bridge.recover()
        self.assertNotEqual(old, self.bridge.configure(self.profile)['id'])

    def test_request_metadata_matches_forwarded_options(self):
        sid = self.bridge.configure(self.profile)['id']
        options = {'method':'GET','headers':{'Accept':'application/pdf','X-Preservation-Agent':'AegisArchive/1.0'}}
        result = self.bridge.fetch(sid, self.url, options)
        self.assertEqual(result['request']['headers']['accept'], 'application/pdf')
        self.assertEqual(result['request']['headers']['x-preservation-agent'], 'AegisArchive/1.0')
        with self.assertRaises(ValueError): self.bridge.fetch(sid, self.url, {'method':'POST'})
        with self.assertRaises(ValueError): self.bridge.fetch(sid, self.url, {'headers':{'Cookie':'hidden'}})
