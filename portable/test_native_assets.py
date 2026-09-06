"""Fail-closed native asset inventory and cache audit; no inference claims."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from portable.provision_models import audit_cache, load_lock, main, source_inventory
from portable import provision_native as native


class NativeAssetAuditTests(unittest.TestCase):
    def lock(self, root):
        content = b'locked native model bytes'
        entry = {
            'path': 'scout/model.gguf',
            'url': 'https://example.invalid/model.gguf',
            'sha256': hashlib.sha256(content).hexdigest(),
            'size_bytes': len(content),
        }
        lock = {
            'schema_version': 1,
            'models': [{
                'role': 'scout',
                'repo': 'example/scout',
                'revision': 'abc',
                'license': 'apache-2.0',
                'files': [entry],
            }],
        }
        path = root / 'lock.json'
        path.write_text(json.dumps(lock), encoding='utf-8')
        return path, entry, content

    def test_source_inventory_retains_licence_and_never_claims_inference(self):
        lock = load_lock(Path(__file__).with_name('model-lock.json'))
        inventory = source_inventory(lock)
        roles = {model['role'] for model in inventory['models']}
        self.assertEqual(roles, {'scout', 'general', 'deep', 'transcription', 'embeddings'})
        self.assertFalse(inventory['inference_claimed'])
        for model in inventory['models']:
            self.assertTrue(model['license'])
            self.assertTrue(model['repo'])
            self.assertTrue(model['files'][0]['url'].startswith('https://'))

    def test_missing_and_corrupt_cache_fail_closed_without_inference_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock_path, entry, content = self.lock(root)
            lock = load_lock(lock_path)
            missing = audit_cache(lock, root / 'models', {'scout'})
            self.assertFalse(missing['complete'])
            self.assertFalse(missing['inference_claimed'])
            self.assertEqual(missing['files'][0]['status'], 'missing')
            cache = root / 'models'
            (cache / 'scout').mkdir(parents=True)
            (cache / entry['path']).write_bytes(b'X' * len(content))
            corrupt = audit_cache(lock, cache, {'scout'})
            self.assertFalse(corrupt['complete'])
            self.assertEqual(corrupt['files'][0]['status'], 'digest_mismatch')
            (cache / entry['path']).write_bytes(content)
            ok = audit_cache(lock, cache, {'scout'})
            self.assertTrue(ok['complete'])
            self.assertEqual(ok['files'][0]['status'], 'verified')
            self.assertFalse(ok['inference_claimed'])
            outside_dir = root / 'outside-role'
            outside_dir.mkdir()
            (outside_dir / 'model.gguf').write_bytes(content)
            (cache / 'scout').rename(root / 'real-scout')
            try:
                (cache / 'scout').symlink_to(outside_dir)
            except (OSError, NotImplementedError):
                return
            escaped = audit_cache(lock, cache, {'scout'})
            self.assertFalse(escaped['complete'])
            self.assertEqual(escaped['files'][0]['status'], 'symlink_rejected')

    def test_audit_cli_exits_nonzero_when_assets_are_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock_path, _, _ = self.lock(root)
            self.assertEqual(main(['--lock', str(lock_path), '--output', str(root / 'models'),
                                   '--audit']), 1)
            receipt = json.loads((root / 'models' / 'model-audit.json').read_text())
            self.assertFalse(receipt['complete'])
            self.assertFalse(receipt['inference_claimed'])

    def test_native_inventory_and_missing_bundle_do_not_fabricate_smoke(self):
        inventory = native.source_inventory()
        self.assertFalse(inventory['inference_claimed'])
        self.assertIn('llama', inventory)
        self.assertIn('speech', inventory)
        self.assertEqual(len(inventory['models']['models']), 5)
        wheels = inventory['speech']['wheels']
        self.assertIn('piper-tts', wheels)
        self.assertTrue(wheels['piper-tts']['wheels'])
        self.assertTrue(all(len(digest) == 64 for digest in wheels['piper-tts']['wheels'].values()))
        with tempfile.TemporaryDirectory() as directory:
            receipt = Path(directory) / 'receipt.json'
            status = native.verify_or_smoke(Path(directory) / 'missing-bundle', receipt, smoke=True)
            self.assertEqual(status, 1)
            report = json.loads(receipt.read_text())
            self.assertEqual(report['status'], 'blocked')
            self.assertFalse(report['inference_claimed'])
            self.assertEqual(report.get('smoke'), 'not_run')

    def test_locked_runtime_targets_cover_three_os_without_inference(self):
        targets = {item['id']: item for item in native.locked_runtime_targets()}
        self.assertIn('python/Linux/x86_64', targets)
        self.assertIn('python/Windows/AMD64', targets)
        self.assertIn('python/Darwin/arm64', targets)
        self.assertIn('llama/Linux', targets)
        self.assertIn('llama/Windows', targets)
        self.assertIn('llama/Darwin', targets)
        self.assertIn('win_git/portable', targets)
        self.assertIn('127.0.0.1', native.DARWIN_NETWORK_POLICY)
        for item in targets.values():
            self.assertEqual(len(item['sha256']), 64)
            self.assertTrue(item['url'].startswith('https://'))

    def test_acquire_verifies_pins_and_skips_large_models_without_inference(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def runtime(url, target, sha, receipt):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'ok')
                if hashlib.sha256(b'ok').hexdigest() != sha:
                    raise ValueError('Upstream checksum mismatch: ' + url)
                receipt.append({'url': url, 'sha256': sha, 'bytes': 2})
                return target

            def fake_model(entry, destination, **_kwargs):
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b'small-model')
                return 'downloaded'

            original_targets = native.locked_runtime_targets
            original_lock = native.load_lock
            native.locked_runtime_targets = lambda: [{
                'id': 'git/source', 'url': 'https://example.invalid/git.tar.gz',
                'sha256': hashlib.sha256(b'ok').hexdigest(), 'license': 'GPL-2.0-only',
            }]
            native.load_lock = lambda _path: {'schema_version': 1, 'models': [
                {'role': 'scout', 'license': 'apache-2.0',
                 'files': [{'path': 'scout/model.gguf', 'url': 'https://example.invalid/big.gguf',
                            'sha256': 'a' * 64, 'size_bytes': 5000}]},
                {'role': 'embeddings', 'license': 'MIT',
                 'files': [{'path': 'embeddings/bge.gguf', 'url': 'https://example.invalid/bge.gguf',
                            'sha256': hashlib.sha256(b'small-model').hexdigest(),
                            'size_bytes': 11}]},
            ]}
            try:
                receipt = root / 'acquisition.json'
                report = native.acquire_locked_assets(
                    root / 'cache', receipt, max_bytes=100, wheels=False,
                    fetch_runtime=runtime, fetch_model_file=fake_model)
            finally:
                native.locked_runtime_targets = original_targets
                native.load_lock = original_lock

            self.assertTrue(report['runtimes_complete'])
            self.assertFalse(report['models_complete'])
            self.assertFalse(report['complete'])
            self.assertFalse(report['inference_claimed'])
            statuses = {item.get('id') or item.get('path'): item['status'] for item in report['files']}
            self.assertEqual(statuses['git/source'], 'verified')
            self.assertEqual(statuses['scout/model.gguf'], 'skipped_size')
            self.assertEqual(statuses['embeddings/bge.gguf'], 'verified')
            self.assertFalse(json.loads(receipt.read_text())['inference_claimed'])
            self.assertFalse(native.acquisition_failed(report))

    def test_acquire_fail_closed_on_checksum_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def bad_fetch(url, target, sha, receipt):
                raise ValueError('Upstream checksum mismatch: ' + url)

            original = native.locked_runtime_targets
            native.locked_runtime_targets = lambda: [{
                'id': 'llama/Linux', 'url': 'https://example.invalid/llama.tar.gz',
                'sha256': 'b' * 64, 'license': 'MIT',
            }]
            native_load = native.load_lock
            native.load_lock = lambda _path: {'schema_version': 1, 'models': []}
            try:
                report = native.acquire_locked_assets(
                    root / 'cache', root / 'receipt.json', wheels=False,
                    fetch_runtime=bad_fetch,
                    fetch_model_file=lambda *args, **kwargs: 'downloaded')
            finally:
                native.locked_runtime_targets = original
                native.load_lock = native_load
            self.assertFalse(report['runtimes_complete'])
            self.assertFalse(report['complete'])
            self.assertFalse(report['inference_claimed'])
            self.assertEqual(report['files'][0]['status'], 'failed')
            self.assertTrue(native.acquisition_failed(report))

    def test_acquire_fails_closed_when_attempted_model_download_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def runtime(url, target, sha, receipt):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'ok')
                receipt.append({'url': url, 'sha256': sha, 'bytes': 2})
                return target

            original_targets = native.locked_runtime_targets
            original_lock = native.load_lock
            native.locked_runtime_targets = lambda: [{
                'id': 'git/source', 'url': 'https://example.invalid/git.tar.gz',
                'sha256': hashlib.sha256(b'ok').hexdigest(), 'license': 'GPL-2.0-only',
            }]
            native.load_lock = lambda _path: {'schema_version': 1, 'models': [
                {'role': 'embeddings', 'license': 'MIT',
                 'files': [{'path': 'embeddings/bge.gguf', 'url': 'https://example.invalid/bge.gguf',
                            'sha256': 'c' * 64, 'size_bytes': 11}]},
            ]}
            try:
                report = native.acquire_locked_assets(
                    root / 'cache', root / 'receipt.json', max_bytes=100, wheels=False,
                    fetch_runtime=runtime,
                    fetch_model_file=lambda *args, **kwargs: (_ for _ in ()).throw(ValueError('digest mismatch')))
            finally:
                native.locked_runtime_targets = original_targets
                native.load_lock = original_lock
            self.assertTrue(report['runtimes_complete'])
            self.assertFalse(report['models_complete'])
            self.assertEqual(report['files'][-1]['status'], 'failed')
            self.assertTrue(native.acquisition_failed(report))

    def test_purge_removes_only_undeclared_bytecode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'bundle'
            for name in ('app', 'data', 'runtime', 'licenses'):
                (root / name).mkdir(parents=True)
            (root / 'app' / 'keep.py').write_text('print(1)\n')
            cache = root / 'runtime' / 'python' / '__pycache__'
            cache.mkdir(parents=True)
            (cache / 'x.cpython-312.pyc').write_bytes(b'pyc')
            extra = root / 'runtime' / 'unexpected.bin'
            extra.write_bytes(b'nope')
            manifest = {
                'schema_version': 1,
                'files': {
                    'app/keep.py': {'sha256': '0' * 64, 'size': 1, 'executable': False},
                },
            }
            (root / 'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'non-bytecode'):
                native.purge_undeclared_bytecode(root)
            extra.unlink()
            removed = native.purge_undeclared_bytecode(root)
            self.assertEqual(removed, ['runtime/python/__pycache__/x.cpython-312.pyc'])
            self.assertFalse(cache.exists())
            self.assertTrue((root / 'app' / 'keep.py').is_file())


if __name__ == '__main__':
    unittest.main()
