#!/usr/bin/env python3
"""
AegisArchive - Universal Cross-Platform Launcher & Local Server
Zero third-party dependencies (Python 3 standard library only).
Works seamlessly on Windows, macOS, and Linux.

Licensed under the Apache License, Version 2.0.
"""

import sys
import os
import socket
import webbrowser
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
WEB_DIR = os.path.join(REPO_ROOT, "web")

class AegisArchiveHandler(SimpleHTTPRequestHandler):
    """Hardened local handler for the zero-install web console.

    Security properties (loopback station hardening):
      * The launcher binds to 127.0.0.1 only; requests carrying a foreign
        ``Host`` header are rejected with 400 (DNS-rebinding defence).
      * Dotfiles and dot-directories (``.git``, hidden metadata, ``._*``
        AppleDouble artifacts) are never served (403).
      * No permissive CORS headers: only same-origin pages can read responses.
      * All responses carry ``Cache-Control: no-store`` so archived material
        never lingers in the host browser cache.
    """

    # Populated by the launcher before serving begins:
    allowed_hosts = set()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def guess_type(self, path):
        if path.endswith(".warc"):
            return "application/warc"
        elif path.endswith(".cdx"):
            return "text/plain"
        elif path.endswith(".js"):
            return "application/javascript"
        elif path.endswith(".json"):
            return "application/json"
        elif path.endswith(".css"):
            return "text/css"
        return super().guess_type(path)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    # --- Hardening guards -------------------------------------------------

    def _host_allowed(self):
        return self.headers.get("Host", "") in self.allowed_hosts

    def _is_forbidden_path(self):
        raw = self.path.split("?", 1)[0].split("#", 1)[0]
        path = unquote(raw)
        return any(seg.startswith(".") for seg in path.split("/") if seg)

    def _pre_flight_checks(self):
        """Return True if the request may proceed; otherwise the rejection
        response has already been sent."""
        if not self._host_allowed():
            self.send_error(400, "Invalid Host header")
            return False
        if self._is_forbidden_path():
            self.send_error(403, "Forbidden path")
            return False
        return True

    def do_GET(self):
        if self._pre_flight_checks():
            super().do_GET()

    def do_HEAD(self):
        if self._pre_flight_checks():
            super().do_HEAD()

    def do_OPTIONS(self):
        if self._pre_flight_checks():
            self.send_response(200)
            self.end_headers()

    def log_message(self, format, *args):
        # Keep console output clean
        pass

def find_available_port(start_port=8000, max_attempts=25):
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return None

def main():
    parser = argparse.ArgumentParser(description="AegisArchive Web Console Launcher")
    parser.add_argument("--port", type=int, default=8000, help="Initial port to bind (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open the default web browser")
    parser.add_argument("--profile", type=str, default=None, help="Optional path to preset profile JSON to load")
    args = parser.parse_args()

    port = find_available_port(args.port)
    if not port:
        print(f"[Error] Could not find an available port in range {args.port}..{args.port+25}.")
        sys.exit(1)

    # Restrict accepted Host headers to loopback names for this session
    # (anti-DNS-rebinding guard for the local station server).
    AegisArchiveHandler.allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    url = f"http://127.0.0.1:{port}/index.html"
    if args.profile:
        abs_profile = os.path.abspath(args.profile)
        url += f"?profile={abs_profile}"

    server = ThreadingHTTPServer(("127.0.0.1", port), AegisArchiveHandler)

    print("=" * 66)
    print("  🛡️  AegisArchive — Server-Preserving Archival Engine")
    print("=" * 66)
    print(f"  Local Web Console: {url}")
    print(f"  WARC Replay Viewer: http://127.0.0.1:{port}/viewer.html")
    print(f"  Serving Directory:  {WEB_DIR}")
    print("  Status:             Nominal (Press Ctrl+C to stop server)")
    print("=" * 66)

    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[AegisArchive] Server stopped gracefully.")
        server.server_close()

if __name__ == "__main__":
    main()
