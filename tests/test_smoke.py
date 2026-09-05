"""Stdlib smoke tests: import paths, WARC verifier, CDX search, MCP dispatch."""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from cli import warc_verify  # noqa: E402
from mcp import server  # noqa: E402

MINIMAL_WARC = (
    b"WARC/1.1\r\nWARC-Type: warcinfo\r\nWARC-Record-ID: <urn:uuid:1>\r\n"
    b"Content-Type: application/warc-fields\r\nContent-Length: 2\r\n\r\nok\r\n\r\n"
)


class SmokeTests(unittest.TestCase):
    def test_verify_warc_accepts_minimal_container(self):
        with tempfile.NamedTemporaryFile(suffix=".warc", delete=False) as fh:
            fh.write(MINIMAL_WARC)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertTrue(warc_verify.verify_warc(fh.name))
        finally:
            os.unlink(fh.name)

    def test_verify_warc_missing_file_is_false(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(warc_verify.verify_warc(os.path.join(ROOT, "does-not-exist.warc")))

    def test_search_cdx_reports_matches(self):
        line = " CDX N b a m s k r M S V g\ncom,example)/ 20260905000000 https://example.com/ text/html 200 X - - 0 0 a.warc\n"
        with tempfile.NamedTemporaryFile("w", suffix=".cdx", delete=False) as fh:
            fh.write(line)
        try:
            result = server.search_cdx("example", fh.name)
        finally:
            os.unlink(fh.name)
        self.assertEqual(result["total_matches"], 1)
        self.assertEqual(result["matches"][0]["status"], "200")

    def test_mcp_initialize_over_stdio(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(ROOT, "mcp", "server.py")],
            input=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}) + "\n",
            capture_output=True, text=True, timeout=30,
        )
        reply = json.loads(proc.stdout.splitlines()[0])
        self.assertEqual(reply["result"]["serverInfo"]["name"], "aegisarchive-mcp")


if __name__ == "__main__":
    unittest.main()
