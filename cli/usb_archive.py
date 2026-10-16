"""Bounded, token-routed archive storage under the application's USB directory."""
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import stat
import threading

CHUNK_LIMIT = 256 * 1024
STATE_LIMIT = 1024 * 1024
METADATA_LIMIT = 2 * 1024 * 1024
KINDS = ('warc', 'cdx')


def encoded_state(state):
    if type(state) is not dict:
        raise ValueError('Checkpoint state must be an object')
    def visit(value, depth=0):
        if depth > 64:
            raise ValueError('Checkpoint state too deep')
        if type(value) is dict:
            for key, child in value.items():
                if key == 'tokens':
                    # PolitenessEngine exports a public token-bucket balance.
                    # Credential-bearing token fields remain prohibited below.
                    if (type(child) not in (int, float) or not 0 <= child <= 2**53 - 1
                            or not math.isfinite(child)):
                        raise ValueError('Pacing tokens must be a finite nonnegative number')
                    continue
                if type(key) is not str or re.search(
                        r'token|credential|password|passphrase|cookie|authorization|secret|auth', key, re.I):
                    raise ValueError('Checkpoint state cannot contain credentials or auth sources')
                visit(child, depth + 1)
        elif type(value) is list:
            for child in value:
                visit(child, depth + 1)
        elif value is not None and type(value) not in (str, int, float, bool):
            raise ValueError('Checkpoint state must contain JSON values')
    try:
        visit(state)
        raw = json.dumps(state, sort_keys=True, separators=(',', ':'),
                         ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (RecursionError, UnicodeError) as exc:
        raise ValueError('Invalid checkpoint state') from exc
    if len(raw) > STATE_LIMIT:
        raise ValueError('Checkpoint state too large')
    return raw


class UsbArchiveStore:
    def __init__(self, root):
        root = Path(root).absolute()
        if root.is_symlink():
            raise ValueError('Archive directory must not be a symbolic link')
        # Canonicalize parent aliases (including macOS /var) once, anchoring all
        # later checks to the selected directory rather than rejecting OS aliases.
        self.root = root.resolve()
        self.sessions = {}
        self.lock = threading.RLock()

    def folder(self, sid):
        if type(sid) is not str or not re.fullmatch('[0-9a-f]{32}', sid):
            raise ValueError('Invalid archive id')
        folder = self.root / sid
        for path in (folder, *folder.parents):
            if path.is_symlink():
                raise ValueError('Archive path must not contain symbolic links')
        if not folder.is_dir():
            raise ValueError('Unknown archive')
        return folder

    @staticmethod
    def open_file(path, writable=False, create=False):
        path = Path(path)
        flags = ((os.O_RDWR if writable else os.O_RDONLY) | getattr(os, 'O_BINARY', 0)
                 | getattr(os, 'O_NOFOLLOW', 0))
        if create:
            flags |= os.O_CREAT
        fd = os.open(path, flags)
        try:
            info, named = os.fstat(fd), path.stat(follow_symlinks=False)
            if (not stat.S_ISREG(info.st_mode) or not stat.S_ISREG(named.st_mode)
                    or info.st_nlink != 1
                    or (info.st_dev, info.st_ino) != (named.st_dev, named.st_ino)):
                raise OSError('Archive file changed')
            return os.fdopen(fd, 'r+b' if writable else 'rb')
        except BaseException:
            os.close(fd)
            raise

    def acquire(self, folder):
        handle = self.open_file(folder / '.writer.lock', writable=True, create=True)
        try:
            if os.name == 'nt':
                import msvcrt
                if os.fstat(handle.fileno()).st_size == 0:
                    handle.write(b'0')
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise ValueError('Archive has an active writer') from exc
        return handle

    @staticmethod
    def release(handle):
        try:
            if os.name == 'nt':
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()

    @staticmethod
    def sync_directory(folder):
        if os.name != 'nt':
            fd = os.open(folder, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
            try:
                os.fsync(fd)
            finally:
                os.close(fd)

    def suspend(self, sid):
        with self.lock:
            self.folder(sid)
            item = self.sessions.pop(sid, None)
            if item is not None and item.get('handle') is not None:
                self.release(item['handle'])
                item['handle'] = None

    def close(self):
        with self.lock:
            for item in self.sessions.values():
                if item.get('handle') is not None:
                    self.release(item['handle'])
                    item['handle'] = None
            self.sessions.clear()

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
            self.folder(sid)
            handle = self.acquire(folder)
            try:
                for kind in KINDS:
                    with (folder / ('archive.' + kind + '.partial')).open('xb'):
                        pass
            except BaseException:
                self.release(handle)
                raise
            self.sessions[sid] = dict(folder=folder, failed=False, finalized=False,
                                     sizes={'warc': 0, 'cdx': 0},
                                     hashes={kind: hashlib.sha256() for kind in KINDS},
                                     handle=handle, identity=self.identity(folder),
                                     lease=secrets.token_hex(32), generation=0,
                                     require_lease=False, profile_hash=None, last={})
            return {'archive_id': sid, 'directory': str(folder),
                    'lease': self.sessions[sid]['lease'], 'generation': 0}

    @staticmethod
    def identity(path):
        info = path.stat(follow_symlinks=False)
        return info.st_dev, info.st_ino

    def session(self, sid):
        if not isinstance(sid, str) or sid not in self.sessions:
            raise ValueError('Unknown archive')
        item = self.sessions[sid]
        if item['failed'] or item['finalized']:
            raise ValueError('Archive is no longer writable')
        self.folder(sid)
        if self.identity(item['folder']) != item['identity'] or item['handle'] is None:
            raise ValueError('Archive directory changed or writer suspended')
        info = os.fstat(item['handle'].fileno())
        if self.identity(item['folder'] / '.writer.lock') != (info.st_dev, info.st_ino):
            raise ValueError('Archive writer lock changed')
        return item

    @staticmethod
    def check_lease(item, lease, required=False):
        if (required or item['require_lease'] or lease is not None) and (
                type(lease) is not str or not re.fullmatch('[0-9a-f]{64}', lease)
                or not secrets.compare_digest(item['lease'], lease)):
            raise ValueError('Stale or missing archive lease')

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

    def chunk(self, sid, kind, offset, data, lease=None):
        with self.lock:
            item = self.session(sid)
            self.check_lease(item, lease)
            if kind not in KINDS or type(offset) is not int or offset < 0:
                raise ValueError('Invalid archive offset or kind')
            if not isinstance(data, str) or len(data) > ((CHUNK_LIMIT + 2) // 3) * 4:
                raise ValueError('Archive chunk too large')
            raw = base64.b64decode(data, validate=True)
            if not raw or len(raw) > CHUNK_LIMIT:
                raise ValueError('Invalid archive chunk')
            last = item['last'].get(kind)
            if offset != item['sizes'][kind]:
                if last == (offset, raw) and offset + len(raw) == item['sizes'][kind]:
                    with self.open_partial(item, kind) as saved:
                        saved.seek(offset)
                        if saved.read(len(raw)) != raw:
                            raise OSError('Retried archive bytes changed')
                    return {'offset': item['sizes'][kind]}
                raise ValueError('Invalid archive offset or kind')
            try:
                with self.open_partial(item, kind, writable=True) as output:
                    output.seek(offset)
                    output.write(raw)
                    output.flush()
                    os.fsync(output.fileno())
                item['hashes'][kind].update(raw)
                item['sizes'][kind] += len(raw)
                item['last'][kind] = (offset, raw)
            except OSError:
                item['failed'] = True
                raise
            return {'offset': item['sizes'][kind]}

    @staticmethod
    def profile(value):
        if type(value) is not str or not re.fullmatch('[0-9a-f]{64}', value):
            raise ValueError('Invalid profile hash')

    def checkpoint(self, sid, generation, state, profile_hash, lease):
        with self.lock:
            item = self.session(sid)
            self.check_lease(item, lease, required=True)
            self.profile(profile_hash)
            if (type(generation) is not int or not 0 <= generation < 2**53 - 1
                    or generation != item['generation']):
                raise ValueError('Stale checkpoint generation')
            if item['profile_hash'] not in (None, profile_hash):
                raise ValueError('Checkpoint profile mismatch')
            state = json.loads(encoded_state(state))
            prefixes = {}
            for kind in KINDS:
                digest = hashlib.sha256()
                with self.open_partial(item, kind, writable=True) as saved:
                    saved.flush()
                    os.fsync(saved.fileno())
                    for block in iter(lambda: saved.read(1024 * 1024), b''):
                        digest.update(block)
                if digest.hexdigest() != item['hashes'][kind].hexdigest():
                    raise OSError('Checkpoint archive prefix changed')
                prefixes[kind] = {'bytes': item['sizes'][kind], 'sha256': digest.hexdigest()}
            metadata = {'schema': 'aegis.usb-checkpoint.v1', 'archive_id': sid,
                        'generation': generation + 1, 'profile_hash': profile_hash,
                        'state': state, 'prefixes': prefixes,
                        'last_chunks': {kind: {'offset': offset, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
                                        for kind, (offset, raw) in item['last'].items()}}
            self.publish_checkpoint(item['folder'], metadata)
            item['generation'] = generation + 1
            item['profile_hash'] = profile_hash
            return {'generation': item['generation'], 'offsets': dict(item['sizes'])}

    def publish_checkpoint(self, folder, metadata):
        raw = json.dumps(metadata, sort_keys=True, separators=(',', ':'),
                         ensure_ascii=False, allow_nan=False).encode('utf-8')
        if len(raw) > METADATA_LIMIT:
            raise ValueError('Checkpoint metadata too large')
        if (folder / 'checkpoint.json').is_symlink():
            raise ValueError('Checkpoint must not be a symbolic link')
        temporary = folder / ('.checkpoint.' + secrets.token_hex(16) + '.tmp')
        with temporary.open('xb') as saved:
            saved.write(raw)
            saved.flush()
            os.fsync(saved.fileno())
        os.replace(temporary, folder / 'checkpoint.json')
        self.sync_directory(folder)

    def read_checkpoint(self, sid, folder):
        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ValueError('Duplicate checkpoint key')
                result[key] = value
            return result
        with self.open_file(folder / 'checkpoint.json') as saved:
            raw = saved.read(METADATA_LIMIT + 1)
        if len(raw) > METADATA_LIMIT:
            raise ValueError('Checkpoint metadata too large')
        try:
            value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs)
            if (type(value) is not dict or set(value) !=
                    {'schema', 'archive_id', 'generation', 'profile_hash', 'state', 'prefixes', 'last_chunks'}
                    or value['schema'] != 'aegis.usb-checkpoint.v1' or value['archive_id'] != sid
                    or type(value['generation']) is not int or not 1 <= value['generation'] < 2**53):
                raise ValueError('Invalid checkpoint metadata')
            self.profile(value['profile_hash'])
            encoded_state(value['state'])
            if type(value['prefixes']) is not dict or set(value['prefixes']) != set(KINDS):
                raise ValueError('Invalid checkpoint prefixes')
            for prefix in value['prefixes'].values():
                if (type(prefix) is not dict or set(prefix) != {'bytes', 'sha256'}
                        or type(prefix['bytes']) is not int or not 0 <= prefix['bytes'] < 2**53
                        or type(prefix['sha256']) is not str
                        or not re.fullmatch('[0-9a-f]{64}', prefix['sha256'])):
                    raise ValueError('Invalid checkpoint prefix')
            if type(value['last_chunks']) is not dict or not set(value['last_chunks']) <= set(KINDS):
                raise ValueError('Invalid checkpoint last chunks')
            for kind, last in value['last_chunks'].items():
                if (type(last) is not dict or set(last) != {'offset', 'bytes', 'sha256'}
                        or type(last['offset']) is not int or last['offset'] < 0
                        or type(last['bytes']) is not int or not 1 <= last['bytes'] <= CHUNK_LIMIT
                        or last['offset'] + last['bytes'] != value['prefixes'][kind]['bytes']
                        or type(last['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', last['sha256'])):
                    raise ValueError('Invalid checkpoint last chunk')
        except (RecursionError, UnicodeError, KeyError, TypeError) as exc:
            raise ValueError('Invalid checkpoint metadata') from exc
        return value

    @staticmethod
    def refuse_finalized(folder):
        if any((folder / name).exists() or (folder / name).is_symlink()
               for name in ('archive.warc', 'archive.cdx', 'receipt.json', 'receipt.partial.json')):
            raise ValueError('Finalized archive cannot be reopened')

    def reopen(self, sid, expected_generation, profile_hash):
        with self.lock:
            folder = self.folder(sid)
            self.profile(profile_hash)
            if type(expected_generation) is not int or not 1 <= expected_generation < 2**53 - 1:
                raise ValueError('Invalid checkpoint generation')
            self.refuse_finalized(folder)
            previous = self.sessions.get(sid)
            if previous is not None:
                if previous['finalized'] or previous.get('handle') is None:
                    raise ValueError('Archive has no active writer')
                info = os.fstat(previous['handle'].fileno())
                if (previous['identity'] != self.identity(folder)
                        or self.identity(folder / '.writer.lock') != (info.st_dev, info.st_ino)):
                    raise ValueError('Archive writer changed')
                handle = previous['handle']
            else:
                handle = self.acquire(folder)
            files = {}
            try:
                metadata = self.read_checkpoint(sid, folder)
                if metadata['generation'] != expected_generation or metadata['profile_hash'] != profile_hash:
                    raise ValueError('Stale checkpoint generation or profile mismatch')
                hashes, sizes, last_chunks = {}, {}, {}
                # Verify both committed prefixes before preserving or truncating anything.
                for kind in KINDS:
                    saved = self.open_file(folder / ('archive.' + kind + '.partial'), writable=True)
                    files[kind] = saved
                    size = metadata['prefixes'][kind]['bytes']
                    if os.fstat(saved.fileno()).st_size < size:
                        raise OSError('Checkpoint archive prefix is truncated')
                    digest, remaining = hashlib.sha256(), size
                    while remaining:
                        block = saved.read(min(remaining, 1024 * 1024))
                        if not block:
                            raise OSError('Checkpoint archive prefix is truncated')
                        digest.update(block)
                        remaining -= len(block)
                    if digest.hexdigest() != metadata['prefixes'][kind]['sha256']:
                        raise OSError('Checkpoint archive prefix hash mismatch')
                    hashes[kind], sizes[kind] = digest, size
                    last = metadata['last_chunks'].get(kind)
                    if last is not None:
                        saved.seek(last['offset'])
                        raw = saved.read(last['bytes'])
                        if hashlib.sha256(raw).hexdigest() != last['sha256']:
                            raise OSError('Checkpoint last chunk hash mismatch')
                        last_chunks[kind] = (last['offset'], raw)
                # All orphan copies must be durable before either source is truncated.
                for kind, saved in files.items():
                    if os.fstat(saved.fileno()).st_size > sizes[kind]:
                        tail = folder / ('archive.' + kind + '.orphan.' + secrets.token_hex(16))
                        saved.seek(sizes[kind])
                        with tail.open('xb') as orphan:
                            for block in iter(lambda: saved.read(1024 * 1024), b''):
                                orphan.write(block)
                            orphan.flush()
                            os.fsync(orphan.fileno())
                self.sync_directory(folder)
                for kind, saved in files.items():
                    saved.truncate(sizes[kind])
                    saved.flush()
                    os.fsync(saved.fileno())
                # Reopening consumes the discover/checkpoint generation. Publish
                # only the verified checkpoint's state and prefixes, never tails.
                metadata['generation'] += 1
                self.publish_checkpoint(folder, metadata)
                self.sessions[sid] = dict(folder=folder, failed=False, finalized=False,
                    sizes=sizes, hashes=hashes, handle=handle, identity=self.identity(folder),
                    lease=secrets.token_hex(32), generation=metadata['generation'],
                    require_lease=True, profile_hash=profile_hash, last=last_chunks)
                item = self.sessions[sid]
                return {'archive_id': sid, 'directory': str(folder), 'lease': item['lease'],
                        'generation': item['generation'], 'offsets': dict(sizes), 'state': metadata['state']}
            except BaseException:
                if previous is None:
                    self.release(handle)
                raise
            finally:
                for saved in files.values():
                    saved.close()

    def discover(self):
        """List bounded, nonsecret checkpoint identities, without rotating leases."""
        with self.lock:
            if not self.root.exists():
                return []
            result = []
            # Avoid reading arbitrary directory names or following linked archives.
            for entry in self.root.iterdir():
                if not re.fullmatch('[0-9a-f]{32}', entry.name):
                    continue
                try:
                    folder = self.folder(entry.name)
                    self.refuse_finalized(folder)
                    metadata = self.read_checkpoint(entry.name, folder)
                    result.append({'archive_id': entry.name, 'generation': metadata['generation'],
                                   'profile_hash': metadata['profile_hash'],
                                   'offsets': {kind: metadata['prefixes'][kind]['bytes'] for kind in KINDS}})
                except (OSError, ValueError):
                    continue
                if len(result) >= 128:
                    break
            return sorted(result, key=lambda item: item['archive_id'])

    def finalize(self, sid, summary, lease=None):
        with self.lock:
            item = self.session(sid)
            self.check_lease(item, lease)
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
            self.release(item['handle'])
            item['handle'] = None
            return receipt
