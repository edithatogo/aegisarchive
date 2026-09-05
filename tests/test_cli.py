import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI_SCRIPT = os.path.join(ROOT, "cli", "aegis_cli.py")


class MockServerHandler(BaseHTTPRequestHandler):
    WITH_RETRY = False
    hits = {"/r": 0}

    def do_GET(self):
        root_links = b'<a href="/b">b</a><a href="/c?utm_source=x&id=2">c</a><a href="/doc.pdf">pdf</a>'
        if self.WITH_RETRY:
            root_links += b'<a href="/r">r</a>'

        pages = {
            "/": root_links,
            "/b": b"<p>b</p>",
            "/c?id=2": b"<p>c</p>",
        }

        if self.path == "/r" and self.WITH_RETRY:
            self.hits["/r"] += 1
            if self.hits["/r"] == 1:
                self.send_response(503)
                self.send_header("Retry-After", "1")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            body, ct = b"<p>r</p>", "text/html; charset=utf-8"
        elif self.path == "/doc.pdf":
            body, ct = b"%PDF-1.4 fake", "application/pdf"
        elif self.path in pages:
            body, ct = pages[self.path], "text/html; charset=utf-8"
        else:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class TestCli(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), MockServerHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def run_cli_harvest(self, with_retry=False):
        MockServerHandler.WITH_RETRY = with_retry
        MockServerHandler.hits["/r"] = 0

        with tempfile.TemporaryDirectory() as tmpdir:
            profile = {
                "profile_id": "test_profile",
                "profile_name": "Test Profile",
                "target": {
                    "allowed_domains": ["127.0.0.1"],
                    "seed_urls": {"tier_1_core": [f"http://127.0.0.1:{self.port}/"]},
                    "max_depth": 3,
                    "max_pages": 50,
                },
                "politeness": {
                    "min_delay_ms": 250,
                    "max_delay_ms": 300,
                    "max_requests_per_minute": 300,
                    "burst_limit": 20,
                    "cooldown_seconds": 5,
                },
                "archival": {"warc_prefix": "test_archive"},
            }
            profile_path = os.path.join(tmpdir, "profile.json")
            with open(profile_path, "w", encoding="utf-8") as f:
                json.dump(profile, f)

            result = subprocess.run(
                [sys.executable, CLI_SCRIPT, "--profile", profile_path, "--output-dir", tmpdir],
                capture_output=True,
                text=True,
                timeout=120,
            )
            warc_files = [f for f in os.listdir(tmpdir) if f.endswith(".warc")]
            self.assertTrue(len(warc_files) > 0, f"No warc files generated: {result.stderr}")
            warc_path = os.path.join(tmpdir, warc_files[0])
            with open(warc_path, "rb") as f:
                warc_bytes = f.read()

            cdx_path = os.path.join(tmpdir, warc_files[0].replace(".warc", ".cdx"))
            with open(cdx_path, "r", encoding="utf-8") as f:
                cdx_lines = [line.strip() for line in f.read().splitlines()[1:] if line.strip()]

            return result, warc_bytes, cdx_lines

    def test_cli_standard_crawl(self):
        result, warc_bytes, cdx_lines = self.run_cli_harvest(with_retry=False)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(warc_bytes.count(b"WARC-Type: response"), 4)
        self.assertEqual(len(cdx_lines), 4)
        for line in cdx_lines:
            parts = line.split()
            self.assertEqual(len(parts), 11, f"CDX line does not have 11 fields: {line}")
        self.assertTrue(any("application/pdf" in line for line in cdx_lines))
        self.assertTrue(any("/c?id=2" in line.split()[2] for line in cdx_lines))

    def test_cli_retry_503_and_retry_after(self):
        result, warc_bytes, cdx_lines = self.run_cli_harvest(with_retry=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(warc_bytes.count(b"WARC-Type: response"), 5)
        self.assertEqual(MockServerHandler.hits["/r"], 2)
        r_entry = next((l for l in cdx_lines if l.split()[2].endswith("/r")), None)
        self.assertIsNotNone(r_entry)
        self.assertEqual(r_entry.split()[4], "200")

    def test_cli_help_flag(self):
        result = subprocess.run(
            [sys.executable, CLI_SCRIPT, "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("AegisArchive Headless Archival Engine", result.stdout)


if __name__ == "__main__":
    unittest.main()
