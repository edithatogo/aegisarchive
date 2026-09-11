"""Progressive local debug journal. Payloads are filtered, never executed."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import stat
import threading
import time
import urllib.parse

LABELS = frozenset(('event', 'stage', 'state', 'source', 'category', 'route', 'reason_code',
                    'error_type', 'cause_type', 'action', 'mimeType', 'digest', 'robots_policy',
                    'native_log_name', 'archive_id', 'session_id', 'label', 'network_transport', 'platform'))
NUMBERS = frozenset(('status', 'elapsed_ms', 'latency_ms', 'size_bytes', 'bytes', 'attempt',
                     'visitedCount', 'queueLength', 'documentsFound', 'availableTokens',
                     'ewmaLatencyMs', 'consecutiveErrors', 'errno', 'winerror', 'captured',
                     'failed', 'pending', 'excluded', 'unsupported', 'max_pages', 'max_depth',
                     'min_delay_ms', 'max_delay_ms', 'max_requests_per_minute', 'offset'))
FLAGS = frozenset(('complete', 'archive_storage_verified', 'auto_detect', 'pac_present',
                   'static_proxy_present', 'bypass_present', 'bypass', 'proxy_configured'))


def filtered(event):
    if not isinstance(event, dict):
        raise ValueError('Debug event must be an object')
    result = {}
    for key, value in event.items():
        if key in LABELS and isinstance(value, str) and re.fullmatch(r'[\w .:/()-]{1,100}', value, re.ASCII):
            result[key] = value
        elif key in NUMBERS and type(value) in (int, float) and abs(value) < 1e15 and math.isfinite(value):
            result[key] = value
        elif key in FLAGS and type(value) is bool:
            result[key] = value
        elif key == 'url' and isinstance(value, str) and len(value) <= 8192:
            try:
                url = urllib.parse.urlsplit(value)
                if url.scheme in ('http', 'https') and url.hostname and not any(ord(c) < 32 for c in value):
                    result['url'] = urllib.parse.urlunsplit((url.scheme, url.netloc.rsplit('@', 1)[-1], url.path, '', ''))
            except ValueError:
                pass
    return result


class DebugJournal:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.path = None
        self.lock = threading.RLock()
        self.clients = {}
        self.sequence = 0
        self.failed = False

    def status(self):
        with self.lock:
            return {'active': self.path is not None, 'failed': self.failed,
                    'log_file': str(self.path) if self.path else None, 'saved_events': self.sequence}

    def start(self):
        with self.lock:
            if self.failed:
                raise OSError('Debug journal unavailable')
            if len(self.clients) >= 64:
                raise ValueError('Debug client limit reached; restart the launcher')
            if self.path is None:
                if self.directory.is_symlink() or getattr(self.directory, 'is_junction', lambda: False)():
                    raise OSError('Debug directory must not be a symlink')
                self.directory.mkdir(parents=True, exist_ok=True)
                path = self.directory / ('debug-' + secrets.token_hex(12) + '.jsonl')
                descriptor = self._open_file(path, create=True)
                os.close(descriptor)
                self.path = path
                self._append([{'event': 'debug_started'}], 'server')
            client = secrets.token_hex(12)
            self.clients[client] = {'next': 0, 'last': None}
            return {**self.status(), 'client_id': client, 'next_sequence': 0}

    def _open_file(self, path, create=False):
        """Anchor POSIX opens to a no-follow directory descriptor.

        Windows lacks dir_fd opens; reject directory reparse links and changed
        directory/file identity before writing through the opened descriptor.
        This is not protection against arbitrary concurrent filesystem owners.
        """
        if self.directory.is_symlink() or getattr(self.directory, 'is_junction', lambda: False)():
            raise OSError('Debug directory must not be a symlink')
        before = self.directory.stat(follow_symlinks=False)
        if not stat.S_ISDIR(before.st_mode):
            raise OSError('Debug directory is not a directory')
        flags = os.O_WRONLY | os.O_APPEND | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
        if create:
            flags |= os.O_CREAT | os.O_EXCL
        directory_fd = descriptor = None
        try:
            if os.open in os.supports_dir_fd:
                directory_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                if not os.path.samestat(before, os.fstat(directory_fd)):
                    raise OSError('Debug directory changed')
                descriptor = os.open(path.name, flags, 0o600, dir_fd=directory_fd)
                current = os.stat(path.name, dir_fd=directory_fd, follow_symlinks=False)
            else:
                descriptor = os.open(path, flags, 0o600)
                after = self.directory.stat(follow_symlinks=False)
                if not os.path.samestat(before, after) or not stat.S_ISDIR(after.st_mode):
                    raise OSError('Debug directory changed')
                current = path.stat(follow_symlinks=False)
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode) or not os.path.samestat(opened, current):
                raise OSError('Debug journal changed')
            result, descriptor = descriptor, None
            return result
        finally:
            if descriptor is not None:
                os.close(descriptor)
            if directory_fd is not None:
                os.close(directory_fd)

    def _append(self, events, source):
        if self.failed:
            raise OSError('Debug journal unavailable')
        rows = [{**filtered(event), 'schema_version': 1, 'journal_sequence': self.sequence + index,
                 'timestamp': time.time(), 'origin': source} for index, event in enumerate(events)]
        data = ''.join(json.dumps(row, ensure_ascii=True) + '\n' for row in rows).encode()
        descriptor = None
        try:
            descriptor = self._open_file(self.path)
            with os.fdopen(descriptor, 'ab') as stream:
                descriptor = None
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            self.sequence += len(rows)
        except OSError:
            self.failed = True
            raise
        finally:
            if descriptor is not None:
                os.close(descriptor)

    def batch(self, client, sequence, events):
        with self.lock:
            if self.failed:
                raise OSError('Debug journal unavailable')
            if client not in self.clients or type(sequence) is not int or not isinstance(events, list) or not 1 <= len(events) <= 32:
                raise ValueError('Invalid debug batch')
            state = self.clients[client]
            fingerprint = hashlib.sha256(json.dumps(events, sort_keys=True).encode()).hexdigest()
            if state['last'] == (sequence, fingerprint):
                return {**self.status(), 'next_sequence': state['next']}
            if sequence != state['next']:
                raise ValueError('Debug sequence mismatch')
            self._append(events, 'browser')
            state['last'] = (sequence, fingerprint)
            state['next'] += len(events)
            return {**self.status(), 'next_sequence': state['next']}

    def native(self, event):
        with self.lock:
            if self.path is not None:
                self._append([event], 'native')
