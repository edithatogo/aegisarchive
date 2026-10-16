import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from cli.usb_archive import UsbArchiveStore, encoded_state


class UsbArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = UsbArchiveStore(Path(self.temp.name).resolve() / 'captures')
        self.addCleanup(self.store.close)
        self.started = self.store.start()
        self.sid = self.started['archive_id']

    def saved_checkpoint(self):
        self.chunk(b'prefix')
        self.chunk(b'index', 'cdx')
        result = self.store.checkpoint(self.sid, 0, {'frontier': ['https://fixture.invalid/next'],
                                                    'writer': {'records': 1}},
                                       'a' * 64, self.started['lease'])
        self.assertEqual(result, {'generation': 1, 'offsets': {'warc': 6, 'cdx': 5}})
        return self.store.root / self.sid

    def test_fresh_store_durable_recovery(self):
        self.saved_checkpoint()
        self.store.suspend(self.sid)
        recovered = UsbArchiveStore(self.store.root)
        self.addCleanup(recovered.close)
        result = recovered.reopen(self.sid, 1, 'a' * 64)
        self.assertEqual(result['offsets'], {'warc': 6, 'cdx': 5})
        self.assertEqual(result['state']['writer']['records'], 1)
        self.assertNotEqual(result['lease'], self.started['lease'])
        recovered.chunk(self.sid, 'warc', 6, base64.b64encode(b'new').decode(), result['lease'])
        saved = recovered.finalize(self.sid, {'complete': True}, result['lease'])
        self.assertEqual(Path(saved['warc_path']).read_bytes(), b'prefixnew')

    def test_prefix_corruption_preserves_checkpoint_and_bytes(self):
        folder = self.saved_checkpoint()
        self.store.suspend(self.sid)
        original = (folder / 'checkpoint.json').read_bytes()
        (folder / 'archive.warc.partial').write_bytes(b'broken')
        with self.assertRaises((ValueError, OSError)):
            self.store.reopen(self.sid, 1, 'a' * 64)
        self.assertEqual((folder / 'archive.warc.partial').read_bytes(), b'broken')
        self.assertEqual((folder / 'checkpoint.json').read_bytes(), original)

    def test_stale_lease_generation_and_profile(self):
        self.saved_checkpoint()
        for generation, profile in [(0, 'a' * 64), (True, 'a' * 64), (1, 'b' * 64)]:
            with self.assertRaises(ValueError):
                self.store.reopen(self.sid, generation, profile)
        result = self.store.reopen(self.sid, 1, 'a' * 64)
        for lease in (None, self.started['lease']):
            with self.assertRaises(ValueError):
                self.store.chunk(self.sid, 'warc', 6, 'YQ==', lease)
            with self.assertRaises(ValueError):
                self.store.finalize(self.sid, {'complete': True}, lease)
        with self.assertRaises(ValueError):
            self.store.checkpoint(self.sid, 0, {}, 'a' * 64, result['lease'])

    def test_reopen_advances_durable_generation_and_rejects_replayed_handle(self):
        folder = self.saved_checkpoint()
        before = json.loads((folder / 'checkpoint.json').read_bytes())
        self.chunk(b'uncommitted-tail', offset=6)
        recovered = self.store.reopen(self.sid, 1, 'a' * 64)
        self.assertEqual(recovered['generation'], 2)
        persisted = json.loads((folder / 'checkpoint.json').read_bytes())
        self.assertEqual(persisted, dict(before, generation=2))
        with self.assertRaises(ValueError):
            self.store.reopen(self.sid, 1, 'a' * 64)
        self.store.chunk(self.sid, 'warc', 6, 'bmV3', recovered['lease'])
        with self.assertRaises(ValueError):
            self.store.checkpoint(self.sid, 1, {}, 'a' * 64, recovered['lease'])
        self.assertEqual(self.store.checkpoint(self.sid, recovered['generation'],
            recovered['state'], 'a' * 64, recovered['lease'])['generation'], 3)

    def test_reopen_generation_is_retained_for_fresh_store(self):
        self.saved_checkpoint()
        self.assertEqual(self.store.reopen(self.sid, 1, 'a' * 64)['generation'], 2)
        self.store.close()
        other = UsbArchiveStore(self.store.root)
        self.addCleanup(other.close)
        with self.assertRaises(ValueError):
            other.reopen(self.sid, 1, 'a' * 64)
        self.assertEqual(other.reopen(self.sid, 2, 'a' * 64)['generation'], 3)

    def test_orphan_tails_preserved_before_truncation(self):
        folder = self.saved_checkpoint()
        self.chunk(b'warc-tail', offset=6)
        self.chunk(b'cdx-tail', 'cdx', 5)
        result = self.store.reopen(self.sid, 1, 'a' * 64)
        self.assertEqual(result['offsets'], {'warc': 6, 'cdx': 5})
        tails = [path.read_bytes() for path in folder.glob('*.orphan.*')]
        self.assertCountEqual(tails, [b'warc-tail', b'cdx-tail'])
        self.assertEqual((folder / 'archive.warc.partial').read_bytes(), b'prefix')
        self.assertEqual((folder / 'archive.cdx.partial').read_bytes(), b'index')

    def test_finalized_never_reopens_or_discovers(self):
        self.saved_checkpoint()
        self.store.finalize(self.sid, {'complete': True})
        with self.assertRaises(ValueError):
            self.store.reopen(self.sid, 1, 'a' * 64)
        self.assertEqual(self.store.discover(), [])

    def test_other_process_cannot_reopen_active_writer(self):
        self.saved_checkpoint()
        child = subprocess.run([sys.executable, '-B', '-c',
            'from cli.usb_archive import UsbArchiveStore; import sys; '
            'UsbArchiveStore(sys.argv[1]).reopen(sys.argv[2], 1, "a"*64)',
            str(self.store.root), self.sid], capture_output=True, cwd=Path(__file__).resolve().parents[1])
        self.assertNotEqual(child.returncode, 0)
        self.assertIn(b'writer', child.stderr.lower())
        other = UsbArchiveStore(self.store.root)
        self.addCleanup(other.close)
        with self.assertRaises((ValueError, OSError)):
            other.reopen(self.sid, 1, 'a' * 64)
        self.store.close()
        self.assertEqual(other.reopen(self.sid, 1, 'a' * 64)['generation'], 2)

    def test_checkpoint_bounded_state_and_secret_rejection(self):
        for state in ({'nested': {'access_token': 'secret'}}, {'Cookie': 'session'},
                      {'authorization': 'secret'}, {'credential': 'secret'},
                      {'payload': 'x' * (1024 * 1024 + 1)}, {'nan': float('nan')}):
            with self.assertRaises(ValueError):
                self.store.checkpoint(self.sid, 0, state, 'a' * 64, self.started['lease'])
        self.assertFalse((self.store.root / self.sid / 'checkpoint.json').exists())

    def test_numeric_pacing_tokens_are_not_credentials(self):
        state = {'pacing': {'tokens': 1.5}, 'writer': {'payloadMap': [
            ['https://fixture.invalid/auth/page', 'public-payload-hash']]}}
        self.assertEqual(json.loads(encoded_state(state)), state)
        for value in ('secret', True, None, -1, float('inf'), float('nan'), {}, []):
            with self.assertRaises(ValueError):
                encoded_state({'pacing': {'tokens': value}})
        for key in ('token', 'access_token', 'refreshToken', 'cookie', 'authSources'):
            with self.assertRaises(ValueError):
                encoded_state({'nested': {key: 'secret'}})

    @unittest.skipUnless(shutil.which('node'), 'Node is needed to inspect the real browser pacing export')
    def test_real_browser_pacing_export_checkpoints_and_reopens(self):
        script = ('const Engine = require("./web/lib/politeness_engine.js");'
                  'console.log(JSON.stringify({pacing:new Engine().exportState(),'
                  'writer:{payloadMap:[["https://fixture.invalid/auth/page","payload"]]}}));')
        state = json.loads(subprocess.check_output(
            ['node', '-e', script], cwd=Path(__file__).resolve().parents[1]))
        self.store.checkpoint(self.sid, 0, state, 'a' * 64, self.started['lease'])
        self.store.suspend(self.sid)
        self.assertEqual(self.store.reopen(self.sid, 1, 'a' * 64)['state'], state)

    def test_exact_last_chunk_retry_only(self):
        self.assertEqual(self.chunk(b'one'), {'offset': 3})
        self.assertEqual(self.chunk(b'one'), {'offset': 3})
        with self.assertRaises(ValueError):
            self.chunk(b'two')
        self.chunk(b'two', offset=3)
        with self.assertRaises(ValueError):
            self.chunk(b'one')

    def test_discovery_metadata_and_invalid_paths(self):
        self.saved_checkpoint()
        found = self.store.discover()
        self.assertEqual(found[0]['archive_id'], self.sid)
        self.assertNotIn('state', found[0])
        self.assertNotIn('lease', found[0])
        for sid in ('../escape', 'A' * 32, 'not-an-id'):
            with self.assertRaises(ValueError):
                self.store.reopen(sid, 1, 'a' * 64)

    def test_checkpoint_failure_preserves_previous_generation(self):
        folder = self.saved_checkpoint()
        previous = (folder / 'checkpoint.json').read_bytes()
        self.chunk(b'tail', offset=6)
        with patch('cli.usb_archive.os.replace', side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):
                self.store.checkpoint(self.sid, 1, {}, 'a' * 64, self.started['lease'])
        self.assertEqual((folder / 'checkpoint.json').read_bytes(), previous)
        self.assertEqual((folder / 'archive.warc.partial').read_bytes(), b'prefixtail')

    def test_recovered_last_chunk_retry_is_idempotent(self):
        self.saved_checkpoint()
        self.store.suspend(self.sid)
        result = self.store.reopen(self.sid, 1, 'a' * 64)
        self.assertEqual(self.store.chunk(self.sid, 'warc', 0, 'cHJlZml4', result['lease']), {'offset': 6})
        with self.assertRaises(ValueError):
            self.store.chunk(self.sid, 'warc', 1, 'cmVmaXg=', result['lease'])

    def test_parent_alias_allowed_but_explicit_root_symlink_rejected(self):
        parent = Path(self.temp.name).resolve()
        alias = parent / 'parent-alias'
        alias.symlink_to(parent, target_is_directory=True)
        other = UsbArchiveStore(alias / 'other-captures')
        self.addCleanup(other.close)
        self.assertEqual(Path(other.start()['directory']).parent, parent / 'other-captures')
        explicit = parent / 'root-alias'
        explicit.symlink_to(self.store.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            UsbArchiveStore(explicit)

    def test_symlinked_checkpoint_partial_and_folder_rejected(self):
        folder = self.saved_checkpoint()
        self.store.suspend(self.sid)
        for name in ('checkpoint.json', 'archive.warc.partial'):
            original = folder / name
            moved = folder / (name + '.original')
            original.rename(moved)
            original.symlink_to(moved)
            with self.assertRaises((ValueError, OSError)):
                self.store.reopen(self.sid, 1, 'a' * 64)
            original.unlink()
            moved.rename(original)
        moved = self.store.root / 'original-folder'
        folder.rename(moved)
        folder.symlink_to(moved, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.store.reopen(self.sid, 1, 'a' * 64)

    def test_tail_copy_failure_keeps_all_original_bytes(self):
        folder = self.saved_checkpoint()
        self.chunk(b'tail', offset=6)
        before = (folder / 'checkpoint.json').read_bytes()
        with patch('cli.usb_archive.os.fsync', side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):
                self.store.reopen(self.sid, 1, 'a' * 64)
        self.assertEqual((folder / 'archive.warc.partial').read_bytes(), b'prefixtail')
        self.assertEqual((folder / 'archive.cdx.partial').read_bytes(), b'index')
        self.assertEqual((folder / 'checkpoint.json').read_bytes(), before)

    def test_checkpoint_fsync_failure_retains_previous_checkpoint(self):
        folder = self.saved_checkpoint()
        before = (folder / 'checkpoint.json').read_bytes()
        self.chunk(b'tail', offset=6)
        with patch('cli.usb_archive.os.fsync', side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):
                self.store.checkpoint(self.sid, 1, {}, 'a' * 64, self.started['lease'])
        self.assertEqual((folder / 'checkpoint.json').read_bytes(), before)
        self.assertEqual((folder / 'archive.warc.partial').read_bytes(), b'prefixtail')

    def test_bounded_and_malformed_persisted_checkpoint(self):
        folder = self.saved_checkpoint()
        self.store.suspend(self.sid)
        path = folder / 'checkpoint.json'
        original = path.read_bytes()
        for raw in (b'x' * (2 * 1024 * 1024 + 1), b'\xff',
                    b'{"nested":' + b'[' * 2000 + b'0' + b']' * 2000 + b'}'):
            path.write_bytes(raw)
            with self.assertRaises(ValueError):
                self.store.reopen(self.sid, 1, 'a' * 64)
            self.assertEqual((folder / 'archive.warc.partial').read_bytes(), b'prefix')
            self.assertEqual(path.read_bytes(), raw)
        value = json.loads(original)
        value['generation'] = True
        path.write_text(json.dumps(value))
        with self.assertRaises(ValueError):
            self.store.reopen(self.sid, 1, 'a' * 64)
        path.write_bytes(original)
        self.assertEqual(self.store.reopen(self.sid, 1, 'a' * 64)['generation'], 2)

    def chunk(self, data, kind='warc', offset=0):
        return self.store.chunk(self.sid, kind, offset, base64.b64encode(data).decode())

    def test_actual_bytes_and_receipt(self):
        data = b'WARC/1.1\r\n\r\nsynthetic bytes\x00\xff'
        self.chunk(data)
        self.chunk(b'CDX synthetic\n', 'cdx')
        result = self.store.finalize(self.sid, {'complete': False})
        self.assertEqual(Path(result['warc_path']).read_bytes(), data)
        self.assertEqual(result['archives']['warc']['sha256'], hashlib.sha256(data).hexdigest())
        receipt = json.loads(Path(result['receipt_path']).read_text())
        self.assertFalse(receipt['complete'])
        self.assertEqual(receipt['archives'], result['archives'])
        with self.assertRaises(ValueError):
            self.chunk(b'late', offset=len(data))

    def test_reject_paths_offsets_and_bad_chunks(self):
        for sid, kind, offset, data in [('../escape','warc',0,'YQ=='), (self.sid,'../escape',0,'YQ=='),
                                       (self.sid,'warc',1,'YQ=='), (self.sid,'warc',True,'YQ=='),
                                       (self.sid,'warc',0,'bad!')]:
            with self.assertRaises(ValueError):
                self.store.chunk(sid,kind,offset,data)
        self.assertEqual(list(Path(self.temp.name).iterdir()), [Path(self.temp.name)/'captures'])

    def test_disk_failure_poisoned_and_no_receipt(self):
        with patch('cli.usb_archive.os.fsync', side_effect=OSError('synthetic disk full')):
            with self.assertRaises(OSError):
                self.chunk(b'bytes')
        with self.assertRaises(ValueError):
            self.store.finalize(self.sid, {'complete': True})
        self.assertFalse((self.store.root/self.sid/'receipt.json').exists())

    def test_finalize_failure_never_claims_saved(self):
        self.chunk(b'bytes')
        with patch('cli.usb_archive.os.replace', side_effect=OSError('synthetic disk failure')):
            with self.assertRaises(OSError):
                self.store.finalize(self.sid, {'complete': True})
        self.assertFalse((self.store.root/self.sid/'receipt.json').exists())

    def test_readback_detects_same_length_corruption(self):
        self.chunk(b'original')
        (self.store.root/self.sid/'archive.warc.partial').write_bytes(b'corrupt!')
        with self.assertRaises(OSError):
            self.store.finalize(self.sid, {'complete': True})
        self.assertFalse((self.store.root/self.sid/'receipt.json').exists())

    def test_chunk_limit(self):
        with self.assertRaises(ValueError):
            self.chunk(b'x' * (256 * 1024 + 1))

    def test_replaced_file_descriptor_is_rejected_before_writing(self):
        outside = Path(self.temp.name) / 'outside'
        outside.write_bytes(b'')
        original_open = os.open
        with patch('cli.usb_archive.os.open', side_effect=lambda path, flags: original_open(outside, flags)):
            with self.assertRaises(OSError):
                self.chunk(b'never write here')
        self.assertEqual(outside.read_bytes(), b'')
        self.assertFalse((self.store.root/self.sid/'receipt.json').exists())

    def test_replaced_file_descriptor_is_rejected_before_hashing(self):
        self.chunk(b'original')
        outside = Path(self.temp.name) / 'outside'
        outside.write_bytes(b'original')
        original_open = os.open
        with patch('cli.usb_archive.os.open', side_effect=lambda path, flags: original_open(outside, flags)):
            with self.assertRaises(OSError):
                self.store.finalize(self.sid, {'complete': True})
        self.assertFalse((self.store.root/self.sid/'receipt.json').exists())
