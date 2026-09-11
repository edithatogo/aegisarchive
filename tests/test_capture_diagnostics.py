import unittest
import ssl
import socket
import urllib.error
from cli.capture_bridge import failure_details

class DiagnosticsTests(unittest.TestCase):
    def test_native_causes_classified_without_exception_text(self):
        for error, category in [(ssl.SSLError('private'), 'tls'), (socket.gaierror('private'), 'dns'), (TimeoutError('private'), 'timeout')]:
            result = failure_details(urllib.error.URLError(error))
            self.assertEqual(result['category'], category)
            self.assertNotIn('private', str(result))

    def test_oversize_body_keeps_stage_and_reason(self):
        import tempfile
        from unittest.mock import patch, MagicMock
        from cli.capture_bridge import CaptureBridge, CaptureFailure
        with tempfile.TemporaryDirectory() as folder:
            bridge = CaptureBridge(folder, 8123)
            sid = bridge.configure({'target': {'allowed_domains': ['example.test']}})['id']
            bridge.session['engine'] = MagicMock()
            bridge.session['engine'].acquire_permission.return_value = {'aborted': False}
            response = MagicMock()
            response.__enter__.return_value = response
            response.read.return_value = b'12345'
            with patch('cli.capture_bridge.MAX_BODY', 4), patch('cli.capture_bridge.route_handlers', return_value=[]), patch('cli.capture_bridge.urllib.request.build_opener') as opener:
                opener.return_value.open.return_value = response
                with self.assertRaises(CaptureFailure) as caught:
                    bridge.fetch(sid, 'https://example.test/')
            self.assertEqual(caught.exception.details['stage'], 'response_body')
            self.assertEqual(caught.exception.details['reason_code'], 'response_too_large')
