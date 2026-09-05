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
        with tempfile.TemporaryDirectory() as directory:
            receipt = Path(directory) / 'receipt.json'
            status = native.verify_or_smoke(Path(directory) / 'missing-bundle', receipt, smoke=True)
            self.assertEqual(status, 1)
            report = json.loads(receipt.read_text())
            self.assertEqual(report['status'], 'blocked')
            self.assertFalse(report['inference_claimed'])
            self.assertEqual(report.get('smoke'), 'not_run')


if __name__ == '__main__':
    unittest.main()
