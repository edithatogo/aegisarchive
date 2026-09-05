#!/usr/bin/env python3
"""
AegisArchive - Headless CLI Archival Engine
Zero external dependencies (Python 3 standard library only).
Provides headless preservation for CI, cron, and server environments.

Licensed under the Apache License, Version 2.0.
"""

import sys
import os
import json
import time
import random
import uuid
import hashlib
import argparse
import urllib.request
import urllib.parse
from datetime import datetime, timezone
import re

def format_warc_date(dt=None):
    if dt is None:
        dt = datetime.now(timezone.utc)
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')

def format_cdx_date(dt=None):
    if dt is None:
        dt = datetime.now(timezone.utc)
    return dt.strftime('%Y%m%d%H%M%S')

def to_surt(url_str):
    try:
        u = urllib.parse.urlparse(url_str)
        host_parts = u.hostname.split('.')
        host_parts.reverse()
        port_part = f":{u.port}" if u.port else ""
        return f"{','.join(host_parts)}{port_part}){u.path}{'?' + u.query if u.query else ''}"
    except Exception:
        return url_str

class PythonWarcWriter:
    def __init__(self, filepath, operator="AegisArchive CLI", organization="Digital Preservation"):
        self.filepath = filepath
        self.cdx_filepath = filepath.replace('.warc', '.cdx')
        self.file = open(filepath, 'wb')
        self.cdx_file = open(self.cdx_filepath, 'w', encoding='utf-8')
        self.cdx_file.write(" CDX N b a m s k r M S V g\n")
        self.current_offset = 0
        self.payload_map = {} # sha256 -> { url, date, record_id }

        # Write warcinfo
        self._write_warcinfo(operator, organization)

    def _write_warcinfo(self, operator, organization):
        rec_id = f"<urn:uuid:{uuid.uuid4()}>"
        date_str = format_warc_date()
        content = (
            f"software: AegisArchive CLI v1.0 (ISO 28500:2017)\r\n"
            f"format: WARC File Format 1.1\r\n"
            f"conformance: ISO 28500:2017\r\n"
            f"operator: {operator}\r\n"
            f"organization: {organization}\r\n"
            f"description: Headless server-preserving forensic web archive\r\n"
        ).encode('utf-8')

        headers = (
            f"WARC/1.1\r\n"
            f"WARC-Type: warcinfo\r\n"
            f"WARC-Date: {date_str}\r\n"
            f"WARC-Filename: {os.path.basename(self.filepath)}\r\n"
            f"WARC-Record-ID: {rec_id}\r\n"
            f"Content-Type: application/warc-fields\r\n"
            f"Content-Length: {len(content)}\r\n\r\n"
        ).encode('utf-8')

        block = headers + content + b"\r\n\r\n"
        self.file.write(block)
        self.current_offset += len(block)

    def write_response(self, url, status, headers_dict, body_bytes):
        rec_id = f"<urn:uuid:{uuid.uuid4()}>"
        now = datetime.now(timezone.utc)
        warc_date = format_warc_date(now)
        cdx_date = format_cdx_date(now)

        digest = hashlib.sha256(body_bytes).hexdigest()
        is_revisit = (digest in self.payload_map and len(body_bytes) > 512)

        http_header_lines = [f"HTTP/1.1 {status} Response"]
        for k, v in headers_dict.items():
            http_header_lines.append(f"{k}: {v}")
        http_headers_block = ("\r\n".join(http_header_lines) + "\r\n\r\n").encode('utf-8')

        rec_offset = self.current_offset

        if is_revisit:
            orig = self.payload_map[digest]
            warc_headers = (
                f"WARC/1.1\r\n"
                f"WARC-Type: revisit\r\n"
                f"WARC-Target-URI: {url}\r\n"
                f"WARC-Date: {warc_date}\r\n"
                f"WARC-Record-ID: {rec_id}\r\n"
                f"WARC-Refers-To-Target-URI: {orig['url']}\r\n"
                f"WARC-Refers-To-Date: {orig['date']}\r\n"
                f"WARC-Profile: http://netpreserve.org/warc/1.1/revisit/identical-payload-digest\r\n"
                f"WARC-Payload-Digest: sha256:{digest}\r\n"
                f"Content-Type: application/http; msgtype=response\r\n"
                f"Content-Length: {len(http_headers_block)}\r\n\r\n"
            ).encode('utf-8')
            full_block = warc_headers + http_headers_block + b"\r\n\r\n"
        else:
            payload_len = len(http_headers_block) + len(body_bytes)
            warc_headers = (
                f"WARC/1.1\r\n"
                f"WARC-Type: response\r\n"
                f"WARC-Target-URI: {url}\r\n"
                f"WARC-Date: {warc_date}\r\n"
                f"WARC-Record-ID: {rec_id}\r\n"
                f"WARC-Payload-Digest: sha256:{digest}\r\n"
                f"Content-Type: application/http; msgtype=response\r\n"
                f"Content-Length: {payload_len}\r\n\r\n"
            ).encode('utf-8')
            full_block = warc_headers + http_headers_block + body_bytes + b"\r\n\r\n"
            self.payload_map[digest] = {"url": url, "date": warc_date}

        self.file.write(full_block)
        self.current_offset += len(full_block)

        # Write CDX
        surt = to_surt(url)
        mime = headers_dict.get('Content-Type', 'application/octet-stream').split(';')[0].strip()
        cdx_line = f"{surt} {cdx_date} {url} {mime} {status} {digest} - - {rec_offset} {os.path.basename(self.filepath)}\n"
        self.cdx_file.write(cdx_line)

        return {"digest": digest, "is_revisit": is_revisit}

    def close(self):
        self.file.close()
        self.cdx_file.close()

def main():
    parser = argparse.ArgumentParser(description="AegisArchive Headless Archival Engine")
    parser.add_argument("--profile", required=True, help="Path to profile JSON configuration")
    parser.add_argument("--output-dir", default="./archive", help="Directory to save WARC/CDX outputs")
    parser.add_argument("--max-pages", type=int, default=None, help="Override maximum page crawl ceiling")
    parser.add_argument("--depth", type=int, default=None, help="Override maximum crawl depth")
    args = parser.parse_args()

    with open(args.profile, 'r', encoding='utf-8') as f:
        profile = json.load(f)

    os.makedirs(args.output_dir, exist_ok=True)
    date_tag = datetime.now().strftime('%Y%m%d_%H%M%S')
    prefix = profile.get('archival', {}).get('warc_prefix', 'archive')
    warc_path = os.path.join(args.output_dir, f"{prefix}_{date_tag}.warc")

    writer = PythonWarcWriter(
        warc_path,
        operator=profile.get('archival', {}).get('operator', 'AegisArchive CLI'),
        organization=profile.get('archival', {}).get('organization', 'Digital Preservation')
    )

    allowed_domains = profile.get('target', {}).get('allowed_domains', [])
    max_depth = args.depth or profile.get('target', {}).get('max_depth', 4)
    max_pages = args.max_pages or profile.get('target', {}).get('max_pages', 500)
    min_delay = profile.get('politeness', {}).get('min_delay_ms', 1200) / 1000.0
    max_delay = profile.get('politeness', {}).get('max_delay_ms', 3200) / 1000.0

    queue = []
    seeds = profile.get('target', {}).get('seed_urls', {}).get('tier_1_core', [])
    for s in seeds:
        queue.append((s, 0))

    visited = set()
    print(f"[AegisArchive CLI] Started with profile: {profile.get('profile_name', 'Custom')}")
    print(f"[AegisArchive CLI] Output target: {warc_path}")

    while queue and len(visited) < max_pages:
        url, depth = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        # Polite delay
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)

        req = urllib.request.Request(url, headers={'User-Agent': 'AegisArchive/1.0 (Ethical Archival Preservation)'})
        start_t = time.time()
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                elapsed_ms = int((time.time() - start_t) * 1000)
                body = resp.read()
                headers = dict(resp.headers)
                status = resp.status
                writer.write_response(url, status, headers, body)
                print(f"[{status}] {url} ({len(body)} bytes, {elapsed_ms} ms)")

                # Extract links if HTML and within depth
                content_type = headers.get('Content-Type', '')
                if 'text/html' in content_type and depth < max_depth:
                    text = body.decode('utf-8', errors='ignore')
                    links = re.findall(r'href=["\']([^"\']+)["\']', text, re.IGNORECASE)
                    for raw in links:
                        full_url = urllib.parse.urljoin(url, raw)
                        parsed = urllib.parse.urlparse(full_url)
                        if parsed.scheme in ('http', 'https') and any(parsed.hostname == d or (parsed.hostname and parsed.hostname.endswith('.' + d)) for d in allowed_domains):
                            clean_url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
                            if clean_url not in visited and clean_url not in [q[0] for q in queue]:
                                queue.append((clean_url, depth + 1))
        except Exception as e:
            print(f"[Error] {url}: {e}")

    writer.close()
    print(f"[AegisArchive CLI] Completed! Archived {len(visited)} pages to {warc_path}")

if __name__ == "__main__":
    main()
