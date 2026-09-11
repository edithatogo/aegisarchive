"""Bounded, token-routed archive storage under the application's USB directory."""
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import threading

CHUNK_LIMIT = 256 * 1024


class UsbArchiveStore:
    def __init__(self, root):
        self.root = Path(root)
        self.sessions = {}
        self.lock = threading.RLock()

    def start(self):
        with self.lock:
            if len(self.sessions) >= 128:
                raise ValueError('Restart the launcher before creating more archives')
            self.root.mkdir(parents=True, exist_ok=True)
            if self.root.is_symlink():
                raise ValueError('Archive directory must not be a symbolic link')
            sid = secrets.token_hex(16)
            folder = self.root / sid
            folder.mkdir()
            for kind in ('warc', 'cdx'):
                with (folder / ('archive.' + kind + '.partial')).open('xb'):
                    pass
            self.sessions[sid] = dict(folder=folder, failed=False, finalized=False,
                                     sizes={'warc': 0, 'cdx': 0},
                                     hashes={kind: hashlib.sha256() for kind in ('warc', 'cdx')})
            return {'archive_id': sid, 'directory': str(folder)}

    def session(self, sid):
        if not isinstance(sid, str) or sid not in self.sessions:
            raise ValueError('Unknown archive')
        item = self.sessions[sid]
        if item['failed'] or item['finalized']:
            raise ValueError('Archive is no longer writable')
        return item

    def open_partial(self, item, kind, writable=False):
        path = item['folder'] / ('archive.' + kind + '.partial')
        flags = (os.O_RDWR if writable else os.O_RDONLY) | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
        fd = os.open(path, flags)
        try:
            info = os.fstat(fd)
            named = path.stat(follow_symlinks=False)
            if (not stat.S_ISREG(info.st_mode) or
                    not stat.S_ISREG(named.st_mode) or
                    (info.st_dev, info.st_ino) != (named.st_dev, named.st_ino) or
                    info.st_size != item['sizes'][kind]):
                raise OSError('Archive file changed')
            return os.fdopen(fd, 'r+b' if writable else 'rb')
        except BaseException:
            os.close(fd)
            raise

    def chunk(self, sid, kind, offset, data):
        with self.lock:
            item = self.session(sid)
            if kind not in ('warc', 'cdx') or type(offset) is not int or offset != item['sizes'][kind]:
                raise ValueError('Invalid archive offset or kind')
            if not isinstance(data, str) or len(data) > ((CHUNK_LIMIT + 2) // 3) * 4:
                raise ValueError('Archive chunk too large')
            raw = base64.b64decode(data, validate=True)
            if not raw or len(raw) > CHUNK_LIMIT:
                raise ValueError('Invalid archive chunk')
            try:
                with self.open_partial(item, kind, writable=True) as output:
                    output.seek(offset)
                    output.write(raw)
                    output.flush()
                    os.fsync(output.fileno())
                item['hashes'][kind].update(raw)
                item['sizes'][kind] += len(raw)
            except OSError:
                item['failed'] = True
                raise
            return {'offset': item['sizes'][kind]}

    def finalize(self, sid, summary):
        with self.lock:
            item = self.session(sid)
            if not isinstance(summary, dict) or type(summary.get('complete')) is not bool:
                raise ValueError('Archive summary requires a complete flag')
            folder = item['folder']
            receipt = {'schema_version': 1, 'archive_id': sid, 'complete': summary['complete'],
                       'archives': {kind: {'bytes': item['sizes'][kind],
                                          'sha256': item['hashes'][kind].hexdigest()}
                                    for kind in ('warc', 'cdx')},
                       'warc_path': str(folder / 'archive.warc'),
                       'cdx_path': str(folder / 'archive.cdx'),
                       'receipt_path': str(folder / 'receipt.json')}
            try:
                for kind in ('warc', 'cdx'):
                    source = folder / ('archive.' + kind + '.partial')
                    actual = hashlib.sha256()
                    with self.open_partial(item, kind) as saved:
                        for block in iter(lambda: saved.read(1024 * 1024), b''):
                            actual.update(block)
                    if actual.hexdigest() != item['hashes'][kind].hexdigest():
                        raise OSError('Archive verification failed')
                    os.replace(source, folder / ('archive.' + kind))
                    # Re-read published bytes: exFAT file identifiers can change
                    # after allocation/rename, so creation-time IDs are not portable.
                    published_hash = hashlib.sha256()
                    with (folder / ('archive.' + kind)).open('rb') as published:
                        if not stat.S_ISREG(os.fstat(published.fileno()).st_mode):
                            raise OSError('Invalid published archive')
                        for block in iter(lambda: published.read(1024 * 1024), b''):
                            published_hash.update(block)
                    if published_hash.hexdigest() != item['hashes'][kind].hexdigest():
                        raise OSError('Archive changed during finalization')
                with (folder / 'receipt.partial.json').open('x', encoding='utf-8') as output:
                    json.dump(receipt, output, indent=2)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(folder / 'receipt.partial.json', folder / 'receipt.json')
            except OSError:
                item['failed'] = True
                raise
            item['finalized'] = True
            return receipt
