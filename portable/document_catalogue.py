"""SQLite-backed immutable document catalogue for offline mirrors."""
from __future__ import annotations
import hashlib
import json
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
CREATE TABLE IF NOT EXISTS change_receipts (
    receipt_id TEXT PRIMARY KEY,
    acquisition_id INTEGER NOT NULL UNIQUE REFERENCES acquisitions(acquisition_id),
    source_id TEXT NOT NULL REFERENCES documents(source_id),
    payload_json TEXT NOT NULL
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
CREATE TRIGGER IF NOT EXISTS derivative_update_revision BEFORE UPDATE OF revision_id ON derivatives
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
        for table, key in (('revisions', 'revision_id'), ('content_objects', 'content_hash'),
                           ('acquisitions', 'acquisition_id'), ('change_receipts', 'receipt_id')):
            self.db.execute(
                f'CREATE TRIGGER IF NOT EXISTS immutable_{table}_insert BEFORE INSERT ON {table} '
                f'WHEN EXISTS (SELECT 1 FROM {table} WHERE {key}=NEW.{key}) '
                "BEGIN SELECT RAISE(ABORT, 'immutable_record'); END")
            for operation in ('UPDATE', 'DELETE'):
                self.db.execute(
                    f'CREATE TRIGGER IF NOT EXISTS immutable_{table}_{operation} '
                    f'BEFORE {operation} ON {table} '
                    "BEGIN SELECT RAISE(ABORT, 'immutable_record'); END")
        self.db.execute('INSERT OR IGNORE INTO source_metadata (source_id) SELECT source_id FROM documents')
        self.db.execute(
            'CREATE TRIGGER IF NOT EXISTS immutable_revision_content BEFORE INSERT ON revisions '
            'WHEN EXISTS (SELECT 1 FROM revisions WHERE source_id=NEW.source_id AND content_hash=NEW.content_hash) '
            "BEGIN SELECT RAISE(ABORT, 'immutable_record'); END")
        self.db.execute(
            'CREATE TRIGGER IF NOT EXISTS immutable_receipt_acquisition BEFORE INSERT ON change_receipts '
            'WHEN EXISTS (SELECT 1 FROM change_receipts WHERE acquisition_id=NEW.acquisition_id) '
            "BEGIN SELECT RAISE(ABORT, 'immutable_record'); END")
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
        if moved_from is not None and (not isinstance(moved_from, str) or not moved_from):
            raise ValueError('invalid_move_origin')
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
            # Read the receipt baseline under the write reservation, otherwise
            # a second connection could commit a new head before our first INSERT.
            if not self.db.in_transaction:
                self.db.execute('BEGIN IMMEDIATE')
            current = self.db.execute('SELECT source_id,revision_id,last_seen FROM urls WHERE url=?', (url,)).fetchone()
            sid = current[0] if current else source_identity(url)
            baseline = current
            if moved_from is not None:
                previous = self.db.execute('SELECT source_id,revision_id,last_seen FROM urls WHERE url=?', (moved_from,)).fetchone()
                if previous is None:
                    raise ValueError('unknown_move_origin')
                if current and current[0] != previous[0]:
                    raise ValueError('source_conflict')
                sid = previous[0]
                baseline = current or previous
            before_hash = self.db.execute('SELECT content_hash FROM revisions WHERE revision_id=?',
                                          (baseline[1],)).fetchone()[0] if baseline else None
            stored = self.db.execute('SELECT content FROM content_objects WHERE content_hash=?', (digest,)).fetchone()
            if stored and stored[0] != content:
                raise ValueError('original_integrity')
            if stored is None:
                self.db.execute('INSERT INTO content_objects VALUES (?,?)', (digest, content))
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
            acquisition = self.db.execute(
                'INSERT INTO acquisitions (source_id,revision_id,url,acquired,mime,handling) VALUES (?,?,?,?,?,?)',
                (sid, rid, url, now, mime, handling))
            # Snapshot the head observed in this transaction, not an invented
            # chronological predecessor. Backdated captures need not advance it.
            payload = dict(schema_version='1.0', acquisition_id=acquisition.lastrowid,
                           source_id=sid, acquired=now, url=url, handling=handling,
                           before_revision_id=baseline[1] if baseline else None,
                           before_url=(url if current else moved_from) if baseline else None,
                           after_revision_id=rid, before_content_hash=before_hash,
                           after_content_hash=digest, moved_from=moved_from,
                           moved=moved_from is not None and moved_from != url,
                           content_changed=before_hash != digest if baseline else None,
                           duplicate_content=stored is not None,
                           advances_url_head=current is None or now >= current[2],
                           comparison_basis='url_head_before_registration')
            encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False)
            receipt_id = hashlib.sha256(encoded.encode('utf-8')).hexdigest()
            self.db.execute('INSERT INTO change_receipts VALUES (?,?,?,?)',
                            (receipt_id, acquisition.lastrowid, sid, encoded))
        return {'source_id': sid, 'revision_id': rid, 'content_hash': digest,
                'mime': mime, 'moved': moved_from is not None and moved_from != url,
                'duplicate': stored is not None, 'receipt_id': receipt_id}

    def _revision_reference(self, revision_id):
        row = self.db.execute('SELECT revision_id,source_id,url,content_hash,mime,size,acquired '
                              'FROM revisions WHERE revision_id=?', (revision_id,)).fetchone()
        if row is None:
            raise LookupError('unknown_revision')
        return dict(zip(('revision_id', 'source_id', 'url', 'content_hash', 'mime', 'size', 'acquired'), row))

    def compare_revisions(self, before_revision_id, after_revision_id):
        """Compare original-byte fingerprints, not extracted text or chronology.

        This is trusted local catalogue metadata access, like acquisitions().
        Cross-source byte matches do not prove movement or semantic equivalence.
        Explicit movement evidence is retained only in new acquisition receipts.
        """
        before, after = self._revision_reference(before_revision_id), self._revision_reference(after_revision_id)
        same_source = before['source_id'] == after['source_id']
        same_bytes = before['content_hash'] == after['content_hash']
        relation = ('same_revision' if before_revision_id == after_revision_id else
                    'content_changed' if same_source else
                    'duplicate_content' if same_bytes else 'distinct_sources')
        return dict(before=before, after=after, same_source=same_source, same_bytes=same_bytes,
                    content_changed=not same_bytes if same_source else None,
                    size_delta=after['size'] - before['size'], relation=relation)

    def duplicates(self, revision_id):
        """List exact original-byte matches; retain separate source identities.

        Local catalogue metadata, not a permission-filtered search/export route.
        The queried revision itself is excluded; no fuzzy/semantic match is made.
        """
        reference = self._revision_reference(revision_id)
        return [self._revision_reference(row[0]) for row in self.db.execute(
            'SELECT revision_id FROM revisions WHERE content_hash=? AND revision_id!=? '
            'ORDER BY source_id,revision_id', (reference['content_hash'], revision_id))]

    def change_receipt(self, receipt_id):
        """Read a fingerprint-verified immutable acquisition receipt.

        No text or document bytes are embedded. Older acquisitions have no new
        receipts: migration must not fabricate declarations of historical moves.
        """
        row = self.db.execute('SELECT acquisition_id,source_id,payload_json FROM change_receipts '
                              'WHERE receipt_id=?', (receipt_id,)).fetchone()
        if row is None:
            raise LookupError('unknown_change_receipt')
        try:
            payload = json.loads(row[2])
            if (hashlib.sha256(row[2].encode('utf-8')).hexdigest() != receipt_id or
                    not isinstance(payload, dict) or payload.get('acquisition_id') != row[0] or
                    payload.get('source_id') != row[1]):
                raise ValueError('change_receipt_integrity')
        except (TypeError, ValueError, RecursionError):
            raise ValueError('change_receipt_integrity') from None
        return dict(payload, receipt_id=receipt_id)

    def change_receipts(self, source_id=None):
        """Read new receipts in ingestion order, optionally for one source."""
        sql, args = 'SELECT receipt_id FROM change_receipts', []
        if source_id is not None:
            sql += ' WHERE source_id=?'
            args.append(source_id)
        sql += ' ORDER BY acquisition_id'
        return [self.change_receipt(row[0]) for row in self.db.execute(sql, args)]

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
