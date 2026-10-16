import copy
import contextlib
from email.message import Message
import gzip
import http.client
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import urllib.parse

from cli.crawl_rules import validate_rules, evaluate_rules, discover_sitemap, scope_hosts
from cli import aegis_cli


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

    def test_unsafe_xml_is_rejected_before_parser_invocation(self):
        payloads = [
            '<!DOCTYPE urlset SYSTEM "https://outside.test/dtd"><urlset/>',
            '<!DOCTYPE urlset [<!ENTITY x SYSTEM "file:///private.txt">]><urlset>&x;</urlset>',
            '<!DOCTYPE urlset [<!ENTITY a "x"><!ENTITY b "&a;&a;">]><urlset>&b;</urlset>',
            '<!ENTITY x "value"><urlset/>',
            '<urlset>' + ' ' * 262144 + '</urlset>',
        ]
        with patch('cli.crawl_rules.ET.fromstring') as parser:
            for payload in payloads:
                with self.subTest(payload=payload[:80]), self.assertRaises(ValueError):
                    discover_sitemap(payload, 'https://example.test/map.xml', ['example.test'])
            parser.assert_not_called()

    def test_numeric_intervals_and_resource_kinds(self):
        rule = {'id': 'asset', 'match': {'kind': 'asset', 'mime': 'image/png',
                'min_bytes': 0, 'max_bytes': 4096, 'max_depth': 4},
                'decision': {'traverse': False}}
        validate_rules({'version': 1, 'rules': [rule]})
        rule['match']['min_bytes'] = 4097
        with self.assertRaises(ValueError):
            validate_rules({'version': 1, 'rules': [rule]})

    def test_sitemap_cycle_identity_ignores_default_ports_and_fragments(self):
        xml = '<sitemapindex>' + ''.join('<sitemap><loc>' + url + '</loc></sitemap>' for url in [
            'https://EXAMPLE.test:443/map.xml#self', 'https://example.test/next.xml#one',
            'https://example.test:443/next.xml#two', 'https://example.test/Next.xml?q=1']) + '</sitemapindex>'
        expected = ['https://example.test/next.xml', 'https://example.test/Next.xml?q=1']
        self.assertEqual(discover_sitemap(xml, 'https://example.test/map.xml', ['example.test'])['sitemaps'], expected)
        self.assertEqual(discover_sitemap(xml, 'https://example.test/map.xml', ['example.test'], ['https://example.test:443/map.xml#old'])['sitemaps'], [])


class CliRuleIntegrationTests(unittest.TestCase):
    """Real CLI frontier/WARC/receipts with synthetic header/body transport spies."""

    def crawl(self, routes, *, rules=None, seeds=None, read_errors=None, **target_options):
        requests, reads, closed = [], [], []

        class Response(io.BytesIO):
            def __init__(self, url, body, headers, status):
                super().__init__(body)
                self.url, self.status, self.headers = url, status, headers

            def read(self, size=-1):
                reads.append((self.url, size))
                if read_errors and self.url in read_errors:
                    raise read_errors[self.url]
                return super().read(size)

            def close(self):
                closed.append(self.url)
                super().close()

        def open_request(request, timeout):
            url = request.full_url
            requests.append(url)
            self.assertEqual(request.get_method(), 'GET')
            if urllib.parse.urlsplit(url).path == '/robots.txt' and url not in routes:
                headers = Message()
                raise urllib.error.HTTPError(url, 404, 'synthetic missing robots', headers, io.BytesIO())
            self.assertIn(url, routes, 'unexpected request outside the synthetic graph')
            body, extra, status = routes[url]
            headers = Message()
            for key, value in extra:
                headers[key] = value
            response = Response(url, body, headers, status)
            if status >= 300:
                raise urllib.error.HTTPError(url, status, 'synthetic status', headers, response)
            return response

        target = dict(allowed_domains=['example.test'], max_depth=5, max_pages=100,
                      seed_urls={'tier_1_core': seeds if seeds is not None else ['https://example.test/']},
                      crawl_rules={'version': 1, 'rules': rules or []})
        target.update(target_options)
        with tempfile.TemporaryDirectory() as folder:
            profile = Path(folder) / 'profile.json'
            profile.write_text(json.dumps({'target': target, 'politeness': {
                'min_delay_ms': 1, 'max_delay_ms': 1, 'max_requests_per_minute': 100000,
                'burst_limit': 100}}))
            with patch.object(sys, 'argv', ['aegis_cli', '--profile', str(profile), '--output-dir', folder]), \
                    patch.object(aegis_cli.urllib.request, 'build_opener') as opener, \
                    contextlib.redirect_stdout(io.StringIO()), \
                    patch.object(aegis_cli.PolitenessEngine, 'acquire_permission',
                                 autospec=True, return_value={'aborted': False}) as permission:
                opener.return_value.open.side_effect = open_request
                aegis_cli.main()
            receipt = json.loads(next(Path(folder).glob('*.coverage.json')).read_text())
            warc = next(Path(folder).glob('*.warc')).read_bytes()
            cdx = next(Path(folder).glob('*.cdx')).read_text().splitlines()[1:]
            self.assertEqual(receipt['archives']['warc']['bytes'], next(Path(folder).glob('*.warc')).stat().st_size)
            self.assertEqual(receipt['archives']['cdx']['bytes'], next(Path(folder).glob('*.cdx')).stat().st_size)
            # Every synthetic request, including robots and sitemap discovery,
            # still passes through the ordinary permission gate.
            self.assertEqual([call.args[1] for call in permission.call_args_list], requests)
        return dict(requests=requests, reads=reads, closed=closed, receipt=receipt,
                    warc=warc, captured=[line.split()[2] for line in cdx])

    @staticmethod
    def route(body, mime='text/html', *headers, status=200):
        return body, [('Content-Type', mime), *headers], status

    def test_known_assets_are_excluded_before_request(self):
        root = 'https://example.test/'
        result = self.crawl({root: self.route(b'<img src="/image"><a href="/page">page</a>'),
                             root+'image': self.route(b'image', 'image/png'),
                             root+'page': self.route(b'page', 'text/plain')}, rules=[
            {'id': 'no-assets', 'match': {'kind': 'asset'}, 'decision': {'download': False}}])
        self.assertNotIn(root+'image', result['requests'])
        self.assertEqual(result['captured'], [root, root+'page'])
        excluded = next(r for r in result['receipt']['resources'] if r['url']==root+'image')
        self.assertEqual(excluded['reason'], 'rule:no-assets')

    def test_download_without_traversal_does_not_enqueue_children(self):
        root = 'https://example.test/'
        result = self.crawl({root: self.route(b'<a href="/child">child</a>'),
                             root+'child': self.route(b'child')}, rules=[
            {'id': 'capture-only', 'match': {}, 'decision': {'traverse': False}}])
        self.assertEqual(result['captured'], [root])
        self.assertEqual(result['requests'], [root+'robots.txt', root])

    def test_headers_resolve_mime_and_size_before_permitted_body_read(self):
        root = 'https://example.test/'
        result = self.crawl({root: self.route(b'alpha', 'text/plain; charset=utf-8', ('Content-Length','5'))}, rules=[
            {'id': 'small-text', 'match': {'mime': 'text/plain', 'max_bytes': 5},
             'decision': {'download': True}},
            {'id': 'deny', 'match': {}, 'decision': {'download': False}}])
        self.assertEqual(result['captured'], [root])
        self.assertEqual([url for url, size in result['reads']], [root])

    def test_header_denial_never_reads_response_body(self):
        root = 'https://example.test/'
        result = self.crawl({root: self.route(b'PRIVATE_BODY', 'application/pdf')}, rules=[
            {'id': 'no-pdf', 'match': {'mime': 'application/pdf'}, 'decision': {'download': False}}])
        self.assertIn(root, result['requests'])
        self.assertEqual(result['reads'], [])
        self.assertIn(root, result['closed'])
        self.assertNotIn(b'PRIVATE_BODY', result['warc'])

    def test_untrustworthy_lengths_fail_closed_without_body_reads(self):
        root = 'https://example.test/'
        for headers in ([], [('Content-Length','bad')], [('Content-Length','-1')],
                        [('Content-Length','5'), ('Content-Length','6')],
                        [('Content-Length','5'), ('Content-Encoding','gzip')],
                        [('Content-Length','5'), ('Transfer-Encoding','chunked')]):
            with self.subTest(headers=headers):
                result = self.crawl({root: self.route(b'alpha', 'text/plain', *headers)}, rules=[
                    {'id': 'size', 'match': {'max_bytes': 10}, 'decision': {'download': True}}])
                self.assertIn(root, result['requests'])
                self.assertEqual(result['reads'], [])
                self.assertEqual(result['captured'], [])

    def test_size_denial_and_first_match_precedence(self):
        root = 'https://example.test/'
        result = self.crawl({root: self.route(b'alpha', 'text/plain', ('Content-Length','5'))}, rules=[
            {'id': 'large', 'match': {'min_bytes': 5}, 'decision': {'download': False}},
            {'id': 'rest', 'match': {}, 'decision': {'download': True}}])
        self.assertIn(root, result['requests'])
        self.assertEqual(result['reads'], [])
        self.assertEqual(result['captured'], [])

    def test_alias_scope_and_cyclic_sitemaps_use_normal_capture_queue(self):
        root = 'https://example.test/'
        alias = 'https://assets.test/'
        routes = {root+'map.xml': self.route(b'<sitemapindex><sitemap><loc>/next.xml</loc></sitemap><sitemap><loc>/map.xml#self</loc></sitemap></sitemapindex>', 'application/xml'),
                  root+'next.xml': self.route(b'<sitemapindex><sitemap><loc>/map.xml</loc></sitemap><sitemap><loc>https://assets.test/pages.xml</loc></sitemap></sitemapindex>', 'application/xml'),
                  alias+'pages.xml': self.route(b'<urlset><url><loc>/page</loc></url><url><loc>https://outside.test/never</loc></url></urlset>', 'application/xml'),
                  alias+'page': self.route(b'page')}
        result = self.crawl(routes, seeds=[], domain_aliases={'example.test':['assets.test']},
                            sitemap_seeds=[root+'map.xml'])
        self.assertEqual(result['captured'], list(routes))
        self.assertEqual(result['receipt']['scope_hosts'], ['assets.test', 'example.test'])
        self.assertEqual(len(result['captured']), len(set(result['captured'])))
        self.assertNotIn('https://outside.test/never', result['requests'])
        for url in routes:
            self.assertEqual(result['requests'].count(url), 1)

    def test_sitemap_body_is_bounded_and_not_parsed_when_oversized(self):
        root = 'https://example.test/'
        result = self.crawl({root+'map.xml': self.route(b'<urlset>'+b' '*262144+b'</urlset>', 'application/xml')},
                            seeds=[], sitemap_seeds=[root+'map.xml'])
        self.assertEqual(result['reads'], [(root+'map.xml', 262145)])
        self.assertEqual(result['captured'], [])
        self.assertTrue(result['receipt']['limitations'])

    def test_query_policy_and_fragment_identity(self):
        root = 'https://example.test/'
        for policy, expected in (('strip_tracking',root+'?q=1'),
                                 ('preserve',root+'?q=1&utm_source=x'), ('drop',root)):
            with self.subTest(policy=policy):
                result = self.crawl({expected: self.route(b'page')}, seeds=[root+'?utm_source=x&q=1#one', root+'?utm_source=x&q=1#two'],
                                    query_policy=policy)
                self.assertEqual(result['captured'], [expected])

    def test_sitemap_and_alias_configuration_bounds_fail_before_network(self):
        for config in ({'sitemap_seeds':['https://example.test/map.xml']*33},
                       {'domain_aliases':{'outside.test':['assets.test']}}, {'query_policy':'invalid'}):
            with self.subTest(config=config), self.assertRaises(ValueError):
                self.crawl({}, seeds=[], **config)

    def test_legacy_path_patterns_use_bounded_literal_alternatives(self):
        root = 'https://example.test/'
        result = self.crawl({root: self.route(b'<a href="/LOGOUT">logout</a><a href="/signin">signin</a><a href="/keep">keep</a>'),
                             root+'keep': self.route(b'keep')}, path_blacklist_regex='/logout|/signin')
        self.assertEqual(result['captured'], [root, root+'keep'])
        for value in ('(a+)+$', '/x.*', '/a||/b', '/a'+'x'*2048, 42):
            for key in ('path_blacklist_regex', 'path_whitelist_regex'):
                with self.subTest(key=key, value=str(value)[:30]), self.assertRaises(ValueError):
                    self.crawl({}, seeds=[], **{key:value})

    def test_redirect_rules_are_rechecked_before_body_and_do_not_grant_scope(self):
        root = 'https://example.test/'
        result = self.crawl({root: self.route(b'redirect', 'text/html', ('Location','https://outside.test/no'), status=302)})
        self.assertEqual(result['captured'], [root])
        self.assertNotIn('https://outside.test/no', result['requests'])
        denied = self.crawl({root: self.route(b'PRIVATE_REDIRECT', 'application/pdf', ('Location','/child'), status=302)}, rules=[
            {'id':'no-pdf', 'match':{'mime':'application/pdf'}, 'decision':{'download':False}}])
        self.assertEqual(denied['reads'], [])
        self.assertEqual(denied['captured'], [])

    def test_sitemap_robots_denial_and_max_pages_are_honoured(self):
        root = 'https://example.test/'
        blocked = self.crawl({root+'robots.txt':self.route(b'', status=403),
                              root+'map.xml':self.route(b'<urlset/>', 'application/xml')},
                             seeds=[], sitemap_seeds=[root+'map.xml'])
        self.assertEqual(blocked['requests'], [root+'robots.txt'])
        self.assertEqual(blocked['captured'], [])
        bounded = self.crawl({root+'map.xml':self.route(b'<urlset><url><loc>/page</loc></url></urlset>', 'application/xml'),
                              root+'page':self.route(b'page')}, seeds=[], sitemap_seeds=[root+'map.xml'], max_pages=1)
        self.assertEqual(bounded['captured'], [root+'map.xml'])
        self.assertEqual(bounded['receipt']['counts']['pending'], 1)

    def test_encoded_sitemap_expansion_is_bounded(self):
        root = 'https://example.test/'
        result = self.crawl({root+'map.xml':self.route(gzip.compress(b'<urlset>'+b' '*262144+b'</urlset>'),
                              'application/xml', ('Content-Encoding','gzip'))},
                            seeds=[], sitemap_seeds=[root+'map.xml'])
        self.assertEqual(result['captured'], [])
        self.assertTrue(all(size==262145 for url,size in result['reads']))
        self.assertTrue(result['receipt']['limitations'] or result['receipt']['counts']['failed'])

    def test_actual_body_size_cannot_bypass_declared_size_rule(self):
        root = 'https://example.test/'
        result = self.crawl({root:self.route(b'alpha', 'text/plain', ('Content-Length','1'))}, rules=[
            {'id':'large', 'match':{'min_bytes':5}, 'decision':{'download':False}}])
        self.assertEqual(result['captured'], [])
        self.assertNotIn(b'alpha', result['warc'])

    def test_bad_encoded_sitemap_redirect_is_failed_without_losing_receipt(self):
        root = 'https://example.test/'
        for body in (b'bad gzip', gzip.compress(b'x'*262145)):
            with self.subTest(encoded_bytes=len(body)):
                result = self.crawl({root+'map.xml':self.route(body, 'application/xml',
                                      ('Content-Encoding','gzip'), ('Location','/other.xml'), status=302)},
                                    seeds=[], sitemap_seeds=[root+'map.xml'])
                self.assertEqual(result['captured'], [])
                self.assertEqual(result['receipt']['counts']['failed'], 1)
                self.assertTrue(all(url in result['closed'] for url,size in result['reads']))

    def test_receipt_retains_decisions_metadata_and_duplicate_discovery_edges(self):
        root = 'https://example.test/'
        result = self.crawl({root:self.route(b'<a href="/a">a</a><a href="/b">b</a>'),
                             root+'a':self.route(b'<a href="/b">b</a>'),
                             root+'b':self.route(b'page', 'text/plain', ('Content-Length','4'))})
        item = next(r for r in result['receipt']['resources'] if r['url']==root+'b')
        self.assertEqual(item['parentUrl'], root)
        self.assertEqual(item['mime'], 'text/plain')
        self.assertEqual(item['declared_bytes'], 4)
        self.assertEqual(item['decision']['state'], 'decided')
        self.assertIn('rule_id', item)
        edges = {(e['source'],e['target']) for e in result['receipt']['link_edges']}
        self.assertEqual(edges, {(root,root+'a'), (root,root+'b'), (root+'a',root+'b')})

    def test_link_edge_limit_is_bounded_and_reported_once(self):
        root = 'https://example.test/'
        links = ''.join('<a href="/p'+str(i)+'">p</a>' for i in range(10002)).encode()
        result = self.crawl({root:self.route(links)}, max_pages=1)
        self.assertEqual(len(result['receipt']['link_edges']), 10000)
        self.assertEqual(sum(r['reason']=='graph_edge_limit' for r in result['receipt']['limitations']), 1)

    def test_conflicting_content_types_fail_closed_before_body(self):
        root = 'https://example.test/'
        for first, last in (('text/plain','application/pdf'), ('application/pdf','text/plain')):
            with self.subTest(first=first):
                result = self.crawl({root:self.route(b'PRIVATE_BODY', first, ('Content-Type',last))}, rules=[
                    {'id':'no-pdf', 'match':{'mime':'application/pdf'}, 'decision':{'download':False}}])
                self.assertEqual(result['reads'], [])
                self.assertEqual(result['captured'], [])
                self.assertNotIn(b'PRIVATE_BODY', result['warc'])
                item = next(r for r in result['receipt']['resources'] if r['url']==root)
                self.assertIsNone(item['mime'])
                self.assertEqual(item['decision']['state'], 'needs_metadata')

    def test_incomplete_normal_redirect_and_robots_reads_preserve_failure_receipt(self):
        root = 'https://example.test/'
        for status, robots in ((200,False), (302,False), (200,True)):
            with self.subTest(status=status, robots=robots):
                broken = root+'robots.txt' if robots else root
                result = self.crawl({root:self.route(b'partial', status=status),
                                     root+'robots.txt':self.route(b'partial')},
                                    read_errors={broken:http.client.IncompleteRead(b'partial', 10)})
                self.assertEqual(result['captured'], [])
                if robots:
                    self.assertEqual(result['receipt']['counts']['excluded'], 1)
                else:
                    self.assertEqual(result['receipt']['counts']['failed'], 1)
                self.assertIn(broken, result['closed'])

    def test_redirect_target_is_recorded_without_traversal(self):
        root = 'https://example.test/'
        result = self.crawl({root:self.route(b'redirect', 'text/html',
                              ('Location','/next?utm_source=x&q=1#fragment'), status=302)}, rules=[
            {'id':'capture-only', 'match':{}, 'decision':{'traverse':False}}])
        self.assertEqual(result['captured'], [root])
        resource = next(r for r in result['receipt']['resources'] if r['url']==root)
        self.assertEqual(resource['redirect_to'], root+'next?q=1')
        self.assertEqual(result['receipt']['link_edges'], [])
