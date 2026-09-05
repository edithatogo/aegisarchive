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
import uuid
import hashlib
import argparse
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone
import re
import collections
import inspect

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from politeness import PolitenessEngine  # noqa: E402  (stdlib-only sibling module)

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


def normalize_headers(items):
    """Lowercases header names (http.client preserves the server's casing; lookups must not) (P1)."""
    return {str(k).lower(): v for k, v in items}


# Mirror of TRACKING_PARAMS in web/lib/core_crawler.js (kept identical by tests/test_cli_parity.py).
TRACKING_PARAMS = {
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'fbclid', 'gclid', 'session_id', 'jsessionid', 'phpsessid',
    '_ga', '_gl', 'msclkid', 'mc_cid', 'mc_eid'
}


def canonicalize_url(raw_url, base_url=None):
    """Mirror of CoreCrawler.canonicalizeUrl: http(s) only, lowercase host, default ports removed,
    fragment dropped, tracking params scrubbed, remaining query sorted and KEPT, trailing slash kept (P2)."""
    try:
        full = urllib.parse.urljoin(base_url, raw_url) if base_url else raw_url
        u = urllib.parse.urlparse(full)
        if u.scheme not in ('http', 'https') or not u.hostname:
            return None
        pairs = [(k, v) for k, v in urllib.parse.parse_qsl(u.query, keep_blank_values=True)
                 if k.lower() not in TRACKING_PARAMS and not k.lower().startswith('utm_')]
        pairs.sort()
        host = u.hostname.lower()
        port = u.port
        if port and not ((u.scheme == 'http' and port == 80) or (u.scheme == 'https' and port == 443)):
            host = f"{host}:{port}"
        return urllib.parse.urlunparse((u.scheme, host, u.path or '/', '', urllib.parse.urlencode(pairs), ''))
    except ValueError:
        return None


def in_scope(url, allowed_domains):
    host = (urllib.parse.urlparse(url).hostname or '').lower()
    return any(host == d.lower() or host.endswith('.' + d.lower()) for d in allowed_domains)


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

    def _write_request(self, url, request_headers, concurrent_to, warc_date):
        rec_id = f"<urn:uuid:{uuid.uuid4()}>"
        u = urllib.parse.urlparse(url)
        path = (u.path or "/") + (f"?{u.query}" if u.query else "")
        lines = [f"GET {path} HTTP/1.1", f"Host: {u.netloc}"] + [f"{k}: {v}" for k, v in request_headers.items()]
        body = ("\r\n".join(lines) + "\r\n\r\n").encode("utf-8")
        headers = (
            f"WARC/1.1\r\nWARC-Type: request\r\nWARC-Target-URI: {url}\r\nWARC-Date: {warc_date}\r\n"
            f"WARC-Record-ID: {rec_id}\r\nWARC-Concurrent-To: {concurrent_to}\r\n"
            f"Content-Type: application/http; msgtype=request\r\nContent-Length: {len(body)}\r\n\r\n"
        ).encode("utf-8")
        block = headers + body + b"\r\n\r\n"
        self.file.write(block)
        self.current_offset += len(block)
        return rec_id

    def write_response(self, url, status, headers_dict, body_bytes, request_headers=None):
        rec_id = f"<urn:uuid:{uuid.uuid4()}>"
        now = datetime.now(timezone.utc)
        warc_date = format_warc_date(now)
        cdx_date = format_cdx_date(now)

        req_id = self._write_request(url, request_headers, rec_id, warc_date) if request_headers is not None else None
        concurrent = f"WARC-Concurrent-To: {req_id}\r\n" if req_id else ""

        digest = hashlib.sha256(body_bytes).hexdigest()
        is_revisit = (digest in self.payload_map and len(body_bytes) > 512)

        omit = {"content-encoding", "transfer-encoding", "content-length"}
        http_header_lines = [f"HTTP/1.1 {status} Response"]
        for k, v in headers_dict.items():
            if k.lower() not in omit:
                http_header_lines.append(f"{k}: {v}")
        http_header_lines.append(f"Content-Length: {len(body_bytes)}")
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
                f"{concurrent}"
                f"WARC-Refers-To: {orig['record_id']}\r\n"
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
                f"{concurrent}"
                f"WARC-Payload-Digest: sha256:{digest}\r\n"
                f"Content-Type: application/http; msgtype=response\r\n"
                f"Content-Length: {payload_len}\r\n\r\n"
            ).encode('utf-8')
            full_block = warc_headers + http_headers_block + body_bytes + b"\r\n\r\n"
            self.payload_map[digest] = {"url": url, "date": warc_date, "record_id": rec_id}

        self.file.write(full_block)
        self.current_offset += len(full_block)

        # Write CDX
        surt = to_surt(url)
        content_type = next((v for k, v in headers_dict.items() if k.lower() == 'content-type'), 'application/octet-stream')
        mime = content_type.split(';')[0].strip()
        cdx_line = f"{surt} {cdx_date} {url} {mime} {status} {digest} - - {len(full_block)} {rec_offset} {os.path.basename(self.filepath)}\n"
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

    politeness = PolitenessEngine(profile.get('politeness', {}))
    MAX_RETRIES = 3
    accepts_request_headers = 'request_headers' in inspect.signature(writer.write_response).parameters

    def requeue(url, depth, retries):
        if retries >= MAX_RETRIES:
            print(f"[Retry] Abandoning {url} after {MAX_RETRIES} retries")
            return
        visited.discard(url)
        queue.append((url, depth, retries + 1))
        pending.add(url)
        print(f"[Retry {retries + 1}/{MAX_RETRIES}] Re-queued {url}")

    queue = collections.deque()
    pending = set()
    seeds = profile.get('target', {}).get('seed_urls', {}).get('tier_1_core', [])
    for s in seeds:
        canon = canonicalize_url(s)
        if canon and canon not in pending:
            queue.append((canon, 0, 0))
            pending.add(canon)

    visited = set()
    print(f"[AegisArchive CLI] Started with profile: {profile.get('profile_name', 'Custom')}")
    print(f"[AegisArchive CLI] Output target: {warc_path}")

    while queue and len(visited) < max_pages:
        url, depth, retries = queue.popleft()
        pending.discard(url)
        if url in visited:
            continue
        visited.add(url)

        gate = politeness.acquire_permission(url)
        if gate['aborted']:
            print("[AegisArchive CLI] Stop requested; finalizing.")
            break

        if urllib.parse.urlparse(url).scheme not in ('http', 'https'):
            print(f"[SKIP] {url} (non-HTTP scheme)")
            continue
        req = urllib.request.Request(url, headers={'User-Agent': 'AegisArchive/1.0 (Ethical Archival Preservation)'})
        start_t = time.time()
        try:
            # Scheme allow-listed above; audit rules cannot see that guard.
            with urllib.request.urlopen(req, timeout=15) as resp:  # nosec B310  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
                elapsed_ms = int((time.time() - start_t) * 1000)
                body = resp.read()
                headers = normalize_headers(resp.headers.items())
                status = resp.status
                politeness.record_success(url, elapsed_ms)
                if accepts_request_headers:
                    writer.write_response(url, status, headers, body, request_headers=dict(req.header_items()))
                else:
                    writer.write_response(url, status, headers, body)
                print(f"[{status}] {url} ({len(body)} bytes, {elapsed_ms} ms)")

                # Extract links if HTML and within depth
                content_type = headers.get('content-type', '')
                if 'text/html' in content_type and depth < max_depth:
                    text = body.decode('utf-8', errors='ignore')
                    links = re.findall(r'(?:href|src)=["\']([^"\']+)["\']', text, re.IGNORECASE)
                    for raw in links:
                        clean_url = canonicalize_url(raw, url)
                        if not clean_url or not in_scope(clean_url, allowed_domains):
                            continue
                        if clean_url not in visited and clean_url not in pending:
                            queue.append((clean_url, depth + 1, 0))
                            pending.add(clean_url)
        except urllib.error.HTTPError as e:
            counted = politeness.record_failure(url, e.code, e.headers.get('Retry-After') if e.headers else None)
            print(f"[HTTP {e.code}] {url}{' (counted toward breaker)' if counted else ''}")
            if counted:
                requeue(url, depth, retries)
        except Exception as e:
            politeness.record_failure(url, 0)
            print(f"[Error] {url}: {e}")
            requeue(url, depth, retries)

    writer.close()
    print(f"[AegisArchive CLI] Completed! Archived {len(visited)} pages to {warc_path}")

if __name__ == "__main__":
    main()
