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
import gzip
import zlib
import urllib.robotparser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mirror_resources import discover, VERSION as DISCOVERY_VERSION
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
        u = urllib.parse.urlsplit(full)
        if u.scheme not in ('http', 'https') or not u.hostname or u.username or u.password:
            return None
        pairs = [(k, v) for k, v in urllib.parse.parse_qsl(u.query, keep_blank_values=True)
                 if k.lower() not in TRACKING_PARAMS and not k.lower().startswith('utm_')]
        pairs.sort(key=lambda pair: pair[0])
        host = u.hostname.lower()
        if ':' in host:
            host = f'[{host}]'
        port = u.port
        if port and not ((u.scheme == 'http' and port == 80) or (u.scheme == 'https' and port == 443)):
            host = f"{host}:{port}"
        return urllib.parse.urlunsplit((u.scheme, host, u.path or '/', urllib.parse.urlencode(pairs), ''))
    except ValueError:
        return None


def in_scope(url, allowed_domains):
    host = (urllib.parse.urlparse(url).hostname or '').lower()
    return any(host == d.lower() or host.endswith('.' + d.lower()) for d in allowed_domains)


class ScopedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Return redirects to the frontier so each hop receives a fresh permission gate."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def decode_payload(body, headers):
    """urllib removes chunk framing, but does not decode Content-Encoding."""
    for encoding in reversed(headers.get('content-encoding', '').lower().split(',')):
        encoding = encoding.strip()
        if encoding == 'gzip':
            body = gzip.decompress(body)
        elif encoding == 'deflate':
            body = zlib.decompress(body)
        elif encoding not in ('', 'identity'):
            raise ValueError(f'Unsupported content encoding: {encoding}')
    return body


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
        u = urllib.parse.urlsplit(url)
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
    max_depth = args.depth if args.depth is not None else profile.get('target', {}).get('max_depth', 4)
    max_pages = args.max_pages or profile.get('target', {}).get('max_pages', 500)

    politeness = PolitenessEngine(profile.get('politeness', {}))
    opener = urllib.request.build_opener(ScopedRedirectHandler())
    MAX_RETRIES = 3
    accepts_request_headers = 'request_headers' in inspect.signature(writer.write_response).parameters

    queue = collections.deque()
    pending, visited = set(), set()
    outcomes, limitations, robots = {}, [], {}
    policy = profile.get('politeness', {}).get('robots_policy', 'respect')
    target_config = profile.get('target', {})

    def enqueue(raw, base=None, depth=0):
        url = canonicalize_url(raw, base)
        if not url:
            limitations.append({'source': base, 'reason': 'unsupported_seed_or_reference'})
            return
        if url in outcomes:
            return
        reason = None
        path = urllib.parse.urlsplit(url).path
        if not in_scope(url, allowed_domains):
            reason = 'scope'
        elif depth > max_depth:
            reason = 'depth_limit'
        elif target_config.get('path_blacklist_regex') and re.search(target_config['path_blacklist_regex'], path, re.I):
            reason = 'path_blacklist'
        elif target_config.get('path_whitelist_regex') and not re.search(target_config['path_whitelist_regex'], path, re.I):
            reason = 'path_whitelist'
        outcomes[url] = {'url': url, 'state': 'excluded' if reason else 'pending', 'reason': reason}
        if not reason:
            queue.append((url, depth, 0)); pending.add(url)

    def requeue(url, depth, retries):
        if retries >= MAX_RETRIES:
            return
        visited.discard(url)
        queue.append((url, depth, retries + 1)); pending.add(url)
        outcomes[url].update(state='pending', reason='retry')

    def allowed_by_robots(url):
        if policy == 'ignore_authorised':
            return True
        u = urllib.parse.urlsplit(url)
        origin = f'{u.scheme}://{u.netloc}'
        if origin not in robots:
            robots_url = origin + '/robots.txt'
            robot = urllib.robotparser.RobotFileParser()
            if politeness.acquire_permission(robots_url)['aborted']:
                return False
            started = time.time()
            try:
                request = urllib.request.Request(robots_url, headers={'User-Agent':'AegisArchive/1.0'})
                with opener.open(request, timeout=15) as response:
                    data = response.read(1024 * 1024 + 1)
                    if len(data) > 1024 * 1024:
                        robot.parse(['User-agent: *', 'Disallow: /'])
                    else:
                        robot.parse(data.decode('utf-8', errors='replace').splitlines())
                    politeness.record_success(robots_url, int((time.time() - started) * 1000))
            except urllib.error.HTTPError as error:
                politeness.record_failure(robots_url, error.code, error.headers.get('Retry-After'))
                robot.parse(['User-agent: *', 'Disallow: /'] if error.code not in (404, 410) else [])
                error.close()
            except (OSError, ValueError):
                politeness.record_failure(robots_url, 0)
                robot.parse(['User-agent: *', 'Disallow: /'])
            robots[origin] = robot
        return robots[origin].can_fetch('AegisArchive', url)

    def archive_response(url, status, headers, body, request_headers):
        if accepts_request_headers:
            return writer.write_response(url, status, headers, body, request_headers=request_headers)
        return writer.write_response(url, status, headers, body)

    seeds = target_config.get('seed_urls', {})
    for tier in ('tier_1_core', 'tier_2_breadth', 'tier_3_discovery'):
        for raw in seeds.get(tier, []):
            enqueue(raw)
    print(f"[AegisArchive CLI] Output target: {warc_path}")
    while queue and len(visited) < max_pages:
        url, depth, retries = queue.popleft(); pending.discard(url)
        if url in visited:
            continue
        visited.add(url)
        if not allowed_by_robots(url):
            outcomes[url].update(state='excluded', reason='robots_policy')
            continue
        if politeness.acquire_permission(url)['aborted']:
            outcomes[url].update(state='pending', reason='aborted'); break
        req = urllib.request.Request(url, headers={'User-Agent':'AegisArchive/1.0 (Ethical Archival Preservation)'})
        start_t = time.time()
        try:
            with opener.open(req, timeout=15) as resp:
                body = resp.read()
                headers = normalize_headers(resp.headers.items())
                body = decode_payload(body, headers)
                status = resp.status
                archive_response(url, status, headers, body, dict(req.header_items()))
                politeness.record_success(url, int((time.time() - start_t) * 1000))
                outcomes[url].update(state='captured', reason=None, status=status, sha256=hashlib.sha256(body).hexdigest(), bytes=len(body))
                content_type = headers.get('content-type', '')
                if content_type.split(';')[0].strip().lower() in ('text/html','application/xhtml+xml','text/css'):
                    charset = resp.headers.get_content_charset() or 'utf-8'
                    try:
                        text = body.decode(charset, errors='strict')
                    except (LookupError, UnicodeError):
                        limitations.append({'source':url, 'reason':'unsupported_or_invalid_charset'}); continue
                    found = discover(text, content_type, url)
                    limitations.extend({'source':url, 'reason':reason} for reason in found['unsupported'])
                    for reference in found['resources']:
                        enqueue(reference['url'], url, depth + 1)
        except urllib.error.HTTPError as error:
            headers = normalize_headers(error.headers.items())
            if error.code in (301, 302, 303, 307, 308):
                body = decode_payload(error.read(), headers)
                archive_response(url, error.code, headers, body, dict(req.header_items()))
                outcomes[url].update(state='captured', reason=None, status=error.code, sha256=hashlib.sha256(body).hexdigest(), bytes=len(body))
                politeness.record_success(url, int((time.time() - start_t) * 1000))
                if headers.get('location'):
                    enqueue(headers['location'], url, depth)
                else:
                    limitations.append({'source':url,'reason':'redirect_without_location'})
            else:
                outcomes[url].update(state='failed',reason='http_error',status=error.code)
                counted = politeness.record_failure(url, error.code, error.headers.get('Retry-After'))
                if counted:
                    requeue(url, depth, retries)
            error.close()
        except (OSError, ValueError, EOFError) as error:
            outcomes[url].update(state='failed',reason='network_or_decode_error')
            politeness.record_failure(url, 0)
            requeue(url, depth, retries)

    writer.close()
    resources = sorted(outcomes.values(), key=lambda item: item['url'])
    counts = {state: sum(item['state'] == state for item in resources) for state in ('captured','excluded','failed','pending','unsupported')}
    def file_digest(path):
        digest = hashlib.sha256()
        with open(path, 'rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        return digest.hexdigest()
    receipt = {'schema_version':1, 'extractor_version':DISCOVERY_VERSION,
               'scope':'discovered_static_resource_graph', 'complete':bool(resources) and counts['captured'] == len(resources) and not limitations,
               'counts':counts, 'discovered':len(resources), 'resources':resources,
               'limitations':limitations, 'robots_policy':policy,
               'archives':{'warc':{'file':os.path.basename(warc_path),'sha256':file_digest(warc_path)},
                           'cdx':{'file':os.path.basename(writer.cdx_filepath),'sha256':file_digest(writer.cdx_filepath)}}}
    receipt_path = warc_path.replace('.warc', '.coverage.json')
    with open(receipt_path, 'w', encoding='utf-8') as stream:
        json.dump(receipt, stream, indent=2); stream.write('\n')
    print('[Coverage] ' + ('COMPLETE' if receipt['complete'] else 'INCOMPLETE') + f' static graph; receipt: {receipt_path}')
    captured_count = sum(item['state'] == 'captured' for item in outcomes.values())
    print(f'[AegisArchive CLI] Captured {captured_count} responses to {warc_path}')

if __name__ == "__main__":
    main()
