#!/usr/bin/env python3
"""
AegisArchive - Universal Cross-Platform Launcher & Local Server
Zero third-party dependencies (Python 3 standard library only).
Works seamlessly on Windows, macOS, and Linux.

Licensed under the Apache License, Version 2.0.
"""

import sys
import os
import json
import time
import secrets
import socket
import threading
import platform
import urllib.request
import webbrowser
import argparse
from datetime import datetime, timezone
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
    session_token = ""       # per-session token guarding control endpoints
    station_info = {}        # status payload served at /__station/status
    last_activity = 0.0      # monotonic-ish timestamp for the idle watchdog

    CONTROL_PREFIX = "/__station/"

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
        type(self).last_activity = time.time()
        if not self._pre_flight_checks():
            return
        if self.path.split("?", 1)[0].startswith(self.CONTROL_PREFIX):
            self._handle_control_get()
        else:
            super().do_GET()

    def do_HEAD(self):
        type(self).last_activity = time.time()
        if self._pre_flight_checks():
            super().do_HEAD()

    def do_POST(self):
        type(self).last_activity = time.time()
        if not self._pre_flight_checks():
            return
        sub = self.path.split("?", 1)[0][len(self.CONTROL_PREFIX):].strip("/")
        if sub == "shutdown":
            # Fail closed: the per-session token is required. Cross-origin
            # pages cannot read it because no CORS headers are emitted.
            if (
                not self.session_token
                or self.headers.get("X-Station-Token") != self.session_token
            ):
                self.send_error(403, "Invalid or missing station token")
                return
            body = b'{"shutdown": "requested"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            threading.Thread(target=self.server.shutdown, daemon=True).start()
        else:
            self.send_error(404, "Unknown control endpoint")

    def _handle_control_get(self):
        sub = self.path.split("?", 1)[0][len(self.CONTROL_PREFIX):].strip("/")
        if sub == "status":
            payload = dict(self.station_info)
            payload["session_token"] = self.session_token
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404, "Unknown control endpoint")

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

def probe_existing_station(port, timeout=0.5):
    """Return True when an AegisArchive station is already serving on port.

    Verifies the endpoint identity (not just that the port is busy) so the
    launcher never mistakes an unrelated local service for this station.
    """
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/__station/status", timeout=timeout
        ) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return isinstance(data, dict) and data.get("station") == "aegisarchive"
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="AegisArchive Web Console Launcher")
    parser.add_argument("--port", type=int, default=8000, help="Initial port to bind (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open the default web browser")
    parser.add_argument("--profile", type=str, default=None, help="Optional path to preset profile JSON to load")
    parser.add_argument("--idle-timeout", type=float, default=0.0, help="Minutes of inactivity before automatic shutdown (0 = disabled)")
    args = parser.parse_args()

    if probe_existing_station(args.port):
        existing_url = f"http://127.0.0.1:{args.port}/index.html"
        print(f"[Info] An AegisArchive station is already active on port {args.port}.")
        if not args.no_browser:
            try:
                webbrowser.open(existing_url)
            except Exception:
                pass
        sys.exit(0)

    port = find_available_port(args.port)
    if not port:
        print(f"[Error] Could not find an available port in range {args.port}..{args.port+25}.")
        sys.exit(1)

    # Restrict accepted Host headers to loopback names for this session
    # (anti-DNS-rebinding guard for the local station server).
    AegisArchiveHandler.allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    # Per-session token guarding control endpoints (e.g. POST shutdown).
    AegisArchiveHandler.session_token = secrets.token_urlsafe(16)
    AegisArchiveHandler.station_info = {
        "station": "aegisarchive",
        "version": "1.1",
        "python": platform.python_version(),
        "platform": platform.system(),
        "port": port,
        "started_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "idle_timeout_min": args.idle_timeout if args.idle_timeout > 0 else None,
    }
    AegisArchiveHandler.last_activity = time.time()

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
    print(f"  Station Status:     http://127.0.0.1:{port}/status.html")
    print(f"  Serving Directory:  {WEB_DIR}")
    idle_note = (
        f"auto-stop after {args.idle_timeout:g} min idle"
        if args.idle_timeout > 0
        else "no idle auto-stop"
    )
    print(f"  Status:             Nominal ({idle_note}; Ctrl+C to stop)")
    print("=" * 66)

    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    if args.idle_timeout > 0:
        def _idle_watchdog():
            while True:
                time.sleep(5)
                if time.time() - AegisArchiveHandler.last_activity >= args.idle_timeout * 60:
                    print("\n[AegisArchive] Idle timeout reached - shutting down.")
                    server.shutdown()
                    return

        threading.Thread(target=_idle_watchdog, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[AegisArchive] Server stopped gracefully.")
    finally:
        # Ensure the listening socket is always released cleanly, including
        # when shutdown was requested via the POST /__station/shutdown
        # endpoint or the idle watchdog (no orphaned listeners left behind).
        server.server_close()

if __name__ == "__main__":
    main()
