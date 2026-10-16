"""SQLite-backed immutable document catalogue for offline mirrors."""
from __future__ import annotations
import hashlib
import math
import mimetypes
import sqlite3
import time
from urllib.parse import urlsplit

PROCESSING_STATES = ('pending', 'complete', 'partial', 'failed', 'encrypted', 'unsupported')

SCHEMA = """CREATE TABLE IF NOT EXISTS documents (source_id TEXT PRIMARY KEY, first_seen REAL NOT NULL, handling TEXT NOT NULL DEFAULT 'unknown');
CREATE TABLE IF NOT EXISTS revisions (revision_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, url TEXT NOT NULL, content_hash TEXT NOT NULL, mime TEXT NOT NULL, size INTEGER NOT NULL, acquired REAL NOT NULL, status TEXT NOT NULL DEFAULT 'captured', UNIQUE(source_id, content_hash), FOREIGN KEY(source_id) REFERENCES documents(source_id));
CREATE TABLE IF NOT EXISTS urls (url TEXT PRIMARY KEY, source_id TEXT NOT NULL, revision_id TEXT NOT NULL, first_seen REAL NOT NULL, last_seen REAL NOT NULL);
CREATE TABLE IF NOT EXISTS derivatives (derivative_id TEXT PRIMARY KEY, revision_id TEXT NOT NULL, kind TEXT NOT NULL, extractor TEXT NOT NULL, output_hash TEXT NOT NULL, status TEXT NOT NULL, text TEXT, locator_json TEXT, handling TEXT NOT NULL DEFAULT 'unknown');
CREATE TABLE IF NOT EXISTS source_metadata (
    source_id TEXT PRIMARY KEY REFERENCES documents(source_id),
    title TEXT, document_date TEXT, version TEXT,
    flags_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS content_objects (
    content_hash TEXT PRIMARY KEY, content BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS acquisitions (
    acquisition_id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES documents(source_id),
    revision_id TEXT NOT NULL REFERENCES revisions(revision_id),
    url TEXT NOT NULL, acquired REAL NOT NULL, mime TEXT NOT NULL,
    handling TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS derivative_insert_state BEFORE INSERT ON derivatives
WHEN NEW.status NOT IN ('pending','complete','partial','failed','encrypted','unsupported')
BEGIN SELECT RAISE(ABORT, 'invalid_processing_state'); END;
CREATE TRIGGER IF NOT EXISTS derivative_update_state BEFORE UPDATE OF status ON derivatives
WHEN NEW.status NOT IN ('pending','complete','partial','failed','encrypted','unsupported')
BEGIN SELECT RAISE(ABORT, 'invalid_processing_state'); END;
CREATE TRIGGER IF NOT EXISTS derivative_revision BEFORE INSERT ON derivatives
WHEN NOT EXISTS (SELECT 1 FROM revisions WHERE revision_id=NEW.revision_id)
BEGIN SELECT RAISE(ABORT, 'unknown_revision'); END;
"""

def source_identity(url: str) -> str:
    return hashlib.sha256(url.encode('utf-8')).hexdigest()

class Catalogue:
    def __init__(self, path=':memory:'):
        self.db = sqlite3.connect(str(path))
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript(SCHEMA)
        for table in ('revisions', 'content_objects', 'acquisitions'):
            for operation in ('UPDATE', 'DELETE'):
                self.db.execute(
                    f'CREATE TRIGGER IF NOT EXISTS immutable_{table}_{operation} '
                    f'BEFORE {operation} ON {table} '
                    "BEGIN SELECT RAISE(ABORT, 'immutable_record'); END")
        self.db.execute('INSERT OR IGNORE INTO source_metadata (source_id) SELECT source_id FROM documents')
        self.db.commit()
    def register(self, url, content, mime=None, handling='unknown', acquired=None,
                 *, moved_from=None):
        """Record an acquisition; callers must explicitly identify a moved URL.

        Identical content alone proves duplication, not that two URLs represent
        one source. Payload storage is shared while source identities remain
        distinct unless moved_from identifies an existing source.
        """
        if not isinstance(url, str) or not url or not isinstance(content, bytes):
            raise ValueError('invalid_registration')
        now = time.time() if acquired is None else acquired
        if (isinstance(now, bool) or not isinstance(now, (float, int))
                or not math.isfinite(now) or now < 0):
            raise ValueError('invalid_acquired_time')
        mime = mime or mimetypes.guess_type(urlsplit(url).path)[0] or 'application/octet-stream'
        if not isinstance(mime, str) or not isinstance(handling, str) or not handling:
            raise ValueError('invalid_metadata')
        mime = mime.split(';', 1)[0].strip().lower()
        digest = hashlib.sha256(content).hexdigest()
        with self.db:
            current = self.db.execute('SELECT source_id FROM urls WHERE url=?', (url,)).fetchone()
            sid = current[0] if current else source_identity(url)
            if moved_from is not None:
                previous = self.db.execute('SELECT source_id FROM urls WHERE url=?', (moved_from,)).fetchone()
                if previous is None:
                    raise ValueError('unknown_move_origin')
                if current and current[0] != previous[0]:
                    raise ValueError('source_conflict')
                sid = previous[0]
            stored = self.db.execute('SELECT content FROM content_objects WHERE content_hash=?', (digest,)).fetchone()
            if stored and stored[0] != content:
                raise ValueError('original_integrity')
            self.db.execute('INSERT OR IGNORE INTO content_objects VALUES (?,?)', (digest, content))
            self.db.execute('INSERT OR IGNORE INTO documents VALUES (?,?,?)', (sid, now, handling))
            self.db.execute('INSERT OR IGNORE INTO source_metadata (source_id) VALUES (?)', (sid,))
            row = self.db.execute('SELECT revision_id FROM revisions WHERE source_id=? AND content_hash=?', (sid, digest)).fetchone()
            rid = row[0] if row else hashlib.sha256((sid + digest).encode()).hexdigest()
            if row is None:
                self.db.execute('INSERT INTO revisions VALUES (?,?,?,?,?,?,?,?)',
                                (rid, sid, url, digest, mime, len(content), now, 'captured'))
            self.db.execute(
                'INSERT INTO urls VALUES (?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET '
                'revision_id=CASE WHEN excluded.last_seen>=urls.last_seen THEN excluded.revision_id ELSE urls.revision_id END,'
                'first_seen=MIN(urls.first_seen,excluded.first_seen),last_seen=MAX(urls.last_seen,excluded.last_seen)',
                (url, sid, rid, now, now))
            self.db.execute(
                'INSERT INTO acquisitions (source_id,revision_id,url,acquired,mime,handling) VALUES (?,?,?,?,?,?)',
                (sid, rid, url, now, mime, handling))
        return {'source_id': sid, 'revision_id': rid, 'content_hash': digest,
                'mime': mime, 'moved': moved_from is not None and moved_from != url,
                'duplicate': stored is not None}

    def revisions(self, url):
        row = self.db.execute('SELECT source_id FROM urls WHERE url=?', (url,)).fetchone()
        sid = row[0] if row else source_identity(url)
        return self.db.execute('SELECT * FROM revisions WHERE source_id=? ORDER BY acquired,revision_id', (sid,)).fetchall()

    def acquisitions(self, url):
        cursor = self.db.execute(
            'SELECT a.* FROM acquisitions a JOIN urls u ON u.source_id=a.source_id '
            'WHERE u.url=? ORDER BY a.acquired,a.acquisition_id', (url,))
        names = [column[0] for column in cursor.description]
        return [dict(zip(names, row)) for row in cursor]

    def original(self, revision_id):
        row = self.db.execute(
            'SELECT o.content,r.content_hash FROM revisions r JOIN content_objects o '
            'ON o.content_hash=r.content_hash WHERE r.revision_id=?', (revision_id,)).fetchone()
        if row is None:
            raise LookupError('original_bytes_unavailable')
        if hashlib.sha256(row[0]).hexdigest() != row[1]:
            raise ValueError('original_integrity')
        return row[0]

    def close(self):
        self.db.close()
