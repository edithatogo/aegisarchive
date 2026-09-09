#!/usr/bin/env python3
"""Local, dependency-free intake of private capture reports into a safe issue ledger."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

STAGES = frozenset(('preflight', 'fetch', 'request', 'response', 'decode', 'hash',
                    'extract', 'discovery', 'robots', 'archive', 'storage', 'export',
                    'capture', 'coverage', 'transport', 'response_body',
                    'archive_write', 'captured', 'http_response', 'unknown'))
ERROR_TYPES = frozenset(('TypeError', 'Error', 'AbortError', 'TimeoutError',
                         'SecurityError', 'NetworkError', 'QuotaExceededError',
                         'InvalidStateError', 'NotAllowedError', 'EncodingError',
                         'SyntaxError', 'RangeError', 'HTTPError', 'network_error',
                         'network_or_decode_error', 'http_error', 'timeout',
                         'aborted', 'storage_error', 'decode_error', 'no_resources_saved',
                         'OSError', 'URLError', 'SSLError', 'gaierror',
                         'ConnectionError', 'ConnectionResetError',
                         'ConnectionRefusedError', 'BrokenPipeError',
                         'UnicodeDecodeError', 'ValueError', 'unknown'))
STATES = ('proposed', 'reproduced', 'fixed', 'verified')
HEX = re.compile(r'^[0-9a-f]{64}$')
MAX_BYTES = 32 * 1024 * 1024


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=True).encode()).hexdigest()


def classification(value, allowed):
    # Never echo attacker-controlled labels: even a short alphanumeric label can
    # contain a person's name or a credential.
    return value if isinstance(value, str) and value in allowed else 'unknown'


def identity(stage, error_type):
    return digest({'stage': stage, 'error_type': error_type})


def read_json(path):
    data = Path(path).read_bytes()
    if len(data) > MAX_BYTES:
        raise ValueError('input exceeds the diagnostic size limit')
    return json.loads(data)


def validate_ledger(ledger):
    """Fail closed on edited/foreign ledgers instead of copying arbitrary data."""
    if not isinstance(ledger, dict) or set(ledger) != {'schema_version', 'findings'}:
        raise ValueError('invalid ledger structure')
    if ledger['schema_version'] != 1 or not isinstance(ledger['findings'], list):
        raise ValueError('unsupported ledger version')
    seen = set()
    for item in ledger['findings']:
        if not isinstance(item, dict) or set(item) != {
                'fingerprint', 'stage', 'error_type', 'state', 'occurrences',
                'report_hashes', 'history', 'recurrence_after_verification'}:
            raise ValueError('invalid finding structure')
        stage, error = item['stage'], item['error_type']
        if classification(stage, STAGES) != stage or classification(error, ERROR_TYPES) != error:
            raise ValueError('invalid finding classification')
        key = identity(stage, error)
        if item['fingerprint'] != key or key in seen:
            raise ValueError('invalid or duplicate fingerprint')
        seen.add(key)
        if item['state'] not in STATES or type(item['occurrences']) is not int or item['occurrences'] < 1:
            raise ValueError('invalid finding state or count')
        hashes = item['report_hashes']
        if not isinstance(hashes, list) or not hashes or any(not isinstance(h, str) or not HEX.fullmatch(h) for h in hashes):
            raise ValueError('invalid report hashes')
        if len(set(hashes)) != len(hashes) or type(item['recurrence_after_verification']) is not bool:
            raise ValueError('invalid recurrence metadata')
        state = 'proposed'
        if not isinstance(item['history'], list):
            raise ValueError('invalid lifecycle history')
        for event in item['history']:
            if not isinstance(event, dict) or set(event) != {'from', 'to', 'evidence_sha256'}:
                raise ValueError('invalid lifecycle event')
            if event['from'] != state or not allowed_transition(state, event['to']):
                raise ValueError('invalid lifecycle transition')
            evidence = event['evidence_sha256']
            if not isinstance(evidence, str) or not HEX.fullmatch(evidence):
                raise ValueError('invalid evidence digest')
            state = event['to']
        if state != item['state']:
            raise ValueError('state does not match lifecycle history')
    return ledger


def allowed_transition(old, new):
    return ((old in STATES[:-1] and new == STATES[STATES.index(old) + 1])
            or (old == 'verified' and new == 'proposed'))


def ingest(report, ledger=None):
    if not isinstance(report, dict) or report.get('schema_version') != 1:
        raise ValueError('expected diagnostic report schema_version 1')
    if not isinstance(report.get('coverage'), dict) or not isinstance(report.get('events'), list):
        raise ValueError('expected report coverage and events')
    # Copy only validated ledger fields; report identifiers and URLs are not kept.
    ledger = json.loads(json.dumps(validate_ledger(ledger))) if ledger is not None else {'schema_version': 1, 'findings': []}
    report_hash = digest(report)
    counts = {}
    for event in report['events']:
        if not isinstance(event, dict):
            raise ValueError('expected event objects')
        http_failure = type(event.get('status')) is int and event['status'] >= 400
        if not (http_failure or event.get('level') == 'error' or event.get('outcome') == 'failed'
                or event.get('error_type') or event.get('error')):
            continue
        raw_error = event.get('error_type')
        if raw_error is None and isinstance(event.get('error'), dict):
            raw_error = event['error'].get('type') or event['error'].get('name')
        if not raw_error and http_failure:
            raw_error = 'HTTPError'
        pair = (classification(event.get('stage'), STAGES), classification(raw_error, ERROR_TYPES))
        counts[pair] = counts.get(pair, 0) + 1
    coverage = report['coverage'].get('counts', report['coverage'])
    if not isinstance(coverage, dict):
        raise ValueError('expected coverage counts object')
    if ((coverage.get('captured') == 0 and type(coverage.get('failed')) is int and coverage['failed'] > 0)
            or (coverage.get('status') == 'failed' and coverage.get('saved', coverage.get('resources_saved')) == 0)):
        counts[('coverage', 'no_resources_saved')] = 1
    existing = {item['fingerprint']: item for item in ledger['findings']}
    for (stage, error), count in sorted(counts.items()):
        key = identity(stage, error)
        item = existing.get(key)
        if item is None:
            item = {'fingerprint': key, 'stage': stage, 'error_type': error,
                    'state': 'proposed', 'occurrences': 0, 'report_hashes': [],
                    'history': [], 'recurrence_after_verification': False}
            ledger['findings'].append(item)
        if report_hash not in item['report_hashes']:
            item['report_hashes'].append(report_hash)
            item['occurrences'] += count
            if item['state'] == 'verified':
                item['recurrence_after_verification'] = True
    ledger['findings'].sort(key=lambda item: item['fingerprint'])
    return validate_ledger(ledger)


def transition(ledger, fingerprint, new_state, evidence_bytes):
    ledger = json.loads(json.dumps(validate_ledger(ledger)))
    matches = [item for item in ledger['findings'] if item['fingerprint'] == fingerprint]
    if len(matches) != 1 or not allowed_transition(matches[0]['state'], new_state):
        raise ValueError('unknown finding or invalid lifecycle transition')
    if not evidence_bytes.strip():
        raise ValueError('nonempty evidence required')
    item = matches[0]
    item['history'].append({'from': item['state'], 'to': new_state,
                            'evidence_sha256': hashlib.sha256(evidence_bytes).hexdigest()})
    item['state'] = new_state
    if new_state in ('proposed', 'verified'):
        item['recurrence_after_verification'] = False
    return validate_ledger(ledger)


def write_atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as output:
            temporary = output.name
            json.dump(value, output, indent=2, sort_keys=True)
            output.write('\n')
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', nargs='?', help='Private diagnostic JSON (read locally only)')
    parser.add_argument('--ledger', required=True, help='Local deduplicated JSON finding ledger')
    parser.add_argument('--finding', help='Full finding fingerprint for a lifecycle update')
    parser.add_argument('--state', choices=STATES)
    parser.add_argument('--evidence-file', help='Local evidence file; only its SHA-256 is retained')
    args = parser.parse_args(argv)
    try:
        updating = any((args.finding, args.state, args.evidence_file))
        if (updating and (args.report or not all((args.finding, args.state, args.evidence_file)))) or (not updating and not args.report):
            raise ValueError('provide a report OR finding, state, and evidence-file')
        if args.report and Path(args.report).resolve() == Path(args.ledger).resolve():
            raise ValueError('report and ledger must be different files')
        ledger = read_json(args.ledger) if Path(args.ledger).exists() else None
        if updating:
            ledger = transition(ledger, args.finding, args.state, Path(args.evidence_file).read_bytes())
        else:
            ledger = ingest(read_json(args.report), ledger)
        write_atomic(args.ledger, ledger)
        print(json.dumps({'schema_version': 1, 'findings': len(ledger['findings']), 'status': 'ok'}))
        return 0
    except (OSError, ValueError, TypeError):
        # Exception text may contain private file paths or report content.
        print(json.dumps({'schema_version': 1, 'status': 'error', 'error_type': 'invalid_input_or_io'}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
