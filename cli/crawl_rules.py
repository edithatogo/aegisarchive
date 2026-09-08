"""Bounded, versioned rules. First matching rule wins; no regular expressions.

This module is deterministic and performs no network requests. Rules refine an
existing scope decision; they never grant access outside the caller's scope.
"""
import copy
import re
from urllib.parse import urlsplit, urljoin
import xml.etree.ElementTree as ET

MAX_RULES = 100
MAX_TEXT = 2048
MAX_INTEGER = 2 ** 53 - 1
ACTIONS = {'discover', 'download', 'traverse'}
TEXT_FIELDS = {'url_prefix', 'path_prefix', 'host', 'mime', 'kind'}
NUMBER_FIELDS = {'min_depth', 'max_depth', 'min_bytes', 'max_bytes'}


def validate_rules(config):
    """Validate a JSON rule configuration without modifying its input."""
    if (not isinstance(config, dict) or set(config) != {'version', 'rules'}
            or type(config['version']) is not int or config['version'] != 1
            or not isinstance(config['rules'], list) or len(config['rules']) > MAX_RULES):
        raise ValueError('Expected version 1 and at most 100 rules')
    identifiers = set()
    for rule in config['rules']:
        if not isinstance(rule, dict) or set(rule) != {'id', 'match', 'decision'}:
            raise ValueError('Rule requires id, match and decision')
        identifier = rule['id']
        if (not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', identifier)
                or identifier in identifiers):
            raise ValueError('Invalid or duplicate rule id')
        identifiers.add(identifier)
        match, decision = rule['match'], rule['decision']
        if not isinstance(match, dict) or set(match) - TEXT_FIELDS - NUMBER_FIELDS:
            raise ValueError('Unknown matcher; regular expressions are unsupported')
        if (not isinstance(decision, dict) or not decision or set(decision) - ACTIONS
                or any(type(value) is not bool for value in decision.values())):
            raise ValueError('Decisions must be boolean actions')
        for key, value in match.items():
            if key in NUMBER_FIELDS:
                if type(value) is not int or not 0 <= value <= MAX_INTEGER:
                    raise ValueError('Matcher bounds must be safe nonnegative integers')
            elif (not isinstance(value, str) or not value or len(value) > MAX_TEXT
                  or any(ord(char) < 32 for char in value)):
                raise ValueError('Invalid matcher text')
        for unit in ('depth', 'bytes'):
            if match.get('min_' + unit, 0) > match.get('max_' + unit, MAX_INTEGER):
                raise ValueError('Reversed matcher interval')
        if 'kind' in match and match['kind'] not in ('page', 'asset', 'sitemap'):
            raise ValueError('Unknown resource kind')
        if 'host' in match and not re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)*', match['host']):
            raise ValueError('Host must be an exact lowercase hostname')
        if 'path_prefix' in match and not match['path_prefix'].startswith('/'):
            raise ValueError('Path prefix must be absolute')
        if 'url_prefix' in match:
            parsed = urlsplit(match['url_prefix'])
            if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError('URL prefix must be an HTTP URL without credentials')
    return copy.deepcopy(config)


def evaluate_rules(config, resource, *, in_scope):
    """Return first-match decisions; unknown response metadata holds downloads.

    A caller may acquire response headers for ``needs_metadata``, subject to its
    ordinary scope/politeness controls, but must reevaluate before reading bytes.
    """
    config = validate_rules(config)
    if type(in_scope) is not bool or not isinstance(resource, dict):
        raise ValueError('Explicit scope and resource required')
    url = resource.get('url')
    if not isinstance(url, str) or len(url) > 8192 or any(ord(c) < 32 for c in url):
        raise ValueError('Invalid resource URL')
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Invalid resource URL')
    if resource.get('kind') not in ('page', 'asset', 'sitemap'):
        raise ValueError('Invalid resource kind')
    for key in ('depth', 'bytes'):
        value = resource.get(key)
        if value is not None and (type(value) is not int or not 0 <= value <= MAX_INTEGER):
            raise ValueError('Invalid resource count')
    if resource.get('mime') is not None and (not isinstance(resource['mime'], str) or len(resource['mime']) > MAX_TEXT):
        raise ValueError('Invalid resource MIME')
    result = dict(discover=in_scope, download=in_scope, traverse=in_scope,
                  rule_id=None, state='decided' if in_scope else 'out_of_scope', missing=[])
    if not in_scope:
        return result
    for rule in config['rules']:
        missing, mismatch = set(), False
        for key, expected in rule['match'].items():
            if key in NUMBER_FIELDS:
                direction, field = key.split('_', 1)
                value = resource.get(field)
                if value is None:
                    missing.add(field)
                elif (direction == 'min' and value < expected) or (direction == 'max' and value > expected):
                    mismatch = True
            elif key == 'mime':
                value = resource.get('mime')
                if value is None:
                    missing.add('mime')
                elif value.split(';')[0].strip().lower() != expected.lower():
                    mismatch = True
            else:
                value = {'url_prefix': url, 'path_prefix': parsed.path or '/',
                         'host': parsed.hostname.lower(), 'kind': resource['kind']}[key]
                if not (value.startswith(expected) if key.endswith('_prefix') else value == expected):
                    mismatch = True
        if mismatch:
            continue
        result['rule_id'] = rule['id']
        if missing:
            result.update(download=False, traverse=False, state='needs_metadata', missing=sorted(missing))
            return result
        result.update(rule['decision'])
        result['download'] = result['discover'] and result['download']
        result['traverse'] = result['download'] and result['traverse']
        return result
    return result


def scope_hosts(allowed_hosts, aliases=None):
    """Expand only operator-declared aliases, never redirect-derived hosts."""
    aliases = {} if aliases is None else aliases
    valid = lambda value: isinstance(value, str) and len(value) <= 253 and re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)*', value)
    if (not isinstance(allowed_hosts, list) or len(allowed_hosts) > 32
            or not all(valid(value) for value in allowed_hosts)
            or not isinstance(aliases, dict) or len(aliases) > 16):
        raise ValueError('Invalid host scope')
    hosts = set(allowed_hosts)
    for primary, extra in aliases.items():
        if primary not in allowed_hosts or not isinstance(extra, list) or len(extra) > 16 or not all(valid(value) for value in extra):
            raise ValueError('Invalid explicit alias')
        hosts.update(extra)
    if len(hosts) > 32:
        raise ValueError('Too many hosts')
    return sorted(hosts)


def discover_sitemap(text, source_url, allowed_hosts, visited=None):
    """Parse a bounded unprefixed sitemap subset, without fetching anything.

    Supports urlset/sitemapindex and the standard default namespace. Extensions,
    DTDs, CDATA, attributes other than the default namespace and nested location markup are rejected rather than partly inferred.
    The caller retains visited sitemap URLs across fetches to terminate cycles.
    """
    hosts = scope_hosts(allowed_hosts)
    if not isinstance(text, str) or len(text.encode('utf-8')) > 262144:
        raise ValueError('Sitemap byte limit')
    if re.search(r'<!DOCTYPE|<!ENTITY|<!\[CDATA\[|</?[A-Za-z_][\w.-]*:', text, re.I):
        raise ValueError('Unsupported sitemap XML declaration or prefix')
    seen = set(visited or [])
    result = {'pages': [], 'sitemaps': [], 'excluded': []}
    source = urlsplit(source_url)
    if source.scheme not in ('http', 'https') or source.hostname not in hosts or source.username or source.password:
        raise ValueError('Sitemap source outside scope')
    if source_url in seen:
        return result
    seen.add(source_url)
    try:
        # Input is a size-bounded Unicode string; all DTD/entity declarations
        # are rejected above before parsing, so entities cannot be defined.
        # Keep the pre-parser rejection regression test when changing this guard.
        root = ET.fromstring(text)  # nosec B314 - guarded, DTD-free sitemap subset
    except ET.ParseError as error:
        raise ValueError('Malformed sitemap XML') from error
    local = lambda tag: tag.removeprefix('{http://www.sitemaps.org/schemas/sitemap/0.9}')
    structure = {'urlset': {'url'}, 'sitemapindex': {'sitemap'},
                 'url': {'loc', 'lastmod', 'changefreq', 'priority'}, 'sitemap': {'loc', 'lastmod'},
                 'loc': set(), 'lastmod': set(), 'changefreq': set(), 'priority': set()}
    root_name = local(root.tag)
    if root_name not in ('urlset', 'sitemapindex'):
        raise ValueError('Unsupported sitemap root')
    nodes = list(root.iter())
    if len(nodes) > 6001:
        raise ValueError('Sitemap node limit')
    for node in nodes:
        name = local(node.tag)
        if node.attrib or name not in structure or any(local(child.tag) not in structure[name] for child in node):
            raise ValueError('Unsupported sitemap structure')
    locations = [node.text.strip() for node in nodes if local(node.tag) == 'loc' and node.text and node.text.strip()]
    if len(locations) > 1000:
        raise ValueError('Sitemap location limit')
    for location in locations:
        if len(location) > 8192:
            raise ValueError('Sitemap URL limit')
        url = urljoin(source_url, location)
        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or parsed.hostname not in hosts or parsed.username or parsed.password:
            if url not in result['excluded']:
                result['excluded'].append(url)
        elif url not in seen:
            result['sitemaps' if root_name == 'sitemapindex' else 'pages'].append(url)
            seen.add(url)
    return result
