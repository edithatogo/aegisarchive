# Track Plan: Headless CLI Parity with the Browser Engine

## Status: PLANNED

Conventions: paths relative to the repository root; line numbers refer to `cli/aegis_cli.py` at commit `3f00f46` (re-locate by the quoted snippet if `warc_interop_20260905` W1/W2/W4/W6 already shifted them); Verify commands run from the repository root with Python >= 3.9; complete a task only when every "Done when" item holds. Edit only the files under **Files**. Never create `._*` files. Standard library only — no `pip install`. Do not commit or push unless the operator explicitly asks. Fixtures live under `tempfile`/`/tmp`, never inside the repository.

## Phase 1 — Specification & approval

- [ ] Capture reproduced defects P1–P5 and requirements R1–R6 in `spec.md` (traces to AC1–AC6).
- [ ] Approval basis: user requested Conductor planning artifacts for the 2026-09-05 review; implementation waits for the integrator to register the track.

## Phase 2 — Correctness of the existing CLI

- [ ] **C1 Case-insensitive response headers** *(AC1)*

  **Files**: `cli/aegis_cli.py` only.

  **Change**:
  1. Add after `to_surt` (after line 41):
     ```python
     def normalize_headers(items):
         """Lowercases header names (http.client preserves the server's casing; lookups must not) (P1)."""
         return {str(k).lower(): v for k, v in items}
     ```
  2. Line 134 `        mime = headers_dict.get('Content-Type', 'application/octet-stream').split(';')[0].strip()` ->
     ```python
             content_type = next((v for k, v in headers_dict.items() if k.lower() == 'content-type'), 'application/octet-stream')
             mime = content_type.split(';')[0].strip()
     ```
  3. Line 197 `                headers = dict(resp.headers)` -> `                headers = normalize_headers(resp.headers.items())`.
  4. Line 203 `                content_type = headers.get('Content-Type', '')` -> `                content_type = headers.get('content-type', '')`.

  **Verify**:
  ```
  python3 -c "
  import sys,tempfile,os;sys.path.insert(0,'cli');import aegis_cli as a
  print(a.normalize_headers([('Content-type','text/html'),('X-A','1')]))
  d=tempfile.mkdtemp();p=os.path.join(d,'t.warc');w=a.PythonWarcWriter(p);w.write_response('http://h.test/',200,{'Content-type':'text/html; charset=utf-8'},b'x');w.close()
  print(open(p.replace('.warc','.cdx')).read().strip().split('\n')[1].split()[3])"
  ```
  Expected: `{'content-type': 'text/html', 'x-a': '1'}` then `text/html`.

  **Done when**: output matches; `python3 -m py_compile cli/aegis_cli.py` exits 0; `python3 cli/aegis_cli.py --help` exits 0.

  **Do not**: change the header casing written into the WARC HTTP block beyond what `normalize_headers` produces (lowercase names are valid HTTP); do not touch `warc_verify.py`.

- [ ] **C2 Keep query strings; canonicalise like the browser** *(AC2)*

  **Files**: `cli/aegis_cli.py` only.

  **Change**:
  1. Add after `normalize_headers` (C1):
     ```python
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
     ```
  2. Lines 174–175 (`for s in seeds:` / `queue.append((s, 0))`) ->
     ```python
         for s in seeds:
             canon = canonicalize_url(s)
             if canon:
                 queue.append((canon, 0))
     ```
  3. Lines 206–213 (link extraction loop) ->
     ```python
                         links = re.findall(r'(?:href|src)=["\']([^"\']+)["\']', text, re.IGNORECASE)
                         for raw in links:
                             clean_url = canonicalize_url(raw, url)
                             if not clean_url or not in_scope(clean_url, allowed_domains):
                                 continue
                             if clean_url not in visited and clean_url not in [q[0] for q in queue]:
                                 queue.append((clean_url, depth + 1))
     ```
     (the O(n) membership test is replaced in C3).

  **Verify**:
  ```
  python3 -c "
  import sys;sys.path.insert(0,'cli');import aegis_cli as a
  print(a.canonicalize_url('https://Example.org/docs/?ref=nav&utm_x=1&b=2'));print(a.canonicalize_url('https://example.org:443/a#frag'));print(a.canonicalize_url('../x?q=1','http://h.test/a/b/'));print(a.canonicalize_url('mailto:a@b.test'));print(a.canonicalize_url('http://127.0.0.1:8123/c?utm_source=x&id=2'));print(a.in_scope('http://sub.h.test/x',['h.test']),a.in_scope('http://evil-h.test/x',['h.test']))"
  ```
  Expected: `https://example.org/docs/?b=2&ref=nav`, `https://example.org/a`, `http://h.test/a/x?q=1`, `None`, `http://127.0.0.1:8123/c?id=2`, `True False`.

  **Done when**: output matches; `py_compile` exits 0.

  **Do not**: strip the trailing slash; do not remove `ref`/`source` from the URL (they are functional parameters); do not add `path_whitelist_regex` handling (out of scope).

- [ ] **C3 O(1) frontier: `deque` + `pending` set** *(AC3)*

  **Files**: `cli/aegis_cli.py` only. Requires C2.

  **Change**:
  1. Add `import collections` to the imports (after `import re`, line 21).
  2. Line 172 `    queue = []` -> `    queue = collections.deque()` and add `    pending = set()` on the next line.
  3. In the seed loop (C2 step 2), guard with `if canon and canon not in pending:` and add `pending.add(canon)` after `queue.append(...)`.
  4. Line 182 `        url, depth = queue.pop(0)` -> `        url, depth = queue.popleft()` followed by `        pending.discard(url)`.
  5. In the link loop (C2 step 3), `if clean_url not in visited and clean_url not in [q[0] for q in queue]:` -> `if clean_url not in visited and clean_url not in pending:` and add `pending.add(clean_url)` after `queue.append(...)`.

  **Verify**:
  ```
  grep -c "for q in queue" cli/aegis_cli.py; grep -c "collections.deque()" cli/aegis_cli.py; grep -c "pending" cli/aegis_cli.py; python3 -m py_compile cli/aegis_cli.py && echo compiled
  ```
  Expected: `0`, `1`, a number `>= 5`, `compiled`.

  **Done when**: output matches; C1 and C2 Verify still pass.

  **Do not**: change the depth-first/breadth-first order (FIFO is preserved by `popleft`); do not introduce a priority queue.

## Phase 3 — Politeness engine port

- [ ] **C4 Create `cli/politeness.py` (stdlib port of the browser engine)** *(AC4)*

  **Files** (create): `cli/politeness.py`. Do not modify `web/lib/politeness_engine.js`.

  **Change**: create the file with exactly this content (208 lines; a self-contained new module — the only task allowed to exceed the 60-line target):
  ```python
  #!/usr/bin/env python3
  """
  AegisArchive - Politeness engine (Python port of web/lib/politeness_engine.js)
  Zero external dependencies (Python 3 standard library only).

  Token bucket, decorrelated full-jitter back-off, EWMA latency with a median warm-up
  baseline, circuit breaker (NOMINAL -> THROTTLED -> TRIPPED -> HALF_OPEN) and
  RFC 9110 Retry-After handling (delta-seconds and HTTP-date, capped).

  Licensed under the Apache License, Version 2.0.
  """

  import math
  import random
  import threading
  import time
  from email.utils import parsedate_to_datetime
  from urllib.parse import urlparse


  class CircuitState:
      NOMINAL = "NOMINAL"
      THROTTLED = "THROTTLED"
      TRIPPED = "TRIPPED"
      HALF_OPEN = "HALF_OPEN"


  def _host_of(url):
      try:
          return (urlparse(url).hostname or "").lower() or None
      except (TypeError, ValueError):
          return None


  class PolitenessEngine:
      """Mirror of the browser engine. Times are seconds internally; the public API uses milliseconds."""

      def __init__(self, config=None, stop_event=None, clock=None, sleeper=None):
          config = config or {}
          self.min_delay_ms = config.get("min_delay_ms") or 1200
          self.max_delay_ms = config.get("max_delay_ms") or 3500
          self.jitter_distribution = config.get("jitter_distribution") or "gaussian"
          self.max_rpm = config.get("max_requests_per_minute") or 30
          self.burst_limit = config.get("burst_limit") or 5
          self.respect_retry_after = config.get("respect_retry_after", True) is not False
          self.adaptive_ewma = config.get("adaptive_ewma_backoff", True) is not False
          self.consecutive_error_tripwire = config.get("consecutive_error_tripwire") or 3
          self.cooldown_seconds = config.get("cooldown_seconds") or 60

          self.stop_event = stop_event or threading.Event()
          self._clock = clock or time.time      # returns seconds
          self._sleeper = sleeper               # optional: sleeper(seconds) -> bool (False = interrupted)

          # Token bucket
          self.tokens = float(self.burst_limit)
          self.last_token_refill = self._clock()
          self.token_fill_rate_per_ms = self.max_rpm / 60000.0

          # Latency EWMA + warm-up baseline
          self.ewma_alpha = 0.2
          self.ewma_latency_ms = None
          self.baseline_latency_ms = None
          self.warmup_size = 10
          self.warmup_samples = []
          self.baseline_drift_alpha = 0.02

          # Back-off and circuit breaker
          self.consecutive_errors = 0
          self.current_backoff_delay_ms = self.min_delay_ms
          self.circuit_state = CircuitState.NOMINAL
          self.circuit_trip_timestamp = None
          self.domain_cooldowns = {}  # host -> wake epoch (seconds)

      # -- helpers -------------------------------------------------------------
      @staticmethod
      def is_countable_failure(status):
          try:
              s = int(status)
          except (TypeError, ValueError):
              return False
          return s == 0 or s == 429 or 500 <= s <= 599

      def parse_retry_after(self, header_value):
          if not header_value:
              return None
          value = str(header_value).strip()
          if value.isdigit():
              return int(value) * 1000
          try:
              dt = parsedate_to_datetime(value)
          except (TypeError, ValueError, IndexError):
              return None
          if dt is None:
              return None
          return max(1000, int((dt.timestamp() - self._clock()) * 1000))

      def _sleep(self, ms):
          """Interruptible sleep. Returns False when stop_event was set."""
          if ms <= 0:
              return not self.stop_event.is_set()
          if self._sleeper is not None:
              return bool(self._sleeper(ms / 1000.0))
          return not self.stop_event.wait(ms / 1000.0)

      def refill_tokens(self):
          now = self._clock()
          elapsed_ms = (now - self.last_token_refill) * 1000.0
          self.tokens = min(float(self.burst_limit), self.tokens + elapsed_ms * self.token_fill_rate_per_ms)
          self.last_token_refill = now

      def calculate_jitter(self, min_ms, max_ms):
          if self.jitter_distribution == "uniform":
              return int(min_ms + random.random() * (max_ms - min_ms))
          mean = (min_ms + max_ms) / 2.0
          std_dev = (max_ms - min_ms) / 6.0
          sample = int(round(random.gauss(mean, std_dev)))
          return max(min_ms, min(max_ms, sample))

      def calculate_decorrelated_backoff(self):
          base = self.min_delay_ms
          cap = max(30000, self.max_delay_ms * 10)
          upper = max(base, self.current_backoff_delay_ms * 3)
          self.current_backoff_delay_ms = min(cap, int(base + random.random() * (upper - base)))
          return self.current_backoff_delay_ms

      # -- recording -----------------------------------------------------------
      def record_success(self, url, latency_ms):
          self.consecutive_errors = 0
          self.current_backoff_delay_ms = self.min_delay_ms
          if self.ewma_latency_ms is None:
              self.ewma_latency_ms = latency_ms
          else:
              self.ewma_latency_ms = int(round(self.ewma_alpha * latency_ms + (1 - self.ewma_alpha) * self.ewma_latency_ms))
          if len(self.warmup_samples) < self.warmup_size:
              self.warmup_samples.append(latency_ms)
              if len(self.warmup_samples) == self.warmup_size:
                  ordered = sorted(self.warmup_samples)
                  self.baseline_latency_ms = ordered[len(ordered) // 2]
          else:
              self.baseline_latency_ms = int(round(
                  (1 - self.baseline_drift_alpha) * self.baseline_latency_ms + self.baseline_drift_alpha * latency_ms
              ))
          if self.circuit_state in (CircuitState.HALF_OPEN, CircuitState.THROTTLED):
              self.circuit_state = CircuitState.NOMINAL

      def record_failure(self, url, status, retry_after_header=None):
          """Returns True when the failure counted toward the breaker (0/429/5xx), else False."""
          if not self.is_countable_failure(status):
              return False
          self.consecutive_errors += 1
          retry_ms = self.parse_retry_after(retry_after_header) if self.respect_retry_after else None
          if retry_ms:
              cap_ms = self.cooldown_seconds * 10 * 1000
              host = _host_of(url)
              if host:
                  self.domain_cooldowns[host] = self._clock() + min(retry_ms, cap_ms) / 1000.0
          if self.consecutive_errors >= self.consecutive_error_tripwire:
              self.circuit_state = CircuitState.TRIPPED
              self.circuit_trip_timestamp = self._clock()
          else:
              self.circuit_state = CircuitState.THROTTLED
              self.calculate_decorrelated_backoff()
          return True

      # -- gate ----------------------------------------------------------------
      def acquire_permission(self, target_url):
          """Blocks until it is polite to send the next request. Returns {delay_ms, state, aborted}."""
          aborted = {"delay_ms": 0, "state": self.circuit_state, "aborted": True}
          if self.circuit_state == CircuitState.TRIPPED:
              remaining = self.cooldown_seconds - (self._clock() - self.circuit_trip_timestamp)
              if remaining > 0 and not self._sleep(remaining * 1000.0):
                  return aborted
              self.circuit_state = CircuitState.HALF_OPEN
          host = _host_of(target_url)
          wake = self.domain_cooldowns.get(host)
          if wake and self._clock() < wake:
              if not self._sleep((wake - self._clock()) * 1000.0):
                  return aborted
              self.domain_cooldowns.pop(host, None)
          self.refill_tokens()
          if self.tokens < 1.0:
              wait_ms = math.ceil((1.0 - self.tokens) / self.token_fill_rate_per_ms)
              if not self._sleep(wait_ms):
                  return aborted
              self.refill_tokens()
          self.tokens -= 1.0
          delay = self.calculate_jitter(self.min_delay_ms, self.max_delay_ms)
          if self.adaptive_ewma and self.ewma_latency_ms and self.baseline_latency_ms:
              strain = self.ewma_latency_ms / max(50, self.baseline_latency_ms)
              if strain > 1.35:
                  delay = int(round(delay * min(3.0, strain)))
                  if self.circuit_state == CircuitState.NOMINAL:
                      self.circuit_state = CircuitState.THROTTLED
          if self.circuit_state == CircuitState.THROTTLED:
              delay = max(delay, self.current_backoff_delay_ms)
          if not self._sleep(delay):
              return aborted
          return {"delay_ms": delay, "state": self.circuit_state, "aborted": False}

      def get_telemetry(self):
          return {
              "circuit_state": self.circuit_state,
              "consecutive_errors": self.consecutive_errors,
              "ewma_latency_ms": self.ewma_latency_ms or 0,
              "baseline_latency_ms": self.baseline_latency_ms or 0,
              "available_tokens": round(self.tokens, 2),
              "max_rpm": self.max_rpm,
          }
  ```

  **Verify**:
  ```
  python3 -c "
  import sys;sys.path.insert(0,'cli');from politeness import PolitenessEngine as P, CircuitState
  e=P({});e.record_success('u',5);print(e.baseline_latency_ms);[e.record_success('u',300) for _ in range(9)];print(e.baseline_latency_ms,len(e.warmup_samples));e.record_success('u',1000);print(e.baseline_latency_ms)
  f=P({});[f.record_failure('http://h.test/',404) for _ in range(3)];print(f.circuit_state,f.consecutive_errors);[f.record_failure('http://h.test/',503) for _ in range(3)];print(f.circuit_state)
  g=P({'cooldown_seconds':60});g.record_failure('http://h.test/',429,'999999');print(g.domain_cooldowns['h.test']-__import__('time').time()<=600.5)
  import threading,time;h=P({'cooldown_seconds':60});h.record_failure('http://h.test/',429,'120');threading.Timer(0.05,h.stop_event.set).start();t=time.time();r=h.acquire_permission('http://h.test/');print(r['aborted'],time.time()-t<1)
  k=P({'min_delay_ms':1,'max_delay_ms':2});print(k.acquire_permission('http://h.test/')['aborted'])"
  ```
  Expected (eight lines): `None`, `300 10`, `314`, `NOMINAL 0`, `TRIPPED`, `True`, `True True`, `False`.

  **Done when**: output matches; `python3 -m py_compile cli/politeness.py` exits 0; `python3 -c "import sys;sys.path.insert(0,'cli');import politeness"` prints nothing.

  **Do not**: import anything outside the standard library; do not add a CLI entry point to this module; do not change the numeric constants (0.2, 10, 0.02, 1.35, 3.0, 30000, x10 cap) — they mirror the browser engine.

- [ ] **C5 Wire the engine into `aegis_cli.py` with retry budget** *(AC5)*

  **Files**: `cli/aegis_cli.py` only. Requires C1–C4.

  **Change**:
  1. Add imports after `import collections` (C3): `import inspect`, `import urllib.error`, and
     ```python
     sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
     from politeness import PolitenessEngine  # noqa: E402  (stdlib-only sibling module)
     ```
  2. Delete lines 169–170 (`min_delay = ...` / `max_delay = ...`) and insert instead:
     ```python
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
     ```
  3. Queue entries become 3-tuples: seed append -> `queue.append((canon, 0, 0))`; link append -> `queue.append((clean_url, depth + 1, 0))`; pop -> `url, depth, retries = queue.popleft()`.
  4. Replace lines 187–189 (`# Polite delay` / `delay = random.uniform(...)` / `time.sleep(delay)`) with:
     ```python
             gate = politeness.acquire_permission(url)
             if gate['aborted']:
                 print("[AegisArchive CLI] Stop requested; finalizing.")
                 break
     ```
  5. Inside the `with urllib.request.urlopen(...) as resp:` block, after `status = resp.status` add `                politeness.record_success(url, elapsed_ms)`, and change the writer call to:
     ```python
                     if accepts_request_headers:
                         writer.write_response(url, status, headers, body, request_headers=dict(req.header_items()))
                     else:
                         writer.write_response(url, status, headers, body)
     ```
  6. Replace the single `except Exception as e:` handler (lines 214–215) with:
     ```python
             except urllib.error.HTTPError as e:
                 counted = politeness.record_failure(url, e.code, e.headers.get('Retry-After') if e.headers else None)
                 print(f"[HTTP {e.code}] {url}{' (counted toward breaker)' if counted else ''}")
                 if counted:
                     requeue(url, depth, retries)
             except Exception as e:
                 politeness.record_failure(url, 0)
                 print(f"[Error] {url}: {e}")
                 requeue(url, depth, retries)
     ```
  7. Remove `import random` if no longer used (`grep -n "random\." cli/aegis_cli.py` must print nothing before removing).

  **Verify** (ephemeral loopback server; nothing is written inside the repository):
  ```
  python3 - <<'EOF'
  import json, os, subprocess, sys, tempfile, threading
  from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
  PAGES = {'/': b'<a href="/b">b</a><a href="/c?utm_source=x&id=2">c</a><a href="/doc.pdf">pdf</a><a href="/r">r</a>', '/b': b'<p>b</p>', '/c?id=2': b'<p>c</p>'}
  hits = {'/r': 0}
  class H(BaseHTTPRequestHandler):
      def do_GET(self):
          if self.path == '/r':
              hits['/r'] += 1
              if hits['/r'] == 1:
                  self.send_response(503); self.send_header('Retry-After', '1'); self.send_header('Content-Length', '0'); self.end_headers(); return
              body, ct = b'<p>r</p>', 'text/html'
          elif self.path == '/doc.pdf':
              body, ct = b'%PDF-1.4 fake', 'application/pdf'
          elif self.path in PAGES:
              body, ct = PAGES[self.path], 'text/html; charset=utf-8'
          else:
              self.send_response(404); self.send_header('Content-Length', '0'); self.end_headers(); return
          self.send_response(200); self.send_header('Content-type', ct); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
      def log_message(self, *a): pass
  srv = ThreadingHTTPServer(('127.0.0.1', 0), H); port = srv.server_address[1]
  threading.Thread(target=srv.serve_forever, daemon=True).start()
  tmp = tempfile.mkdtemp()
  profile = {"profile_id": "t", "profile_name": "t", "target": {"allowed_domains": ["127.0.0.1"], "seed_urls": {"tier_1_core": [f"http://127.0.0.1:{port}/"]}, "max_depth": 3, "max_pages": 50},
             "politeness": {"min_delay_ms": 250, "max_delay_ms": 300, "max_requests_per_minute": 300, "burst_limit": 20, "cooldown_seconds": 5}, "archival": {"warc_prefix": "t"}}
  pp = os.path.join(tmp, 'p.json'); json.dump(profile, open(pp, 'w'))
  r = subprocess.run([sys.executable, 'cli/aegis_cli.py', '--profile', pp, '--output-dir', tmp], capture_output=True, text=True, timeout=120)
  warc = [f for f in os.listdir(tmp) if f.endswith('.warc')][0]
  data = open(os.path.join(tmp, warc), 'rb').read()
  cdx = [l for l in open(os.path.join(tmp, warc[:-5] + '.cdx')).read().splitlines()[1:] if l.strip()]
  print(r.returncode, data.count(b'WARC-Type: response'), len(cdx), {len(l.split()) for l in cdx}, any('application/pdf' in l for l in cdx), any('/c?id=2' in l for l in cdx), hits['/r'], any(l.split()[2].endswith('/r') and l.split()[4] == '200' for l in cdx))
  srv.shutdown()
  EOF
  ```
  Expected: `0 5 5 {11} True True 2 True` (with `warc_interop_20260905` W2 applied; before W2 the set prints `{10}`). The five responses are `/`, `/b`, `/c?id=2`, `/doc.pdf` and `/r` (archived on its second attempt after the 503 + `Retry-After: 1`).

  **Done when**: output matches; `python3 cli/aegis_cli.py --help` exits 0; C1–C3 Verify still pass; `grep -c "time.sleep" cli/aegis_cli.py` prints `0`.

  **Do not**: add concurrency; do not fetch robots.txt (out of scope); do not change CLI flag names; do not bypass `acquire_permission` for any request.

## Phase 4 — Tests

- [ ] **C6 Tests to add (stdlib only)** *(AC5, AC6; regression for AC1–AC4)*

  **Files** (create): `tests/test_cli.py`, `tests/test_politeness.py`, `tests/test_cli_parity.py`. Create `tests/` if absent (other tracks may already have created it; never delete their files).

  **Change**:
  - `tests/test_cli.py` — `unittest.TestCase` with a class-level fixture like the C5 Verify server (`ThreadingHTTPServer(("127.0.0.1", 0), Handler)`, 3 HTML pages sent with `Content-type` casing + 1 PDF; the root page's `/r` link is only emitted when the handler class attribute `WITH_RETRY` is true), a profile written to `tempfile.TemporaryDirectory()`, and the CLI run through `subprocess.run([sys.executable, <repo>/cli/aegis_cli.py, ...], timeout=120)`. Test 1 (`WITH_RETRY = False`): return code 0; `WARC-Type: response` count 4; CDX data lines 4, each with 11 fields; a line with MIME `application/pdf`; a line whose URL ends with `/c?id=2`. Test 2 (`WITH_RETRY = True`, `/r` answers 503 + `Retry-After: 1` then 200): 5 response records, `/r` archived with status `200`, served exactly twice. Test 3: `--help` exits 0.
  - `tests/test_politeness.py` — unit tests reproducing the C4 Verify lines, plus: `parse_retry_after` HTTP-date returns `>= 1000`, garbage returns `None`; a `sleeper` stub proves `acquire_permission` waits for the token bucket when `burst_limit=1` and `max_requests_per_minute=60` (second call requests a sleep of about 1000 ms); `get_telemetry()` keys.
  - `tests/test_cli_parity.py` — reads `web/lib/core_crawler.js`, extracts the `TRACKING_PARAMS = new Set([...])` literal with a regex, parses the quoted strings and asserts equality with `aegis_cli.TRACKING_PARAMS`; also asserts `aegis_cli.canonicalize_url` matches the browser's expected outputs for the AC2 vectors.

  **Verify**:
  ```
  python3 -m unittest discover -s tests -p 'test_*.py' -v
  ```
  Expected: every test `ok`, final line `OK`.

  **Done when**: the command exits 0 on a clean checkout; tests bind only `127.0.0.1`, write only under `tempfile`, and finish in under 30 s.

  **Do not**: add `requirements*.txt`, `pytest`, or `package.json`; do not edit `.github/workflows/ci.yml` (G3); do not edit other tracks' test files.

## Phase 5 — Completion

- [ ] **F1** Final validation: all Verify commands of C1–C6; `python3 -m py_compile cli/aegis_cli.py cli/politeness.py cli/warc_verify.py cli/launch.py mcp/server.py`; leak-prevention gate clean; append `checkpoint_validated` to `evidence.jsonl`.
- [ ] **F2** Update `metadata.json` (`status`, `updated_at`); hand registry update (G2) and CI wiring (G3: unittest step + `cli/politeness.py` in the `py_compile` list) to the integrator.
