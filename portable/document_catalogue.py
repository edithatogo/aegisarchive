"""SQLite-backed immutable document catalogue for offline mirrors."""
from __future__ import annotations
import hashlib, mimetypes, sqlite3, time
from pathlib import Path

SCHEMA = """CREATE TABLE IF NOT EXISTS documents (source_id TEXT PRIMARY KEY, first_seen REAL NOT NULL, handling TEXT NOT NULL DEFAULT 'unknown');
CREATE TABLE IF NOT EXISTS revisions (revision_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, url TEXT NOT NULL, content_hash TEXT NOT NULL, mime TEXT NOT NULL, size INTEGER NOT NULL, acquired REAL NOT NULL, status TEXT NOT NULL DEFAULT 'captured', UNIQUE(source_id, content_hash), FOREIGN KEY(source_id) REFERENCES documents(source_id));
CREATE TABLE IF NOT EXISTS urls (url TEXT PRIMARY KEY, source_id TEXT NOT NULL, revision_id TEXT NOT NULL, first_seen REAL NOT NULL, last_seen REAL NOT NULL);
CREATE TABLE IF NOT EXISTS derivatives (derivative_id TEXT PRIMARY KEY, revision_id TEXT NOT NULL, kind TEXT NOT NULL, extractor TEXT NOT NULL, output_hash TEXT NOT NULL, status TEXT NOT NULL, text TEXT, locator_json TEXT, handling TEXT NOT NULL DEFAULT 'unknown');
"""

def source_identity(url: str) -> str:
    return hashlib.sha256(url.encode('utf-8')).hexdigest()

class Catalogue:
    def __init__(self, path=':memory:'):
        self.db = sqlite3.connect(str(path)); self.db.executescript(SCHEMA); self.db.commit()
    def register(self, url, content, mime=None, handling='unknown', acquired=None):
        now = acquired or time.time(); sid = source_identity(url); digest = hashlib.sha256(content).hexdigest()
        mime = mime or mimetypes.guess_type(url)[0] or 'application/octet-stream'
        self.db.execute('INSERT OR IGNORE INTO documents VALUES (?,?,?)',(sid,now,handling))
        row = self.db.execute('SELECT revision_id FROM revisions WHERE source_id=? AND content_hash=?',(sid,digest)).fetchone()
        if row: rid=row[0]
        else:
            rid=hashlib.sha256((sid+digest).encode()).hexdigest(); self.db.execute('INSERT INTO revisions VALUES (?,?,?,?,?,?,?,?)',(rid,sid,url,digest,mime,len(content),now,'captured'))
        self.db.execute('INSERT INTO urls VALUES (?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET revision_id=excluded.revision_id,last_seen=excluded.last_seen',(url,sid,rid,now,now)); self.db.commit()
        return {'source_id':sid,'revision_id':rid,'content_hash':digest,'mime':mime,'moved':False}
    def revisions(self, url):
        sid=source_identity(url); return self.db.execute('SELECT * FROM revisions WHERE source_id=? ORDER BY acquired',(sid,)).fetchall()
    def close(self): self.db.close()
