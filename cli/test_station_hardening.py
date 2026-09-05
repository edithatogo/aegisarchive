#!/usr/bin/env python3
"""
Automated hardening tests for the AegisArchive local station server.
Python 3 standard library only.

Run from the repository root:
    python3 cli/test_station_hardening.py
"""

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
