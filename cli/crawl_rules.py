"""Bounded, versioned rules. First matching rule wins; no regular expressions.

This module is deterministic and performs no network requests. Rules refine an
existing scope decision; they never grant access outside the caller's scope.
"""
import copy
import re
from urllib.parse import urlsplit

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
