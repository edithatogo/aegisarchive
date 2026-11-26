"""Dependency-free deterministic export of captured URL/payload records."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import gzip
import hashlib
import io
import json
import os
import posixpath
import sys
from tempfile import TemporaryDirectory
import zipfile
import zlib
from pathlib import Path
from urllib.parse import urlparse

from .warc_verify import STREAM_CHUNK, copy_record_block, parse_warc_header, read_record_header

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


def _scan_members(source, write):
    spans = []
    while source.peek(1):
        offset = source.tell()
        with io.BufferedReader(_Member(source), buffer_size=STREAM_CHUNK) as record:
            header = read_record_header(record)
            _, length = parse_warc_header(header, unique=('content-length',))
            write(header)
            copy_record_block(record, length, write)
            if record.read(1):
                raise ValueError('Gzip member contains bytes beyond its WARC record')
        spans.append({'offset': offset, 'length': source.tell() - offset})
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


def main(argv=None):
    parser = argparse.ArgumentParser(description='Export a finalized saved capture.')
    commands = parser.add_subparsers(dest='command', required=True)
    warc = commands.add_parser('warc-gzip', help='Write one gzip member per WARC record')
    warc.add_argument('source')
    warc.add_argument('output')
    args = parser.parse_args(argv)
    try:
        result = export_warc_gzip(args.source, args.output)
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
