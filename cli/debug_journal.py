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
                self.directory.mkdir(parents=True, exist_ok=True)
                path = self.directory / ('debug-' + secrets.token_hex(12) + '.jsonl')
                with path.open('x', encoding='utf-8'):
                    pass
                self.path = path
                self._append([{'event': 'debug_started'}], 'server')
            client = secrets.token_hex(12)
            self.clients[client] = {'next': 0, 'last': None}
            return {**self.status(), 'client_id': client, 'next_sequence': 0}

    def _append(self, events, source):
        if self.failed:
            raise OSError('Debug journal unavailable')
        rows = [{**filtered(event), 'schema_version': 1, 'journal_sequence': self.sequence + index,
                 'timestamp': time.time(), 'origin': source} for index, event in enumerate(events)]
        data = ''.join(json.dumps(row, ensure_ascii=True) + '\n' for row in rows).encode()
        descriptor = None
        try:
            descriptor = os.open(self.path, os.O_WRONLY | os.O_APPEND | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0))
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or not os.path.samestat(info, self.path.stat(follow_symlinks=False)):
                raise OSError('Debug journal is not a regular file')
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
