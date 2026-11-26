"""Dependency-free deterministic export of captured URL/payload records."""
from __future__ import annotations
import argparse
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
import posixpath
import re
import sys
from tempfile import TemporaryDirectory
import zipfile
import zlib
from pathlib import Path
from urllib.parse import urlparse

from .aegis_cli import to_surt
from .warc_verify import (STREAM_CHUNK, copy_record_block, copy_record_bytes,
                          header_fields, parse_warc_header, read_record_header)

_REVISIT_PROFILES = {
    f'http://netpreserve.org/warc/{version}/revisit/identical-payload-digest' for version in ('1.0', '1.1')
}
_INDEX_HEADERS = ('warc-type', 'warc-target-uri', 'warc-date', 'warc-record-id', 'content-type',
                  'warc-payload-digest', 'warc-block-digest', 'warc-refers-to',
                  'warc-refers-to-target-uri', 'warc-refers-to-date', 'warc-profile')

def safe_path(url: str) -> str:
    p = urlparse(url)
    if p.scheme not in ('http','https') or not p.netloc: raise ValueError('unsupported URL')
    path = p.path or '/index.html'
    if path.endswith('/'): path += 'index.html'
    name = posixpath.normpath(path).lstrip('/')
    if name == '..' or name.startswith('../') or '\\' in name: raise ValueError('unsafe path')
    if p.query: name += '__q_' + hashlib.sha256(p.query.encode()).hexdigest()[:12]
    return name[:240]

def export_directory(records, destination):
    root = Path(destination); root.mkdir(parents=True, exist_ok=True); manifest=[]
    for url, payload in sorted(records, key=lambda x:x[0]):
        rel=safe_path(url); target=root/rel; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(payload)
        manifest.append({'url':url,'path':rel,'sha256':hashlib.sha256(payload).hexdigest(),'bytes':len(payload)})
    (root/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n',encoding='utf-8'); return manifest

def export_zip(records, destination):
    import tempfile, shutil
    with tempfile.TemporaryDirectory() as t:
        export_directory(records,t)
        with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as z:
            for p in sorted(Path(t).rglob('*')):
                if p.is_file():
                    info=zipfile.ZipInfo(p.relative_to(t).as_posix(),date_time=(1980,1,1,0,0,0)); info.compress_type=zipfile.ZIP_DEFLATED; z.writestr(info,p.read_bytes())


@contextmanager
def _new_export(destination):
    output = Path(destination).absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError(f'Export already exists: {output}')
    with TemporaryDirectory(dir=output.parent, prefix='.aegis-export-') as folder:
        staged = Path(folder) / output.name
        yield staged
        if os.name == 'nt':
            staged.rename(output)
        else:
            os.link(staged, output)


def _finalized_source(source):
    path = Path(source).resolve(strict=True)
    if not path.is_file() or path.suffix.lower() != '.warc' or '.partial' in path.suffixes:
        raise ValueError('Select a finalized uncompressed .warc file')
    receipt = None
    if path.name == 'archive.warc':
        if any(path.with_name(name).exists() for name in ('archive.warc.partial', 'receipt.partial.json')):
            raise ValueError('Archive finalization is incomplete')
        receipt_path = path.with_name('receipt.json')
        if receipt_path.is_file():
            receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
            if not isinstance(receipt, dict) or receipt.get('complete') is not True:
                raise ValueError('Archive receipt does not mark the capture complete')
    return path, receipt


def _write_members(source, target):
    path, receipt = _finalized_source(source)
    spans = []
    digest = hashlib.sha256()
    with path.open('rb') as stream, target.open('wb') as output:
        before = os.fstat(stream.fileno())
        while (header := read_record_header(stream, eof_ok=True)) is not None:
            _, length = parse_warc_header(header, unique=('content-length',))
            offset = output.tell()
            with gzip.GzipFile(filename='', mode='wb', fileobj=output, mtime=0) as member:
                def write(data):
                    digest.update(data)
                    member.write(data)

                write(header)
                copy_record_block(stream, length, write)
            spans.append({'offset': offset, 'length': output.tell() - offset})
        after = path.stat()
        if not os.path.samestat(before, after) or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError('Source WARC changed during export')
    if not spans:
        raise ValueError('Empty WARC')
    source_sha = digest.hexdigest()
    if receipt is not None:
        archives = receipt.get('archives')
        recorded = archives.get('warc') if isinstance(archives, dict) else None
        if not isinstance(recorded, dict) or recorded.get('bytes') != before.st_size or recorded.get('sha256') != source_sha:
            raise ValueError('Source WARC does not match its finalization receipt')
    return spans, source_sha


class _Member(io.RawIOBase):
    """Decode one gzip member while leaving subsequent compressed bytes buffered."""
    def __init__(self, source):
        self.source = source
        self.decoder = zlib.decompressobj(31)

    def readable(self):
        return True

    def readinto(self, target):
        while not self.decoder.eof and len(target):
            chunk = self.source.peek(STREAM_CHUNK)[:STREAM_CHUNK]
            if not chunk:
                raise ValueError('Truncated gzip member')
            try:
                data = self.decoder.decompress(chunk, len(target))
            except zlib.error as error:
                raise ValueError('Invalid gzip member') from error
            tail = self.decoder.unused_data if self.decoder.eof else self.decoder.unconsumed_tail
            self.source.read(len(chunk) - len(tail))
            if data:
                target[:len(data)] = data
                return len(data)
        return 0


def _scan_members(source, write, inspect=None):
    spans = []
    while source.peek(1):
        offset = source.tell()
        with io.BufferedReader(_Member(source), buffer_size=STREAM_CHUNK) as record:
            header = read_record_header(record)
            unique = ('content-length',) if inspect is None else ('content-length', *_INDEX_HEADERS)
            headers, length = parse_warc_header(header, unique=unique)
            write(header)
            span = {'offset': offset}
            if inspect is None:
                copy_record_block(record, length, write)
            else:
                span['capture'] = inspect(record, headers, length)
            if record.read(1):
                raise ValueError('Gzip member contains bytes beyond its WARC record')
        span['length'] = source.tell() - offset
        spans.append(span)
    if not spans:
        raise ValueError('Empty compressed WARC')
    return spans


def export_warc_gzip(source, destination):
    """Publish a new record-compressed WARC after byte-exact readback."""
    if not str(destination).lower().endswith('.warc.gz'):
        raise ValueError('Compressed WARC output must end in .warc.gz')
    with _new_export(destination) as staged:
        spans, source_sha = _write_members(source, staged)
        digest = hashlib.sha256()
        with staged.open('rb') as stream:
            if _scan_members(stream, digest.update) != spans or digest.hexdigest() != source_sha:
                raise ValueError('Compressed WARC readback does not match source')
    return {'members': spans, 'source_sha256': source_sha}


def _digest_spec(value):
    algorithm, _, encoded = value.lower().partition(':')
    if algorithm not in ('sha1', 'sha256'):
        raise ValueError('Unsupported WARC digest')
    digest = hashlib.new(algorithm, usedforsecurity=False)
    if re.fullmatch(rf'[0-9a-f]{{{2 * digest.digest_size}}}', encoded):
        expected = bytes.fromhex(encoded)
    else:
        try:
            expected = base64.b32decode(encoded.upper() + '=' * (-len(encoded) % 8))
        except ValueError:
            raise ValueError('Malformed WARC digest') from None
    if len(expected) != digest.digest_size:
        raise ValueError('Malformed WARC digest')
    return digest, expected


def _discard(_):
    pass


def _index_capture(stream, headers, length, originals):
    kind = headers.get('warc-type')
    if kind not in ('response', 'revisit', 'resource'):
        copy_record_block(stream, length, _discard)
        return None
    if 'warc-segment-number' in headers or ('warc-truncated' in headers and kind != 'revisit'):
        raise ValueError('CDXJ requires complete replayable response records')

    url = headers.get('warc-target-uri', '')
    if url.startswith('<') and url.endswith('>'):
        url = url[1:-1]
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username is not None or any(c.isspace() for c in url):
        raise ValueError('Invalid HTTP capture URL for CDXJ')
    if parsed.port == 0:
        raise ValueError('Invalid HTTP capture port')
    key = to_surt(parsed._replace(path=parsed.path or '/').geturl()).lower()
    try:
        stamp = datetime.fromisoformat(headers.get('warc-date', ''))
    except ValueError:
        raise ValueError('Invalid WARC capture time') from None
    if stamp.utcoffset() is None:
        raise ValueError('WARC capture time requires a time zone')
    stamp = stamp.astimezone(timezone.utc)
    timestamp = stamp.strftime('%Y%m%d%H%M%S')
    if stamp.microsecond:
        timestamp += f'{stamp.microsecond // 1000:03d}'

    digest_label = headers.get('warc-payload-digest')
    block_label = headers.get('warc-block-digest')
    block = _digest_spec(block_label) if block_label is not None else None
    mime = headers.get('content-type', '').split(';', 1)[0].strip().lower()
    status = '200'
    if kind in ('response', 'revisit') and length:
        if mime != 'application/http':
            raise ValueError('Expected archived HTTP response headers')
        raw = read_record_header(stream, min(length, STREAM_CHUNK))
        length -= len(raw)
        match = re.fullmatch(rb'HTTP/[0-9.]+ ([0-9]{3})(?: .*)?', raw.split(b'\r\n', 1)[0])
        if not match or not 100 <= int(match[1]) <= 599:
            raise ValueError('Invalid archived HTTP status')
        status = match[1].decode('ascii')
        fields = header_fields(raw, unique=('content-type', 'transfer-encoding'))
        if fields.get('transfer-encoding', 'identity').lower() != 'identity':
            raise ValueError('CDXJ requires a decoded archived HTTP payload')
        mime = fields.get('content-type', '').split(';', 1)[0].strip().lower()
        if block:
            block[0].update(raw)
    elif kind == 'response':
        raise ValueError('Archived response has no HTTP block')

    if kind == 'revisit':
        anchor = originals.get(headers.get('warc-refers-to'))
        if length or headers.get('warc-profile') not in _REVISIT_PROFILES or not anchor or digest_label is None:
            raise ValueError('Unresolved archived revisit')
        declared, expected = _digest_spec(digest_label)
        if (declared.name, expected) != anchor['digest_key']:
            raise ValueError('Archived revisit digest mismatch')
        if (headers.get('warc-refers-to-target-uri', anchor['url']).removeprefix('<').removesuffix('>') != anchor['url']
                or headers.get('warc-refers-to-date', anchor['warc_date']) != anchor['warc_date']):
            raise ValueError('Archived revisit target mismatch')
        if not mime or mime == 'application/http':
            mime = anchor['page_mime']
        if block and block[0].digest() != block[1]:
            raise ValueError('WARC block digest mismatch')
        copy_record_block(stream, 0, _discard)
        return dict(key=key, url=url, timestamp=timestamp, date=stamp.isoformat(), status=status,
                    mime='warc/revisit', page_mime=mime, digest=anchor['digest'])

    digest, expected = _digest_spec(digest_label) if digest_label is not None else (hashlib.sha256(), None)

    def checked_write(data):
        digest.update(data)
        if block:
            block[0].update(data)

    copy_record_bytes(stream, length, checked_write)
    copy_record_block(stream, 0, _discard)
    actual = digest.digest()
    if expected is not None and actual != expected:
        raise ValueError('WARC payload digest mismatch')
    if block and block[0].digest() != block[1]:
        raise ValueError('WARC block digest mismatch')
    capture = dict(key=key, url=url, timestamp=timestamp, date=stamp.isoformat(), status=status,
                   mime=mime or 'application/octet-stream', page_mime=mime,
                   digest=digest_label or f'sha256:{actual.hex()}')
    record_id = headers.get('warc-record-id')
    if record_id:
        if record_id in originals:
            raise ValueError('Duplicate WARC record identity')
        originals[record_id] = dict(digest_key=(digest.name, actual), warc_date=headers['warc-date'],
                                    url=url, page_mime=mime, digest=capture['digest'])
    return capture


def _indexed_members(stream):
    originals = {}
    return _scan_members(stream, _discard, lambda record, headers, length: _index_capture(record, headers, length, originals))


def _cdxj_bytes(members, filename):
    rows = []
    for member in members:
        capture = member['capture']
        if capture is None:
            continue
        data = {key: capture[key] for key in ('url', 'mime', 'status', 'digest')}
        data.update(filename=filename, offset=str(member['offset']), length=str(member['length']))
        line = f"{capture['key']} {capture['timestamp']} {json.dumps(data, sort_keys=True, separators=(',', ':'))}\n"
        rows.append(line.encode('utf-8'))
    if not rows:
        raise ValueError('No replayable records to index')
    # ponytail: sort index rows in memory. Consider an external merge when
    # large captures outgrow this metadata budget.
    return b''.join(sorted(rows))


def _cdxj_for_file(archive):
    path = Path(archive).resolve(strict=True)
    if not path.is_file() or not path.name.lower().endswith('.warc.gz'):
        raise ValueError('CDXJ input must be a record-compressed .warc.gz')
    with path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        rows = _cdxj_bytes(_indexed_members(stream), path.name)
        after = path.stat()
        if not os.path.samestat(before, after) or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError('Compressed WARC changed while indexing')
    return rows


def _check_index(stream, expected):
    if stream.read(len(expected) + 1) != expected:
        raise ValueError('CDXJ index does not match verified compressed records')


def verify_cdxj(archive, index):
    """Validate the exact canonical index emitted for this archive."""
    expected = _cdxj_for_file(archive)
    with Path(index).open('rb') as stream:
        _check_index(stream, expected)
    return {'entries': expected.count(b'\n')}


def export_cdxj(archive, destination):
    if Path(destination).suffix.lower() != '.cdxj':
        raise ValueError('CDXJ output must end in .cdxj')
    with _new_export(destination) as staged:
        expected = _cdxj_for_file(archive)
        staged.write_bytes(expected)
        with staged.open('rb') as stream:
            _check_index(stream, expected)
    return {'entries': expected.count(b'\n')}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Export a finalized saved capture.')
    commands = parser.add_subparsers(dest='command', required=True)
    warc = commands.add_parser('warc-gzip', help='Write one gzip member per WARC record')
    warc.add_argument('source')
    warc.add_argument('output')
    cdxj = commands.add_parser('cdxj', help='Write a CDXJ index for a record-compressed WARC')
    cdxj.add_argument('source')
    cdxj.add_argument('output')
    check = commands.add_parser('verify-cdxj', help='Check a CDXJ index against the compressed WARC')
    check.add_argument('source')
    check.add_argument('output', metavar='index')
    args = parser.parse_args(argv)
    try:
        operation = {'warc-gzip': export_warc_gzip, 'cdxj': export_cdxj, 'verify-cdxj': verify_cdxj}
        result = operation[args.command](args.source, args.output)
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
