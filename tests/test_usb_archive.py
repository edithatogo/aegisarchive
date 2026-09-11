import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from cli.usb_archive import UsbArchiveStore


class UsbArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = UsbArchiveStore(Path(self.temp.name) / 'captures')
        self.sid = self.store.start()['archive_id']

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
