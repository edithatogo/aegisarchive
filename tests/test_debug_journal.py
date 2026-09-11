import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from cli.debug_journal import DebugJournal


class DebugJournalTests(unittest.TestCase):
    def test_debug_endpoints_require_station_token_and_same_origin(self):
        from http.server import ThreadingHTTPServer
        from cli.capture_bridge import CaptureBridge
        from cli.launch import AegisArchiveHandler
        import threading
        import urllib.request
        import urllib.error
        with tempfile.TemporaryDirectory() as folder:
            class Handler(AegisArchiveHandler): pass
            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            host = '127.0.0.1:%s' % server.server_port
            Handler.allowed_hosts = {host}
            server.capture_bridge = CaptureBridge(folder, server.server_port)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            try:
                for action in ('debug-start', 'debug-status', 'debug-events'):
                    for headers in ({}, {'X-Capture-Token': server.capture_bridge.token, 'Origin': 'https://outside.test'}):
                        request = urllib.request.Request('http://' + host + '/__station/capture/' + action, data=b'{}', headers=headers)
                        with self.assertRaises(urllib.error.HTTPError) as caught: urllib.request.urlopen(request)
                        self.assertEqual(caught.exception.code, 403); caught.exception.close()
                self.assertFalse(server.capture_bridge.debug.status()['active'])
                request = urllib.request.Request('http://' + host + '/__station/capture/debug-start', data=b'{}', headers={'X-Capture-Token': server.capture_bridge.token})
                with urllib.request.urlopen(request) as response: result = json.load(response)
                self.assertTrue(Path(result['log_file']).is_file())
            finally:
                server.shutdown(); server.server_close(); thread.join()

    def test_stop_and_recover_remain_available_after_debug_failure(self):
        from cli.capture_bridge import CaptureBridge
        with tempfile.TemporaryDirectory() as folder:
            bridge = CaptureBridge(folder, 8123)
            session = bridge.configure({'target': {'allowed_domains': ['example.test']}})
            bridge.debug.start(); bridge.debug.failed = True
            self.assertEqual(bridge.close(session['id']), {'stopped': True, 'logging_failed': True})
            self.assertTrue(bridge.session['stop'].is_set())
            self.assertEqual(bridge.recover(), {'stopped': True})

    def test_progressive_durable_redacted_and_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = DebugJournal(folder)
            session = journal.start()
            event = {'event': 'request', 'url': 'https://user:password@example.test/path?token=secret', 'cookie': 'secret', 'body': 'private body', 'status': 200}
            result = journal.batch(session['client_id'], 0, [event])
            self.assertEqual(result['next_sequence'], 1)
            before = Path(session['log_file']).read_bytes()
            journal.batch(session['client_id'], 0, [event])
            self.assertEqual(before, Path(session['log_file']).read_bytes())
            self.assertNotIn(b'secret', before); self.assertNotIn(b'password', before); self.assertNotIn(b'private body', before)
            self.assertIn(b'https://example.test/path', before)
            with self.assertRaises(ValueError): journal.batch(session['client_id'], 0, [{'event': 'different'}])

    def test_fsync_failure_is_not_acknowledged(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = DebugJournal(folder); session = journal.start()
            with patch('cli.debug_journal.os.fsync', side_effect=OSError('private disk error')):
                with self.assertRaises(OSError): journal.batch(session['client_id'], 0, [{'event': 'progress'}])
            self.assertTrue(journal.status()['failed'])
            with self.assertRaises(OSError): journal.batch(session['client_id'], 0, [{'event': 'progress'}])

    def test_native_events_and_reload_share_journal(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = DebugJournal(folder); first = journal.start()
            journal.native({'event': 'network_stage', 'stage': 'dns'})
            second = journal.start()
            self.assertEqual(first['log_file'], second['log_file'])
            self.assertNotEqual(first['client_id'], second['client_id'])
            records = [json.loads(line) for line in Path(first['log_file']).read_text().splitlines()]
            self.assertTrue(any(row.get('stage') == 'dns' for row in records))
            with self.assertRaises(ValueError): journal.batch(second['client_id'], 1, [{'event': 'gap'}])
            with self.assertRaises(ValueError): journal.batch(second['client_id'], 0, [{}] * 33)
