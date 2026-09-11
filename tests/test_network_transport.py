import json
import socket
import ssl
import io
import threading
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import Mock, patch

from cli.network_transport import NetworkTrace, route_handlers
from cli.windows_proxy import ProxyDiscoveryError


class RouteTests(unittest.TestCase):
    def test_new_stages_survive_sanitized_diagnostic_intake(self):
        from scripts.diagnostic_intake import ingest
        stages = ['proxy_resolution', 'dns', 'tcp_connect', 'proxy_tunnel', 'tls', 'request_headers', 'response_headers']
        report = {'schema_version': 1, 'coverage': {}, 'events': [
            {'stage': stage, 'error_type': 'ProxyDiscoveryError' if stage == 'proxy_resolution' else 'URLError'}
            for stage in stages]}
        self.assertEqual({item['stage'] for item in ingest(report)['findings']}, set(stages))

    def test_auto_proxy_and_direct_results_are_explicit(self):
        for proxy, count, expected in [('proxy.example.test:8080', 1, 'proxy'), (None, 0, 'direct')]:
            events = []
            api = Mock()
            api.settings.return_value = {'pac_url': 'https://secret.example.test/pac?token=private', 'auto_detect': False}
            api.resolve.return_value = (proxy, count)
            trace = NetworkTrace(lambda **event: events.append(event))
            with patch('cli.network_transport.sys.platform', 'win32'), patch('cli.network_transport.urllib.request.getproxies_environment', return_value={}), patch('cli.network_transport.WindowsProxyAPI', return_value=api):
                handlers = route_handlers('https://target.example.test/', trace)
            self.assertEqual(events[-1]['route'], expected)
            self.assertEqual(events[-1]['source'], 'windows_auto')
            self.assertNotIn('secret', json.dumps(events))
            self.assertNotIn('private', json.dumps(events))
            self.assertNotIn('proxy.example.test', json.dumps(events))
            self.assertEqual(len(handlers), 1)

    def test_explicit_environment_precedes_windows_auto(self):
        trace = NetworkTrace(lambda **event: None)
        with patch('cli.network_transport.sys.platform', 'win32'), patch('cli.network_transport.urllib.request.getproxies_environment', return_value={'http': 'http://proxy.example.test:80'}), patch('cli.network_transport.WindowsProxyAPI') as api:
            route_handlers('http://target.example.test/', trace)
        api.assert_not_called()

    def test_discovery_failure_does_not_fall_back(self):
        api = Mock(); api.settings.side_effect = ProxyDiscoveryError(12180)
        trace = NetworkTrace(lambda **event: None)
        with patch('cli.network_transport.sys.platform', 'win32'), patch('cli.network_transport.urllib.request.getproxies_environment', return_value={}), patch('cli.network_transport.WindowsProxyAPI', return_value=api):
            with self.assertRaises(ProxyDiscoveryError): route_handlers('http://target.example.test/', trace)
        self.assertEqual(trace.stage, 'proxy_resolution')

    def test_dns_failure_is_attributed_without_addresses(self):
        events = []; trace = NetworkTrace(lambda **event: events.append(event))
        with patch('cli.network_transport.socket.getaddrinfo', side_effect=socket.gaierror(-2, 'private error')):
            with self.assertRaises(socket.gaierror): trace.connect(('private.example.test', 80), 30)
        self.assertEqual(trace.stage, 'dns')
        self.assertNotIn('private', json.dumps(events))

    def test_tcp_failure_closes_socket(self):
        trace = NetworkTrace(lambda **event: None); sock = Mock()
        sock.connect.side_effect = TimeoutError('private')
        with patch('cli.network_transport.socket.getaddrinfo', return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('192.0.2.1', 80))]), patch('cli.network_transport.socket.socket', return_value=sock):
            with self.assertRaises(TimeoutError): trace.connect(('private.example.test', 80), 30)
        sock.close.assert_called_once()
        self.assertEqual(trace.stage, 'tcp_connect')

    def test_proxy_request_and_tunnel_refusal_use_selected_route(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import urllib.request
        from cli.network_transport import _ResolvedProxy
        seen = []
        class Proxy(BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append(self.path)
                self.send_response(200); self.end_headers(); self.wfile.write(b'proxied')
            def do_CONNECT(self):
                seen.append(self.path)
                self.send_response(407); self.end_headers()
            def log_message(self, *args): pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Proxy)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            proxy = '127.0.0.1:%s' % server.server_port
            trace = NetworkTrace(lambda **event: None)
            opener = urllib.request.build_opener(_ResolvedProxy({'http': proxy, 'https': proxy}), *trace.handlers())
            with patch('urllib.request.proxy_bypass', return_value=True):
                with opener.open('http://unresolvable.example.test/page', timeout=2) as response:
                    self.assertEqual(response.read(), b'proxied')
                with self.assertRaises(urllib.error.URLError):
                    opener.open('https://unresolvable.example.test/', timeout=2)
            self.assertEqual(trace.stage, 'proxy_tunnel')
            self.assertEqual(seen, ['http://unresolvable.example.test/page', 'unresolvable.example.test:443'])
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_tls_verification_error_keeps_stage_and_hostname(self):
        import urllib.request
        trace = NetworkTrace(lambda **event: None)
        context = ssl.create_default_context()
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        sock = Mock()
        with patch.object(trace, 'connect', return_value=sock), patch.object(context, 'wrap_socket', side_effect=ssl.SSLCertVerificationError('private')) as wrap:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), *trace.handlers(context))
            with self.assertRaises(urllib.error.URLError): opener.open('https://example.test/', timeout=2)
            wrap.assert_called_once_with(sock, server_hostname='example.test')
        self.assertEqual(trace.stage, 'tls')

    def test_https_success_uses_supplied_context(self):
        import urllib.request
        trace = NetworkTrace(lambda **event: None)
        context = ssl.create_default_context()
        sock = Mock(); wrapped = Mock()
        wrapped.makefile.return_value = io.BytesIO(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok')
        with patch.object(trace, 'connect', return_value=sock), patch.object(context, 'wrap_socket', return_value=wrapped):
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), *trace.handlers(context))
            with opener.open('https://example.test/', timeout=2) as response:
                self.assertEqual(response.read(), b'ok')
        self.assertEqual(trace.stage, 'response_headers')

    def test_bridge_records_failure_stage_and_numeric_code(self):
        from cli.capture_bridge import CaptureBridge, CaptureFailure
        with tempfile.TemporaryDirectory() as folder:
            bridge = CaptureBridge(folder, 8123)
            session = bridge.configure({'target': {'allowed_domains': ['example.test']}})
            bridge.session['engine'] = Mock()
            bridge.session['engine'].acquire_permission.return_value = {'aborted': False}
            with patch('cli.network_transport.socket.getaddrinfo', side_effect=socket.gaierror(-2, 'secret error')), patch('cli.capture_bridge.route_handlers', return_value=[urllib.request.ProxyHandler({})]):
                with self.assertRaises(CaptureFailure) as caught: bridge.fetch(session['id'], 'http://example.test/')
            self.assertEqual(caught.exception.details['stage'], 'dns')
            self.assertEqual(caught.exception.details['errno'], -2)
            self.assertNotIn('secret error', Path(session['log_file']).read_text())
