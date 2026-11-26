"""Build a new offline search catalogue from explicitly selected WARC files."""

import argparse
import base64
from collections import Counter
from contextlib import closing
from datetime import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
import zlib

from cli.warc_verify import RECORD_SEPARATOR, header_fields, parse_warc_header
from .document_catalogue import Catalogue
from .document_extract import MAX_BYTES, extract
from .document_search import SearchIndex

MAX_HEADER = 64 * 1024
CHUNK = 1024 * 1024
HANDLING = ('public', 'restricted', 'unknown')
TEXT_MIME = ('text/html', 'text/plain')
REVISIT_PROFILES = {
    f'http://netpreserve.org/warc/{version}/revisit/identical-payload-digest' for version in ('1.0', '1.1')
}
SINGLE_WARC_FIELDS = {
    'content-length', 'content-type', 'warc-type', 'warc-target-uri', 'warc-date',
    'warc-record-id', 'warc-block-digest', 'warc-payload-digest', 'warc-refers-to',
    'warc-profile', 'warc-truncated', 'warc-segment-number',
}


def _read_header(stream, limit, *, eof_ok=False):
    lines = []
    while limit > 0:
        line = stream.readline(limit + 1)
        if not line and not lines and eof_ok:
            return None
        if len(line) > limit or not line.endswith(b'\r\n'):
            break
        lines.append(line)
        if line == b'\r\n':
            return b''.join(lines)
        limit -= len(line)
    raise ValueError('truncated or oversized record header')


def _declared_digest(value):
    if value is None:
        return None
    algorithm, _, encoded = value.lower().partition(':')
    if algorithm not in ('sha1', 'sha256'):
        raise ValueError('unsupported WARC digest algorithm')
    checksum = hashlib.new(algorithm, usedforsecurity=False)
    if re.fullmatch(rf'[0-9a-f]{{{2 * checksum.digest_size}}}', encoded):
        expected = bytes.fromhex(encoded)
    else:
        try:
            expected = base64.b32decode(encoded.upper() + '=' * (-len(encoded) % 8))
        except ValueError:
            raise ValueError('malformed WARC digest') from None
    if len(expected) != checksum.digest_size:
        raise ValueError('malformed WARC digest')
    return checksum, expected


def _read_record(stream, headers, length, handling):
    kind = headers.get('warc-type')
    block = _declared_digest(headers.get('warc-block-digest'))
    mime = headers.get('content-type', '').split(';', 1)[0].lower().strip()
    reason = None
    if kind == 'continuation' or 'warc-segment-number' in headers:
        reason = 'segmented_record'
    elif 'warc-truncated' in headers and not (kind == 'revisit' and headers['warc-truncated'] == 'length'):
        reason = 'truncated_capture'
    elif kind == 'revisit' and length == 0:
        mime = ''
    elif kind in ('response', 'revisit') and mime == 'application/http':
        http = _read_header(stream, min(length, MAX_HEADER))
        length -= len(http)
        if block:
            block[0].update(http)
        status = re.fullmatch(rb'HTTP/[0-9.]+ ([0-9]{3})(?: .*)?', http.split(b'\r\n', 1)[0])
        if status is None:
            raise ValueError('malformed archived HTTP status')
        fields = header_fields(http, unique=('content-length', 'content-type', 'content-encoding', 'transfer-encoding'))
        mime = fields.get('content-type', '').split(';', 1)[0].lower().strip()
        status_code = int(status[1])
        if any(fields.get(key, 'identity').lower() != 'identity' for key in ('content-encoding', 'transfer-encoding')):
            reason = 'encoded_payload'
        elif not 200 <= status_code < 300 or status_code == 206:
            reason = 'http_status'
        elif kind == 'response' and 'content-length' in fields:
            size = fields['content-length']
            if not re.fullmatch(r'[0-9]{1,18}', size) or int(size) != length:
                raise ValueError('archived HTTP Content-Length does not match payload')
    elif kind != 'resource':
        reason = 'unsupported_record'

    # WARC block digests cover stored bytes. Payload digests can refer to
    # reassembled segments or an HTTP entity after transfer decoding.
    payload = None
    if kind in ('response', 'resource') and reason in (None, 'http_status'):
        payload = _declared_digest(headers.get('warc-payload-digest'))
    if handling != 'public':
        reason = 'handling'
    elif reason is None and mime not in TEXT_MIME and (kind != 'revisit' or mime):
        reason = 'unsupported_type'
    elif reason is None and length > MAX_BYTES:
        reason = 'size_limit'

    data = bytearray() if reason is None else None
    while length:
        chunk = stream.read(min(length, CHUNK))
        if not chunk:
            raise ValueError('truncated record data')
        length -= len(chunk)
        if block:
            block[0].update(chunk)
        if payload:
            payload[0].update(chunk)
        if data is not None:
            data.extend(chunk)
    if stream.read(len(RECORD_SEPARATOR)) != RECORD_SEPARATOR:
        raise ValueError('missing WARC record terminator')
    for field, digest in (('block', block), ('payload', payload)):
        if digest and digest[0].digest() != digest[1]:
            raise ValueError(f'WARC {field} digest mismatch')
    return (bytes(data) if data is not None else None), mime, reason


def _capture(headers, body, mime, reference, catalogue, index, anchors):
    kind = headers['warc-type']
    record_id = headers.get('warc-record-id')
    url = headers.get('warc-target-uri', '')
    if url.startswith('<') and url.endswith('>'):
        url = url[1:-1]
    captured = headers.get('warc-date', '')
    target_url = urlsplit(url)
    if not record_id or not target_url.scheme:
        raise ValueError('missing or invalid capture identity')
    if target_url.scheme not in ('http', 'https'):
        return 'unsupported_target'
    if not target_url.hostname:
        raise ValueError('missing or invalid capture identity')
    if target_url.username is not None or target_url.password is not None:
        return 'credentialed_target'
    try:
        stamp = datetime.fromisoformat(captured)
    except ValueError:
        raise ValueError('malformed WARC capture time') from None
    if stamp.utcoffset() is None:
        raise ValueError('capture time has no time zone')
    reference.update(record_id=record_id, captured_at=captured)
    if kind == 'revisit':
        target = headers.get('warc-refers-to')
        profile = headers.get('warc-profile', '')
        digest = _declared_digest(headers.get('warc-payload-digest'))
        if body or target not in anchors or not digest or profile not in REVISIT_PROFILES:
            return 'unresolved_revisit'
        body = catalogue.original(anchors[target]['revision_id'])
        mime = mime or anchors[target]['mime']
        digest[0].update(body)
        if digest[0].digest() != digest[1]:
            raise ValueError('WARC revisit digest mismatch')
        reference['refers_to'] = target

    result = extract(body, mime)
    if result['status'] not in ('complete', 'partial') or not result['text'].strip():
        return result['reason'] or 'empty_text'
    if record_id in anchors:
        previous = anchors[record_id]
        if (previous['url'] != url or previous['captured_at'] != captured
                or previous['sha256'] != result['source_hash'] or previous['mime'] != mime):
            raise ValueError('conflicting WARC record identity')
        return 'duplicate_record'

    revision = catalogue.register(url, body, mime, handling='public', acquired=stamp.timestamp())
    result.update(warc=reference, acquisition_receipt_id=revision['receipt_id'])
    index.add(result, revision['source_id'], revision['revision_id'])
    anchors[record_id] = dict(revision_id=revision['revision_id'], url=url,
                              captured_at=captured, sha256=revision['content_hash'], mime=mime)
    return None


def _index_archive(archive, archive_id, handling, catalogue, index, anchors, counts, skipped):
    compressed = archive.suffix.lower() == '.gz'
    opener = gzip.open if compressed else open
    with opener(archive, 'rb') as stream:
        before = os.fstat(stream.fileno())
        number = 0
        while True:
            offset = stream.tell()
            try:
                header = _read_header(stream, MAX_HEADER, eof_ok=True)
                if header is None:
                    break
                number += 1
                headers, length = parse_warc_header(header, unique=SINGLE_WARC_FIELDS)
                body, mime, reason = _read_record(stream, headers, length, handling)
                if reason is None:
                    reference = dict(archive=archive.name, archive_id=archive_id, offset=offset,
                                     length=stream.tell() - offset,
                                     offset_kind='uncompressed' if compressed else 'file')
                    reason = _capture(headers, body, mime, reference, catalogue, index, anchors)
            except (EOFError, OSError, ValueError, zlib.error) as error:
                raise ValueError(f'{archive.name}, stream offset {offset}: {error}') from None
            counts['records'] += 1
            if reason is None:
                counts['indexed'] += 1
            else:
                skipped[reason] += 1
        after = archive.stat()
        if number == 0:
            raise ValueError(f'{archive.name}: empty WARC')
        if not os.path.samestat(before, after) or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError(f'{archive.name}: WARC changed during intake')


def build_catalogue(destination, archives, *, handling):
    """Stream records into a new catalogue and publish only after validation."""
    if handling not in HANDLING:
        raise ValueError('explicit public, restricted or unknown handling is required')
    output = Path(destination).absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError(f'Catalogue already exists: {output}')
    inputs = list(dict.fromkeys(Path(archive).resolve(strict=True) for archive in archives))
    if not inputs or any(not path.is_file() for path in inputs):
        raise ValueError('select at least one regular WARC file')

    counts = Counter(records=0, indexed=0)
    skipped = Counter()
    # ponytail: keep just the revisit references in memory. Move these to
    # SQLite if indexing corpora with enough records to put pressure on RAM.
    anchors = {}
    with TemporaryDirectory(dir=output.parent, prefix='.warc-intake-') as temporary:
        staged = Path(temporary) / 'catalogue.sqlite'
        with closing(Catalogue(staged)) as catalogue:
            index = SearchIndex(catalogue)
            with catalogue.db:
                catalogue.db.execute('CREATE TABLE warc_inputs (archive_id INTEGER PRIMARY KEY, path TEXT NOT NULL)')
                catalogue.db.executemany('INSERT INTO warc_inputs VALUES (?,?)', enumerate(map(str, inputs), 1))
            for archive_id, archive in enumerate(inputs, 1):
                _index_archive(archive, archive_id, handling, catalogue, index, anchors, counts, skipped)
        if os.name == 'nt':
            staged.rename(output)
        else:
            os.link(staged, output)
    return dict(archives=len(inputs), handling=handling, **counts, skipped=dict(skipped),
                inputs=dict(enumerate(map(str, inputs), 1)))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('catalogue', help='New SQLite catalogue path')
    parser.add_argument('archives', nargs='+', help='Saved WARC or WARC.gz files in capture order')
    parser.add_argument('--handling', required=True, choices=HANDLING)
    args = parser.parse_args(argv)
    try:
        result = build_catalogue(args.catalogue, args.archives, handling=args.handling)
    except (OSError, sqlite3.Error, ValueError) as error:
        print(error, file=sys.stderr)
        return 2
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
