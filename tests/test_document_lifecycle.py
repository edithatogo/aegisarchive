"""Synthetic acceptance cases for the document lifecycle contract."""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from portable.document_catalogue import Catalogue
from portable.document_extract import extract


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


if __name__ == '__main__':
    unittest.main()
