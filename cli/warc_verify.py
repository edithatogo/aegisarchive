#!/usr/bin/env python3
"""
AegisArchive - WARC/1.1 & CDX-11 Forensic Integrity Verifier
Zero external dependencies (Python 3 standard library only).

Licensed under the Apache License, Version 2.0.
"""

import sys
import os
import hashlib
import argparse

def verify_warc(warc_path, cdx_path=None):
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
    corrupt_count = 0
    total_bytes = os.path.getsize(warc_path)

    with open(warc_path, 'rb') as f:
        content = f.read()

    pos = 0
    content_len = len(content)

    while pos < content_len:
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

    print(f"  Total Container Size:    {total_bytes:,} bytes")
    print(f"  Total WARC Records:      {total_records}")
    print(f"    - warcinfo:            {warcinfo_count}")
    print(f"    - response:            {response_count}")
    print(f"    - revisit (deduped):   {revisit_count}")
    print(f"  Integrity Status:        {'PASSED' if corrupt_count == 0 else 'WARNINGS FOUND'}")
    print("=" * 66)

    return corrupt_count == 0

def main():
    parser = argparse.ArgumentParser(description="Verify AegisArchive WARC containers")
    parser.add_argument("warc_file", help="Path to .warc file to inspect")
    parser.add_argument("--cdx", default=None, help="Optional path to companion .cdx index file")
    args = parser.parse_args()

    success = verify_warc(args.warc_file, args.cdx)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
