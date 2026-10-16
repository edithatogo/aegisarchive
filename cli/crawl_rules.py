"""Bounded, versioned rules. First matching rule wins; no regular expressions.

This module is deterministic and performs no network requests. Rules refine an
existing scope decision; they never grant access outside the caller's scope.
"""
import copy
import hashlib
import json
import math
import re
from urllib.parse import urlsplit, urljoin, urlunsplit
import xml.etree.ElementTree as ET

MAX_RULES = 100
MAX_TEXT = 2048
MAX_INTEGER = 2 ** 53 - 1
ACTIONS = {'discover', 'download', 'traverse'}
TEXT_FIELDS = {'url_prefix', 'path_prefix', 'host', 'mime', 'kind'}
NUMBER_FIELDS = {'min_depth', 'max_depth', 'min_bytes', 'max_bytes'}
MAX_CANDIDATES = 10000
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_JSON_DEPTH = 20
MAX_JSON_NODES = 1000000
RESOURCE_STATES = ('captured', 'excluded', 'failed', 'pending', 'unsupported')


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
    return _evaluate_validated_rules(config, resource, in_scope=in_scope)


def _evaluate_validated_rules(config, resource, *, in_scope):
    """Evaluate already validated configuration (also used by bounded preview)."""
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


def _validate_json(value, *, allow_floats=False):
    """Validate a bounded JSON tree without serializing or coercing metadata.

    Default canonical mode requires native safe integers. Source-text mode may
    retain finite fractional metadata; report quantity fields are checked later.
    """
    active = set()
    nodes = 0
    minimum_bytes = 0

    def visit(item, depth):
        nonlocal nodes, minimum_bytes
        nodes += 1
        minimum_bytes += 1
        if minimum_bytes > MAX_JSON_BYTES:
            raise ValueError('JSON byte limit')
        if depth > MAX_JSON_DEPTH or nodes > MAX_JSON_NODES:
            raise ValueError('JSON structural limit')
        kind = type(item)
        if item is None or kind is bool:
            return
        if kind is int:
            if not -MAX_INTEGER <= item <= MAX_INTEGER:
                raise ValueError('JSON numbers must be safe integers')
            return
        if kind is float and allow_floats:
            if not math.isfinite(item) or abs(item) > MAX_INTEGER:
                raise ValueError('JSON number exceeds finite safe magnitude')
            return
        if kind is str:
            if len(item) > MAX_JSON_BYTES:
                raise ValueError('JSON byte limit')
            try:
                minimum_bytes += len(item.encode('utf-8'))
            except UnicodeError:
                raise ValueError('Invalid JSON Unicode') from None
            if minimum_bytes > MAX_JSON_BYTES:
                raise ValueError('JSON byte limit')
            return
        if kind not in (dict, list):
            raise ValueError('Unsupported JSON value')
        identity = id(item)
        if identity in active:
            raise ValueError('JSON cycle')
        if len(item) > MAX_JSON_NODES:
            raise ValueError('JSON structural limit')
        active.add(identity)
        if kind is dict:
            for key, child in item.items():
                if type(key) is not str:
                    raise ValueError('JSON object keys must be strings')
                visit(key, depth + 1)
                visit(child, depth + 1)
        else:
            for child in item:
                visit(child, depth + 1)
        active.remove(identity)

    visit(value, 0)


def _canonical_json(value):
    """Canonical UTF-8 JSON with UTF-16 key order and safe integers only."""
    _validate_json(value)

    def ordered(item):
        if type(item) is dict:
            return {key: ordered(item[key]) for key in sorted(item, key=lambda text: text.encode('utf-16-be'))}
        if type(item) is list:
            return [ordered(child) for child in item]
        return item

    chunks, total = [], 0
    try:
        encoder = json.JSONEncoder(ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        for chunk in encoder.iterencode(ordered(value)):
            raw = chunk.encode('utf-8')
            total += len(raw)
            if total > MAX_JSON_BYTES:
                raise ValueError('JSON byte limit')
            chunks.append(raw)
    except (TypeError, UnicodeError, RecursionError):
        raise ValueError('Invalid JSON input') from None
    return b''.join(chunks)


def _same_json(left, right):
    """Compare JSON trees: numeric equality is allowed, boolean coercion is not."""
    if type(left) is not type(right):
        if type(left) in (int, float) and type(right) in (int, float):
            return left == right
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(_same_json(left[key], right[key]) for key in left)
    if type(left) is list:
        return len(left) == len(right) and all(_same_json(a, b) for a, b in zip(left, right))
    return left == right


def _source_json(receipt, receipt_text):
    """Validate strict original JSON and return its exact UTF-8 source bytes."""
    if type(receipt_text) is not str or len(receipt_text) > MAX_JSON_BYTES:
        raise ValueError('Invalid source JSON text or byte limit')
    try:
        encoded = receipt_text.encode('utf-8')
    except UnicodeError:
        raise ValueError('Invalid source JSON Unicode') from None
    if len(encoded) > MAX_JSON_BYTES:
        raise ValueError('JSON byte limit')

    def reject_constant(unused):
        raise ValueError('Nonfinite source JSON number')

    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate source JSON key')
            result[key] = value
        return result

    try:
        parsed = json.loads(receipt_text, parse_constant=reject_constant, object_pairs_hook=object_pairs)
    except (ValueError, RecursionError):
        raise ValueError('Invalid source JSON') from None
    _validate_json(parsed, allow_floats=True)
    _validate_json(receipt, allow_floats=True)
    if not _same_json(parsed, receipt):
        raise ValueError('Source JSON does not match receipt')
    return encoded


def _http_identity(value):
    if (type(value) is not str or not value or len(value) > 8192 or
            any(ord(char) <= 32 or ord(char) == 127 for char in value)):
        raise ValueError('Invalid resource URL')
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname or
                parsed.username is not None or parsed.password is not None):
            raise ValueError('Invalid resource URL')
        parsed.port  # Validate malformed/out-of-range ports, without a request.
    except ValueError:
        raise ValueError('Invalid resource URL') from None
    return parsed


def preview_rules(config, resources, allowed_hosts):
    """Pure ordered previews; metadata needs remain unresolved, never fetched.

    At most 10,000 JSON candidate objects are accepted. Scope includes only the
    explicitly supplied hosts and their subdomains, with no redirect inference.
    Returns [{resource: deep copy, decision: rule evaluation}], in input order.
    """
    if type(resources) is not list or len(resources) > MAX_CANDIDATES:
        raise ValueError('Preview resource limit')
    _canonical_json(config)
    _canonical_json(resources)
    rules = validate_rules(config)
    hosts = scope_hosts(allowed_hosts)
    result = []
    for resource in resources:
        if type(resource) is not dict:
            raise ValueError('Invalid preview resource')
        host = _http_identity(resource.get('url')).hostname.lower()
        in_scope = any(host == allowed or host.endswith('.' + allowed) for allowed in hosts)
        decision = _evaluate_validated_rules(rules, resource, in_scope=in_scope)
        result.append({'resource': copy.deepcopy(resource), 'decision': decision})
    return result


def _safe_count(value):
    return type(value) is int and 0 <= value <= MAX_INTEGER


def _fingerprint(value):
    return type(value) is str and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def _sum_counts(values):
    total = sum(values)
    if not _safe_count(total):
        raise ValueError('Report aggregate exceeds safe integer range')
    return total


def build_report(receipt, expected_receipt_sha256=None, receipt_text=None):
    """Reconcile capture receipt assertions without reading archive files.

    With receipt_text, identity hashes its exact UTF-8 bytes after strict parsing
    and tree equality checks. This permits finite fractional source metadata;
    quantities remain safe integers. Without text, identity uses canonical JSON
    with safe integers only. The returned receipt and resource lists are deep copies;
    derived lists sort by URL and duplicate groups by captured SHA-256. Missing
    or inaccessible resources are observations, never proof of source absence.
    """
    encoded = _canonical_json(receipt) if receipt_text is None else _source_json(receipt, receipt_text)
    if type(receipt) is not dict or type(receipt.get('schema_version')) is not int or receipt['schema_version'] != 1:
        raise ValueError('Invalid receipt schema')
    if expected_receipt_sha256 is not None and not _fingerprint(expected_receipt_sha256):
        raise ValueError('Invalid expected receipt fingerprint')
    resources, counts = receipt.get('resources'), receipt.get('counts')
    if type(resources) is not list or len(resources) > MAX_CANDIDATES:
        raise ValueError('Receipt resource limit')
    if (type(counts) is not dict or set(counts) != set(RESOURCE_STATES) or
            not all(_safe_count(value) for value in counts.values()) or
            not _safe_count(receipt.get('discovered')) or receipt['discovered'] != len(resources)):
        raise ValueError('Receipt totals mismatch')
    actual = dict.fromkeys(RESOURCE_STATES, 0)
    seen, groups = set(), {}
    payload, declared, unknown = [], [], 0
    for resource in resources:
        if type(resource) is not dict:
            raise ValueError('Invalid receipt resource')
        url = resource.get('url')
        _http_identity(url)
        if url in seen:
            raise ValueError('Duplicate receipt resource URL')
        seen.add(url)
        state = resource.get('state')
        if type(state) is not str or state not in actual:
            raise ValueError('Invalid receipt resource state')
        actual[state] += 1
        if resource.get('redirect_to') is not None:
            _http_identity(resource['redirect_to'])
        if resource.get('parentUrl') is not None:
            _http_identity(resource['parentUrl'])
        if resource.get('bytes') is not None and not _safe_count(resource['bytes']):
            raise ValueError('Invalid resource size')
        if resource.get('status') is not None and (not _safe_count(resource['status']) or resource['status'] > 599):
            raise ValueError('Invalid resource status')
        size = resource.get('declared_bytes')
        if size is None:
            unknown += 1
        elif not _safe_count(size):
            raise ValueError('Invalid declared resource size')
        else:
            declared.append(size)
        if state == 'captured':
            status, size, digest = resource.get('status'), resource.get('bytes'), resource.get('sha256')
            if (type(status) is not int or not 200 <= status < 400 or
                    not _safe_count(size) or not _fingerprint(digest)):
                raise ValueError('Invalid captured resource metadata')
            payload.append(size)
            groups.setdefault(digest, []).append(url)
    if actual != counts:
        raise ValueError('Receipt totals mismatch')
    if (type(receipt.get('complete')) is not bool or type(receipt.get('limitations')) is not list or
            (receipt['complete'] and (not resources or actual['captured'] != len(resources) or receipt['limitations']))):
        raise ValueError('Invalid receipt completeness assertion')
    if receipt.get('scope_hosts') is not None:
        scope_hosts(receipt['scope_hosts'])
    if receipt.get('link_edges') is not None:
        edges = receipt['link_edges']
        if type(edges) is not list or len(edges) > MAX_CANDIDATES:
            raise ValueError('Receipt graph limit')
        for edge in edges:
            if type(edge) is not dict:
                raise ValueError('Invalid receipt graph edge')
            _http_identity(edge.get('source'))
            _http_identity(edge.get('target'))
    archives = receipt.get('archives')
    if type(archives) is not dict:
        raise ValueError('Missing receipt archive fingerprints')
    archive_sizes = []
    for name in ('warc', 'cdx'):
        archive = archives.get(name)
        if type(archive) is not dict or not _fingerprint(archive.get('sha256')):
            raise ValueError('Invalid receipt archive fingerprint')
        size = archive.get('bytes')
        if size is not None and not _safe_count(size):
            raise ValueError('Invalid archive size')
        archive_sizes.append(size)
    digest = hashlib.sha256(encoded).hexdigest()
    if expected_receipt_sha256 is not None and digest != expected_receipt_sha256:
        raise ValueError('Receipt fingerprint mismatch')
    ordered = sorted(copy.deepcopy(resources), key=lambda resource: resource['url'].encode('utf-16-be'))
    return dict(schema_version=1, capture_receipt_sha256=digest,
                receipt_identity_format='canonical_json_utf8' if receipt_text is None else 'source_json_utf8',
                evidence_state='receipt_assertions_not_archive_verification', receipt=copy.deepcopy(receipt),
                counts=actual, totals=dict(discovered=len(resources), **actual),
                failures=[resource for resource in ordered if resource['state'] == 'failed'],
                missing_resources=[resource for resource in ordered if resource['state'] in ('failed', 'pending', 'unsupported')],
                redirects=[resource for resource in ordered if resource['state'] == 'captured' and
                           300 <= resource['status'] < 400],
                duplicates=[dict(sha256=key, urls=sorted(urls, key=lambda url: url.encode('utf-16-be')))
                            for key, urls in sorted(groups.items()) if len(urls) > 1],
                storage=dict(captured_payload_bytes=_sum_counts(payload),
                             archive_bytes=_sum_counts(archive_sizes) if None not in archive_sizes else None,
                             declared_payload_bytes=_sum_counts(declared), unknown_estimate_resources=unknown))


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


def _sitemap_identity(url):
    """Normalize fetch identity without collapsing case-sensitive paths or queries."""
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Invalid sitemap identity')
    host = parsed.hostname.lower()
    host = '[' + host + ']' if ':' in host else host
    port = parsed.port
    if port is not None and port != {'http': 80, 'https': 443}[parsed.scheme]:
        host += ':' + str(port)
    return urlunsplit((parsed.scheme, host, parsed.path or '/', parsed.query, ''))


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
    seen = {_sitemap_identity(url) for url in (visited or [])}
    result = {'pages': [], 'sitemaps': [], 'excluded': []}
    source = urlsplit(source_url)
    if source.scheme not in ('http', 'https') or source.hostname not in hosts or source.username or source.password:
        raise ValueError('Sitemap source outside scope')
    source_url = _sitemap_identity(source_url)
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
        else:
            url = _sitemap_identity(url)
            if url not in seen:
                result['sitemaps' if root_name == 'sitemapindex' else 'pages'].append(url)
                seen.add(url)
    return result
