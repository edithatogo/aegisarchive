import copy
import contextlib
from email.message import Message
import gzip
import hashlib
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
from cli import crawl_rules as rules_api


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
            receipt_text = next(Path(folder).glob('*.coverage.json')).read_text()
            receipt = json.loads(receipt_text)
            warc = next(Path(folder).glob('*.warc')).read_bytes()
            cdx = next(Path(folder).glob('*.cdx')).read_text().splitlines()[1:]
            self.assertEqual(receipt['archives']['warc']['bytes'], next(Path(folder).glob('*.warc')).stat().st_size)
            self.assertEqual(receipt['archives']['cdx']['bytes'], next(Path(folder).glob('*.cdx')).stat().st_size)
            # Every synthetic request, including robots and sitemap discovery,
            # still passes through the ordinary permission gate.
            self.assertEqual([call.args[1] for call in permission.call_args_list], requests)
        return dict(requests=requests, reads=reads, closed=closed, receipt=receipt, receipt_text=receipt_text,
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


class RulePreviewReportTests(unittest.TestCase):
    def receipt(self):
        digest = hashlib.sha256(b'alpha').hexdigest()
        resources = [
            dict(url='https://example.test/a', state='captured', bytes=5, declared_bytes=5, status=200, sha256=digest),
            dict(url='https://example.test/b', state='captured', bytes=5, declared_bytes=5, status=200, sha256=digest),
            dict(url='https://example.test/r', state='captured', bytes=0, declared_bytes=0, status=302,
                 sha256=hashlib.sha256(b'').hexdigest(), redirect_to='https://example.test/a'),
            dict(url='https://example.test/f', state='failed', status=403, declared_bytes=8, reason='http_error'),
            dict(url='https://example.test/p', state='pending', declared_bytes=None),
            dict(url='https://example.test/u', state='unsupported'),
        ]
        return dict(schema_version=1, discovered=6, resources=resources, complete=False, limitations=[],
                    counts=dict(captured=3, excluded=0, failed=1, pending=1, unsupported=1),
                    archives=dict(warc=dict(sha256='1'*64, bytes=1000), cdx=dict(sha256='2'*64, bytes=100)))

    def test_preview_is_deterministic_scoped_and_never_fetches(self):
        config = {'version':1, 'rules':[
            {'id':'pdf', 'match':{'mime':'application/pdf'}, 'decision':{'download':False}}]}
        resources = [dict(url='https://example.test/a', kind='page', depth=0),
                     dict(url='https://sub.example.test/b', kind='asset', depth=1, mime='application/pdf'),
                     dict(url='https://example.test.evil/c', kind='page', depth=0)]
        original = copy.deepcopy((config, resources))
        with patch('urllib.request.urlopen', side_effect=AssertionError('preview network access')), \
                patch('urllib.request.build_opener', side_effect=AssertionError('preview network access')):
            first = rules_api.preview_rules(config, resources, ['example.test'])
            self.assertEqual(rules_api.preview_rules(config, resources, ['example.test']), first)
        self.assertEqual((config, resources), original)
        self.assertEqual(first[0]['resource'], resources[0])
        self.assertEqual(first[0]['decision']['rule_id'], 'pdf')
        self.assertEqual(first[0]['decision']['state'], 'needs_metadata')
        self.assertFalse(first[1]['decision']['download'])
        self.assertEqual(first[2]['decision']['state'], 'out_of_scope')
        first[0]['resource']['url'] = 'changed'
        self.assertEqual(resources, original[1])

    def test_preview_bounds_and_invalid_resources_raise_without_truncation(self):
        valid = dict(url='https://example.test/', kind='page', depth=0)
        for resources in ([valid]*10001, (valid,), [dict(valid, url='https://user:secret@example.test/')],
                          [dict(valid, depth=True)], [dict(valid, extra=float('nan'))]):
            with self.subTest(shape=type(resources).__name__), self.assertRaises(ValueError):
                rules_api.preview_rules({'version':1,'rules':[]}, resources, ['example.test'])

    def test_report_reconciles_failures_redirects_duplicates_and_storage(self):
        receipt = self.receipt()
        report = rules_api.build_report(receipt)
        self.assertEqual(report['evidence_state'], 'receipt_assertions_not_archive_verification')
        self.assertEqual(report['counts'], receipt['counts'])
        self.assertEqual(report['totals'], dict(discovered=6, **receipt['counts']))
        self.assertEqual(report['storage'], dict(captured_payload_bytes=10, archive_bytes=1100,
                         declared_payload_bytes=18, unknown_estimate_resources=2))
        self.assertEqual([r['url'] for r in report['failures']], ['https://example.test/f'])
        self.assertEqual([r['state'] for r in report['missing_resources']], ['failed','pending','unsupported'])
        self.assertEqual(report['redirects'], [receipt['resources'][2]])
        self.assertEqual(report['duplicates'], [dict(sha256=receipt['resources'][0]['sha256'],
                         urls=['https://example.test/a', 'https://example.test/b'])])
        self.assertEqual(report['receipt'], receipt)
        report['receipt']['resources'][0]['url'] = 'changed'
        self.assertEqual(receipt, self.receipt())

    def test_canonical_unicode_identity_binds_whole_receipt_not_report_order(self):
        receipt = self.receipt()
        receipt['label'] = 'Résumé 💡'
        receipt['extra'] = {'\ue000':'private use', '💡':'astral'}
        def ordered(value):
            if isinstance(value, dict):
                return {key:ordered(value[key]) for key in sorted(value, key=lambda text:text.encode('utf-16-be'))}
            if isinstance(value, list):
                return [ordered(item) for item in value]
            return value
        canonical = json.dumps(ordered(receipt), ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        expected = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
        report = rules_api.build_report(receipt, expected_receipt_sha256=expected)
        self.assertEqual(report['capture_receipt_sha256'], expected)
        reordered = dict(reversed(list(receipt.items())))
        self.assertEqual(rules_api.build_report(reordered)['capture_receipt_sha256'], expected)
        reversed_resources = copy.deepcopy(receipt)
        reversed_resources['resources'].reverse()
        self.assertNotEqual(rules_api.build_report(reversed_resources)['capture_receipt_sha256'], expected)
        self.assertEqual(rules_api.build_report(reversed_resources)['failures'], report['failures'])

    def test_expected_fingerprint_rejects_tampered_content(self):
        receipt = self.receipt()
        digest = rules_api.build_report(receipt)['capture_receipt_sha256']
        receipt['resources'][0]['sha256'] = '3'*64
        with self.assertRaises(ValueError):
            rules_api.build_report(receipt, digest)
        for invalid in ('bad', False, 0, 'A'*64):
            with self.subTest(expected=invalid), self.assertRaises(ValueError):
                rules_api.build_report(self.receipt(), invalid)

    def test_counts_and_discovered_must_match_exactly(self):
        for change in ({'discovered':5}, {'discovered':True},
                       {'counts':dict(captured=2,excluded=0,failed=1,pending=1,unsupported=1)},
                       {'counts':dict(captured=3,excluded=False,failed=1,pending=1,unsupported=1)},
                       {'counts':dict(captured=3,excluded=0,failed=1,pending=1,unsupported=1,other=0)}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                rules_api.build_report(dict(self.receipt(), **change))

    def test_malformed_resource_identity_and_capture_fields_are_rejected(self):
        for change in ({'url':'file:///tmp/x'}, {'url':'https://@example.test/'},
                       {'url':'https://example.test:bad/'}, {'url':'https://example.test/\n'},
                       {'url':'https://example.test/b'}, {'state':'absent'}, {'bytes':True},
                       {'bytes':-1}, {'status':True}, {'status':99}, {'status':600},
                       {'sha256':'not-a-hash'}, {'redirect_to':'https://user:secret@example.test/'}):
            receipt = self.receipt()
            receipt['resources'][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                rules_api.build_report(receipt)

    def test_required_capture_fields_and_archive_hashes_cannot_be_missing(self):
        for key in ('status','bytes','sha256'):
            receipt = self.receipt()
            del receipt['resources'][0][key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                rules_api.build_report(receipt)
        for key in ('warc','cdx'):
            receipt = self.receipt()
            del receipt['archives'][key]['sha256']
            with self.subTest(archive=key), self.assertRaises(ValueError):
                rules_api.build_report(receipt)

    def test_unknown_archive_estimate_is_null_and_never_zero_fabricated(self):
        receipt = self.receipt()
        del receipt['archives']['cdx']['bytes']
        self.assertIsNone(rules_api.build_report(receipt)['storage']['archive_bytes'])
        for value in (-1, True, 1.5, '100'):
            receipt['archives']['cdx']['bytes'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                rules_api.build_report(receipt)

    def test_non_json_cycles_depth_and_oversized_inputs_raise(self):
        cycle = []
        cycle.append(cycle)
        deep = 'leaf'
        for unused in range(21):
            deep = [deep]
        for value in (float('nan'), float('inf'), 1.5, 1.0, 2**53, b'bytes', ('tuple',),
                      {'set'}, {1:'non-string-key'}, cycle, deep, 'x'*(16*1024*1024+1)):
            receipt = self.receipt()
            receipt['extra'] = value
            with self.subTest(value_type=type(value).__name__), self.assertRaises(ValueError):
                rules_api.build_report(receipt)
        for schema in (True, 1.0, 2):
            with self.subTest(schema=schema), self.assertRaises(ValueError):
                rules_api.build_report(dict(self.receipt(), schema_version=schema))

    def test_resource_ceiling_and_aggregate_safe_integer_bounds(self):
        receipt = self.receipt()
        receipt['resources'] = [receipt['resources'][0]]*10001
        with self.assertRaises(ValueError):
            rules_api.build_report(receipt)
        receipt = self.receipt()
        receipt['archives']['warc']['bytes'] = 2**53-1
        with self.assertRaises(ValueError):
            rules_api.build_report(receipt)

    def test_receipt_report_roundtrip_is_network_free_and_input_immutable(self):
        receipt = self.receipt()
        original = copy.deepcopy(receipt)
        with patch('urllib.request.urlopen', side_effect=AssertionError('report network access')), \
                patch('urllib.request.build_opener', side_effect=AssertionError('report network access')):
            first = rules_api.build_report(receipt)
            self.assertEqual(rules_api.build_report(receipt), first)
        self.assertEqual(receipt, original)
        self.assertEqual(json.loads(json.dumps(first, ensure_ascii=False)), first)

    def test_completeness_assertion_cannot_hide_failures_or_limits(self):
        for change in ({'complete':True}, {'complete':1}, {'complete':None}, {'limitations':'bad'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                rules_api.build_report(dict(self.receipt(), **change))
        receipt = self.receipt()
        receipt['resources'] = receipt['resources'][:3]
        receipt.update(discovered=3, complete=True, counts=dict(captured=3,excluded=0,failed=0,pending=0,unsupported=0))
        self.assertTrue(rules_api.build_report(receipt)['receipt']['complete'])
        receipt['limitations'] = ['bounded discovery']
        with self.assertRaises(ValueError):
            rules_api.build_report(receipt)

    def test_optional_url_status_scope_and_graph_fields_are_validated(self):
        for change in ({'parentUrl':'file:///tmp/x'}, {'bytes':-1}, {'bytes':True}, {'status':-1}, {'status':600}):
            receipt = self.receipt()
            receipt['resources'][3].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                rules_api.build_report(receipt)
        for change in ({'scope_hosts':'example.test'}, {'scope_hosts':['bad/host']},
                       {'link_edges':{}}, {'link_edges':[dict(source='https://example.test/', target='file:///tmp/x')]},
                       {'link_edges':[dict(source='https://example.test/', target='https://example.test/a')]*10001}):
            with self.subTest(field=next(iter(change))), self.assertRaises(ValueError):
                rules_api.build_report(dict(self.receipt(), **change))
        for status in (100, 199, 400, 599):
            receipt = self.receipt()
            receipt['resources'][0]['status'] = status
            with self.subTest(captured_status=status), self.assertRaises(ValueError):
                rules_api.build_report(receipt)

    def test_redirect_without_location_is_not_dropped_from_report(self):
        receipt = self.receipt()
        del receipt['resources'][2]['redirect_to']
        self.assertEqual(rules_api.build_report(receipt)['redirects'], [receipt['resources'][2]])

    def test_unpaired_surrogates_are_rejected_in_keys_and_values(self):
        for extra in ({'bad':'\ud800'}, {'\udfff':'bad'}):
            with self.subTest(extra=repr(extra)), self.assertRaises(ValueError):
                rules_api.build_report(dict(self.receipt(), extra=extra))

    def test_derived_url_lists_follow_browser_utf16_order(self):
        receipt = self.receipt()
        receipt['resources'][0]['url'] = 'https://example.test/\ue000'
        receipt['resources'][1]['url'] = 'https://example.test/💡'
        self.assertEqual(rules_api.build_report(receipt)['duplicates'][0]['urls'],
                         ['https://example.test/💡', 'https://example.test/\ue000'])

    def test_source_json_identity_preserves_fractional_robots_metadata(self):
        receipt = self.receipt()
        receipt['robots_provenance'] = {'https://example.test':{'fetched_at':1792134550.125}}
        text = json.dumps(receipt, ensure_ascii=False, indent=2) + '\n'
        digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
        report = rules_api.build_report(receipt, expected_receipt_sha256=digest, receipt_text=text)
        self.assertEqual(report['capture_receipt_sha256'], digest)
        self.assertEqual(report['receipt_identity_format'], 'source_json_utf8')
        self.assertEqual(report['receipt'], receipt)
        self.assertNotEqual(rules_api.build_report(receipt, receipt_text=text+' ')['capture_receipt_sha256'], digest)
        with self.assertRaises(ValueError):
            rules_api.build_report(receipt)
        with self.assertRaises(ValueError):
            rules_api.build_report(receipt, expected_receipt_sha256='0'*64, receipt_text=text)
        self.assertEqual(rules_api.build_report(self.receipt())['receipt_identity_format'], 'canonical_json_utf8')

    def test_source_json_must_match_the_supplied_receipt_without_type_coercion(self):
        receipt = self.receipt()
        text = json.dumps(receipt)
        for other in (dict(receipt, discovered=7), dict(receipt, label='other')):
            with self.subTest(change=set(other)), self.assertRaises(ValueError):
                rules_api.build_report(other, receipt_text=text)
        # Python equality treats False == 0; source matching must not do so.
        altered = copy.deepcopy(receipt)
        altered['counts']['excluded'] = False
        with self.assertRaises(ValueError):
            rules_api.build_report(receipt, receipt_text=json.dumps(altered))
        report = rules_api.build_report(receipt, receipt_text=text.replace('"discovered": 6', '"discovered": 6.0'))
        self.assertEqual(report['counts'], receipt['counts'])

    def test_source_mode_never_relaxes_safe_integer_quantities(self):
        for target, key, value in (('resource','bytes',5.5), ('resource','declared_bytes',1.25),
                                   ('resource','status',200.0), ('archive','bytes',100.5),
                                   ('receipt','discovered',6.0), ('resource','bytes',2**53)):
            receipt = self.receipt()
            destination = receipt['resources'][0] if target=='resource' else receipt['archives']['warc'] if target=='archive' else receipt
            destination[key] = value
            with self.subTest(target=target,key=key,value=value), self.assertRaises(ValueError):
                rules_api.build_report(receipt, receipt_text=json.dumps(receipt))

    def test_source_json_rejects_nonfinite_invalid_unicode_depth_and_size(self):
        for value in (float('nan'), float('inf'), float('-inf')):
            receipt = dict(self.receipt(), metadata=value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                rules_api.build_report(receipt, receipt_text=json.dumps(receipt))
        receipt = dict(self.receipt(), metadata=float('inf'))
        with self.assertRaises(ValueError):
            rules_api.build_report(receipt, receipt_text=json.dumps(receipt).replace('Infinity','1e999'))
        for text in ('{broken', '[]', '\ud800', ' '* (16*1024*1024+1), b'{}'):
            with self.subTest(text_type=type(text).__name__), self.assertRaises(ValueError):
                rules_api.build_report(self.receipt(), receipt_text=text)
        deep = 'leaf'
        for unused in range(21):
            deep = [deep]
        receipt = dict(self.receipt(), extra=deep)
        with self.assertRaises(ValueError):
            rules_api.build_report(receipt, receipt_text=json.dumps(receipt))

    def test_source_json_rejects_duplicate_keys_instead_of_discarding_evidence(self):
        receipt = self.receipt()
        text = json.dumps(receipt)
        text = text.replace('"schema_version": 1', '"schema_version": 2, "schema_version": 1')
        with self.assertRaises(ValueError):
            rules_api.build_report(receipt, receipt_text=text)

    def test_actual_cli_receipt_with_robots_timestamp_reports_without_rewriting(self):
        root = 'https://example.test/'
        capture = CliRuleIntegrationTests().crawl({root:CliRuleIntegrationTests.route(b'page')})
        receipt, text = capture['receipt'], capture['receipt_text']
        self.assertIsInstance(receipt['robots_provenance']['https://example.test']['fetched_at'], float)
        before = copy.deepcopy(receipt)
        report = rules_api.build_report(receipt, receipt_text=text)
        self.assertEqual(report['capture_receipt_sha256'], hashlib.sha256(text.encode('utf-8')).hexdigest())
        self.assertEqual(report['receipt_identity_format'], 'source_json_utf8')
        self.assertEqual(report['counts']['captured'], 1)
        self.assertEqual(receipt, before)

    def test_source_metadata_numbers_remain_within_safe_magnitude(self):
        for value in (2**53, -(2**53), float(2**53), -float(2**53), 1e100):
            receipt = dict(self.receipt(), metadata=value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                rules_api.build_report(receipt, receipt_text=json.dumps(receipt))
        for value in (2**53-1, -(2**53-1), 0.125, -0.125):
            receipt = dict(self.receipt(), metadata=value)
            self.assertEqual(rules_api.build_report(receipt, receipt_text=json.dumps(receipt))['receipt'], receipt)

    def test_source_matching_treats_json_numbers_equally_but_not_booleans(self):
        receipt = dict(self.receipt(), metadata=123)
        text = json.dumps(dict(receipt, metadata=123.0))
        self.assertEqual(rules_api.build_report(receipt, receipt_text=text)['receipt'], receipt)
        with self.assertRaises(ValueError):
            rules_api.build_report(dict(receipt, metadata=True), receipt_text=json.dumps(dict(receipt, metadata=1)))
