"""Serve one selected saved WARC on a private, disposable loopback origin."""
import argparse
from http.server import BaseHTTPRequestHandler
import os
from pathlib import Path
from secrets import token_hex
from shutil import copyfileobj
from threading import Thread

from .launch import ThreadingHTTPServer


_WEB = Path(__file__).resolve().parents[1] / 'web'
_FILES = {
    '': ('replay/index.html', 'text/html; charset=utf-8'),
    'app.js': ('replay/app.js', 'text/javascript; charset=utf-8'),
    'worker.js': ('replay/worker.js', 'text/javascript; charset=utf-8'),
    'warc_reader.js': ('lib/warc_reader.js', 'text/javascript; charset=utf-8'),
    'offline_navigation.js': ('lib/offline_navigation.js', 'text/javascript; charset=utf-8'),
}
_CSP = (
    "default-src 'none'; script-src 'self'; worker-src 'self'; connect-src 'self'; "
    "frame-src 'self' about:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'; "
    "style-src 'self' 'unsafe-inline'; img-src 'self'; font-src 'self'; media-src 'self'"
)


def _signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


class ReplayHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        # Do not copy the private session URL into a request log.
        pass

    def _respond(self, status, size, mime='text/plain'):
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(size))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy', _CSP)
        self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.end_headers()

    def _local_path(self):
        if self.headers.get_all('Host') != [self.server.authority]:
            self._respond(421, 0)
            return None
        if not self.path.startswith(self.server.scope):
            self._respond(404, 0)
            return None
        return self.path.removeprefix(self.server.scope)

    def do_GET(self):
        name = self._local_path()
        if name is None:
            return
        if name == 'archive':
            self._archive()
        elif name in _FILES:
            location, mime = _FILES[name]
            data = (_WEB / location).read_bytes()
            self._respond(200, len(data), mime)
            self.wfile.write(data)
        else:
            self._respond(404, 0)

    def _archive(self):
        try:
            archive = self.server.archive.open('rb')
        except OSError:
            self._respond(409, 0)
            return
        with archive:
            current = os.fstat(archive.fileno())
            if _signature(current) != self.server.signature:
                self._respond(409, 0)
                return
            mime = 'application/gzip' if self.server.archive.suffix.lower() == '.gz' else 'application/warc'
            self._respond(200, current.st_size, mime)
            try:
                copyfileobj(archive, self.wfile, 64 * 1024)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def do_POST(self):
        name = self._local_path()
        if name is None:
            return
        if name != 'stop':
            self._respond(404, 0)
            return
        if self.headers.get_all('Origin') != [self.server.origin]:
            self._respond(403, 0)
            return
        self._respond(204, 0)
        Thread(target=self.server.shutdown, daemon=True).start()


def create_server(archive_path):
    archive = Path(archive_path).resolve(strict=True)
    suffix = archive.name.lower()
    if not archive.is_file() or not suffix.endswith(('.warc', '.warc.gz')) or '.partial.' in suffix:
        raise ValueError('Select a saved .warc or .warc.gz file')
    signature = _signature(archive.stat())
    session = token_hex(16)
    server = ThreadingHTTPServer(('127.0.0.1', 0), ReplayHandler)
    server.archive = archive
    server.signature = signature
    server.scope = f'/{session}/'
    server.authority = f'{session}.localhost:{server.server_port}'
    server.origin = 'http://' + server.authority
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive')
    args = parser.parse_args(argv)
    try:
        server = create_server(args.archive)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    with server:
        print(server.origin + server.scope, flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
