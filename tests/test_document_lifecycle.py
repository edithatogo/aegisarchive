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
