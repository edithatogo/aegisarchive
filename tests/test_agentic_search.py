import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from portable.document_catalogue import Catalogue
from portable.document_extract import extract
from portable.document_search import SearchIndex, main


class AgenticSearchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.saved = self.root / 'saved #archive.sqlite'
        with contextlib.closing(Catalogue(self.saved)) as catalogue:
            index = SearchIndex(catalogue)
            for name in ('public', 'private'):
                body = f'<p>Leave approval and archived {name} notes.</p>'.encode()
                record = catalogue.register(f'https://fixture.test/{name}', body, 'text/html', handling='public')
                index.add(extract(body, 'text/html'), record['source_id'], record['revision_id'])
                if name == 'public':
                    self.public = record
                else:
                    catalogue.set_handling(record['source_id'], 'restricted', reason='Fixture restriction')
                    self.private = record
        assets = {}
        for name in ('llama', 'scout'):
            data = f'fixture {name}'.encode()
            (self.root / name).write_bytes(data)
            assets[name] = dict(path=name, sha256=hashlib.sha256(data).hexdigest())
        self.manifest = self.root / 'manifest.json'
        self.manifest.write_text(json.dumps(dict(assets=assets)), encoding='utf-8')

    def search(self, query, *options):
        before = self.saved.read_bytes()
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(main([str(self.saved), query, *options]), 0)
        self.assertEqual(self.saved.read_bytes(), before)
        return json.loads(stdout.getvalue())

    def test_keyword_is_default_and_initial_hits_keep_the_model_idle(self):
        with patch('portable.intelligence.run_tool') as planner:
            ordinary = self.search('leave approval')
            agentic = self.search('leave approval', '--agentic', str(self.manifest))
        planner.assert_not_called()
        self.assertEqual(ordinary['mode'], 'keyword')
        self.assertEqual(agentic['follow_up'], 'not_needed')
        self.assertEqual(ordinary['hits'], agentic['hits'])
        self.assertEqual(len(ordinary['hits']), 1)

    def test_one_offline_rewrite_returns_the_saved_revision_and_honours_filters(self):
        question = 'Who signs off on time away?'
        with patch('portable.intelligence.run_tool', return_value='QUERY: leave approval\n') as planner:
            result = self.search(question, '--agentic', str(self.manifest))
        planner.assert_called_once()
        arguments = planner.call_args.args[1]
        self.assertIn('--offline', arguments)
        prompt = arguments[arguments.index('-p') + 1]
        self.assertIn(question, prompt)
        self.assertNotIn('archived', prompt)
        self.assertEqual(result['mode'], 'agentic')
        self.assertEqual(result['follow_up'], 'searched')
        hit, = result['hits']
        self.assertEqual(hit['original']['revision_id'], self.public['revision_id'])
        self.assertEqual(hit['original']['content_hash'], self.public['content_hash'])
        self.assertTrue(hit['locators'])
        with patch('portable.intelligence.run_tool', return_value='QUERY: leave approval\n'):
            hidden = self.search(question, '--agentic', str(self.manifest),
                                 '--revision-id', self.private['revision_id'])
        self.assertEqual(hidden, dict(mode='agentic', follow_up='searched', hits=[]))

    def test_model_failures_have_an_explicit_empty_outcome(self):
        question = 'Who signs off on time away?'
        missing = self.search(question, '--agentic', str(self.root / 'missing.json'))
        self.assertEqual(missing, dict(mode='agentic', follow_up='model_unavailable', hits=[]))
        with patch('portable.intelligence.run_tool', return_value='QUERY: leave\nQUERY: approval\n'):
            invalid = self.search(question, '--agentic', str(self.manifest))
        self.assertEqual(invalid, dict(mode='agentic', follow_up='invalid_rewrite', hits=[]))
        self.manifest.write_text('[' * 4000 + ']' * 4000, encoding='utf-8')
        malformed = self.search(question, '--agentic', str(self.manifest))
        self.assertEqual(malformed, missing)

    def test_missing_or_unindexed_catalogue_is_not_created_or_indexed(self):
        path = self.root / 'unindexed.sqlite'
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            self.assertEqual(main([str(path), 'leave']), 2)
            self.assertFalse(path.exists())
            Catalogue(path).close()
            before = path.read_bytes()
            self.assertEqual(main([str(path), 'leave']), 2)
        self.assertEqual(path.read_bytes(), before)
        self.assertIn('indexed saved catalogue', errors.getvalue())
