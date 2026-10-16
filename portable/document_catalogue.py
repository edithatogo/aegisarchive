"""SQLite-backed immutable document catalogue for offline mirrors."""
from __future__ import annotations
from contextlib import contextmanager
import hashlib
import json
import math
import mimetypes
import sqlite3
import time
from urllib.parse import urlsplit

PROCESSING_STATES = ('pending', 'complete', 'partial', 'failed', 'encrypted', 'unsupported')
_UNSET = object()

# Shared by safe original export and derivative retrieval/export. Raw catalogue
# access remains a trusted local administration API, not a security sandbox.
REVISION_ELIGIBLE = """
    s.handling='public' AND m.flags_json='[]'
    AND EXISTS (SELECT 1 FROM source_policy p WHERE p.source_id=s.source_id AND p.removed=0)
    AND EXISTS (SELECT 1 FROM acquisitions a WHERE a.revision_id=r.revision_id)
    AND NOT EXISTS (SELECT 1 FROM acquisitions a WHERE a.revision_id=r.revision_id AND a.handling!='public')
    AND NOT EXISTS (SELECT 1 FROM derivatives other WHERE other.revision_id=r.revision_id AND other.handling!='public')
"""

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
CREATE TABLE IF NOT EXISTS source_policy (
    source_id TEXT PRIMARY KEY REFERENCES documents(source_id),
    retain_until REAL CHECK(retain_until IS NULL OR retain_until>=0),
    legal_hold INTEGER NOT NULL DEFAULT 0 CHECK(legal_hold IN (0,1)),
    removed INTEGER NOT NULL DEFAULT 0 CHECK(removed IN (0,1))
);
CREATE TABLE IF NOT EXISTS handling_events (
    event_id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES documents(source_id),
    action TEXT NOT NULL, reason TEXT NOT NULL, recorded REAL NOT NULL,
    details_json TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS propagate_source_handling AFTER UPDATE OF handling ON documents
WHEN NEW.handling!='public'
BEGIN UPDATE derivatives SET handling=NEW.handling WHERE revision_id IN
    (SELECT revision_id FROM revisions WHERE source_id=NEW.source_id); END;
CREATE TRIGGER IF NOT EXISTS quarantine_flag_update AFTER UPDATE OF flags_json ON source_metadata
WHEN NEW.flags_json!='[]'
BEGIN UPDATE documents SET handling='quarantined' WHERE source_id=NEW.source_id; END;
CREATE TRIGGER IF NOT EXISTS quarantine_flag_insert AFTER INSERT ON source_metadata
WHEN NEW.flags_json!='[]'
BEGIN UPDATE documents SET handling='quarantined' WHERE source_id=NEW.source_id; END;
CREATE TRIGGER IF NOT EXISTS restrict_reacquisition AFTER INSERT ON acquisitions
WHEN NEW.handling!='public'
BEGIN UPDATE documents SET handling=NEW.handling WHERE source_id=NEW.source_id AND handling='public';
UPDATE derivatives SET handling=(SELECT handling FROM documents WHERE source_id=NEW.source_id)
WHERE revision_id=NEW.revision_id; END;
CREATE TRIGGER IF NOT EXISTS withdraw_source AFTER UPDATE OF removed ON source_policy
WHEN NEW.removed=1
BEGIN UPDATE documents SET handling='revoked' WHERE source_id=NEW.source_id; END;
CREATE TRIGGER IF NOT EXISTS permanent_withdrawal BEFORE UPDATE OF removed ON source_policy
WHEN OLD.removed=1 AND NEW.removed!=1
BEGIN SELECT RAISE(ABORT,'source_removed'); END;
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
CREATE TRIGGER IF NOT EXISTS reject_removed_derivative BEFORE INSERT ON derivatives
WHEN EXISTS (SELECT 1 FROM revisions r JOIN source_policy p ON p.source_id=r.source_id
             WHERE r.revision_id=NEW.revision_id AND p.removed=1)
BEGIN SELECT RAISE(ABORT,'source_removed'); END;
CREATE TRIGGER IF NOT EXISTS reject_removed_derivative_update BEFORE UPDATE OF revision_id ON derivatives
WHEN EXISTS (SELECT 1 FROM revisions r JOIN source_policy p ON p.source_id=r.source_id
             WHERE r.revision_id=NEW.revision_id AND p.removed=1)
BEGIN SELECT RAISE(ABORT,'source_removed'); END;
"""

def source_identity(url: str) -> str:
    return hashlib.sha256(url.encode('utf-8')).hexdigest()

class Catalogue:
    def __init__(self, path=':memory:'):
        self.db = sqlite3.connect(str(path))
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript(SCHEMA)
        for table, key in (('revisions', 'revision_id'), ('content_objects', 'content_hash'),
                           ('acquisitions', 'acquisition_id'), ('change_receipts', 'receipt_id'),
                           ('handling_events', 'event_id')):
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
        self.db.execute('INSERT OR IGNORE INTO source_policy (source_id) SELECT source_id FROM documents')
        # Upgrade conservatively; never interpret legacy metadata as clearance.
        self.db.execute("UPDATE documents SET handling='quarantined' WHERE handling NOT IN ('quarantined','revoked') "
                        "AND source_id IN (SELECT source_id FROM source_metadata WHERE flags_json!='[]')")
        self.db.execute('UPDATE documents SET handling=(SELECT a.handling FROM acquisitions a '
                        "WHERE a.source_id=documents.source_id AND a.handling!='public' "
                        'ORDER BY a.acquired DESC,a.acquisition_id DESC LIMIT 1) '
                        "WHERE handling='public' AND EXISTS (SELECT 1 FROM acquisitions a "
                        "WHERE a.source_id=documents.source_id AND a.handling!='public')")
        self.db.execute('UPDATE derivatives SET handling=(SELECT s.handling FROM revisions r '
                        'JOIN documents s ON s.source_id=r.source_id WHERE r.revision_id=derivatives.revision_id) '
                        "WHERE handling='public' AND revision_id IN (SELECT r.revision_id FROM revisions r "
                        "JOIN documents s ON s.source_id=r.source_id WHERE s.handling!='public')")
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
            policy = self.db.execute('SELECT removed FROM source_policy WHERE source_id=?', (sid,)).fetchone()
            if policy and policy[0]:
                raise ValueError('source_removed')
            before_hash = self.db.execute('SELECT content_hash FROM revisions WHERE revision_id=?',
                                          (baseline[1],)).fetchone()[0] if baseline else None
            stored = self.db.execute('SELECT content FROM content_objects WHERE content_hash=?', (digest,)).fetchone()
            if stored and stored[0] != content:
                raise ValueError('original_integrity')
            if stored is None:
                self.db.execute('INSERT INTO content_objects VALUES (?,?)', (digest, content))
            self.db.execute('INSERT OR IGNORE INTO documents VALUES (?,?,?)', (sid, now, handling))
            self.db.execute('INSERT OR IGNORE INTO source_metadata (source_id) VALUES (?)', (sid,))
            self.db.execute('INSERT OR IGNORE INTO source_policy (source_id) VALUES (?)', (sid,))
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

    @contextmanager
    def _policy_change(self, source_id, reason):
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
            raise ValueError('invalid_policy_reason')
        if not isinstance(source_id, str) or not source_id:
            raise ValueError('invalid_source_id')
        with self.db:
            if not self.db.in_transaction:
                self.db.execute('BEGIN IMMEDIATE')
            row = self.db.execute('SELECT s.handling,p.retain_until,p.legal_hold,p.removed '
                                  'FROM documents s JOIN source_policy p ON p.source_id=s.source_id '
                                  'WHERE s.source_id=?', (source_id,)).fetchone()
            if row is None:
                raise LookupError('unknown_source')
            if row[3]:
                raise ValueError('source_removed')
            yield row

    def _handling_event(self, source_id, action, reason, details):
        self.db.execute('INSERT INTO handling_events (source_id,action,reason,recorded,details_json) '
                        'VALUES (?,?,?,?,?)', (source_id, action, reason, time.time(),
                                             json.dumps(details, sort_keys=True, allow_nan=False)))

    def set_handling(self, source_id, handling, *, reason):
        """Restrict a source explicitly; this API never clears nonpublic evidence."""
        if handling not in ('public', 'unknown', 'restricted', 'quarantined', 'revoked'):
            raise ValueError('invalid_handling')
        with self._policy_change(source_id, reason) as row:
            if handling == 'public' and row[0] != 'public':
                raise ValueError('handling_relaxation_requires_review')
            self.db.execute('UPDATE documents SET handling=? WHERE source_id=?', (handling, source_id))
            self._handling_event(source_id, 'handling', reason, {'before': row[0], 'after': handling})

    def flag_source(self, source_id, flag, *, reason):
        """Add a flag and quarantine source/derivatives, never clear flags."""
        if not isinstance(flag, str) or not flag.strip() or len(flag) > 100:
            raise ValueError('invalid_source_flag')
        with self._policy_change(source_id, reason):
            try:
                flags = json.loads(self.db.execute('SELECT flags_json FROM source_metadata '
                                                   'WHERE source_id=?', (source_id,)).fetchone()[0])
                if not isinstance(flags, list) or any(not isinstance(v, str) for v in flags):
                    raise ValueError('invalid_source_flags')
            except (ValueError, TypeError, RecursionError):
                raise ValueError('invalid_source_flags') from None
            flags = sorted(set(flags + [flag]))
            self.db.execute('UPDATE source_metadata SET flags_json=? WHERE source_id=?',
                            (json.dumps(flags, separators=(',', ':')), source_id))
            self._handling_event(source_id, 'flag', reason, {'flag': flag})

    def set_retention(self, source_id, *, retain_until=_UNSET, legal_hold=_UNSET, reason):
        """Record a decision, preserving omitted fields; expiry never deletes data."""
        if ((legal_hold is not _UNSET and type(legal_hold) is not bool) or
                (retain_until is not _UNSET and retain_until is not None and
                (type(retain_until) not in (int, float) or not math.isfinite(retain_until) or retain_until < 0))):
            raise ValueError('invalid_retention')
        with self._policy_change(source_id, reason) as row:
            retain_until = row[1] if retain_until is _UNSET else retain_until
            legal_hold = bool(row[2]) if legal_hold is _UNSET else legal_hold
            self.db.execute('UPDATE source_policy SET retain_until=?,legal_hold=? WHERE source_id=?',
                            (retain_until, int(legal_hold), source_id))
            self._handling_event(source_id, 'retention', reason,
                                 {'before_until': row[1], 'before_hold': bool(row[2]),
                                  'retain_until': retain_until, 'legal_hold': legal_hold})

    def remove_source(self, source_id, *, confirm_source_id=None, reason):
        """Confirmed logical withdrawal: delete derivatives, retain archive history.

        Not physical original-byte erasure or secure deletion. Holds and future
        retention block the operation. The source cannot be silently recaptured.
        """
        if confirm_source_id != source_id or not isinstance(source_id, str) or not source_id:
            raise ValueError('confirmation_required')
        with self._policy_change(source_id, reason) as row:
            if row[2]:
                raise ValueError('legal_hold')
            if row[1] is not None and row[1] > time.time():
                raise ValueError('retention_active')
            self.db.execute('UPDATE source_policy SET removed=1 WHERE source_id=?', (source_id,))
            # Only optional derived stores are removed; immutable archive objects
            # and acquisition/change receipts (including shared bytes) remain.
            for table, column in (('text_index', 'source_id'), ('search_derivative_metadata', 'derivative_id')):
                if self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
                    predicate = ('source_id=?' if column=='source_id' else
                                 'derivative_id IN (SELECT d.derivative_id FROM derivatives d '
                                 'JOIN revisions r ON r.revision_id=d.revision_id WHERE r.source_id=?)')
                    self.db.execute('DELETE FROM ' + table + ' WHERE ' + predicate, (source_id,))
            cursor = self.db.execute('DELETE FROM derivatives WHERE revision_id IN '
                                     '(SELECT revision_id FROM revisions WHERE source_id=?)', (source_id,))
            result = dict(source_id=source_id, derivatives_deleted=cursor.rowcount, originals_retained=True)
            self._handling_event(source_id, 'withdrawal', reason, result)
        return result

    def handling_history(self, source_id):
        cursor = self.db.execute('SELECT event_id,action,reason,recorded,details_json '
                                 'FROM handling_events WHERE source_id=? ORDER BY event_id', (source_id,))
        return [dict(event_id=row[0], action=row[1], reason=row[2], recorded=row[3],
                     details=json.loads(row[4])) for row in cursor]

    def export_original(self, revision_id):
        """Return a current-policy checked in-memory original export, not a file.

        Immutable raw original() remains a trusted administration route. Already
        exported copies are point-in-time snapshots and cannot be recalled.
        """
        row = self.db.execute('SELECT r.source_id,r.url,r.content_hash,r.mime,o.content '
                              'FROM revisions r JOIN documents s ON s.source_id=r.source_id '
                              'JOIN source_metadata m ON m.source_id=s.source_id '
                              'JOIN content_objects o ON o.content_hash=r.content_hash '
                              'WHERE r.revision_id=? AND ' + REVISION_ELIGIBLE, (revision_id,)).fetchone()
        if row is None:
            raise LookupError('original_unavailable')
        if hashlib.sha256(row[4]).hexdigest() != row[2]:
            raise ValueError('original_integrity')
        return dict(kind='original', revision_id=revision_id, source_id=row[0], url=row[1],
                    content_hash=row[2], mime=row[3], content=row[4], handling='public', flags=[])

    def close(self):
        self.db.close()
