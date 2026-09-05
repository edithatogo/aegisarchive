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
            if compressed:
                continue  # offsets are only checkable against the uncompressed stream
            length, offset = int(parts[8]), int(parts[9])
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

    content = read_container(warc_path)

    pos = 0
    content_len = len(content)

    while pos < content_len:
        rec_start = pos
        header_end = content.find(b"\r\n\r\n", pos)
        if header_end == -1:
            break

        header_bytes = content[pos:header_end]
        try:
            header_str = header_bytes.decode('utf-8', errors='replace')
        except Exception:
            corrupt_count += 1
            break

        headers = {}
        for line in header_str.split('\r\n'):
            idx = line.find(':')
            if idx != -1:
                headers[line[:idx].strip().lower()] = line[idx+1:].strip()

        rec_type = headers.get('warc-type', 'unknown')
        body_len = int(headers.get('content-length', '0'))
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
        rec_body = content[rec_body_start:rec_body_end]

        expected_digest = headers.get('warc-payload-digest', '')
        if expected_digest.startswith('sha256:'):
            # Check payload digest (skip HTTP header in response)
            expected_hex = expected_digest.split(':', 1)[1]
            if rec_type == 'response':
                http_sep = rec_body.find(b"\r\n\r\n")
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
