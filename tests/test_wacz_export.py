from contextlib import closing
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import warnings
from zipfile import ZIP_STORED, ZipFile

from cli.aegis_cli import PythonWarcWriter
from cli.export_mirror import export_wacz, verify_wacz


DOCUMENT = b'<!doctype html><h1>Archived WACZ page</h1><link rel="stylesheet" href="archive.css">'
STYLESHEET = b'h1{color:rgb(10,20,30)}'
CAPTURE_DATE = '2026-11-26T12:34:56Z'


def create_archive(path, origin):
    with (patch('cli.aegis_cli.format_warc_date', return_value=CAPTURE_DATE),
          closing(PythonWarcWriter(str(path))) as writer):
        writer.write_response(origin + '/archive.html', 200, {'Content-Type': 'text/html'}, DOCUMENT)
        writer.write_response(origin + '/archive.css', 200, {'Content-Type': 'text/css'}, STYLESHEET)


class WaczPackageTest(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.warc = self.root / 'archive.warc'
        self.bundle = self.root / 'archive.wacz'
        self.origin = 'https://example.test'
        create_archive(self.warc, self.origin)

    def test_deterministic_package_and_independent_zip_readback(self):
        args = [sys.executable, '-m', 'cli.export_mirror']
        result = dict(entries=2, pages=1, wacz_version='1.1.1')
        self.assertEqual(json.loads(subprocess.check_output([*args, 'wacz', str(self.warc), str(self.bundle)])), result)
        self.assertEqual(json.loads(subprocess.check_output([*args, 'verify-wacz', str(self.bundle)])), result)
        second = self.root / 'second.wacz'
        self.assertEqual(export_wacz(self.warc, second), result)
        self.assertEqual(second.read_bytes(), self.bundle.read_bytes())
        with ZipFile(self.bundle) as package:
            self.assertEqual(package.namelist(), ['archive/data.warc.gz', 'indexes/index.cdxj',
                                                  'pages/pages.jsonl', 'datapackage.json', 'datapackage-digest.json'])
            self.assertEqual(package.getinfo('archive/data.warc.gz').compress_type, ZIP_STORED)
            manifest = package.read('datapackage.json')
            self.assertEqual(json.loads(package.read('datapackage-digest.json')),
                             dict(path='datapackage.json', hash='sha256:' + hashlib.sha256(manifest).hexdigest()))
            metadata = json.loads(manifest)
            self.assertEqual(metadata['profile'], 'data-package')
            self.assertEqual(metadata['wacz_version'], '1.1.1')
            self.assertEqual(metadata['mainPageUrl'], self.origin + '/archive.html')
            for resource in metadata['resources']:
                data = package.read(resource['path'])
                self.assertEqual(resource['bytes'], len(data))
                self.assertEqual(resource['hash'], 'sha256:' + hashlib.sha256(data).hexdigest())
            pages = [json.loads(row) for row in package.read('pages/pages.jsonl').splitlines()]
            self.assertEqual(pages[0]['format'], 'json-pages-1.0')
            self.assertEqual(pages[1]['ts'], '2026-11-26T12:34:56+00:00')
            self.assertEqual(pages[1]['url'], metadata['mainPageUrl'])
            compressed = package.read('archive/data.warc.gz')
            self.assertEqual(gzip.decompress(compressed), self.warc.read_bytes())
            for row in package.read('indexes/index.cdxj').splitlines():
                data = json.loads(row.split(b' ', 2)[2])
                offset, length = int(data['offset']), int(data['length'])
                raw = gzip.decompress(compressed[offset:offset + length])
                self.assertIn(data['url'].encode(), raw)
                expected = DOCUMENT if data['url'].endswith('.html') else STYLESHEET
                self.assertEqual(raw.split(b'\r\n\r\n', 2)[2][:-4], expected)
        with self.assertRaises(FileExistsError):
            export_wacz(self.warc, self.bundle)

    def test_altered_package_with_valid_zip_crc_fails(self):
        export_wacz(self.warc, self.bundle)
        with ZipFile(self.bundle) as package:
            members = {name: package.read(name) for name in package.namelist()}
        rejected = self.root / 'rejected.wacz'
        for path, data, message in (
            ('indexes/index.cdxj', members['indexes/index.cdxj'].split(b'\n', 1)[1], 'CDXJ index'),
            ('pages/pages.jsonl', b'{}\n', 'WACZ pages'),
            ('datapackage.json', members['datapackage.json'].replace(b'1.1.1', b'1.1.0'), 'WACZ manifest'),
            ('datapackage-digest.json', b'{}\n', 'WACZ manifest digest'),
            ('archive/data.warc.gz', members['archive/data.warc.gz'][:-1], 'Truncated gzip'),
        ):
            with self.subTest(path=path):
                with ZipFile(rejected, 'w') as package:
                    for name, original in members.items():
                        package.writestr(name, data if name == path else original)
                with self.assertRaisesRegex(ValueError, message):
                    verify_wacz(rejected)
        for bad_path in ('../data.warc.gz', 'pages/pages.jsonl'):
            with ZipFile(rejected, 'w') as package:
                for name, data in members.items():
                    package.writestr(name, data)
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore', UserWarning)
                    package.writestr(bad_path, b'extra')
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                verify_wacz(rejected)

    def test_failed_readback_keeps_package_private(self):
        original = self.warc.read_bytes()
        with patch('cli.export_mirror.verify_wacz', side_effect=ValueError('fixture readback failure')):
            with self.assertRaisesRegex(ValueError, 'readback failure'):
                export_wacz(self.warc, self.bundle)
        self.assertFalse(self.bundle.exists())
        self.assertEqual(self.warc.read_bytes(), original)

    def test_revisit_without_http_headers_does_not_invent_a_successful_page(self):
        payload = b'<h1>Not found</h1>' * 100
        with closing(PythonWarcWriter(str(self.warc))) as writer:
            writer.write_response(self.origin + '/not-found', 404, {'Content-Type': 'text/html'}, payload)
            writer.write_response(self.origin + '/also-missing', 404, {'Content-Type': 'text/html'}, payload)
        contents = self.warc.read_bytes()
        prefix, _, revisit = contents.rpartition(b'WARC/1.1\r\n')
        header, _ = revisit.split(b'\r\n\r\n', 1)
        header = re.sub(rb'Content-Length: \d+', b'Content-Length: 0', header)
        self.warc.write_bytes(prefix + b'WARC/1.1\r\n' + header + b'\r\n\r\n\r\n\r\n')
        self.assertEqual(export_wacz(self.warc, self.bundle)['pages'], 0)
        with ZipFile(self.bundle) as package:
            rows = [json.loads(line.split(b' ', 2)[2]) for line in package.read('indexes/index.cdxj').splitlines()]
            self.assertEqual([(row['mime'], row['status']) for row in rows],
                             [('warc/revisit', '-'), ('text/html', '404')])
