import json
import io
import sys
import subprocess
from unittest import mock
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
    def test_retry_after_survives_failed_body_read(self):
        from cli.capture_bridge import CaptureFailure
        archive = self.bridge.archives.start()
        sid = self.bridge.configure(self.profile, archive['archive_id'], archive['lease'])['id']
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.code, response.headers = 429, {'Retry-After':'120'}
        response.read.side_effect = OSError('Synthetic truncated response')
        with mock.patch('cli.capture_bridge.urllib.request.build_opener') as build:
            build.return_value.open.return_value = response
            with self.assertRaises(CaptureFailure):
                self.bridge.fetch(sid, self.url)
        saved = json.loads((self.bridge.archives.folder(archive['archive_id']) / 'native-pacing.json').read_text())
        self.assertGreaterEqual(saved['domain_cooldowns']['127.0.0.1']-saved['saved_at_ms'],119000)
        self.assertEqual(saved['consecutive_errors'],1)

    def test_reopen_serializes_ownership_and_stale_fetch_cannot_run(self):
        import base64
        archive = self.bridge.archives.start()
        sid = self.bridge.configure(self.profile, archive['archive_id'], archive['lease'])['id']
        self.bridge.persist_pacing(self.bridge.session)
        self.bridge.archives.chunk(archive['archive_id'],'warc',0,base64.b64encode(b'prefix').decode(),archive['lease'])
        checkpoint = self.bridge.archives.checkpoint(archive['archive_id'],0,{},'a'*64,archive['lease'])
        entered, release = threading.Event(), threading.Event()
        original = self.bridge.archives.reopen
        result = []
        def held_reopen(*args):
            entered.set()
            if not release.wait(5): raise AssertionError('Reopen barrier timed out')
            return original(*args)
        with mock.patch.object(self.bridge.archives,'reopen',side_effect=held_reopen):
            worker = threading.Thread(target=lambda:result.append(self.bridge.reopen_archive(
                archive['archive_id'],checkpoint['generation'],'a'*64)))
            worker.start()
            try:
                self.assertTrue(entered.wait(5))
                acquired = self.bridge.lock.acquire(blocking=False)
                if acquired: self.bridge.lock.release()
                self.assertFalse(acquired,'Ownership transition must retain bridge lock')
            finally:
                release.set(); worker.join(5)
        self.assertEqual(len(result),1)
        with self.assertRaises(ValueError):
            self.bridge.configure(self.profile,archive['archive_id'],archive['lease'])
        with self.assertRaises(ValueError):
            self.bridge.fetch(sid,self.url)
        current = self.bridge.configure(self.profile,archive['archive_id'],result[0]['lease'])
        old_session = self.bridge.session
        self.bridge.archives.reopen(archive['archive_id'],result[0]['generation'],'a'*64)
        with self.assertRaises(ValueError):
            self.bridge.fetch(current['id'],self.url)
        with self.assertRaises(ValueError):
            self.bridge.persist_pacing(old_session)
        self.assertEqual(self.seen,[])

    def test_received_retry_after_is_journaled_before_response_is_returned(self):
        archive = self.bridge.archives.start()
        sid = self.bridge.configure(self.profile, archive['archive_id'], archive['lease'])['id']
        response = self.bridge.fetch(sid, self.url + '/slow')
        self.assertEqual(response['status'], 429)
        path = self.bridge.archives.folder(archive['archive_id']) / 'native-pacing.json'
        saved = json.loads(path.read_text())
        self.assertGreater(saved['domain_cooldowns']['127.0.0.1'], saved['saved_at_ms'])
        self.bridge.recover()
        self.bridge.configure(self.profile, archive['archive_id'], archive['lease'])
        restored = self.bridge.session['engine'].export_state()
        self.assertGreaterEqual(restored['domain_cooldowns']['127.0.0.1'],
                                saved['domain_cooldowns']['127.0.0.1'])

    def test_archive_bound_pacing_survives_browser_session_replacement(self):
        archive = self.bridge.archives.start()
        self.addCleanup(self.bridge.archives.close)
        sid = self.bridge.configure(self.profile, archive['archive_id'], archive['lease'])['id']
        engine = self.bridge.session['engine']
        engine.record_failure(self.url, 429, '20')
        self.bridge.persist_pacing(self.bridge.session)
        expected = engine.export_state()
        self.bridge.recover()
        self.bridge.configure(self.profile, archive['archive_id'], archive['lease'])
        restored = self.bridge.session['engine'].export_state()
        self.assertEqual(restored['domain_cooldowns'], expected['domain_cooldowns'])
        self.assertNotEqual(self.bridge.session['id'], sid)
        journal = self.bridge.archives.folder(archive['archive_id']) / 'native-pacing.json'
        self.assertNotIn('authentication', journal.read_text())
        self.bridge.recover()
        journal.write_text('{}')
        with self.assertRaises(ValueError):
            self.bridge.configure(self.profile, archive['archive_id'], archive['lease'])

    def rule_options(self, match, *, kind='asset', url=None):
        return {'rule_context': {'config': {'version': 1, 'rules': [
            {'id': 'deny', 'match': match, 'decision': {'download': False}}]},
            'resource': {'url': url or self.url, 'kind': kind, 'depth': 0}}}

    def test_rules_reject_context_before_network(self):
        sid = self.bridge.configure(self.profile)['id']
        options = [self.rule_options({}, url=self.url + '/different'),
                   {'rule_context': None}, {'rule_context': {}},
                   {'rule_context': {'config': {'version': 2, 'rules': []},
                                     'resource': {'url': self.url, 'kind': 'asset', 'depth': 0}}}]
        with mock.patch('cli.capture_bridge.urllib.request.build_opener') as build:
            for option in options:
                with self.subTest(option=option), self.assertRaises(ValueError):
                    self.bridge.fetch(sid, self.url, option)
            build.assert_not_called()
        self.assertEqual(self.seen, [])

    def test_predecided_rule_denial_never_opens_network(self):
        sid = self.bridge.configure(self.profile)['id']
        with mock.patch('cli.capture_bridge.urllib.request.build_opener') as build:
            value = self.bridge.fetch(sid, self.url, self.rule_options({'path_prefix': '/'}))
        build.assert_not_called()
        self.assertEqual(value['body'], '')
        self.assertFalse(value['rule_decision']['download'])

    def test_response_rules_do_not_read_excluded_bodies(self):
        sid = self.bridge.configure(self.profile)['id']
        cases = [({'mime': 'application/pdf'}, {'Content-Type': 'application/pdf'}, 200),
                 ({'min_bytes': 10}, {'Content-Length': '100'}, 200),
                 ({'min_bytes': 10}, {'Content-Length': 'invalid'}, 200),
                 ({'min_bytes': 10}, {'Content-Length': '100', 'Content-Encoding': 'gzip'}, 200),
                 ({'min_bytes': 10}, {}, 503)]
        for match, headers, status in cases:
            response = mock.MagicMock()
            response.__enter__.return_value = response
            response.code, response.headers = status, headers
            with self.subTest(match=match, headers=headers), \
                 mock.patch('cli.capture_bridge.urllib.request.build_opener') as build, \
                 mock.patch.object(self.bridge.session['engine'], 'record_failure') as failure:
                build.return_value.open.return_value = response
                value = self.bridge.fetch(sid, self.url, self.rule_options(match))
                response.read.assert_not_called()
                self.assertEqual(value['status'], status)
                self.assertEqual(value['body'], '')
                self.assertFalse(value['rule_decision']['download'])
                if status == 503:
                    failure.assert_called_once_with(self.url, 503, None)

    def test_sitemap_native_body_cap(self):
        sid = self.bridge.configure(self.profile)['id']
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.code, response.headers = 200, {}
        response.read.return_value = b'<urlset/>'
        options = self.rule_options({'path_prefix': '/excluded'}, kind='sitemap')
        with mock.patch('cli.capture_bridge.urllib.request.build_opener') as build:
            build.return_value.open.return_value = response
            self.bridge.fetch(sid, self.url, options)
        response.read.assert_called_once_with(262144 + 1)
        from cli.capture_bridge import CaptureFailure
        response.read.return_value = b'x' * (262144 + 1)
        with mock.patch('cli.capture_bridge.urllib.request.build_opener') as build:
            build.return_value.open.return_value = response
            with self.assertRaises(CaptureFailure) as caught:
                self.bridge.fetch(sid, self.url, options)
        self.assertEqual(caught.exception.details['reason_code'], 'response_too_large')

    def test_response_rule_nonmatch_retains_body(self):
        from email.message import Message
        sid = self.bridge.configure(self.profile)['id']
        response = mock.MagicMock()
        response.__enter__.return_value = response
        headers = Message()
        headers['Content-Length'] = '2'
        headers['Content-Length'] = '2'
        response.code, response.headers = 200, headers
        response.read.return_value = b'ok'
        with mock.patch('cli.capture_bridge.urllib.request.build_opener') as build:
            build.return_value.open.return_value = response
            value = self.bridge.fetch(sid, self.url, self.rule_options({'min_bytes': 10}))
        self.assertEqual(value['body'], 'b2s=')
        self.assertTrue(value['rule_decision']['download'])

    def test_conflicting_response_metadata_holds_body(self):
        from email.message import Message
        sid = self.bridge.configure(self.profile)['id']
        for name, values, match in [
                ('Content-Type', ['application/pdf', 'text/html'], {'mime': 'application/pdf'}),
                ('Content-Type', ['text/html', 'application/pdf'], {'mime': 'application/pdf'}),
                ('Content-Length', ['100', '2'], {'min_bytes': 10}),
                ('Content-Length', ['2', '100'], {'min_bytes': 10}),
                ('Content-Length', ['+100'], {'min_bytes': 10})]:
            headers = Message()
            for value in values:
                headers[name] = value
            response = mock.MagicMock()
            response.__enter__.return_value = response
            response.code, response.headers = 200, headers
            with self.subTest(name=name, values=values), \
                    mock.patch('cli.capture_bridge.urllib.request.build_opener') as build:
                build.return_value.open.return_value = response
                value = self.bridge.fetch(sid, self.url, self.rule_options(match))
                response.read.assert_not_called()
                self.assertEqual(value['rule_decision']['state'], 'needs_metadata')

    def test_transfer_encoding_makes_declared_size_unknown(self):
        sid = self.bridge.configure(self.profile)['id']
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.code = 200
        response.headers = {'Content-Length': '2', 'Transfer-Encoding': 'chunked'}
        response.read.return_value = b'x' * 100
        with mock.patch('cli.capture_bridge.urllib.request.build_opener') as build:
            build.return_value.open.return_value = response
            value = self.bridge.fetch(sid, self.url, self.rule_options({'min_bytes': 10}))
        response.read.assert_not_called()
        self.assertEqual(value['body'], '')
        self.assertEqual(value['rule_decision']['state'], 'needs_metadata')
        self.assertEqual(value['rule_decision']['missing'], ['bytes'])

    def test_comma_joined_mime_is_unknown(self):
        sid = self.bridge.configure(self.profile)['id']
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.code = 200
        response.headers = {'Content-Type': 'text/plain, application/pdf'}
        response.read.return_value = b'synthetic'
        with mock.patch('cli.capture_bridge.urllib.request.build_opener') as build:
            build.return_value.open.return_value = response
            value = self.bridge.fetch(sid, self.url, self.rule_options({'mime': 'application/pdf'}))
        response.read.assert_not_called()
        self.assertEqual(value['body'], '')
        self.assertEqual(value['rule_decision']['state'], 'needs_metadata')
        self.assertEqual(value['rule_decision']['missing'], ['mime'])

    def test_incomplete_body_returns_capture_diagnostic(self):
        from http.client import IncompleteRead
        from cli.capture_bridge import CaptureFailure
        sid = self.bridge.configure(self.profile)['id']
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.code, response.headers = 200, {}
        response.read.side_effect = IncompleteRead(b'synthetic', 100)
        with mock.patch('cli.capture_bridge.urllib.request.build_opener') as build:
            build.return_value.open.return_value = response
            with self.assertRaises(CaptureFailure) as caught:
                self.bridge.fetch(sid, self.url)
        self.assertEqual(caught.exception.details['error_type'], 'IncompleteRead')
        self.assertEqual(caught.exception.details['stage'], 'response_body')

    def test_alias_scope_is_explicit(self):
        self.profile['target'] = {'allowed_domains': ['primary.test'],
                                  'domain_aliases': {'primary.test': ['alias.test']}}
        sid = self.bridge.configure(self.profile)['id']
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.code, response.headers = 302, {'Location': 'http://redirect.test/'}
        response.read.return_value = b''
        with mock.patch('cli.capture_bridge.urllib.request.build_opener') as build:
            build.return_value.open.return_value = response
            self.bridge.fetch(sid, 'http://alias.test/')
            with self.assertRaises(ValueError):
                self.bridge.fetch(sid, 'http://redirect.test/')
            self.assertEqual(build.return_value.open.call_count, 1)
        self.assertNotIn('redirect.test', self.bridge.session['hosts'])
        self.bridge.close(sid)
        self.profile['target']['domain_aliases'] = {'other.test': ['alias.test']}
        with self.assertRaises(ValueError):
            self.bridge.configure(self.profile)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.seen = []
        seen = self.seen
        class Source(BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append((self.path, self.headers.get('Cookie')))
                if self.path == '/redirect':
                    self.send_response(302); self.send_header('Location', 'http://outside.test/never')
                elif self.path == '/slow':
                    self.send_response(429); self.send_header('Retry-After', '20')
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
        self.bridge = CaptureBridge(Path(self.temp.name) / 'logs', self.station.server_port)
        self.station.capture_bridge = self.bridge
        threading.Thread(target=self.station.serve_forever, daemon=True).start()
        self.station_url = 'http://127.0.0.1:' + str(self.station.server_port)
        self.profile = {'target': {'allowed_domains':['127.0.0.1']}, 'politeness': {'min_delay_ms':250,'max_delay_ms':250,'max_requests_per_minute':300}}

    def tearDown(self):
        self.station.shutdown(); self.station.server_close()
        self.source.shutdown(); self.source.server_close()
        self.bridge.archives.close()
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

    def test_archive_routes_require_token_and_bound_writes(self):
        url = self.station_url + '/__station/capture/archive-start'
        for headers in ({}, {'X-Capture-Token': self.bridge.token, 'Origin': 'https://outside.test'}):
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(urllib.request.Request(url, data=b'{}', headers=headers))
            self.assertEqual(caught.exception.code, 403)
        headers = {'X-Capture-Token': self.bridge.token}
        with urllib.request.urlopen(urllib.request.Request(url, data=b'{}', headers=headers)) as response:
            sid = json.load(response)['archive_id']
        payload = json.dumps({'archive_id': sid, 'kind': '../escape', 'offset': 0, 'data': 'YQ=='}).encode()
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(urllib.request.Request(self.station_url + '/__station/capture/archive-chunk', data=payload, headers=headers))
        self.assertEqual(caught.exception.code, 400)
        with mock.patch.object(self.bridge.archives, 'chunk', side_effect=OSError('private synthetic path')):
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(urllib.request.Request(self.station_url + '/__station/capture/archive-chunk', data=payload, headers=headers))
            self.assertEqual(caught.exception.code, 507)
            body = json.load(caught.exception)
            self.assertEqual(body['diagnostic']['stage'], 'storage')
            self.assertNotIn('private synthetic path', json.dumps(body))
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


class LauncherEncodingTests(unittest.TestCase):
    def test_legacy_windows_output_does_not_prevent_startup(self):
        from cli import launch
        raw = io.BytesIO()
        output = io.TextIOWrapper(raw, encoding='cp1252')
        server = mock.MagicMock()
        server.serve_forever.side_effect = KeyboardInterrupt
        with mock.patch.object(sys, 'argv', ['launch.py','--no-browser']), \
             mock.patch.object(sys, 'stdout', output), \
             mock.patch.object(launch, 'probe_existing_station', return_value=False), \
             mock.patch.object(launch, 'find_available_port', return_value=8765), \
             mock.patch.object(launch, 'WEB_DIR', '/synthetic/\u4e00/web'), \
             mock.patch.object(launch, 'ThreadingHTTPServer', return_value=server):
            launch.main()
            output.flush()
            self.assertIn(b'Local Web Console:', raw.getvalue())
            server.serve_forever.assert_called_once()
            server.server_close.assert_called_once()

    def test_isolated_portable_launcher_imports_its_sibling_module(self):
        launcher = Path(__file__).resolve().parents[1] / 'cli' / 'launch.py'
        with tempfile.TemporaryDirectory() as elsewhere:
            result = subprocess.run([sys.executable, '-I', '-B', str(launcher), '--help'],
                                    cwd=elsewhere, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        self.assertIn(b'AegisArchive Web Console Launcher', result.stdout)
