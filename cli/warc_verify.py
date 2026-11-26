#!/usr/bin/env python3
"""
AegisArchive - WARC/1.1 & CDX-11 Forensic Integrity Verifier
Zero external dependencies (Python 3 standard library only).

Licensed under the Apache License, Version 2.0.
"""

import sys
import os
import hashlib
import gzip
import argparse
import re

RECORD_SEPARATOR = b'\r\n\r\n'
STREAM_CHUNK = 64 * 1024


def header_fields(block, *, unique=()):
    headers = {}
    for line in block.decode('utf-8', errors='replace').split('\r\n'):
        key, colon, value = line.partition(':')
        if colon:
            key = key.strip().lower()
            if key in unique and key in headers:
                raise ValueError(f'Duplicate {key} header')
            headers[key] = value.strip()
    return headers


def parse_warc_header(block, *, unique=()):
    headers = header_fields(block, unique=unique)
    length = headers.get('content-length', '')
    if not block.startswith((b'WARC/1.1\r\n', b'WARC/1.0\r\n')) or not re.fullmatch(r'[0-9]{1,18}', length):
        raise ValueError('Malformed WARC version or Content-Length')
    return headers, int(length)


def read_record_header(stream, limit=STREAM_CHUNK, *, eof_ok=False):
    """Read a bounded CRLF-terminated header without crossing its byte limit."""
    lines = []
    while limit > 0:
        line = stream.readline(limit + 1)
        if not line and not lines and eof_ok:
            return None
        if len(line) > limit or not line.endswith(b'\r\n'):
            break
        lines.append(line)
        if line == b'\r\n' and len(lines) > 1:
            return b''.join(lines)
        limit -= len(line)
    raise ValueError('Truncated or oversized record header')


def copy_record_bytes(stream, length, write):
    """Copy an exact number of record bytes in bounded chunks."""
    while length:
        chunk = stream.read(min(length, STREAM_CHUNK))
        if not chunk:
            raise ValueError('Truncated WARC record block')
        write(chunk)
        length -= len(chunk)


def copy_record_block(stream, length, write):
    """Copy one framed block, including its separator, in bounded chunks."""
    copy_record_bytes(stream, length, write)
    separator = stream.read(len(RECORD_SEPARATOR))
    if separator != RECORD_SEPARATOR:
        raise ValueError('Missing WARC record separator')
    write(separator)


def read_container(path):
    """Reads a .warc or (multi-member) .warc.gz container fully into memory."""
    opener = gzip.open if path.endswith('.gz') else open
    with opener(path, 'rb') as f:
        return f.read()

def verify_cdx(cdx_path, content, record_spans, compressed):
    """Each CDX line must have 11 fields; for plain .warc, (offset, length) must match a record boundary."""
    spans = {(off, ln) for off, ln, _ in record_spans}
    checked = bad = 0
    with open(cdx_path, 'r', encoding='utf-8', errors='replace') as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip() or line.startswith(' CDX'):
                continue
            parts = line.split()
            if len(parts) != 11:
                print(f"  [Warning] CDX line {lineno}: expected 11 fields, found {len(parts)}")
                bad += 1
                continue
            checked += 1
            try:
                length, offset = int(parts[8]), int(parts[9])
                if length <= 0 or offset < 0:
                    raise ValueError('invalid span')
            except ValueError:
                print(f"  [Warning] CDX line {lineno}: invalid offset or length")
                bad += 1
                continue
            if compressed:
                continue  # compressed offsets are not uncompressed-stream offsets
            if not content.startswith(b"WARC/1.1", offset) or (offset, length) not in spans:
                print(f"  [Warning] CDX line {lineno}: offset {offset} / length {length} is not a record boundary ({parts[2]})")
                bad += 1
    suffix = " (offsets not checked: compressed container)" if compressed else ""
    print(f"  CDX entries verified:    {checked - bad}/{checked}{suffix}")
    return bad

def verify_warc(warc_path, cdx_path=None, _spans_out=None):
    if not os.path.isfile(warc_path):
        print(f"[Error] WARC file not found: {warc_path}")
        return False

    print("=" * 66)
    print(f"  Validating ISO 28500 Container: {os.path.basename(warc_path)}")
    print("=" * 66)

    total_records = 0
    warcinfo_count = 0
    response_count = 0
    revisit_count = 0
    request_count = 0
    corrupt_count = 0
    total_bytes = os.path.getsize(warc_path)
    record_spans = []  # (offset, length, target_uri)

    try:
        content = read_container(warc_path)
    except (OSError, EOFError, ValueError) as exc:
        print(f"  [Warning] Cannot read container: {exc}")
        return False
    if not content:
        print('  [Warning] Empty container')
        return False

    pos = 0
    content_len = len(content)

    while pos < content_len:
        rec_start = pos
        header_end = content.find(RECORD_SEPARATOR, pos)
        if header_end == -1:
            corrupt_count += 1
            break

        try:
            headers, body_len = parse_warc_header(content[pos:header_end])
        except ValueError as exc:
            print(f"  [Warning] {exc} at offset {pos}; stopping scan.")
            corrupt_count += 1
            break

        rec_type = headers.get('warc-type', 'unknown')
        target_uri = headers.get('warc-target-uri', '-')

        total_records += 1
        if rec_type == 'warcinfo':
            warcinfo_count += 1
        elif rec_type == 'response':
            response_count += 1
        elif rec_type == 'revisit':
            revisit_count += 1
        elif rec_type == 'request':
            request_count += 1

        rec_body_start = header_end + 4
        rec_body_end = rec_body_start + body_len
        if rec_body_end > content_len or content[rec_body_end:rec_body_end+4] != RECORD_SEPARATOR:
            print(f"  [Warning] Truncated record or missing terminator at offset {pos}")
            corrupt_count += 1
            break
        rec_body = content[rec_body_start:rec_body_end]

        expected_digest = headers.get('warc-payload-digest', '')
        if expected_digest.startswith('sha256:'):
            # Check payload digest (skip HTTP header in response)
            expected_hex = expected_digest.split(':', 1)[1]
            if rec_type == 'response':
                http_sep = rec_body.find(RECORD_SEPARATOR)
                if http_sep == -1:
                    corrupt_count += 1
                if http_sep != -1:
                    actual_payload = rec_body[http_sep+4:]
                    actual_hex = hashlib.sha256(actual_payload).hexdigest()
                    if actual_hex != expected_hex:
                        print(f"  [Warning] Digest mismatch for {target_uri}: expected {expected_hex[:12]}..., got {actual_hex[:12]}...")
                        corrupt_count += 1

        pos = rec_body_end
        while pos < content_len and (content[pos] == 13 or content[pos] == 10):
            pos += 1

        record_spans.append((rec_start, pos - rec_start, target_uri))

    if _spans_out is not None:
        _spans_out.extend(record_spans)

    print(f"  Total Container Size:    {total_bytes:,} bytes")
    print(f"  Total WARC Records:      {total_records}")
    print(f"    - warcinfo:            {warcinfo_count}")
    print(f"    - response:            {response_count}")
    print(f"    - revisit (deduped):   {revisit_count}")
    print(f"    - request:             {request_count}")

    if cdx_path:
        if os.path.isfile(cdx_path):
            corrupt_count += verify_cdx(cdx_path, content, record_spans, warc_path.endswith('.gz'))
        else:
            print(f"  [Warning] CDX file not found: {cdx_path}")
            corrupt_count += 1

    print(f"  Integrity Status:        {'PASSED' if corrupt_count == 0 else 'WARNINGS FOUND'}")
    print("=" * 66)

    return corrupt_count == 0

def main():
    parser = argparse.ArgumentParser(description="Verify AegisArchive WARC containers")
    parser.add_argument("warc_file", help="Path to .warc file to inspect")
    parser.add_argument("--cdx", default=None, help="Companion .cdx index: verify 11 fields and record offsets/lengths")
    args = parser.parse_args()

    success = verify_warc(args.warc_file, args.cdx)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
