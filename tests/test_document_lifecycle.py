"""Synthetic acceptance cases for the document lifecycle contract."""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from portable.document_catalogue import Catalogue
from portable.document_extract import extract
from portable import document_extract
from portable.document_search import SearchIndex
from optional.document_processing.test_adapters import ParentTests as OptionalParentTests
from optional.document_processing.test_adapters import ParserTests as OptionalParserTests
from optional.document_processing.test_ocr import Core as OptionalOCRCoreTests
from optional.document_processing.test_ocr import RealOCR as OptionalOCRAcceptanceTests


class CatalogueSchemaTests(unittest.TestCase):
    def setUp(self):
        self.catalogue = Catalogue()
        self.addCleanup(self.catalogue.close)

    def test_unknown_metadata_is_not_invented(self):
        result = self.catalogue.register('https://fixture.test/a', b'hello')
        row = self.catalogue.db.execute(
            'SELECT title, document_date, version, flags_json FROM source_metadata '
            'WHERE source_id=?', (result['source_id'],)).fetchone()
        self.assertEqual(row, (None, None, None, '[]'))
        self.assertEqual(result['content_hash'], hashlib.sha256(b'hello').hexdigest())
        self.assertEqual(result['mime'], 'application/octet-stream')

    def test_derivative_states_and_revision_reference_are_enforced(self):
        result = self.catalogue.register('https://fixture.test/a.txt', b'hello')
        for state in ('pending', 'complete', 'partial', 'failed', 'encrypted', 'unsupported'):
            self.catalogue.db.execute(
                'INSERT INTO derivatives VALUES (?,?,?,?,?,?,?,?,?)',
                (state, result['revision_id'], 'text', 'test-1', 'abc', state,
                 '', '[]', 'unknown'))
        with self.assertRaises(sqlite3.IntegrityError):
            self.catalogue.db.execute(
                'INSERT INTO derivatives VALUES (?,?,?,?,?,?,?,?,?)',
                ('bad', result['revision_id'], 'text', 'test-1', '', 'invented', '', '[]', 'unknown'))
        with self.assertRaises(sqlite3.IntegrityError):
            self.catalogue.db.execute(
                'INSERT INTO derivatives VALUES (?,?,?,?,?,?,?,?,?)',
                ('orphan', 'absent', 'text', 'test-1', '', 'complete', '', '[]', 'unknown'))
        with self.assertRaises(sqlite3.IntegrityError):
            self.catalogue.db.execute("UPDATE derivatives SET revision_id='absent' WHERE derivative_id='complete'")

    def test_legacy_database_is_upgraded_without_losing_revisions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'catalogue.sqlite'
            previous = Catalogue(path)
            result = previous.register('https://fixture.test/a', b'old')
            previous.db.execute('DROP TABLE source_metadata')
            previous.db.commit()
            previous.close()
            current = Catalogue(path)
            self.addCleanup(current.close)
            self.assertEqual(current.revisions('https://fixture.test/a')[0][0], result['revision_id'])
            row = current.db.execute('SELECT flags_json FROM source_metadata').fetchone()
            self.assertEqual(row, ('[]',))


class RegistrationHistoryTests(unittest.TestCase):
    def setUp(self):
        self.catalogue = Catalogue()
        self.addCleanup(self.catalogue.close)

    def test_same_bytes_deduplicate_storage_without_inventing_movement(self):
        first = self.catalogue.register('https://fixture.test/a', b'original', acquired=0)
        second = self.catalogue.register('https://fixture.test/b', b'original', acquired=1)
        self.assertNotEqual(first['source_id'], second['source_id'])
        self.assertEqual(first['content_hash'], second['content_hash'])
        self.assertFalse(second['moved'])
        self.assertTrue(second['duplicate'])
        self.assertEqual(self.catalogue.db.execute('SELECT COUNT(*) FROM content_objects').fetchone()[0], 1)
        self.assertEqual(self.catalogue.original(first['revision_id']), b'original')
        self.assertEqual(self.catalogue.acquisitions('https://fixture.test/a')[0]['acquired'], 0)

    def test_explicit_move_retains_source_history_and_changed_versions(self):
        old = 'https://fixture.test/old.txt'
        new = 'https://fixture.test/new.txt'
        first = self.catalogue.register(old, b'version one', acquired=1)
        moved = self.catalogue.register(new, b'version one', moved_from=old, acquired=2)
        changed = self.catalogue.register(new, b'version two', acquired=3)
        self.assertEqual(first['source_id'], moved['source_id'])
        self.assertEqual(first['revision_id'], moved['revision_id'])
        self.assertTrue(moved['moved'])
        self.assertEqual(first['source_id'], changed['source_id'])
        self.assertNotEqual(first['revision_id'], changed['revision_id'])
        self.assertEqual(len(self.catalogue.revisions(old)), 2)
        self.assertEqual(len(self.catalogue.acquisitions(new)), 3)
        self.assertEqual(self.catalogue.original(first['revision_id']), b'version one')
        self.assertEqual(self.catalogue.original(changed['revision_id']), b'version two')

    def test_repeat_acquisition_preserves_observed_mime_and_handling(self):
        url = 'https://fixture.test/a'
        first = self.catalogue.register(url, b'hello', mime='text/plain', handling='restricted', acquired=1)
        again = self.catalogue.register(url, b'hello', mime='text/markdown', acquired=2)
        self.assertEqual(first['revision_id'], again['revision_id'])
        events = self.catalogue.acquisitions(url)
        self.assertEqual([e['mime'] for e in events], ['text/plain', 'text/markdown'])
        self.assertEqual([e['handling'] for e in events], ['restricted', 'unknown'])
        self.assertEqual(self.catalogue.db.execute('SELECT handling FROM documents').fetchone()[0], 'restricted')

    def test_observations_and_originals_are_immutable(self):
        self.catalogue.register('https://fixture.test/a', b'hello')
        for table in ('revisions', 'content_objects', 'acquisitions'):
            with self.subTest(table=table), self.assertRaises(sqlite3.IntegrityError):
                self.catalogue.db.execute('DELETE FROM ' + table)

    def test_replacement_inserts_cannot_destroy_originals_or_observations(self):
        result = self.catalogue.register('https://fixture.test/a', b'original')
        for table in ('revisions', 'content_objects', 'acquisitions'):
            with self.subTest(table=table), self.assertRaises(sqlite3.IntegrityError):
                self.catalogue.db.execute(f'INSERT OR REPLACE INTO {table} SELECT * FROM {table}')
        self.assertEqual(self.catalogue.original(result['revision_id']), b'original')

    def test_legacy_records_are_not_fabricated_but_can_be_recaptured(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'legacy.sqlite'
            db = sqlite3.connect(path)
            db.executescript('''
                CREATE TABLE documents (source_id TEXT PRIMARY KEY,first_seen REAL NOT NULL,handling TEXT NOT NULL);
                CREATE TABLE revisions (revision_id TEXT PRIMARY KEY,source_id TEXT NOT NULL,url TEXT NOT NULL,content_hash TEXT NOT NULL,mime TEXT NOT NULL,size INTEGER NOT NULL,acquired REAL NOT NULL,status TEXT NOT NULL,UNIQUE(source_id,content_hash));
                CREATE TABLE urls (url TEXT PRIMARY KEY,source_id TEXT NOT NULL,revision_id TEXT NOT NULL,first_seen REAL NOT NULL,last_seen REAL NOT NULL);
                CREATE TABLE derivatives (derivative_id TEXT PRIMARY KEY,revision_id TEXT NOT NULL,kind TEXT NOT NULL,extractor TEXT NOT NULL,output_hash TEXT NOT NULL,status TEXT NOT NULL,text TEXT,locator_json TEXT,handling TEXT NOT NULL);
            ''')
            url = 'https://fixture.test/legacy'
            sid = hashlib.sha256(url.encode()).hexdigest()
            digest = hashlib.sha256(b'legacy').hexdigest()
            rid = hashlib.sha256((sid + digest).encode()).hexdigest()
            db.execute('INSERT INTO documents VALUES (?,?,?)', (sid, 1, 'unknown'))
            db.execute('INSERT INTO revisions VALUES (?,?,?,?,?,?,?,?)', (rid, sid, url, digest, 'text/plain', 6, 1, 'captured'))
            db.execute('INSERT INTO urls VALUES (?,?,?,?,?)', (url, sid, rid, 1, 1))
            db.commit()
            db.close()
            current = Catalogue(path)
            self.addCleanup(current.close)
            old_row = list(current.revisions(url)[0])
            old_row[0] = 'replacement-id'
            with self.assertRaises(sqlite3.IntegrityError):
                current.db.execute('INSERT OR REPLACE INTO revisions VALUES (?,?,?,?,?,?,?,?)', old_row)
            self.assertEqual(current.revisions(url)[0][0], rid)
            self.assertEqual(current.acquisitions(url), [])
            with self.assertRaisesRegex(LookupError, '^original_bytes_unavailable$'):
                current.original(rid)
            recaptured = current.register(url, b'legacy', acquired=2)
            self.assertEqual(recaptured['revision_id'], rid)
            self.assertEqual(len(current.acquisitions(url)), 1)
            self.assertEqual(current.original(rid), b'legacy')

    def test_move_cannot_merge_existing_unrelated_sources(self):
        self.catalogue.register('https://fixture.test/a', b'a')
        self.catalogue.register('https://fixture.test/b', b'b')
        with self.assertRaisesRegex(ValueError, '^source_conflict$'):
            self.catalogue.register('https://fixture.test/b', b'b', moved_from='https://fixture.test/a')
        self.assertEqual(len(self.catalogue.acquisitions('https://fixture.test/b')), 1)

    def test_invalid_timestamp_rolls_back_and_mime_handles_query(self):
        with self.assertRaises(ValueError):
            self.catalogue.register('https://fixture.test/a', b'a', acquired=float('nan'))
        self.assertEqual(self.catalogue.db.execute('SELECT COUNT(*) FROM documents').fetchone()[0], 0)
        result = self.catalogue.register('https://fixture.test/a.txt?v=1', b'hello')
        self.assertEqual(result['mime'], 'text/plain')


class NativeExtractionTests(unittest.TestCase):
    def test_hidden_and_implied_html_closures(self):
        result = extract(b'<head><meta><body><p hidden>PRIVATE</p><p>Visible', 'text/html')
        self.assertEqual(result['text'], 'Visible')
        result = extract(b'<ul>' + b'<li>Item' * 600 + b'</ul>', 'text/html')
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(len(result['locators']), 600)
        result = extract(b'<div hidden><p>PRIVATE</p></div><p>Visible', 'text/html')
        self.assertEqual(result['text'], 'Visible')
        self.assertEqual(extract(b'<head><title>Title</title>Visible', 'text/html')['text'], 'Visible')

    def test_malformed_declaration_has_no_source_in_diagnostic(self):
        result = extract(b'<![PRIVATE]>Visible', 'text/html')
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['reason'], 'malformed_input')
        self.assertEqual(result['text'], '')
        self.assertNotIn('PRIVATE', json.dumps(result))

    def test_marked_declaration_boundaries_are_consistent_across_parsers(self):
        for content in (b'<![PRIVATE]>Visible', b'<![private]>Visible',
                        b'<div><![UNRECOGNISED]>Visible</div>'):
            with self.subTest(content=content):
                result = extract(content, 'text/html')
                self.assertEqual(result['status'], 'failed')
                self.assertEqual(result['reason'], 'malformed_input')
                self.assertEqual(result['text'], '')
                self.assertEqual(result['locators'], [])
                self.assertNotIn('PRIVATE', json.dumps(result))
                self.assertNotIn('UNRECOGNISED', json.dumps(result))
        controls = (
            (b'<!DOCTYPE html><p>Visible</p>', 'Visible'),
            (b'<!-- <![PRIVATE]> --><p>Visible</p>', 'Visible'),
            (b'<script>const s="<![PRIVATE]>";</script><p>Visible</p>', 'Visible'),
            (b'<style>/* <![PRIVATE]> */</style><p>Visible</p>', 'Visible'),
            (b'<p>&lt;![PRIVATE]&gt;</p>', '<![PRIVATE]>'),
            (b'<![CDATA[Hidden]]><p>Visible</p>', 'Visible'),
            (b'<!--[if IE]>Hidden<![endif]--><p>Visible</p>', 'Visible'),
            (b'<![if IE]>Conditional<![endif]>Visible', 'ConditionalVisible'),
        )
        for content, text in controls:
            with self.subTest(content=content):
                result = extract(content, 'text/html')
                self.assertEqual(result['status'], 'complete')
                self.assertEqual(result['text'], text)
    def test_html_extracts_visible_blocks_and_skips_active_content(self):
        content = b'<head><title>hidden</title></head><h1>A &amp; B</h1><script>secret()</script><style>.x{}</style><p>Second <b>paragraph</b></p>'
        result = extract(content, 'TEXT/HTML; charset=utf-8')
        self.assertEqual(result['text'], 'A & B\nSecond paragraph')
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(content[:6], b'<head>')
        self.assertEqual(result['locator_space'], 'derivative_text')

    def test_locators_are_exact_unicode_ranges(self):
        text = 'écho\r\nsecond\nlast'
        result = extract(text.encode())
        self.assertEqual([result['text'][p['start']:p['end']] for p in result['locators']], ['écho', 'second', 'last'])
        self.assertTrue(all(p['end'] <= len(text) for p in result['locators']))
        self.assertEqual(result['output_hash'], hashlib.sha256(text.encode()).hexdigest())
        self.assertEqual(result['offset_unit'], 'unicode_codepoint')
        self.assertEqual(extract(text.encode()), result)

    def test_invalid_encoding_is_partial_but_valid_replacement_character_is_not(self):
        result = extract(b'prefix\xffsuffix')
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['reason'], 'invalid_encoding')
        self.assertEqual(extract('\ufffd'.encode())['status'], 'complete')

    def test_bounds_return_content_free_diagnostics(self):
        for content, mime, limit in [(b'PRIVATE', 'text/plain', 2), (b'PRIVATE', 'application/pdf', 100)]:
            result = extract(content, mime, limit)
            self.assertIn(result['status'], ('failed', 'unsupported'))
            self.assertEqual(result['text'], '')
            self.assertNotIn('PRIVATE', json.dumps(result))
        self.assertEqual(extract(b'a', limit=-1)['reason'], 'invalid_limit')
        self.assertEqual(extract('secret')['reason'], 'invalid_content')

    def test_empty_and_many_lines_have_valid_locators(self):
        self.assertEqual(extract(b'')['locators'], [])
        result = extract(b'x\n' * 20000)
        self.assertEqual(len(result['locators']), 20000)
        self.assertEqual(result['locators'][-1]['end'], 39999)

    def test_html_depth_limit_fails_without_exposing_content(self):
        result = extract(b'<div>' * 600 + b'PRIVATE' + b'</div>' * 600, 'text/html')
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['reason'], 'structure_limit')
        self.assertNotIn('PRIVATE', json.dumps(result))


class OptionalIntegrationTests(unittest.TestCase):
    def test_binary_parsers_require_explicit_opt_in(self):
        default = extract(b'%PDF-synthetic', 'application/pdf', optional_python='/absent/python')
        self.assertEqual(default['reason'], 'no_builtin_extractor')
        enabled = extract(b'%PDF-synthetic', 'application/pdf', optional=True,
                          optional_python='/absent/python')
        self.assertEqual(enabled['reason'], 'worker_unavailable')
        self.assertEqual(enabled['locator_space'], 'derivative_text')
        self.assertEqual(enabled['text'], '')

    def test_native_extraction_remains_available_when_optional_runtime_missing(self):
        result = extract(b'<p>Native</p>', 'text/html', optional=True,
                         optional_python='/absent/python')
        self.assertEqual(result['text'], 'Native')
        self.assertEqual(result['status'], 'complete')


class HandlingRetentionTests(unittest.TestCase):
    def setUp(self):
        self.catalogue = Catalogue()
        self.addCleanup(self.catalogue.close)
        self.index = SearchIndex(self.catalogue)
        self.revision = self.catalogue.register('https://fixture.test/a', b'alpha', handling='public')
        self.sid, self.rid = self.revision['source_id'], self.revision['revision_id']
        self.did = self.index.add(extract(b'alpha'), self.sid, self.rid)

    def test_restricting_source_propagates_to_derivatives_and_removes_cached_text(self):
        self.catalogue.set_handling(self.sid, 'restricted', reason='synthetic classification')
        self.assertEqual(self.catalogue.db.execute('SELECT handling FROM derivatives').fetchone()[0], 'restricted')
        self.assertEqual(self.catalogue.db.execute('SELECT COUNT(*) FROM text_index').fetchone()[0], 0)
        self.assertEqual(self.index.search('alpha'), [])
        with self.assertRaises(LookupError):
            self.index.export(self.did)
        with self.assertRaises(LookupError):
            self.catalogue.export_original(self.rid)
        self.assertEqual(self.catalogue.original(self.rid), b'alpha')

    def test_flagging_quarantines_existing_and_future_derivatives(self):
        self.catalogue.flag_source(self.sid, 'review_required', reason='synthetic flag')
        self.assertEqual(self.catalogue.db.execute('SELECT handling FROM documents').fetchone()[0], 'quarantined')
        self.assertEqual(json.loads(self.catalogue.db.execute('SELECT flags_json FROM source_metadata').fetchone()[0]),
                         ['review_required'])
        self.assertEqual(self.catalogue.db.execute('SELECT COUNT(*) FROM text_index').fetchone()[0], 0)
        other = dict(extract(b'alpha'), extractor='synthetic-alternate')
        self.index.add(other, self.sid, self.rid, handling='public')
        self.assertEqual(self.index.search('alpha'), [])
        self.assertTrue(all(row[0]=='quarantined' for row in self.catalogue.db.execute('SELECT handling FROM derivatives')))

    def test_direct_metadata_restrictions_also_invalidate_the_cache(self):
        for sql in ("UPDATE documents SET handling='restricted'",
                    "UPDATE source_metadata SET flags_json='[\"review\"]'",
                    "UPDATE derivatives SET handling='restricted'"):
            with self.subTest(sql=sql):
                # Fresh catalogue for each independent direct-SQL restriction.
                c = Catalogue()
                try:
                    index = SearchIndex(c)
                    r = c.register('https://fixture.test/a', b'alpha', handling='public')
                    index.add(extract(b'alpha'), r['source_id'], r['revision_id'])
                    c.db.execute(sql)
                    self.assertEqual(c.db.execute('SELECT COUNT(*) FROM text_index').fetchone()[0], 0)
                    self.assertEqual(index.search('alpha'), [])
                finally:
                    c.close()

    def test_restricted_reacquisition_propagates_without_overwriting_history(self):
        self.catalogue.register('https://fixture.test/a', b'alpha', handling='restricted')
        self.assertEqual(self.catalogue.db.execute('SELECT COUNT(*) FROM text_index').fetchone()[0], 0)
        self.assertEqual(self.catalogue.db.execute('SELECT handling FROM derivatives').fetchone()[0], 'restricted')
        self.assertEqual([a['handling'] for a in self.catalogue.acquisitions('https://fixture.test/a')],
                         ['public', 'restricted'])

    def test_exports_include_current_handling_and_original_lineage(self):
        derivative = self.index.export(self.did)
        original = self.catalogue.export_original(self.rid)
        self.assertEqual(derivative['handling'], 'public')
        self.assertEqual(derivative['flags'], [])
        self.assertEqual(derivative['original']['content_hash'], self.revision['content_hash'])
        self.assertEqual(original['handling'], 'public')
        self.assertEqual(original['content'], b'alpha')
        self.assertEqual(original['content_hash'], hashlib.sha256(original['content']).hexdigest())
        self.catalogue.flag_source(self.sid, 'review', reason='later synthetic restriction')
        with self.assertRaises(LookupError):
            self.index.export(self.did)
        with self.assertRaises(LookupError):
            self.catalogue.export_original(self.rid)

    def test_no_automatic_clearance_of_nonpublic_sources(self):
        self.catalogue.set_handling(self.sid, 'restricted', reason='synthetic')
        with self.assertRaisesRegex(ValueError, 'handling_relaxation_requires_review'):
            self.catalogue.set_handling(self.sid, 'public', reason='not a clearance')
        self.assertEqual(self.index.search('alpha'), [])

    def test_explicit_withdrawal_requires_exact_confirmation(self):
        for confirmation in (None, 'wrong-source'):
            with self.subTest(confirmation=confirmation), self.assertRaisesRegex(ValueError, 'confirmation_required'):
                self.catalogue.remove_source(self.sid, confirm_source_id=confirmation, reason='synthetic')
        self.assertEqual(len(self.index.search('alpha')), 1)

    def test_hold_and_future_retention_block_withdrawal(self):
        import time
        self.catalogue.set_retention(self.sid, retain_until=time.time()+3600, reason='synthetic retention')
        with self.assertRaisesRegex(ValueError, 'retention_active'):
            self.catalogue.remove_source(self.sid, confirm_source_id=self.sid, reason='synthetic')
        self.catalogue.set_retention(self.sid, retain_until=0, legal_hold=True, reason='synthetic hold')
        with self.assertRaisesRegex(ValueError, 'legal_hold'):
            self.catalogue.remove_source(self.sid, confirm_source_id=self.sid, reason='synthetic')
        self.assertEqual(len(self.index.search('alpha')), 1)

    def test_withdrawal_removes_derived_text_not_originals_or_receipts(self):
        self.catalogue.set_retention(self.sid, retain_until=0, reason='synthetic expired retention')
        result = self.catalogue.remove_source(self.sid, confirm_source_id=self.sid, reason='synthetic withdrawal')
        self.assertEqual(result['derivatives_deleted'], 1)
        self.assertTrue(result['originals_retained'])
        self.assertEqual(self.catalogue.db.execute('SELECT COUNT(*) FROM derivatives').fetchone()[0], 0)
        self.assertEqual(self.catalogue.db.execute('SELECT COUNT(*) FROM text_index').fetchone()[0], 0)
        self.assertEqual(self.catalogue.db.execute('SELECT COUNT(*) FROM search_derivative_metadata').fetchone()[0], 0)
        self.assertEqual(self.catalogue.original(self.rid), b'alpha')
        self.assertEqual(len(self.catalogue.change_receipts()), 1)
        with self.assertRaises(LookupError):
            self.catalogue.export_original(self.rid)
        with self.assertRaisesRegex(ValueError, 'source_removed'):
            self.catalogue.register('https://fixture.test/a', b'alpha', handling='public')
        with self.assertRaisesRegex(ValueError, 'source_removed'):
            self.index.add(extract(b'alpha'), self.sid, self.rid)

    def test_withdrawing_one_duplicate_preserves_the_other_source(self):
        second = self.catalogue.register('https://fixture.test/b', b'alpha', handling='public')
        self.index.add(extract(b'alpha'), second['source_id'], second['revision_id'])
        self.catalogue.remove_source(self.sid, confirm_source_id=self.sid, reason='synthetic')
        hits = self.index.search('alpha')
        self.assertEqual([h['source_id'] for h in hits], [second['source_id']])
        self.assertEqual(self.catalogue.original(second['revision_id']), b'alpha')

    def test_policy_history_is_immutable_and_failure_rolls_back_restriction(self):
        self.catalogue.set_handling(self.sid, 'restricted', reason='synthetic review')
        history = self.catalogue.handling_history(self.sid)
        self.assertEqual(history[-1]['action'], 'handling')
        self.assertEqual(history[-1]['reason'], 'synthetic review')
        with self.assertRaises(sqlite3.IntegrityError), self.catalogue.db:
            self.catalogue.db.execute("UPDATE handling_events SET reason='changed'")
        self.catalogue.db.execute("CREATE TRIGGER synthetic_policy_failure BEFORE INSERT ON handling_events "
                                  "BEGIN SELECT RAISE(ABORT,'synthetic_failure'); END")
        self.catalogue.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.catalogue.flag_source(self.sid, 'newflag', reason='synthetic failure')
        self.assertEqual(self.catalogue.db.execute('SELECT flags_json FROM source_metadata').fetchone()[0], '[]')
        self.assertEqual(self.catalogue.db.execute('SELECT handling FROM documents').fetchone()[0], 'restricted')

    def test_validation_rejects_missing_reasons_and_invalid_retention(self):
        with self.assertRaises(ValueError):
            self.catalogue.set_handling(self.sid, 'restricted', reason='')
        for deadline in (-1, True, float('nan'), float('inf'), 'tomorrow'):
            with self.subTest(deadline=deadline), self.assertRaises(ValueError):
                self.catalogue.set_retention(self.sid, retain_until=deadline, reason='synthetic')
        with self.assertRaises(LookupError):
            self.catalogue.flag_source('missing', 'review', reason='synthetic')
        self.assertEqual(len(self.index.search('alpha')), 1)

    def test_retention_updates_preserve_omitted_hold_and_deadline(self):
        import time
        deadline = time.time()+3600
        self.catalogue.set_retention(self.sid, retain_until=deadline, legal_hold=True, reason='synthetic')
        self.catalogue.set_retention(self.sid, retain_until=deadline+100, reason='date correction only')
        self.assertEqual(self.catalogue.db.execute('SELECT legal_hold FROM source_policy').fetchone()[0], 1)
        self.catalogue.set_retention(self.sid, legal_hold=False, reason='explicit synthetic hold release')
        self.assertEqual(self.catalogue.db.execute('SELECT retain_until FROM source_policy').fetchone()[0], deadline+100)

    def test_withdrawal_audit_failure_rolls_back_text_cache_and_tombstone(self):
        self.assertTrue(callable(getattr(self.catalogue, 'remove_source', None)))
        self.catalogue.db.execute("CREATE TRIGGER synthetic_withdrawal_failure BEFORE INSERT ON handling_events "
                                  "WHEN NEW.action='withdrawal' BEGIN SELECT RAISE(ABORT,'synthetic_failure'); END")
        self.catalogue.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.catalogue.remove_source(self.sid, confirm_source_id=self.sid, reason='synthetic')
        self.assertEqual(len(self.index.search('alpha')), 1)
        self.assertEqual(self.catalogue.db.execute('SELECT removed FROM source_policy').fetchone()[0], 0)

    def test_removed_sources_reject_direct_derivative_insertions(self):
        self.catalogue.remove_source(self.sid, confirm_source_id=self.sid, reason='synthetic')
        with self.assertRaises(sqlite3.IntegrityError), self.catalogue.db:
            self.catalogue.db.execute('INSERT INTO derivatives VALUES (?,?,?,?,?,?,?,?,?)',
                ('stale-writer', self.rid, 'text', 'synthetic', hashlib.sha256(b'alpha').hexdigest(),
                 'complete', 'alpha', '[]', 'public'))

    def test_reopen_quarantines_legacy_flagged_sources_and_derivatives(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'legacy.sqlite'
            old = Catalogue(path)
            r = old.register('https://fixture.test/legacy', b'alpha', handling='public')
            index = SearchIndex(old)
            index.add(extract(b'alpha'), r['source_id'], r['revision_id'])
            old.db.execute('DROP TRIGGER quarantine_flag_update')
            old.db.execute("UPDATE source_metadata SET flags_json='[\"legacy-review\"]'")
            old.db.commit()
            old.close()
            current = Catalogue(path)
            self.addCleanup(current.close)
            self.assertEqual(current.db.execute('SELECT handling FROM documents').fetchone()[0], 'quarantined')
            self.assertEqual(current.db.execute('SELECT handling FROM derivatives').fetchone()[0], 'quarantined')
            self.assertEqual(SearchIndex(current).search('alpha'), [])

    def test_derivative_add_serializes_policy_reads_with_insert_and_retry(self):
        for retry in (False, True):
            with self.subTest(retry=retry), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'concurrent-policy.sqlite'
                primary, other = Catalogue(path), Catalogue(path)
                try:
                    index = SearchIndex(primary)
                    r = primary.register('https://fixture.test/a', b'alpha', handling='public')
                    if retry:
                        index.add(extract(b'alpha'), r['source_id'], r['revision_id'])
                    other.db.execute('PRAGMA busy_timeout=0')
                    outcomes = []

                    def interleave(statement):
                        if (statement.startswith(('INSERT INTO derivatives', 'UPDATE derivatives SET handling='))
                                and not outcomes):
                            outcomes.append('attempted')
                            try:
                                other.set_handling(r['source_id'], 'restricted', reason='synthetic concurrent restriction')
                                outcomes.append('applied')
                            except sqlite3.OperationalError:
                                outcomes.append('locked')

                    primary.db.set_trace_callback(interleave)
                    did = index.add(extract(b'alpha'), r['source_id'], r['revision_id'])
                    primary.db.set_trace_callback(None)
                    self.assertEqual(outcomes, ['attempted', 'locked'])
                    other.set_handling(r['source_id'], 'restricted', reason='synthetic subsequent restriction')
                    self.assertEqual(primary.db.execute(
                        'SELECT handling FROM derivatives WHERE derivative_id=?', (did,)).fetchone()[0], 'restricted')
                    self.assertEqual(index.search('alpha'), [])
                finally:
                    primary.close()
                    other.close()


class RevisionChangeTests(unittest.TestCase):
    def setUp(self):
        self.catalogue = Catalogue()
        self.addCleanup(self.catalogue.close)

    def register(self, content=b'alpha', url='https://fixture.test/a.txt', **options):
        return self.catalogue.register(url, content, **options)

    def test_movement_and_byte_changes_are_independent_receipt_fields(self):
        first = self.register(acquired=1)
        moved = self.register(url='https://fixture.test/b.txt', moved_from='https://fixture.test/a.txt', acquired=2)
        changed = self.register(b'beta', 'https://fixture.test/c.txt',
                                moved_from='https://fixture.test/b.txt', acquired=3)
        receipts = self.catalogue.change_receipts(first['source_id'])
        self.assertEqual(len(receipts), 3)
        self.assertIsNone(receipts[0]['content_changed'])
        self.assertFalse(receipts[1]['content_changed'])
        self.assertTrue(receipts[1]['moved'])
        self.assertTrue(receipts[2]['content_changed'])
        self.assertTrue(receipts[2]['moved'])
        self.assertEqual(receipts[1]['before_revision_id'], first['revision_id'])
        self.assertEqual(receipts[2]['after_revision_id'], changed['revision_id'])
        self.assertEqual(receipts[1]['receipt_id'], moved['receipt_id'])
        self.assertEqual(self.catalogue.original(first['revision_id']), b'alpha')

    def test_duplicate_bytes_do_not_invent_a_move_or_merge_sources(self):
        first = self.register()
        second = self.register(url='https://fixture.test/b.txt')
        comparison = self.catalogue.compare_revisions(first['revision_id'], second['revision_id'])
        self.assertEqual(comparison['relation'], 'duplicate_content')
        self.assertFalse(comparison['same_source'])
        self.assertTrue(comparison['same_bytes'])
        self.assertIsNone(comparison['content_changed'])
        receipt = self.catalogue.change_receipt(second['receipt_id'])
        self.assertFalse(receipt['moved'])
        self.assertTrue(receipt['duplicate_content'])
        self.assertIsNone(receipt['before_revision_id'])
        self.assertEqual([r['revision_id'] for r in self.catalogue.duplicates(first['revision_id'])],
                         [second['revision_id']])

    def test_comparison_distinguishes_changed_unchanged_and_unrelated(self):
        first = self.register(acquired=1)
        changed = self.register(b'beta', acquired=2)
        unrelated = self.register(b'gamma', 'https://fixture.test/other.txt')
        same = self.catalogue.compare_revisions(first['revision_id'], first['revision_id'])
        self.assertEqual(same['relation'], 'same_revision')
        different = self.catalogue.compare_revisions(first['revision_id'], changed['revision_id'])
        self.assertEqual(different['relation'], 'content_changed')
        self.assertTrue(different['content_changed'])
        self.assertEqual(different['size_delta'], -1)
        other = self.catalogue.compare_revisions(first['revision_id'], unrelated['revision_id'])
        self.assertEqual(other['relation'], 'distinct_sources')
        self.assertIsNone(other['content_changed'])
        with self.assertRaises(LookupError):
            self.catalogue.compare_revisions(first['revision_id'], 'missing')
        with self.assertRaises(LookupError):
            self.catalogue.duplicates('missing')

    def test_backdated_capture_receipt_does_not_claim_current_head_advanced(self):
        current = self.register(b'current', acquired=10)
        late = self.register(b'old capture', acquired=1)
        receipt = self.catalogue.change_receipt(late['receipt_id'])
        self.assertFalse(receipt['advances_url_head'])
        self.assertEqual(receipt['comparison_basis'], 'url_head_before_registration')
        self.assertEqual(receipt['before_revision_id'], current['revision_id'])
        self.assertEqual(self.catalogue.db.execute('SELECT revision_id FROM urls').fetchone()[0], current['revision_id'])

    def test_repeat_acquisitions_have_distinct_immutable_receipts(self):
        first, second = self.register(), self.register()
        self.assertNotEqual(first['receipt_id'], second['receipt_id'])
        self.assertEqual(len(self.catalogue.change_receipts()), 2)
        receipt = self.catalogue.change_receipt(first['receipt_id'])
        for sql, values in (
                ('UPDATE change_receipts SET payload_json=? WHERE receipt_id=?', ('{}', first['receipt_id'])),
                ('DELETE FROM change_receipts WHERE receipt_id=?', (first['receipt_id'],)),
                ('INSERT OR REPLACE INTO change_receipts VALUES (?,?,?,?)',
                 (first['receipt_id'], receipt['acquisition_id'], first['source_id'], '{}')),
                ('INSERT OR REPLACE INTO change_receipts VALUES (?,?,?,?)',
                 ('different-id', receipt['acquisition_id'], first['source_id'], '{}'))):
            with self.subTest(sql=sql), self.assertRaises(sqlite3.IntegrityError), self.catalogue.db:
                self.catalogue.db.execute(sql, values)
        self.assertEqual(self.catalogue.change_receipt(first['receipt_id']), receipt)

    def test_receipt_failure_rolls_back_acquisition_and_original_changes(self):
        first = self.register()
        self.assertIn('receipt_id', first)
        self.catalogue.db.execute("CREATE TRIGGER synthetic_receipt_failure BEFORE INSERT ON change_receipts "
                                  "BEGIN SELECT RAISE(ABORT,'synthetic_failure'); END")
        self.catalogue.db.commit()
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'synthetic_failure'):
            self.register(b'beta')
        self.assertEqual(len(self.catalogue.acquisitions('https://fixture.test/a.txt')), 1)
        self.assertEqual(len(self.catalogue.revisions('https://fixture.test/a.txt')), 1)
        self.assertEqual(self.catalogue.db.execute('SELECT COUNT(*) FROM content_objects').fetchone()[0], 1)
        self.assertEqual(len(self.catalogue.change_receipts()), 1)

    def test_reopen_preserves_receipts_without_fabricating_legacy_events(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'catalogue.sqlite'
            original = Catalogue(path)
            result = original.register('https://fixture.test/a.txt', b'alpha')
            self.assertIn('receipt_id', result)
            receipt = original.change_receipt(result['receipt_id'])
            original.close()
            reopened = Catalogue(path)
            self.addCleanup(reopened.close)
            self.assertEqual(reopened.change_receipts(), [receipt])
            with self.assertRaises(LookupError):
                reopened.change_receipt('missing')

    def test_legacy_acquisitions_are_not_backfilled_with_invented_move_receipts(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'legacy.sqlite'
            previous = Catalogue(path)
            original = previous.register('https://fixture.test/old.txt', b'alpha')
            # Synthetic pre-T7 schema: retain original acquisition, omit the new table.
            previous.db.execute('DROP TABLE change_receipts')
            previous.db.commit()
            previous.close()
            current = Catalogue(path)
            self.addCleanup(current.close)
            self.assertEqual(current.change_receipts(), [])
            self.assertEqual(current.original(original['revision_id']), b'alpha')
            moved = current.register('https://fixture.test/new.txt', b'alpha',
                                     moved_from='https://fixture.test/old.txt')
            self.assertEqual(len(current.change_receipts()), 1)
            self.assertTrue(current.change_receipt(moved['receipt_id'])['moved'])

    def test_receipt_fingerprint_detects_malformed_stored_payload(self):
        result = self.register()
        # Simulate damaged storage in an isolated synthetic database.
        self.catalogue.db.execute('DROP TRIGGER immutable_change_receipts_UPDATE')
        self.catalogue.db.execute('UPDATE change_receipts SET payload_json=?', ('[]',))
        with self.assertRaisesRegex(ValueError, '^change_receipt_integrity$'):
            self.catalogue.change_receipt(result['receipt_id'])

    def test_reverted_bytes_reuse_revision_but_keep_the_new_change_event(self):
        first = self.register(acquired=1)
        changed = self.register(b'beta', acquired=2)
        reverted = self.register(acquired=3)
        self.assertEqual(first['revision_id'], reverted['revision_id'])
        receipt = self.catalogue.change_receipt(reverted['receipt_id'])
        self.assertEqual(receipt['before_revision_id'], changed['revision_id'])
        self.assertTrue(receipt['content_changed'])
        self.assertFalse(receipt['moved'])
        self.assertEqual(len(self.catalogue.change_receipts()), 3)

    def test_repeated_move_declaration_compares_existing_destination_head(self):
        self.register(acquired=1)
        target = self.register(b'beta', 'https://fixture.test/b.txt',
                               moved_from='https://fixture.test/a.txt', acquired=2)
        repeated = self.register(b'beta', 'https://fixture.test/b.txt',
                                 moved_from='https://fixture.test/a.txt', acquired=3)
        receipt = self.catalogue.change_receipt(repeated['receipt_id'])
        self.assertEqual(receipt['before_revision_id'], target['revision_id'])
        self.assertFalse(receipt['content_changed'])
        self.assertTrue(receipt['moved'])

    def test_receipt_baseline_is_read_under_the_registration_write_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'concurrent.sqlite'
            primary, other = Catalogue(path), Catalogue(path)
            self.addCleanup(primary.close)
            self.addCleanup(other.close)
            first = primary.register('https://fixture.test/a', b'alpha', acquired=1)
            other.db.execute('PRAGMA busy_timeout=0')
            outcomes = []

            def interleave(statement):
                if statement.startswith('SELECT content FROM content_objects') and not outcomes:
                    outcomes.append('attempted')
                    try:
                        other.register('https://fixture.test/a', b'gamma', acquired=2)
                        outcomes.append('wrote')
                    except sqlite3.OperationalError:
                        outcomes.append('locked')

            # A real second connection attempts a write after the first has read
            # its baseline, before its first INSERT. It must not overtake it.
            primary.db.set_trace_callback(interleave)
            latest = primary.register('https://fixture.test/a', b'beta', acquired=3)
            primary.db.set_trace_callback(None)
            self.assertEqual(outcomes, ['attempted', 'locked'])
            self.assertEqual(primary.change_receipt(latest['receipt_id'])['before_revision_id'], first['revision_id'])


class DerivativeComparisonTests(unittest.TestCase):
    def setUp(self):
        self.catalogue = Catalogue()
        self.addCleanup(self.catalogue.close)
        self.index = SearchIndex(self.catalogue)

    def add(self, content, mime='text/plain', **changes):
        revision = self.catalogue.register('https://fixture.test/a', content, handling='public')
        result = dict(extract(content, mime), **changes)
        return self.index.add(result, revision['source_id'], revision['revision_id'])

    def test_text_diff_is_separate_from_original_byte_comparison(self):
        first, second = self.add(b'alpha\nold'), self.add(b'alpha\nnew')
        result = self.index.compare(first, second)
        self.assertFalse(result['same_output'])
        self.assertTrue(result['original_content_changed'])
        self.assertEqual(result['diff_status'], 'complete')
        self.assertIn('-old\n+new', result['text_diff'])
        same_text = self.add(b'<p>alpha</p>', 'text/html')
        other_bytes = self.add(b'<div>alpha</div>', 'text/html')
        equal = self.index.compare(same_text, other_bytes)
        self.assertTrue(equal['same_output'])
        self.assertTrue(equal['original_content_changed'])
        self.assertEqual(equal['text_diff'], '')

    def test_comparison_checks_current_handling_and_preserves_partial_warning(self):
        first = self.add(b'alpha')
        second = self.add(b'alpha\xff')
        result = self.index.compare(first, second)
        self.assertEqual(result['after']['status'], 'partial')
        self.assertEqual(result['after']['reason'], 'invalid_encoding')
        self.catalogue.db.execute("UPDATE documents SET handling='restricted'")
        with self.assertRaisesRegex(LookupError, 'derivative_unavailable'):
            self.index.compare(first, second)

    def test_large_text_diffs_are_explicitly_not_generated(self):
        first = self.add(b'alpha' * 7000)
        second = self.add(b'beta' * 9000)
        result = self.index.compare(first, second)
        self.assertEqual(result['diff_status'], 'not_generated_size_limit')
        self.assertIsNone(result['text_diff'])
        self.assertFalse(result['same_output'])

    def test_line_ending_changes_are_not_hidden_in_an_empty_diff(self):
        for old, new in ((b'alpha', b'alpha\n'), (b'alpha\r\n', b'alpha\n')):
            with self.subTest(old=old):
                result = self.index.compare(self.add(old), self.add(new))
                self.assertFalse(result['same_output'])
                self.assertEqual(result['diff_status'], 'complete')
                self.assertIn('-alpha', result['text_diff'])
                self.assertIn('+alpha', result['text_diff'])


class RevisionSearchTests(unittest.TestCase):
    def setUp(self):
        self.catalogue = Catalogue()
        self.addCleanup(self.catalogue.close)
        self.index = SearchIndex(self.catalogue)

    def register(self, text=b'alpha evidence', url='https://fixture.test/a.txt', **options):
        options.setdefault('handling', 'public')
        return self.catalogue.register(url, text, **options)

    def add(self, revision, result=None, **options):
        if result is None:
            result = extract(self.catalogue.original(revision['revision_id']))
        return self.index.add(result, revision['source_id'], revision['revision_id'], **options)

    def test_repeat_indexing_returns_one_result(self):
        revision = self.register()
        first = self.add(revision, handling='public')
        self.assertEqual(self.add(revision, handling='public'), first)
        self.assertEqual(len(self.index.search('alpha')), 1)

    def test_equal_output_retains_distinct_sources_and_revisions(self):
        first = self.register(b'<p>alpha</p>', 'https://fixture.test/a.html')
        second = self.register(b'<div>alpha</div>', 'https://fixture.test/a.html')
        third = self.register(b'<p>alpha</p>', 'https://fixture.test/b.html')
        ids = [self.add(revision, extract(self.catalogue.original(revision['revision_id']), 'text/html'),
                        handling='public') for revision in (first, second, third)]
        self.assertEqual(len(set(ids)), 3)
        hits = self.index.search('alpha', source_id=first['source_id'])
        self.assertEqual({h['revision_id'] for h in hits}, {first['revision_id'], second['revision_id']})
        hits = self.index.search('alpha', revision_id=second['revision_id'])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]['source_id'], first['source_id'])
        self.assertEqual(self.catalogue.original(hits[0]['original']['revision_id']), b'<div>alpha</div>')
        self.assertEqual(hits[0]['original']['url'], 'https://fixture.test/a.html')
        self.assertEqual(hits[0]['original']['content_hash'], second['content_hash'])

    def test_source_revision_mismatch_is_rejected_without_mutation(self):
        first, second = self.register(), self.register(url='https://fixture.test/b.txt')
        with self.assertRaisesRegex(ValueError, 'source_revision_mismatch'):
            self.index.add(extract(b'alpha'), first['source_id'], second['revision_id'], handling='public')
        self.assertEqual(self.index.search('alpha'), [])
        self.assertEqual(self.catalogue.db.execute('SELECT COUNT(*) FROM derivatives').fetchone()[0], 0)

    def test_ineligible_statuses_and_empty_outputs_are_not_searchable(self):
        revision = self.register()
        for status in ('pending', 'failed', 'encrypted', 'unsupported'):
            value = dict(extract(b'alpha'), status=status)
            self.add(revision, value, handling='public')
        self.assertEqual(self.index.search('alpha'), [])
        self.add(revision, extract(b''), handling='public')
        self.assertEqual(self.index.search('alpha'), [])

    def test_partial_result_retains_citations_and_coverage(self):
        revision = self.register(b'alpha\xff')
        result = extract(b'alpha\xff')
        result['coverage'] = {'scope': 'fixture', 'omitted_pages': [2]}
        self.add(revision, result)
        hit = self.index.search('alpha')[0]
        self.assertEqual(hit['status'], 'partial')
        self.assertEqual(hit['reason'], 'invalid_encoding')
        self.assertEqual(hit['locators'], [{'paragraph': 1, 'start': 0, 'end': 6}])
        self.assertEqual(hit['coverage'], {'scope': 'fixture', 'omitted_pages': [2]})
        self.assertTrue(hit['original']['available'])

    def test_handling_cannot_be_elevated_by_the_caller(self):
        for handling in ('unknown', 'restricted', 'quarantined', 'revoked'):
            with self.subTest(handling=handling):
                revision = self.register(url='https://fixture.test/' + handling, handling=handling)
                self.add(revision, handling='public')
                self.assertEqual(self.index.search('alpha'), [])

    def test_policy_changes_hide_previously_indexed_results(self):
        revision = self.register()
        did = self.add(revision, handling='public')
        self.assertEqual(len(self.index.search('alpha')), 1)
        self.catalogue.db.execute("UPDATE documents SET handling='restricted'")
        self.assertEqual(self.index.search('alpha'), [])
        self.catalogue.db.execute("UPDATE documents SET handling='public'")
        self.catalogue.db.execute("UPDATE source_metadata SET flags_json='[\"quarantine\"]'")
        self.assertEqual(self.index.search('alpha'), [])
        self.catalogue.db.execute("UPDATE source_metadata SET flags_json='[]'")
        self.catalogue.db.execute("UPDATE derivatives SET handling='restricted' WHERE derivative_id=?", (did,))
        self.assertEqual(self.index.search('alpha'), [])

    def test_restricted_reacquisition_is_honoured_at_query_time(self):
        revision = self.register()
        self.add(revision, handling='public')
        self.register(handling='restricted')
        self.assertEqual(self.index.search('alpha'), [])

    def test_output_hash_and_ocr_source_hash_are_verified(self):
        revision = self.register()
        for change in ({'output_hash': 'incorrect'}, {'source_hash': 'incorrect'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.add(revision, dict(extract(b'alpha'), **change), handling='public')
        self.assertEqual(self.index.search('alpha'), [])

    def test_ocr_kind_confidence_and_engine_provenance_survive_storage(self):
        revision = self.register()
        result = dict(extract(b'alpha'), kind='ocr', derivative_id='ocr:fixture',
                      source_hash=revision['content_hash'], confidence=92,
                      engines={'tesseract': 'synthetic-1', 'traineddata_sha256': 'fixture-model'},
                      locators=[{'page': 2, 'start': 0, 'end': 5, 'confidence': 92}],
                      coverage={'scope': 'fixture', 'total_pages': 2})
        self.add(revision, result)
        hit = self.index.search('alpha', kind='ocr')[0]
        self.assertEqual(hit['kind'], 'ocr')
        self.assertEqual(hit['confidence'], 92)
        self.assertEqual(hit['extraction_derivative_id'], 'ocr:fixture')
        self.assertEqual(hit['engines'], result['engines'])
        self.assertEqual(hit['locators'][0]['page'], 2)
        self.assertEqual(self.index.search('alpha', kind='text'), [])

    def test_legacy_fts_rows_are_not_trusted_or_duplicated(self):
        revision = self.register()
        self.catalogue.db.execute('INSERT INTO text_index VALUES (?,?,?,?)',
                                  ('orphan', 'alpha', revision['source_id'], revision['revision_id']))
        self.assertEqual(self.index.search('alpha'), [])
        self.add(revision)
        reopened = SearchIndex(self.catalogue)
        self.assertEqual(len(reopened.search('alpha')), 1)

    def test_filters_and_query_bounds(self):
        self.add(self.register())
        for query in ('', ' ', None, 'x' * 4097, '"'):
            with self.subTest(query=str(query)[:20]), self.assertRaises(ValueError):
                self.index.search(query)
        for limit in (0, -1, True, 101, '20'):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.index.search('alpha', limit=limit)
        self.assertEqual(self.index.search('alpha', source_id="' OR 1=1 --"), [])
        self.assertEqual(self.index.search('alpha', revision_id='absent'), [])

    def test_disk_reopen_keeps_history_and_requires_legacy_revalidation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'catalogue.sqlite'
            catalogue = Catalogue(path)
            revision = catalogue.register('https://fixture.test/a.txt', b'alpha', handling='public')
            catalogue.db.execute('INSERT INTO derivatives VALUES (?,?,?,?,?,?,?,?,?)',
                                 ('legacy', revision['revision_id'], 'text', 'old-1',
                                  hashlib.sha256(b'alpha').hexdigest(), 'complete',
                                  'alpha', "[{'paragraph': 1}]", 'public'))
            catalogue.db.execute('CREATE VIRTUAL TABLE text_index USING fts5('
                                 'derivative_id UNINDEXED,text,source_id UNINDEXED,revision_id UNINDEXED)')
            catalogue.db.execute('INSERT INTO text_index VALUES (?,?,?,?)',
                                 ('legacy', 'alpha', revision['source_id'], revision['revision_id']))
            catalogue.db.commit()
            index = SearchIndex(catalogue)
            self.assertEqual(index.search('alpha'), [])
            did = index.add(extract(b'alpha'), revision['source_id'], revision['revision_id'])
            catalogue.close()
            reopened = Catalogue(path)
            self.addCleanup(reopened.close)
            hits = SearchIndex(reopened).search('alpha')
            self.assertEqual([h['derivative_id'] for h in hits], [did])
            self.assertEqual(reopened.original(hits[0]['revision_id']), b'alpha')
            self.assertEqual(reopened.db.execute(
                "SELECT extractor,locator_json FROM derivatives WHERE derivative_id='legacy'").fetchone(),
                ('old-1', "[{'paragraph': 1}]"))

    def test_legacy_derivative_restriction_survives_new_extraction_identity(self):
        revision = self.register()
        result = extract(b'alpha evidence')
        self.catalogue.db.execute('INSERT INTO derivatives VALUES (?,?,?,?,?,?,?,?,?)',
                                 (result['output_hash'], revision['revision_id'], 'text', 'old-1',
                                  result['output_hash'], 'complete', result['text'], '[]', 'restricted'))
        did = self.add(revision, handling='public')
        self.assertEqual(self.index.search('alpha'), [])
        self.assertEqual(self.catalogue.db.execute(
            'SELECT handling FROM derivatives WHERE derivative_id=?', (did,)).fetchone()[0], 'restricted')

    def test_corrupt_stored_metadata_fails_with_content_free_error(self):
        revision = self.register()
        self.add(revision)
        for invalid in ('[]', '{broken', '{"kind":"text"}'):
            self.catalogue.db.execute('UPDATE search_derivative_metadata SET extraction_json=?', (invalid,))
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, '^invalid_search_metadata$'):
                self.index.search('alpha')


class OCRIntegrationTests(unittest.TestCase):
    def test_missing_ocr_remains_a_separate_content_free_derivative(self):
        original = b'synthetic source'
        baseline = extract(original)
        result = document_extract.extract_ocr(
            original, 'image/png', optional_python='/absent/python',
            tesseract_path='/absent/tesseract', tessdata_dir='/absent/tessdata')
        self.assertEqual(result['kind'], 'ocr')
        self.assertEqual(result['status'], 'unsupported')
        self.assertIsNone(result['confidence'])
        self.assertEqual(result['text'], '')
        self.assertEqual(result['locators'], [])
        self.assertNotIn('synthetic source', json.dumps(result))
        self.assertTrue(result['derivative_id'].startswith('ocr:'))
        self.assertEqual(extract(original), baseline)
        self.assertEqual(original, b'synthetic source')

    def test_ocr_identity_includes_source_and_extractor_provenance(self):
        from unittest.mock import patch
        worker_result = dict(kind='ocr', status='complete', reason='', text='Alpha',
                             output_hash=hashlib.sha256(b'Alpha').hexdigest(),
                             source_hash='source-a', extractor='tesseract/5.5.3',
                             engines={'model_hash': 'model-a'}, confidence=90, locators=[])
        with patch('optional.document_processing.ocr.extract_ocr', return_value=worker_result):
            first = document_extract.extract_ocr(b'a', 'image/png')
        other = dict(worker_result, source_hash='source-b')
        with patch('optional.document_processing.ocr.extract_ocr', return_value=other):
            second = document_extract.extract_ocr(b'b', 'image/png')
        self.assertNotEqual(first['derivative_id'], second['derivative_id'])
        other_model = dict(worker_result, engines={'model_hash': 'model-b'})
        with patch('optional.document_processing.ocr.extract_ocr', return_value=other_model):
            third = document_extract.extract_ocr(b'a', 'image/png')
        self.assertNotEqual(first['derivative_id'], third['derivative_id'])
        self.assertEqual(first['text'], 'Alpha')
        self.assertEqual(first['locator_space'], 'derivative_text')

    def test_public_api_with_real_engine(self):
        from optional.document_processing.test_ocr import RealOCR, PYTHON, ENGINE, MODELS
        if not all((PYTHON, ENGINE, MODELS)):
            self.skipTest('explicit OCR test configuration required')
        fixture = RealOCR()
        content = fixture.encoded(fixture.fixture('ALPHA'))
        result = document_extract.extract_ocr(
            content, 'IMAGE/PNG; charset=binary', optional_python=PYTHON,
            tesseract_path=ENGINE, tessdata_dir=MODELS)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['kind'], 'ocr')
        self.assertIn('ALPHA', result['text'])
        self.assertTrue(result['derivative_id'].startswith('ocr:'))
        self.assertEqual(result['source_hash'], hashlib.sha256(content).hexdigest())
        self.assertTrue(0 <= result['confidence'] <= 100)
        catalogue = Catalogue()
        self.addCleanup(catalogue.close)
        revision = catalogue.register('https://fixture.test/scanned.png', content, handling='public')
        index = SearchIndex(catalogue)
        index.add(result, revision['source_id'], revision['revision_id'])
        hit = index.search('ALPHA', kind='ocr')[0]
        self.assertEqual(hit['locators'], result['locators'])
        self.assertEqual(hit['confidence'], result['confidence'])
        self.assertEqual(hit['engines'], result['engines'])
        self.assertEqual(hit['extraction_derivative_id'], result['derivative_id'])
        self.assertEqual(catalogue.original(hit['original']['revision_id']), content)


if __name__ == '__main__':
    unittest.main()
