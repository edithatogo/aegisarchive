"""Revision-aware, offline FTS5 retrieval over validated text derivatives.

SearchIndex.add retains its positional arguments. Search adds keyword-only
revision_id/kind filters; old source_id/limit positional calls remain valid.
Only public, unflagged complete/partial nonblank derivatives are searchable.
An omitted handling label inherits the source label; a caller cannot clear a
source or acquisition restriction. Catalogue policy APIs govern explicit
quarantine, retention and withdrawal. Results include an original reference resolved
with catalogue.original(hit['original']['revision_id']), never a live fetch.

Existing catalogue rows remain untouched. Legacy FTS rows lacking validated
search metadata are ignored until explicitly re-added from extraction results.
No automatic corpus rebuild, OCR, network access or dependency is required.
"""
import hashlib
import difflib
import json
import math
import sqlite3

from .document_catalogue import PROCESSING_STATES, REVISION_ELIGIBLE


# Policy is checked before LIMIT, so hidden hits cannot crowd eligible results
# out of a page. Cache insertion uses the same eligibility predicate.
ELIGIBLE = """
    d.status IN ('complete','partial') AND length(trim(d.text)) > 0
    AND d.handling='public' AND
""" + REVISION_ELIGIBLE
JOINS = """
    JOIN derivatives d ON d.derivative_id=text_index.derivative_id
    JOIN search_derivative_metadata x ON x.derivative_id=d.derivative_id
    JOIN revisions r ON r.revision_id=d.revision_id
    JOIN documents s ON s.source_id=r.source_id
    JOIN source_metadata m ON m.source_id=s.source_id
"""


def _json(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError, RecursionError):
        raise ValueError('invalid_derivative_metadata') from None


class SearchIndex:
    def __init__(self, catalogue):
        self.db = catalogue.db
        with self.db:
            self.db.execute('CREATE VIRTUAL TABLE IF NOT EXISTS text_index USING fts5('
                            'derivative_id UNINDEXED,text,source_id UNINDEXED,revision_id UNINDEXED)')
            self.db.execute('CREATE TABLE IF NOT EXISTS search_derivative_metadata ('
                            'derivative_id TEXT PRIMARY KEY REFERENCES derivatives(derivative_id),'
                            'extraction_json TEXT NOT NULL)')
            # Incremental cache invalidation, not a corpus rebuild. These triggers
            # also cover restrictions made through another catalogue connection.
            for name, event, condition, predicate in (
                    ('source', 'UPDATE OF handling ON documents', "NEW.handling!='public'", 'source_id=NEW.source_id'),
                    ('flags', 'UPDATE OF flags_json ON source_metadata', "NEW.flags_json!='[]'", 'source_id=NEW.source_id'),
                    ('withdrawal', 'UPDATE OF removed ON source_policy', 'NEW.removed=1', 'source_id=NEW.source_id'),
                    ('acquisition', 'INSERT ON acquisitions', "NEW.handling!='public'", 'revision_id=NEW.revision_id'),
                    ('derivative_insert', 'INSERT ON derivatives', "NEW.handling!='public'", 'revision_id=NEW.revision_id'),
                    ('derivative_update', 'UPDATE OF handling,status ON derivatives',
                     "NEW.handling!='public' OR NEW.status NOT IN ('complete','partial')",
                     "derivative_id=NEW.derivative_id OR (NEW.handling!='public' AND revision_id=NEW.revision_id)")):
                self.db.execute('CREATE TRIGGER IF NOT EXISTS invalidate_search_' + name + ' AFTER ' + event +
                                ' WHEN ' + condition + ' BEGIN DELETE FROM text_index WHERE ' + predicate + '; END')
            self.db.execute('CREATE TRIGGER IF NOT EXISTS invalidate_search_derivative_delete '
                            'AFTER DELETE ON derivatives BEGIN DELETE FROM text_index '
                            'WHERE derivative_id=OLD.derivative_id; END')
            self.db.execute('DELETE FROM text_index WHERE NOT EXISTS ('
                            'SELECT 1 FROM derivatives d JOIN search_derivative_metadata x ON x.derivative_id=d.derivative_id '
                            'JOIN revisions r ON r.revision_id=d.revision_id '
                            'JOIN documents s ON s.source_id=r.source_id '
                            'JOIN source_metadata m ON m.source_id=s.source_id '
                            'WHERE d.derivative_id=text_index.derivative_id AND ' + ELIGIBLE + ')')

    def add(self, result, source_id, revision_id, handling=None, kind=None):
        """Store extraction, then replace only its own FTS cache entry.

        IDs include revision and extraction metadata, not just output bytes.
        OCR confidence, coverage and engine/model provenance survive. Repeated
        adds are idempotent and cannot relax an existing handling restriction.
        """
        # Reserve the writer before reading policy, not just before INSERT.
        # Otherwise a concurrent restriction can leave a stale public label on
        # a new derivative even though retrieval correctly denies its text.
        with self.db:
            if not self.db.in_transaction:
                self.db.execute('BEGIN IMMEDIATE')
            return self._add_locked(result, source_id, revision_id, handling, kind)

    def _add_locked(self, result, source_id, revision_id, handling, kind):
        revision = self.db.execute(
            'SELECT r.content_hash,s.handling FROM revisions r JOIN documents s '
            'ON s.source_id=r.source_id WHERE r.revision_id=? AND r.source_id=?',
            (revision_id, source_id)).fetchone()
        if revision is None:
            raise ValueError('source_revision_mismatch')
        if self.db.execute('SELECT removed FROM source_policy WHERE source_id=?', (source_id,)).fetchone() == (1,):
            raise ValueError('source_removed')
        if not isinstance(result, dict):
            raise ValueError('invalid_derivative')
        text, status = result.get('text'), result.get('status')
        extractor, locators = result.get('extractor'), result.get('locators')
        if (not isinstance(text, str) or len(text) > 8388608 or
                not isinstance(status, str) or status not in PROCESSING_STATES or
                not isinstance(extractor, str) or not extractor or
                not isinstance(locators, list) or len(locators) > 100000):
            raise ValueError('invalid_derivative')
        if result.get('output_hash') != hashlib.sha256(text.encode('utf-8')).hexdigest():
            raise ValueError('output_hash_mismatch')
        if 'source_hash' in result and result['source_hash'] != revision[0]:
            raise ValueError('source_hash_mismatch')
        selected_kind = result.get('kind', kind or 'text')
        if (selected_kind not in ('text', 'ocr') or
                (kind is not None and kind != selected_kind)):
            raise ValueError('invalid_derivative_kind')
        for loc in locators:
            if (not isinstance(loc, dict) or type(loc.get('start')) is not int or
                    type(loc.get('end')) is not int or
                    not 0 <= loc['start'] <= loc['end'] <= len(text)):
                raise ValueError('invalid_derivative_locators')
        if text.strip() and status in ('complete', 'partial') and not locators:
            raise ValueError('missing_derivative_locators')
        if selected_kind == 'ocr' and text:
            confidence = result.get('confidence')
            if ('source_hash' not in result or not isinstance(result.get('engines'), dict) or
                    not result['engines'] or type(confidence) not in (int, float) or
                    not math.isfinite(confidence) or not 0 <= confidence <= 100):
                raise ValueError('invalid_ocr_provenance')
        label = revision[1] if handling is None else handling
        if not isinstance(label, str) or not label:
            raise ValueError('invalid_handling')
        if revision[1] != 'public':
            label = revision[1]
        # Conservatively carry revision restrictions across legacy IDs and
        # extractor changes; a new identity is not permission to clear evidence.
        restriction = self.db.execute(
            "SELECT handling FROM derivatives WHERE revision_id=? AND handling!='public' "
            'ORDER BY derivative_id LIMIT 1', (revision_id,)).fetchone()
        if restriction:
            label = restriction[0]
        metadata = {key: value for key, value in result.items() if key not in ('text', 'locators')}
        metadata['kind'] = selected_kind
        encoded, locator_json = _json(metadata), _json(locators)
        if len(encoded) + len(locator_json) > 16777216:
            raise ValueError('derivative_metadata_limit')
        identity = _json([revision_id, encoded, locator_json])
        did = 'search:' + hashlib.sha256(identity.encode('utf-8')).hexdigest()
        with self.db:
            existing = self.db.execute('SELECT handling FROM derivatives WHERE derivative_id=?', (did,)).fetchone()
            if existing is None:
                self.db.execute('INSERT INTO derivatives VALUES (?,?,?,?,?,?,?,?,?)',
                                (did, revision_id, selected_kind, extractor, result['output_hash'],
                                 status, text, locator_json, label))
                self.db.execute('INSERT INTO search_derivative_metadata VALUES (?,?)', (did, encoded))
            else:
                # Reclassification belongs to the explicit T8 workflow.
                if existing[0] != 'public':
                    label = existing[0]
                self.db.execute('UPDATE derivatives SET handling=? WHERE derivative_id=?', (label, did))
            self.db.execute('DELETE FROM text_index WHERE derivative_id=?', (did,))
            eligible = self.db.execute(
                'SELECT 1 FROM derivatives d JOIN revisions r ON r.revision_id=d.revision_id '
                'JOIN documents s ON s.source_id=r.source_id '
                'JOIN source_metadata m ON m.source_id=s.source_id '
                'WHERE d.derivative_id=? AND ' + ELIGIBLE, (did,)).fetchone()
            if eligible:
                self.db.execute('INSERT INTO text_index VALUES (?,?,?,?)', (did, text, source_id, revision_id))
        return did

    def search(self, query, source_id=None, limit=20, *, revision_id=None, kind=None):
        """Return cited complete/partial hits using bound FTS5 query syntax.

        Partial text is searchable with status/reason/coverage retained. A match
        or OCR confidence never establishes source truth. Syntax errors raise
        a content-free ValueError.
        """
        if not isinstance(query, str) or not query.strip() or len(query) > 4096:
            raise ValueError('invalid_search_query')
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('invalid_search_limit')
        if any(value is not None and (not isinstance(value, str) or not value)
               for value in (source_id, revision_id)):
            raise ValueError('invalid_search_filter')
        if kind is not None and kind not in ('text', 'ocr'):
            raise ValueError('invalid_search_kind')
        sql = """SELECT d.derivative_id,d.text,r.source_id,r.revision_id,
                        d.kind,d.status,d.extractor,d.output_hash,d.locator_json,
                        x.extraction_json,r.url,r.content_hash,
                        EXISTS(SELECT 1 FROM content_objects o WHERE o.content_hash=r.content_hash)
                 FROM text_index """ + JOINS + """
                 WHERE text_index MATCH ? AND text_index.text=d.text
                 AND text_index.source_id=r.source_id AND text_index.revision_id=r.revision_id
                 AND """ + ELIGIBLE
        args = [query]
        for column, value in (('r.source_id', source_id), ('r.revision_id', revision_id), ('d.kind', kind)):
            if value is not None:
                sql += ' AND ' + column + '=?'
                args.append(value)
        sql += ' ORDER BY bm25(text_index),d.derivative_id LIMIT ?'
        args.append(limit)
        try:
            rows = self.db.execute(sql, args).fetchall()
        except sqlite3.OperationalError:
            raise ValueError('invalid_search_query') from None
        return self._hits(rows)

    @staticmethod
    def _hits(rows):
        hits = []
        for did, text, sid, rid, stored_kind, status, extractor, digest, locations, metadata, url, source_hash, available in rows:
            try:
                hit, locators = json.loads(metadata), json.loads(locations)
                identity = _json([rid, metadata, locations])
                expected = 'search:' + hashlib.sha256(identity.encode('utf-8')).hexdigest()
                if (not isinstance(hit, dict) or not isinstance(locators, list) or expected != did or
                        hit.get('output_hash') != digest or hit.get('kind') != stored_kind or
                        hit.get('status') != status or hit.get('extractor') != extractor or
                        hashlib.sha256(text.encode('utf-8')).hexdigest() != digest):
                    raise ValueError('invalid_search_metadata')
            except (TypeError, ValueError, RecursionError):
                raise ValueError('invalid_search_metadata') from None
            if 'derivative_id' in hit:
                hit['extraction_derivative_id'] = hit['derivative_id']
            hit.update(derivative_id=did, text=text, source_id=sid, revision_id=rid,
                       kind=stored_kind, status=status, extractor=extractor, output_hash=digest,
                       locators=locators,
                       original=dict(revision_id=rid, url=url, content_hash=source_hash, available=bool(available)))
            hits.append(hit)
        return hits

    def _comparison_hit(self, derivative_id):
        if not isinstance(derivative_id, str) or not derivative_id:
            raise ValueError('invalid_derivative_id')
        rows = self.db.execute("""
            SELECT d.derivative_id,d.text,r.source_id,r.revision_id,
                   d.kind,d.status,d.extractor,d.output_hash,d.locator_json,
                   x.extraction_json,r.url,r.content_hash,
                   EXISTS(SELECT 1 FROM content_objects o WHERE o.content_hash=r.content_hash)
            FROM derivatives d
            JOIN search_derivative_metadata x ON x.derivative_id=d.derivative_id
            JOIN revisions r ON r.revision_id=d.revision_id
            JOIN documents s ON s.source_id=r.source_id
            JOIN source_metadata m ON m.source_id=s.source_id
            WHERE d.derivative_id=? AND """ + ELIGIBLE, (derivative_id,)).fetchall()
        if not rows:
            raise LookupError('derivative_unavailable')
        return self._hits(rows)[0]

    def compare(self, before_derivative_id, after_derivative_id):
        """Bounded text diff with current retrieval policy and full provenance.

        Original-byte equality is reported separately from derivative equality.
        Partial extraction/coverage warnings remain on each side. A diff is not
        a semantic or clinical judgement, nor proof that extraction is complete.
        This is a display comparison, not an applicable patch. Missing terminal
        linefeeds are annotated when that state differs between the inputs.
        Large/different-kind inputs are explicitly not diffed. No network, OCR,
        extraction, cache rebuild or persistent comparison record is triggered.
        """
        before, after = self._comparison_hit(before_derivative_id), self._comparison_hit(after_derivative_id)
        same_output = before['output_hash'] == after['output_hash']
        same_source = before['source_id'] == after['source_id']
        same_original = before['original']['content_hash'] == after['original']['content_hash']
        diff, status = None, 'complete'
        if before['kind'] != after['kind']:
            status = 'not_comparable_kind'
        elif same_output:
            diff = ''
        elif max(len(before['text']), len(after['text'])) > 32768:
            status = 'not_generated_size_limit'
        else:
            old, new = before['text'].splitlines(keepends=True), after['text'].splitlines(keepends=True)
            if max(len(old), len(new)) > 1000:
                status = 'not_generated_size_limit'
            else:
                parts, size = [], 0
                for line in difflib.unified_diff(old, new, fromfile=before_derivative_id,
                                                 tofile=after_derivative_id, lineterm='\n'):
                    if not line.endswith('\n'):
                        line += '\n'
                        if before['text'].endswith('\n') != after['text'].endswith('\n'):
                            line += '\\ No newline at end of file\n'
                    if size + len(line) > 65536:
                        status = 'partial_output_limit'
                        break
                    parts.append(line)
                    size += len(line)
                diff = ''.join(parts)
        return dict(before=before, after=after, same_output=same_output,
                    same_source=same_source, same_original_bytes=same_original,
                    original_content_changed=not same_original if same_source else None,
                    diff_status=status, text_diff=diff)

    def export(self, derivative_id):
        """Return a freshly policy-checked derivative snapshot with handling.

        No file is written. Existing exported snapshots are not live permissions
        and cannot be recalled; consumers must enforce their own storage/access.
        """
        return dict(self._comparison_hit(derivative_id), handling='public', flags=[], export_kind='derivative')
