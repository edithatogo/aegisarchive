"""Integrity and restart behavior of pinned model provisioning; no network calls."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

from portable.provision_models import HTTPSRedirectHandler, fetch, load_lock, main


class Response(io.BytesIO):
    def __init__(self, content, status=200, headers=None):
        super().__init__(content)
        self.status = status
        self.headers = headers or {}


class Transport:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


class ModelProvisioningTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.content = b'locked native model bytes'
        self.entry = {
            'path': 'scout/model.gguf',
            'url': 'https://example.invalid/model.gguf',
            'sha256': hashlib.sha256(self.content).hexdigest(),
            'size_bytes': len(self.content),
        }
        self.model = self.root / self.entry['path']
        self.model.parent.mkdir()
        self.partial = self.model.with_name(self.model.name + '.part')

    def lock(self, entries=None):
        target = self.root / 'lock.json'
        target.write_text(json.dumps({'schema_version': 1, 'models': [
            {'role': 'scout', 'files': entries if entries is not None else [self.entry]}
        ]}), encoding='utf-8')
        return target

    def test_cached_bytes_require_digest_and_offline_never_opens_transport(self):
        self.model.write_bytes(self.content)
        transport = Transport()
        self.assertEqual(fetch(self.entry, self.model, offline=True, opener=transport), 'cached')
        self.model.write_bytes(b'X' * len(self.content))
        with self.assertRaisesRegex(ValueError, 'invalid offline'):
            fetch(self.entry, self.model, offline=True, opener=transport)
        self.assertEqual(transport.requests, [])

    def test_range_resume_publishes_only_verified_complete_file(self):
        self.partial.write_bytes(self.content[:7])
        transport = Transport(Response(self.content[7:], 206, {
            'Content-Range': f'bytes 7-{len(self.content)-1}/{len(self.content)}'}))
        self.assertEqual(fetch(self.entry, self.model, opener=transport, attempts=1), 'downloaded')
        self.assertEqual(transport.requests[0].get_header('Range'), 'bytes=7-')
        self.assertEqual(self.model.read_bytes(), self.content)
        self.assertFalse(self.partial.exists())

    def test_server_ignoring_range_restarts_instead_of_appending(self):
        self.partial.write_bytes(self.content[:7])
        fetch(self.entry, self.model, opener=Transport(Response(self.content)), attempts=1)
        self.assertEqual(self.model.read_bytes(), self.content)

    def test_short_read_retains_partial_and_retry_resumes(self):
        transport = Transport(Response(self.content[:7]), Response(self.content[7:], 206, {
            'Content-Range': f'bytes 7-{len(self.content)-1}/{len(self.content)}'}))
        with patch('portable.provision_models.time.sleep') as sleep:
            fetch(self.entry, self.model, opener=transport, attempts=2)
        sleep.assert_called_once()
        self.assertEqual(transport.requests[1].get_header('Range'), 'bytes=7-')
        self.assertEqual(self.model.read_bytes(), self.content)

    def test_terminal_incomplete_download_preserves_existing_file_and_partial(self):
        self.model.write_bytes(b'previous incomplete cache')
        with self.assertRaisesRegex(ValueError, 'Incomplete download'):
            fetch(self.entry, self.model, opener=Transport(Response(self.content[:7])), attempts=1)
        self.assertEqual(self.model.read_bytes(), b'previous incomplete cache')
        self.assertEqual(self.partial.read_bytes(), self.content[:7])

    def test_corrupt_completed_partial_is_not_accepted_and_is_retained(self):
        corrupt = b'X' * len(self.content)
        self.partial.write_bytes(corrupt)
        fetch(self.entry, self.model, opener=Transport(Response(self.content)), attempts=1)
        self.assertEqual(self.partial.with_name(self.partial.name + '.invalid').read_bytes(), corrupt)
        self.assertEqual(self.model.read_bytes(), self.content)

    def test_wrong_digest_oversize_and_inconsistent_range_fail_closed(self):
        responses = [
            Response(b'X' * len(self.content)),
            Response(self.content + b'extra'),
            Response(self.content, 206, {'Content-Range': 'bytes 1-5/6'}),
            Response(self.content, headers={'Content-Encoding': 'gzip'}),
        ]
        for response in responses:
            with self.subTest(headers=response.headers):
                self.partial.unlink(missing_ok=True)
                with self.assertRaises(ValueError):
                    fetch(self.entry, self.model, opener=Transport(response), attempts=1)
                self.assertFalse(self.model.exists())

    def test_retry_after_is_respected(self):
        throttled = urllib.error.HTTPError(self.entry['url'], 429, 'rate limited', {'Retry-After': '17'}, None)
        transport = Transport(throttled, Response(self.content))
        with patch('portable.provision_models.time.sleep') as sleep:
            fetch(self.entry, self.model, opener=transport, attempts=2)
        sleep.assert_called_once_with(17.0)

    def test_lock_rejects_path_escape_duplicate_and_unpinned_bytes(self):
        for invalid in (
            {**self.entry, 'path': '../outside'},
            {**self.entry, 'path': 'scout/../../outside'},
            {**self.entry, 'sha256': 'latest'},
            {**self.entry, 'url': 'http://example.invalid/model'},
            {**self.entry, 'size_bytes': True},
        ):
            with self.subTest(entry=invalid), self.assertRaises(ValueError):
                load_lock(self.lock([invalid]))
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            load_lock(self.lock([self.entry, self.entry]))

    def test_https_redirect_cannot_downgrade(self):
        request = urllib.request.Request(self.entry['url'])
        with self.assertRaisesRegex(ValueError, 'HTTPS'):
            HTTPSRedirectHandler().redirect_request(request, None, 302, '', {},
                                                    'http://example.invalid/model')

    def test_cli_offline_receipt_bound_to_lock_and_failure_keeps_previous_receipt(self):
        self.model.write_bytes(self.content)
        lock = self.lock()
        with patch('portable.provision_models.urllib.request.build_opener',
                   side_effect=AssertionError('offline invocation touched network')):
            self.assertEqual(main(['--lock', str(lock), '--output', str(self.root), '--offline']), 0)
            receipt_path = self.root / 'model-receipt.json'
            before = receipt_path.read_bytes()
            receipt = json.loads(before)
            self.assertEqual(receipt['lock_sha256'], hashlib.sha256(lock.read_bytes()).hexdigest())
            self.assertEqual(receipt['files'][0]['status'], 'cached')
            self.model.write_bytes(b'corrupted')
            with self.assertRaises(ValueError):
                main(['--lock', str(lock), '--output', str(self.root), '--offline'])
        self.assertEqual(receipt_path.read_bytes(), before)

    def test_receipt_partial_symlink_cannot_overwrite_outside_output(self):
        self.model.write_bytes(self.content)
        lock = self.lock()
        outside = self.root / 'outside-important.txt'
        outside.write_text('preserve', encoding='utf-8')
        try:
            (self.root / 'model-receipt.json.part').symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest('Symlink creation unavailable on this platform')
        self.assertEqual(main(['--lock', str(lock), '--output', str(self.root), '--offline']), 0)
        self.assertEqual(outside.read_text(encoding='utf-8'), 'preserve')
        self.assertTrue((self.root / 'model-receipt.json.part').is_symlink())
        self.assertTrue((self.root / 'model-receipt.json').is_file())
        self.assertEqual(sorted(path.name for path in self.root.iterdir()),
                         ['lock.json', 'model-receipt.json', 'model-receipt.json.part',
                          'outside-important.txt', 'scout'])

    def test_offline_provision_writes_provenance_sidecar_without_inference(self):
        self.model.write_bytes(self.content)
        lock = self.lock()
        self.assertEqual(main(['--lock', str(lock), '--output', str(self.root), '--offline']), 0)
        sidecar = json.loads(self.model.with_name(self.model.name + '.provenance.json').read_text())
        self.assertEqual(sidecar['kind'], 'locked_asset_provenance')
        self.assertFalse(sidecar['inference_claimed'])
        self.assertEqual(sidecar['sha256'], self.entry['sha256'])
        self.assertEqual(sidecar['url'], self.entry['url'])


if __name__ == '__main__':
    unittest.main()
