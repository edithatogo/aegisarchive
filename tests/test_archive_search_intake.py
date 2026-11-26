import base64
from contextlib import closing
import gzip
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cli.aegis_cli import PythonWarcWriter
from cli.warc_verify import RECORD_SEPARATOR, parse_warc_header
from portable.archive_search_intake import build_catalogue
from portable.document_catalogue import Catalogue
from portable.document_search import SearchIndex


class ArchiveSearchIntakeTests(unittest.TestCase):
    def setUp(self):
        workspace = TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.root = Path(workspace.name)
        self.archive = self.root / 'capture.warc'
        self.saved = self.root / 'search.sqlite'
        self.html = b'<p>Archive approval ' + b'record ' * 100 + b'</p>'
        with closing(PythonWarcWriter(str(self.archive))) as writer:
            writer.write_response('https://fixture.test/first', 200, {'Content-Type': 'text/html'}, self.html)
            result = writer.write_response('https://fixture.test/duplicate', 200, {'Content-Type': 'text/html'}, self.html)
            self.assertTrue(result['is_revisit'])
            writer.write_response('https://fixture.test/plain', 200, {'Content-Type': 'text/plain'}, b'backup schedule')
            writer.write_response('https://fixture.test/pdf', 200, {'Content-Type': 'application/pdf'}, b'%PDF archive')

    def test_plain_and_gzip_capture_text_and_revisit_citations(self):
        original = self.archive.read_bytes()
        compressed = self.root / 'compressed.warc.gz'
        middle = len(original) // 2
        compressed.write_bytes(gzip.compress(original[:middle]) + gzip.compress(original[middle:]))
        compressed_before = hashlib.sha256(compressed.read_bytes()).hexdigest()
        for archive in (self.archive, compressed):
            with self.subTest(archive=archive.name):
                output = self.root / (archive.name + '.sqlite')
                summary = build_catalogue(output, [archive], handling='public')
                self.assertEqual(summary['indexed'], 3)
                self.assertEqual(summary['skipped'], {'unsupported_record': 1, 'unsupported_type': 1})
                with closing(Catalogue(output, read_only=True)) as catalogue:
                    search = SearchIndex(catalogue)
                    hits = {hit['original']['url']: hit for hit in search.search('approval')}
                    first = hits['https://fixture.test/first']
                    copied = hits['https://fixture.test/duplicate']
                    self.assertNotEqual(first['revision_id'], copied['revision_id'])
                    self.assertEqual(first['original']['content_hash'], hashlib.sha256(self.html).hexdigest())
                    self.assertEqual(first['original']['content_hash'], copied['original']['content_hash'])
                    self.assertEqual(first['warc']['record_id'], copied['warc']['refers_to'])
                    self.assertEqual(copied['warc']['archive'], archive.name)
                    citation = first['warc']
                    self.assertEqual(citation['offset_kind'], 'file' if archive == self.archive else 'uncompressed')
                    self.assertTrue(original[citation['offset']:][:8].startswith(b'WARC/1.1'))
                    receipt = catalogue.change_receipt(first['acquisition_receipt_id'])
                    self.assertEqual(receipt['after_content_hash'], first['original']['content_hash'])
                    self.assertEqual(len(search.search('backup')), 1)
        self.assertEqual(self.archive.read_bytes(), original)
        self.assertEqual(hashlib.sha256(compressed.read_bytes()).hexdigest(), compressed_before)

    def test_missing_classification_and_nonpublic_captures(self):
        with self.assertRaises(ValueError):
            build_catalogue(self.saved, [self.archive], handling=None)
        for handling in ('unknown', 'restricted'):
            output = self.root / f'{handling}.sqlite'
            summary = build_catalogue(output, [self.archive], handling=handling)
            self.assertEqual(summary['indexed'], 0)
            with closing(Catalogue(output, read_only=True)) as catalogue:
                self.assertEqual(SearchIndex(catalogue).search('approval'), [])
                self.assertEqual(catalogue.db.execute('SELECT COUNT(*) FROM content_objects').fetchone()[0], 0)

    def test_corrupt_container_leaves_existing_outputs_and_inputs_intact(self):
        broken = self.root / 'broken.warc'
        broken.write_bytes(self.archive.read_bytes().replace(b'backup schedule', b'broken schedule'))
        with self.assertRaisesRegex(ValueError, 'WARC payload digest mismatch'):
            build_catalogue(self.saved, [broken], handling='public')
        self.assertFalse(self.saved.exists())
        self.saved.write_bytes(b'existing local file')
        with self.assertRaises(FileExistsError):
            build_catalogue(self.saved, [self.archive], handling='public')
        self.assertEqual(self.saved.read_bytes(), b'existing local file')

    def test_warc_10_resource_with_base32_digest(self):
        body = b'temporary visitor pass'
        checksum = base64.b32encode(hashlib.sha1(body, usedforsecurity=False).digest()).decode()
        record = (
            'WARC/1.0\r\nWARC-Type: resource\r\nWARC-Target-URI: https://fixture.test/pass\r\n'
            'WARC-Date: 2026-11-01T12:00:00Z\r\nWARC-Record-ID: <urn:uuid:fixture>\r\n'
            f'Content-Type: text/plain\r\nWARC-Block-Digest: sha1:{checksum}\r\n'
            f'Content-Length: {len(body)}\r\n\r\n'
        ).encode() + body + b'\r\n\r\n'
        split = self.root / 'split'
        split.mkdir()
        archive = split / self.archive.name
        archive.write_bytes(record)
        result = build_catalogue(self.saved, [archive, self.archive], handling='public')
        self.assertEqual(result['indexed'], 4)
        with closing(Catalogue(self.saved, read_only=True)) as catalogue:
            index = SearchIndex(catalogue)
            hit, = index.search('visitor pass')
            self.assertEqual(hit['warc']['captured_at'], '2026-11-01T12:00:00Z')
            plain, = index.search('backup schedule')
            self.assertEqual(hit['warc']['archive'], plain['warc']['archive'])
            self.assertNotEqual(hit['warc']['archive_id'], plain['warc']['archive_id'])
            inputs = dict(catalogue.db.execute('SELECT archive_id,path FROM warc_inputs'))
            self.assertEqual(inputs, {1: str(archive.resolve()), 2: str(self.archive.resolve())})

    def test_segmented_and_chunked_frames_are_skipped_with_block_integrity(self):
        def frame(label, extra, block, payload):
            headers = (
                'WARC/1.1\r\nWARC-Type: response\r\n'
                f'WARC-Target-URI: https://fixture.test/{label}\r\n'
                f'WARC-Record-ID: <urn:uuid:{label}>\r\nWARC-Date: 2026-11-01T12:00:00Z\r\n'
                'Content-Type: application/http; msgtype=response\r\n'
                f'WARC-Block-Digest: sha256:{hashlib.sha256(block).hexdigest()}\r\n'
                f'WARC-Payload-Digest: sha256:{hashlib.sha256(payload).hexdigest()}\r\n'
                f'{extra}Content-Length: {len(block)}\r\n\r\n'
            )
            return headers.encode() + block + RECORD_SEPARATOR

        prefix = b'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n'
        segmented = frame('segment', 'WARC-Segment-Number: 1\r\n', prefix + b'\r\npart', b'part and rest')
        wire = prefix + b'Transfer-Encoding: chunked\r\n\r\n5\r\nhello\r\n0\r\n\r\n'
        chunked = frame('chunked', '', wire, b'hello')
        chunked_error = frame('chunked-error', '', wire.replace(b'200 OK', b'404 Not Found'), b'hello')
        archive = self.root / 'unsupported.warc'
        archive.write_bytes(segmented + chunked + chunked_error)
        result = build_catalogue(self.saved, [archive, self.archive], handling='public')
        self.assertEqual(result['indexed'], 3)
        self.assertEqual(result['skipped']['segmented_record'], 1)
        self.assertEqual(result['skipped']['encoded_payload'], 2)
        archive.write_bytes(segmented + chunked.replace(b'hello', b'error'))
        failed = self.root / 'corrupt.sqlite'
        with self.assertRaisesRegex(ValueError, 'WARC block digest mismatch'):
            build_catalogue(failed, [archive], handling='public')
        self.assertFalse(failed.exists())

    def test_zero_length_and_standard_header_only_revisits_resolve(self):
        raw = self.archive.read_bytes()
        offset = raw.index(b'WARC/1.1\r\nWARC-Type: revisit')
        header_end = raw.index(RECORD_SEPARATOR, offset)
        header = raw[offset:header_end]
        _, length = parse_warc_header(header)
        end = header_end + len(RECORD_SEPARATOR) + length + len(RECORD_SEPARATOR)
        empty = header.replace(f'Content-Length: {length}'.encode(), b'Content-Length: 0')
        frames = (empty + RECORD_SEPARATOR * 2,
                  header + b'\r\nWARC-Truncated: length' + raw[header_end:end])
        for number, frame in enumerate(frames):
            with self.subTest(number=number):
                archive = self.root / f'revisit-{number}.warc'
                archive.write_bytes(raw[:offset] + frame + raw[end:])
                output = self.root / f'revisit-{number}.sqlite'
                result = build_catalogue(output, [archive], handling='public')
                self.assertEqual(result['indexed'], 3)
                with closing(Catalogue(output, read_only=True)) as catalogue:
                    hits = SearchIndex(catalogue).search('approval')
                    self.assertEqual(len(hits), 2)
                    self.assertEqual(sum('refers_to' in hit['warc'] for hit in hits), 1)
