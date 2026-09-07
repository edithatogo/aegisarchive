import copy
import unittest

from cli.crawl_rules import validate_rules, evaluate_rules, discover_sitemap, scope_hosts


class RuleSchemaTests(unittest.TestCase):
    def test_order_and_independent_actions_are_preserved(self):
        config = {'version': 1, 'rules': [
            {'id': 'files', 'match': {'path_prefix': '/files/'},
             'decision': {'download': True, 'traverse': False}},
            {'id': 'rest', 'match': {}, 'decision': {'discover': False}},
        ]}
        original = copy.deepcopy(config)
        self.assertEqual(validate_rules(config), config)
        self.assertEqual(config, original)

    def test_unsafe_or_ambiguous_schema_is_rejected(self):
        invalid = [
            {'version': True, 'rules': []},
            {'version': 1, 'rules': [], 'extra': 1},
            {'version': 1, 'rules': [{'id': 'x', 'match': {'regex': '(a+)+$'}, 'decision': {'download': True}}]},
            {'version': 1, 'rules': [{'id': 'x', 'match': {'max_depth': True}, 'decision': {'download': True}}]},
            {'version': 1, 'rules': [{'id': 'x', 'match': {}, 'decision': {'download': 1}}]},
            {'version': 1, 'rules': [{'id': 'x', 'match': {'host': 'example.test.evil/'}, 'decision': {'download': True}}]},
        ]
        for config in invalid:
            with self.subTest(config=config), self.assertRaises(ValueError):
                validate_rules(config)

    def test_duplicate_ids_and_unbounded_inputs_are_rejected(self):
        rule = {'id': 'x', 'match': {}, 'decision': {'download': True}}
        for rules in ([rule, rule], [dict(rule, id=str(i)) for i in range(101)]):
            with self.assertRaises(ValueError):
                validate_rules({'version': 1, 'rules': rules})
        rule['match'] = {'path_prefix': '/' + 'x' * 2048}
        with self.assertRaises(ValueError):
            validate_rules({'version': 1, 'rules': [rule]})


class RuleEvaluationTests(unittest.TestCase):
    resource = {'url': 'https://example.test/files/a.pdf', 'kind': 'asset', 'depth': 2}

    def test_first_matching_rule_and_scope_ceiling(self):
        config = {'version': 1, 'rules': [
            {'id': 'files', 'match': {'host': 'example.test', 'path_prefix': '/files/'},
             'decision': {'traverse': False}},
            {'id': 'rest', 'match': {}, 'decision': {'discover': False}}]}
        result = evaluate_rules(config, self.resource, in_scope=True)
        self.assertEqual(result, dict(discover=True, download=True, traverse=False,
                                     rule_id='files', state='decided', missing=[]))
        denied = evaluate_rules(config, self.resource, in_scope=False)
        self.assertEqual(denied['state'], 'out_of_scope')
        self.assertFalse(denied['download'])

    def test_unknown_metadata_does_not_skip_a_potential_deny(self):
        config = {'version': 1, 'rules': [
            {'id': 'large', 'match': {'min_bytes': 10, 'mime': 'application/pdf'},
             'decision': {'download': False}}]}
        result = evaluate_rules(config, self.resource, in_scope=True)
        self.assertEqual(result['state'], 'needs_metadata')
        self.assertEqual(result['missing'], ['bytes', 'mime'])
        self.assertFalse(result['download'])
        result = evaluate_rules(config, dict(self.resource, bytes=10, mime='application/pdf'), in_scope=True)
        self.assertFalse(result['download'])
        self.assertFalse(result['traverse'])
        result = evaluate_rules(config, dict(self.resource, bytes=9), in_scope=True)
        self.assertTrue(result['download'])

    def test_exact_host_and_invalid_resources(self):
        config = {'version': 1, 'rules': [
            {'id': 'only', 'match': {'host': 'example.test'}, 'decision': {'download': False}}]}
        result = evaluate_rules(config, dict(self.resource, url='https://example.test.evil/a'), in_scope=True)
        self.assertTrue(result['download'])
        for change in ({'url': 'file:///tmp/a'}, {'url': 'https://user:secret@example.test/'}, {'depth': True}):
            with self.assertRaises(ValueError):
                evaluate_rules(config, dict(self.resource, **change), in_scope=True)


class SitemapTests(unittest.TestCase):
    def test_scope_aliases_are_explicit_and_bounded(self):
        self.assertEqual(scope_hosts(['example.test'], {'example.test': ['assets.test']}), ['assets.test', 'example.test'])
        with self.assertRaises(ValueError):
            scope_hosts(['example.test'], {'unapproved.test': ['assets.test']})

    def test_sitemap_scope_duplicates_and_cycles(self):
        xml = '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.test/a?x=1&amp;y=2</loc></url><url><loc>https://example.test/a?x=1&amp;y=2</loc></url><url><loc>https://outside.test/a</loc></url></urlset>'
        result = discover_sitemap(xml, 'https://example.test/map.xml', ['example.test'])
        self.assertEqual(result['pages'], ['https://example.test/a?x=1&y=2'])
        self.assertEqual(result['excluded'], ['https://outside.test/a'])
        index = '<sitemapindex><sitemap><loc>https://example.test/map.xml</loc></sitemap><sitemap><loc>https://example.test/next.xml</loc></sitemap></sitemapindex>'
        self.assertEqual(discover_sitemap(index, 'https://example.test/map.xml', ['example.test'])['sitemaps'], ['https://example.test/next.xml'])
        self.assertEqual(discover_sitemap(index, 'https://example.test/map.xml', ['example.test'], ['https://example.test/map.xml'])['sitemaps'], [])

    def test_sitemap_rejects_entity_expansion_and_limits(self):
        for xml in ('<!DOCTYPE x [<!ENTITY x "bad">]><urlset/>', '<urlset><url></urlset>', '<urlset x="1"/>', '<urlset><url><loc><![CDATA[/a]]></loc></url></urlset>', '<urlset><url><loc>&#1;</loc></url></urlset>', '<urlset>' + ' ' * 262144 + '</urlset>'):
            with self.assertRaises(ValueError):
                discover_sitemap(xml, 'https://example.test/map.xml', ['example.test'])

    def test_numeric_intervals_and_resource_kinds(self):
        rule = {'id': 'asset', 'match': {'kind': 'asset', 'mime': 'image/png',
                'min_bytes': 0, 'max_bytes': 4096, 'max_depth': 4},
                'decision': {'traverse': False}}
        validate_rules({'version': 1, 'rules': [rule]})
        rule['match']['min_bytes'] = 4097
        with self.assertRaises(ValueError):
            validate_rules({'version': 1, 'rules': [rule]})
