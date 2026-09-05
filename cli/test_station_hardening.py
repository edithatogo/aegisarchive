#!/usr/bin/env python3
"""
Automated hardening tests for the AegisArchive local station server.
Python 3 standard library only.

Run from the repository root:
    python3 cli/test_station_hardening.py
"""

import json
import os
import socket
import threading
import unittest
import urllib.error
import urllib.request

import launch


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class StationHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = _free_port()
        cls.loopback_host = f"127.0.0.1:{cls.port}"
        launch.AegisArchiveHandler.allowed_hosts = {
            cls.loopback_host,
            f"localhost:{cls.port}",
        }
        cls.httpd = launch.ThreadingHTTPServer(
            ("127.0.0.1", cls.port), launch.AegisArchiveHandler
        )
        cls.httpd.daemon_threads = True
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def _request(self, path, host=None, method="GET"):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}", method=method
        )
        if host is not None:
            req.add_header("Host", host)
        opener = urllib.request.OpenerDirector()
        opener.add_handler(urllib.request.HTTPHandler())
        try:
            with opener.open(req, timeout=5) as resp:
                return resp.status, dict(resp.headers)
        except urllib.error.HTTPError as err:
            return err.code, dict(err.headers)

    # --- AC1: dotfiles and dot-directories are never served ---------------

    def test_dot_directory_forbidden(self):
        status, _ = self._request("/.git/config")
        self.assertEqual(status, 403)

    def test_appledouble_file_forbidden(self):
        status, _ = self._request("/._index.html")
        self.assertEqual(status, 403)

    def test_hidden_metadata_forbidden(self):
        status, _ = self._request("/.DS_Store")
        self.assertEqual(status, 403)

    def test_percent_encoded_dot_path_forbidden(self):
        status, _ = self._request("/%2egit/config")
        self.assertEqual(status, 403)

    # --- AC2: foreign Host headers are rejected (anti-DNS-rebinding) ------

    def test_foreign_host_rejected(self):
        status, _ = self._request("/index.html", host="attacker.example")
        self.assertEqual(status, 400)

    def test_localhost_host_accepted(self):
        status, _ = self._request("/index.html", host=f"localhost:{self.port}")
        self.assertEqual(status, 200)

    # --- AC3: responses carry Cache-Control: no-store ----------------------

    def test_cache_control_no_store(self):
        status, headers = self._request("/index.html")
        self.assertEqual(status, 200)
        self.assertIn("no-store", headers.get("Cache-Control", ""))


class StationControlEndpointTests(unittest.TestCase):
    """AC4/AC6: session-token-guarded shutdown and status self-test surface."""

    @classmethod
    def setUpClass(cls):
        cls.port = _free_port()
        cls.loopback_host = f"127.0.0.1:{cls.port}"
        launch.AegisArchiveHandler.allowed_hosts = {cls.loopback_host}
        launch.AegisArchiveHandler.session_token = "test-token-123"
        launch.AegisArchiveHandler.station_info = {
            "station": "aegisarchive",
            "port": cls.port,
        }
        cls.httpd = launch.ThreadingHTTPServer(
            ("127.0.0.1", cls.port), launch.AegisArchiveHandler
        )
        cls.httpd.daemon_threads = True
        cls.serve_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.serve_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        launch.AegisArchiveHandler.session_token = ""

    def _request(self, path, method="GET", token=None):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}", method=method, data=b""
        )
        req.add_header("Host", self.loopback_host)
        if token is not None:
            req.add_header("X-Station-Token", token)
        opener = urllib.request.OpenerDirector()
        opener.add_handler(urllib.request.HTTPHandler())
        try:
            with opener.open(req, timeout=5) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as err:
            return err.code, err.read()

    def test_status_endpoint_reports_station(self):
        status, body = self._request("/__station/status")
        self.assertEqual(status, 200)
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(payload.get("station"), "aegisarchive")

    def test_status_endpoint_does_not_expose_token(self):
        # The session token must never be disclosed by the unauthenticated
        # status endpoint (defence-in-depth; only POST shutdown needs it).
        status, body = self._request("/__station/status")
        self.assertEqual(status, 200)
        payload = json.loads(body.decode("utf-8"))
        self.assertNotIn("session_token", payload)
        self.assertNotIn("test-token-123", body.decode("utf-8"))

    def test_unknown_control_endpoint_404(self):
        status, _ = self._request("/__station/nope")
        self.assertEqual(status, 404)

    def test_shutdown_without_token_forbidden(self):
        status, _ = self._request("/__station/shutdown", method="POST")
        self.assertEqual(status, 403)

    def test_shutdown_with_wrong_token_forbidden(self):
        status, _ = self._request(
            "/__station/shutdown", method="POST", token="wrong-token"
        )
        self.assertEqual(status, 403)

    def test_shutdown_with_valid_token_stops_server(self):
        # Self-contained: uses a dedicated server instance so the class-level
        # server keeps serving the remaining tests regardless of test order.
        port = _free_port()
        original_hosts = launch.AegisArchiveHandler.allowed_hosts
        launch.AegisArchiveHandler.allowed_hosts = set(original_hosts) | {f"127.0.0.1:{port}"}
        launch.AegisArchiveHandler.session_token = "dedicated-token"
        httpd = launch.ThreadingHTTPServer(
            ("127.0.0.1", port), launch.AegisArchiveHandler
        )
        httpd.daemon_threads = True
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/__station/shutdown", method="POST", data=b""
            )
            req.add_header("Host", f"127.0.0.1:{port}")
            req.add_header("X-Station-Token", "dedicated-token")
            opener = urllib.request.OpenerDirector()
            opener.add_handler(urllib.request.HTTPHandler())
            with opener.open(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
        finally:
            httpd.server_close()
            launch.AegisArchiveHandler.allowed_hosts = original_hosts
            launch.AegisArchiveHandler.session_token = "test-token-123"


class BundleIntegrityTests(unittest.TestCase):
    """AC5: fail-closed verification of the SHA-256 bundle manifest."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.good = os.path.join(self.tmp.name, "artifact.bin")
        with open(self.good, "wb") as fh:
            fh.write(b"aegisarchive-integrity-payload")
        self.manifest = os.path.join(self.tmp.name, "CHECKSUMS.sha256")
        import verify_bundle
        self.vb = verify_bundle

    def test_verify_passes_for_intact_artifact(self):
        digest = self.vb.sha256_of(self.good)
        with open(self.manifest, "w", encoding="utf-8") as fh:
            fh.write(f"{digest}  artifact.bin\n")
        self.assertEqual(self.vb.verify(self.manifest, self.tmp.name), 0)

    def test_verify_fails_for_tampered_artifact(self):
        with open(self.manifest, "w", encoding="utf-8") as fh:
            fh.write(f"{'0' * 64}  artifact.bin\n")
        self.assertEqual(self.vb.verify(self.manifest, self.tmp.name), 1)

    def test_verify_fails_closed_for_missing_artifact(self):
        digest = self.vb.sha256_of(self.good)
        with open(self.manifest, "w", encoding="utf-8") as fh:
            fh.write(f"{digest}  artifact.bin\n{digest}  gone.bin\n")
        self.assertEqual(self.vb.verify(self.manifest, self.tmp.name), 1)

    def test_verify_fails_closed_for_missing_manifest(self):
        self.assertEqual(
            self.vb.verify(os.path.join(self.tmp.name, "nope.sha256"), self.tmp.name), 1
        )

    def test_generate_roundtrip(self):
        out = os.path.join(self.tmp.name, "gen.sha256")
        count = self.vb.generate_manifest(self.tmp.name, out)
        self.assertEqual(count, 1)
        self.assertEqual(self.vb.verify(out, self.tmp.name), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
