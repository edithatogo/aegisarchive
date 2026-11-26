from contextlib import closing
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from cli.aegis_cli import PythonWarcWriter
from cli.export_mirror import export_cdxj, export_warc_gzip, verify_cdxj


class CdxjRowsTest(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.warc = self.root / 'capture.warc'
        self.compressed = self.root / 'capture.warc.gz'
        self.index = self.root / 'capture.cdxj'
        self.first_url = 'https://www.example.test/Page?Q=Two'
        self.revisit_url = 'https://www.example.test/Page?Q=One%20Two'
        self.payload = b'<p>Repeatable archived payload</p>' * 4096
        with (patch('cli.aegis_cli.format_warc_date', return_value='2026-11-26T17:23:45.125Z'),
              closing(PythonWarcWriter(str(self.warc))) as writer):
            writer.write_response(self.first_url, 200, {'Content-Type': 'text/html; charset=utf-8'},
                                  self.payload, request_headers={'User-Agent': 'Fixture'})
            writer.write_response(self.revisit_url, 200, {'Content-Type': 'text/html'}, self.payload)
            writer.write_response('https://www.example.test', 404, {'Content-Type': 'text/plain'}, b'Not found')
        self.members = export_warc_gzip(self.warc, self.compressed)['members']

    def test_sorted_original_urls_and_exact_ranges(self):
        self.assertEqual(export_cdxj(self.compressed, self.index), {'entries': 3})
        lines = self.index.read_bytes().splitlines()
        self.assertEqual(lines, sorted(lines))
        rows = [line.decode().split(' ', 2) for line in lines]
        self.assertEqual([key for key, _, _ in rows],
                         ['test,example,www)/', 'test,example,www)/page?q=one%20two', 'test,example,www)/page?q=two'])
        expected = [
            ('https://www.example.test', 'text/plain', '404', b'Not found', 'response', 4),
            (self.revisit_url, 'warc/revisit', '200', self.payload, 'revisit', 3),
            (self.first_url, 'text/html', '200', self.payload, 'response', 2),
        ]
        joined = self.compressed.read_bytes()
        for (key, timestamp, payload), (url, mime, status, data, kind, number) in zip(rows, expected, strict=True):
            self.assertEqual(timestamp, '20261126172345125')
            row = json.loads(payload)
            span = self.members[number]
            self.assertEqual(row, dict(url=url, mime=mime, status=status, filename='capture.warc.gz',
                                       digest='sha256:' + hashlib.sha256(data).hexdigest(),
                                       **{name: str(value) for name, value in span.items()}))
            offset, length = int(row['offset']), int(row['length'])
            record = gzip.decompress(joined[offset:offset + length])
            self.assertIn(f'WARC-Type: {kind}\r\n'.encode(), record)
            self.assertIn(f'WARC-Target-URI: {url}\r\n'.encode(), record)
            self.assertEqual(record.split(b'\r\n\r\n', 2)[2][:-4], data if kind == 'response' else b'')
        self.assertEqual(verify_cdxj(self.compressed, self.index), {'entries': 3})

    def test_incorrect_or_missing_references_fail_readback(self):
        export_cdxj(self.compressed, self.index)
        original = self.index.read_bytes()
        first, tail = original.split(b'\n', 1)
        key, stamp, data = first.split(b' ', 2)
        row = json.loads(data)
        for field, value in (('offset', '-1'), ('length', '1'), ('url', 'https://different.test/'),
                             ('digest', 'sha256:' + '0' * 64)):
            with self.subTest(field=field):
                changed = json.dumps(dict(row, **{field: value}), sort_keys=True, separators=(',', ':')).encode()
                self.index.write_bytes(b' '.join((key, stamp, changed)) + b'\n' + tail)
                with self.assertRaisesRegex(ValueError, 'does not match'):
                    verify_cdxj(self.compressed, self.index)
        for changed in (tail, original + first + b'\n'):
            self.index.write_bytes(changed)
            with self.assertRaisesRegex(ValueError, 'does not match'):
                verify_cdxj(self.compressed, self.index)

    def test_bad_member_or_payload_does_not_publish(self):
        first = self.compressed.read_bytes()
        self.compressed.write_bytes(first[:-1])
        with self.assertRaisesRegex(ValueError, 'Truncated gzip'):
            export_cdxj(self.compressed, self.index)
        self.assertFalse(self.index.exists())
        wrong = self.root / 'bad.warc'
        wrong.write_bytes(self.warc.read_bytes().replace(b'Not found', b'Not valid'))
        bad_archive = self.root / 'bad.warc.gz'
        export_warc_gzip(wrong, bad_archive)
        with self.assertRaisesRegex(ValueError, 'payload digest mismatch'):
            export_cdxj(bad_archive, self.index)
        self.assertFalse(self.index.exists())
        offset = self.members[3]['offset']
        self.compressed.write_bytes(first[:offset] + first[offset + self.members[3]['length']:])
        export_cdxj(self.compressed, self.index)
        saved = self.index.read_bytes()
        with self.assertRaises(FileExistsError):
            export_cdxj(bad_archive, self.index)
        self.assertEqual(self.index.read_bytes(), saved)

    def test_cli_checks_index(self):
        command = [sys.executable, '-m', 'cli.export_mirror']
        args = [str(self.compressed), str(self.index)]
        for operation in ('cdxj', 'verify-cdxj'):
            self.assertEqual(json.loads(subprocess.check_output([*command, operation, *args])), {'entries': 3})
        self.index.write_bytes(b'incomplete\n')
        failed = subprocess.run([*command, 'verify-cdxj', *args], capture_output=True, text=True)
        self.assertEqual(failed.returncode, 2)
        self.assertIn('does not match', failed.stderr)
