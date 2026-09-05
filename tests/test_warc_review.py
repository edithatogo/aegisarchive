"""Regression cases for misleading integrity success and malformed CDX spans."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from cli.warc_verify import verify_warc
from cli.aegis_cli import PythonWarcWriter


class ReviewIntegrityTests(unittest.TestCase):
    def test_invalid_containers_fail_closed(self):
        cases = [b'', b'garbage', b'WARC/1.1\r\nContent-Length: 20\r\n\r\nx',
                 b'WARC/1.1\r\nContent-Length: ' + b'1' * 5000 + b'\r\n\r\n']
        with tempfile.TemporaryDirectory() as td, contextlib.redirect_stdout(io.StringIO()):
            p = Path(td) / 'bad.warc'
            for data in cases:
                p.write_bytes(data)
                self.assertFalse(verify_warc(str(p)))
            p = Path(td) / 'bad.warc.gz'
            p.write_bytes(b'not gzip')
            self.assertFalse(verify_warc(str(p)))

    def test_non_numeric_cdx_span_reports_failure(self):
        with tempfile.TemporaryDirectory() as td, contextlib.redirect_stdout(io.StringIO()):
            p = Path(td) / 't.warc'
            w = PythonWarcWriter(str(p))
            w.write_response('http://h.test/', 200, {}, b'hello')
            w.close()
            cdx = p.with_suffix('.cdx')
            lines = cdx.read_text().splitlines()
            fields = lines[1].split()
            fields[9] = 'invalid'
            cdx.write_text(lines[0] + '\n' + ' '.join(fields) + '\n')
            self.assertFalse(verify_warc(str(p), str(cdx)))
