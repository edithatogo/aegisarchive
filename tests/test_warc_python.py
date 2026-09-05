import gzip
import os
import re
import shutil
import sys
import tempfile
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, 'cli'))
sys.path.insert(0, os.path.join(BASE_DIR, 'mcp'))

import aegis_cli as a
import server
import warc_verify as v


class TestWarcPython(unittest.TestCase):
    def test_warc_writer_header_hygiene(self):
        with tempfile.TemporaryDirectory() as td:
            warc_path = os.path.join(td, 'test.warc')
            writer = a.PythonWarcWriter(warc_path)
            raw_headers = {
                'Content-Encoding': 'gzip',
                'Transfer-Encoding': 'chunked',
                'Content-Length': '99',
                'Content-Type': 'text/plain',
            }
            writer.write_response('http://h.test/', 200, raw_headers, b'hello')
            writer.close()

            with open(warc_path, 'rb') as f:
                content = f.read()

            self.assertNotIn(b'content-encoding', content.lower())
            self.assertNotIn(b'transfer-encoding', content.lower())
            self.assertIn(b'Content-Length: 5\r\n', content)

    def test_cdx_11_fields_and_offsets(self):
        with tempfile.TemporaryDirectory() as td:
            warc_path = os.path.join(td, 'test.warc')
            writer = a.PythonWarcWriter(warc_path)
            writer.write_response(
                'http://h.test/a', 200, {'Content-Type': 'text/html'}, b'<p>a</p>'
            )
            writer.write_response(
                'http://h.test/b', 200, {'Content-Type': 'text/plain'}, b'b' * 600
            )
            writer.close()

            cdx_path = warc_path.replace('.warc', '.cdx')
            with open(cdx_path, 'r', encoding='utf-8') as f:
                lines = [ln.strip() for ln in f if ln.strip()]

            self.assertEqual(lines[0], 'CDX N b a m s k r M S V g')
            for line in lines[1:]:
                parts = line.split()
                self.assertEqual(len(parts), 11)

    def test_warc_refers_to_on_revisit(self):
        with tempfile.TemporaryDirectory() as td:
            warc_path = os.path.join(td, 'test.warc')
            writer = a.PythonWarcWriter(warc_path)
            writer.write_response(
                'http://h.test/a', 200, {'Content-Type': 'text/plain'}, b'x' * 600
            )
            r2 = writer.write_response(
                'http://h.test/b', 200, {'Content-Type': 'text/plain'}, b'x' * 600
            )
            writer.close()

            self.assertTrue(r2['is_revisit'])
            with open(warc_path, 'rb') as f:
                b = f.read()
            idx = b.index(b'WARC-Type: revisit')
            m = re.search(rb'WARC-Refers-To: (<urn:uuid:[0-9a-f-]+>)', b[idx:])
            self.assertIsNotNone(m)
            self.assertIn(b'WARC-Record-ID: ' + m.group(1), b[:idx])

    def test_warc_request_record_concurrent(self):
        with tempfile.TemporaryDirectory() as td:
            warc_path = os.path.join(td, 'test.warc')
            writer = a.PythonWarcWriter(warc_path)
            writer.write_response(
                'http://h.test/p?q=1',
                200,
                {'Content-Type': 'text/html'},
                b'hello',
                request_headers={'User-agent': 'AegisArchive/1.0'},
            )
            writer.close()

            with open(warc_path, 'rb') as f:
                b = f.read()

            self.assertEqual(b.count(b'WARC-Type: request'), 1)
            self.assertEqual(b.count(b'WARC-Concurrent-To: '), 2)
            self.assertIn(
                b'GET /p?q=1 HTTP/1.1\r\nHost: h.test\r\nUser-agent: AegisArchive/1.0\r\n\r\n',
                b,
            )

            cdx_path = warc_path.replace('.warc', '.cdx')
            with open(cdx_path, 'r', encoding='utf-8') as f:
                parts = f.read().strip().split('\n')[1].split()
            rec_offset = int(parts[9])
            self.assertTrue(b.startswith(b'WARC/1.1\r\nWARC-Type: response', rec_offset))

    def test_warc_verify_with_cdx_and_compressed(self):
        with tempfile.TemporaryDirectory() as td:
            warc_path = os.path.join(td, 't.warc')
            cdx_path = os.path.join(td, 't.cdx')
            writer = a.PythonWarcWriter(warc_path)
            writer.write_response(
                'http://h.test/a', 200, {'Content-Type': 'text/html'}, b'<p>a</p>'
            )
            writer.write_response(
                'http://h.test/b', 200, {'Content-Type': 'text/plain'}, b'b' * 600
            )
            writer.write_response(
                'http://h.test/c', 200, {'Content-Type': 'text/plain'}, b'b' * 600
            )
            writer.close()

            # Clean warc + clean cdx
            self.assertTrue(v.verify_warc(warc_path, cdx_path))

            # Compressed warc.gz
            gz_path = warc_path + '.gz'
            with open(warc_path, 'rb') as f_in, gzip.open(gz_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
            self.assertTrue(v.verify_warc(gz_path, cdx_path))

            # Tampered cdx offset should fail verification
            with open(cdx_path, 'r', encoding='utf-8') as f:
                lines = f.read().split('\n')
            parts = lines[-2].split()
            parts[9] = '1'  # bad offset
            lines[-2] = ' '.join(parts)
            bad_cdx_path = os.path.join(td, 'bad.cdx')
            with open(bad_cdx_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            self.assertFalse(v.verify_warc(warc_path, bad_cdx_path))

    def test_mcp_search_cdx_length_offset_filename(self):
        with tempfile.TemporaryDirectory() as td:
            cdx_path = os.path.join(td, 't.cdx')
            with open(cdx_path, 'w', encoding='utf-8') as f:
                f.write(
                    ' CDX N b a m s k r M S V g\n'
                    'test,h)/ 20260905000000 http://h.test/ text/html 200 abc - - 455 513 t.warc\n'
                )
            res = server.search_cdx('h.test', cdx_path)
            self.assertEqual(len(res['matches']), 1)
            m = res['matches'][0]
            self.assertEqual(m['length'], '455')
            self.assertEqual(m['offset'], '513')
            self.assertEqual(m['filename'], 't.warc')


if __name__ == '__main__':
    unittest.main()
