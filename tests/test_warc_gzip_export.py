from contextlib import closing, redirect_stdout
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zlib

from cli.aegis_cli import PythonWarcWriter
from cli.export_mirror import export_warc_gzip
from cli.warc_verify import verify_warc


class GzipMembersTest(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.warc = self.root / 'archive.warc'
        self.output = self.root / 'archive.warc.gz'
        payload = b'<p>Archived payload</p>' * 5000
        with closing(PythonWarcWriter(str(self.warc))) as writer:
            writer.write_response('https://fixture.test/page?a=1', 200, {'Content-Type': 'text/html'},
                                  payload, request_headers={'User-Agent': 'Fixture'})
            writer.write_response('https://fixture.test/page?a=2', 200, {'Content-Type': 'text/html'}, payload)

    def test_each_member_recovers_exactly_one_original_record(self):
        plain = []
        with redirect_stdout(io.StringIO()):
            self.assertTrue(verify_warc(str(self.warc), _spans_out=plain))
        original = self.warc.read_bytes()
        result = export_warc_gzip(self.warc, self.output)
        zipped = self.output.read_bytes()
        self.assertEqual(len(result['members']), 4)
        self.assertEqual(result['source_sha256'], hashlib.sha256(original).hexdigest())
        self.assertEqual(gzip.decompress(zipped), original)
        for span, (start, length, _) in zip(result['members'], plain, strict=True):
            cut = zipped[span['offset']:span['offset'] + span['length']]
            reader = zlib.decompressobj(31)
            self.assertEqual(reader.decompress(cut), original[start:start + length])
            self.assertTrue(reader.eof)
            self.assertFalse(reader.unused_data)
        self.assertEqual(self.warc.read_bytes(), original)

    def test_cli_and_deterministic_output(self):
        args = [sys.executable, '-m', 'cli.export_mirror', 'warc-gzip', str(self.warc), str(self.output)]
        reply = json.loads(subprocess.check_output(args, text=True))
        other = self.root / 'copy.warc.gz'
        self.assertEqual(reply, export_warc_gzip(self.warc, other))
        self.assertEqual(other.read_bytes(), self.output.read_bytes())
        rejected = subprocess.run(args, text=True, capture_output=True)
        self.assertEqual(rejected.returncode, 2)
        self.assertIn('already exists', rejected.stderr)

    def test_incomplete_or_interrupted_output_does_not_publish(self):
        original = self.warc.read_bytes()
        self.warc.write_bytes(original[:-1])
        with self.assertRaisesRegex(ValueError, 'separator'):
            export_warc_gzip(self.warc, self.output)
        self.assertFalse(self.output.exists())
        self.warc.write_bytes(original)
        (self.root / 'receipt.json').write_text('{"complete": false}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'does not mark'):
            export_warc_gzip(self.warc, self.output)
        (self.root / 'receipt.json').unlink()
        with patch('cli.export_mirror._scan_members', side_effect=OSError('fixture interruption')):
            with self.assertRaisesRegex(OSError, 'interruption'):
                export_warc_gzip(self.warc, self.output)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.warc.read_bytes(), original)

    def test_finalization_receipt_must_match_source_bytes(self):
        receipt = self.root / 'receipt.json'
        data = self.warc.read_bytes()
        metadata = {'complete': True, 'archives': {'warc': {'bytes': len(data), 'sha256': '0' * 64}}}
        receipt.write_text(json.dumps(metadata), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'does not match'):
            export_warc_gzip(self.warc, self.output)
        self.assertFalse(self.output.exists())
        metadata['archives']['warc']['sha256'] = hashlib.sha256(data).hexdigest()
        receipt.write_text(json.dumps(metadata), encoding='utf-8')
        export_warc_gzip(self.warc, self.output)
        self.assertEqual(gzip.decompress(self.output.read_bytes()), data)
