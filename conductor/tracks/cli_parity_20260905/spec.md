# Track Specification: Headless CLI Parity with the Browser Engine

## Overview

`cli/aegis_cli.py` is the headless counterpart of the browser crawler but implements a much weaker crawl: header lookups are case-sensitive, query strings are dropped, the queue membership test is linear, and politeness is a plain `random.uniform` sleep with no rate limit, back-off, breaker or `Retry-After` handling. A review reproduced the header defect end-to-end (against a server sending `Content-type`, the CLI followed 0 links and recorded `application/octet-stream` in the CDX). This track ports the engine to a stdlib-only `cli/politeness.py`, aligns URL handling with the browser, and adds a local `http.server` test fixture.

## Authoritative inputs

- Repository invariants: `AGENTS.md` (stdlib-only CLI, all crawler egress through a politeness engine); workflow guardrails: `conductor/workflow.md`.
- Template conventions: `conductor/tracks/portable_station_hardening_20260905/`.
- Reference implementation: `web/lib/politeness_engine.js` and `web/lib/core_crawler.js` as amended by `engine_correctness_20260905` (warm-up baseline, countable failures, retry budget, Retry-After cap, canonicalization).

## Reproduced defects

- **P1** `headers = dict(resp.headers)` then `headers.get('Content-Type')`: `http.client` preserves the server's casing, so `Content-type` (lowercase t) yields no match; HTML pages are not parsed for links and the CDX MIME field falls back to `application/octet-stream`.
- **P2** Link normalisation uses `urlunparse((scheme, netloc, path, '', '', ''))`, discarding every query string, so `?id=2`-style resources collapse onto one URL and are never captured; tracking parameters are not scrubbed either.
- **P3** `clean_url not in [q[0] for q in queue]` is O(n) per discovered link; with thousands of queued URLs discovery becomes quadratic.
- **P4** Politeness is `time.sleep(random.uniform(min, max))`: no token bucket, no EWMA adaptation, no circuit breaker, no `Retry-After`, no retry of transient failures, and no way to interrupt a sleep.
- **P5** No automated test exercises the CLI against a real HTTP server.

## Requirements

- **R1 — Case-insensitive headers**: response header keys are normalised to lowercase (`normalize_headers`), and the writer looks up `content-type` case-insensitively.
- **R2 — URL canonicalisation parity**: `canonicalize_url(raw, base=None)` mirrors `CoreCrawler.canonicalizeUrl`: http(s) only, lowercase host, default ports removed, fragment dropped, tracking parameters (same `TRACKING_PARAMS` set as the browser, `utm_*` prefix) scrubbed, remaining query parameters sorted and kept, trailing slash preserved; seeds and discovered links both pass through it; scope check mirrors `allowed_domains` suffix matching.
- **R3 — O(1) frontier**: the queue is a `collections.deque` of `(url, depth, retries)` with a companion `pending` set kept in sync.
- **R4 — Politeness engine port**: `cli/politeness.py` (stdlib only) provides `CircuitState`, `PolitenessEngine(config, stop_event=None, clock=None, sleeper=None)` with `is_countable_failure`, `parse_retry_after` (delta-seconds and HTTP-date), token bucket, gaussian/uniform jitter, decorrelated full-jitter back-off, EWMA with 10-sample median warm-up and 0.02 drift, circuit breaker, `Retry-After` capped at `cooldown_seconds * 10`, interruptible sleeps via `threading.Event`, `acquire_permission(url) -> {delay_ms, state, aborted}` and `get_telemetry()`.
- **R5 — Engine wiring**: `aegis_cli.py` calls `acquire_permission` before every request, `record_success` on 2xx/3xx, `record_failure` on `HTTPError`/`URLError`, re-queues countable failures up to 3 times, and stops cleanly when the gate reports `aborted`.
- **R6 — Tests**: `tests/test_cli.py` runs the CLI as a subprocess against a `ThreadingHTTPServer(("127.0.0.1", 0), ...)` serving 3 HTML pages (with `Content-type` casing) and 1 PDF, asserting 4 response records, 4 CDX lines of 11 fields, a kept query string and the PDF MIME; a retry case (first hit 503, second 200); `tests/test_politeness.py` unit-tests R4; a parity test asserts the Python `TRACKING_PARAMS` equals the set parsed from `web/lib/core_crawler.js`.

## Acceptance criteria

- **AC1**: `normalize_headers([('Content-type','text/html'),('X-A','1')])` returns `{'content-type': 'text/html', 'x-a': '1'}`; a writer call with `{'Content-type': 'text/html; charset=utf-8'}` produces CDX MIME `text/html` (R1).
- **AC2**: `canonicalize_url('https://Example.org/docs/?ref=nav&utm_x=1&b=2')` returns `https://example.org/docs/?b=2&ref=nav`; `('https://example.org:443/a#frag')` returns `https://example.org/a`; `('../x?q=1', 'http://h.test/a/b/')` returns `http://h.test/a/x?q=1`; `('mailto:a@b.test')` returns `None` (R2).
- **AC3**: `grep -c "for q in queue" cli/aegis_cli.py` is `0`; the file uses `collections.deque` and a `pending` set (R3).
- **AC4**: The `cli/politeness.py` Verify prints `None`, `300 10`, `314`, `NOMINAL 0`, `TRIPPED`, `True`, `True True`, `False` (R4).
- **AC5**: Against the local fixture (3 HTML pages + 1 PDF) the CLI exits 0 and writes exactly 4 `WARC-Type: response` records and 4 CDX lines with 11 fields including `application/pdf` and `/c?id=2`; with the additional `/r` URL answering 503 then 200, a fifth response record is written with status 200 after exactly one retry (server sees two hits) (R5).
- **AC6**: `python3 -m unittest discover -s tests -p 'test_*.py'` ends `OK`; `python3 cli/aegis_cli.py --help` exits 0; CI leak-prevention gate passes (R6).

## Non-functional constraints

- Python 3 standard library only; Python >= 3.9; no network beyond loopback in tests; tests write only under `tempfile` directories.
- CLI flags (`--profile`, `--output-dir`, `--max-pages`, `--depth`) and `PythonWarcWriter` public methods keep their names; new parameters are optional.
- Each task changes fewer than ~60 lines, except C4 which creates one self-contained new file whose complete content is given verbatim.

## Gates

- **G1 (publication)**: pushing requires explicit user authorization; this track does not push.
- **G2 (registry)**: registration in `conductor/tracks.md` / `conductor/index.md` is performed by the integrator.
- **G3 (CI wiring)**: adding `python3 -m unittest discover -s tests` to `.github/workflows/ci.yml` is owned by the integrator; `cli/politeness.py` should also be added to the `py_compile` list there.

## Cross-track dependencies

- `warc_interop_20260905` W2 (CDX `S` field) — `tests/test_cli.py` asserts 11 fields; without W2 the same fixture yields 10. W6 (request records, `request_headers=` parameter) — C5 passes `request_headers` only if the writer accepts it (guarded with `inspect.signature`), so C5 works before or after W6.
- `engine_correctness_20260905` T7 (removes `ref`/`source` from the browser `TRACKING_PARAMS`) — the parity test in C6 compares the two sets and fails until T7 lands; T1–T4 define the engine semantics that C4 mirrors (values are restated here so C4 can be implemented independently).

## Out of scope

- robots.txt in the CLI (follow-up once the browser implementation from `engine_correctness_20260905` T9 is stable), tiered seeds (`tier_2/3`) in the CLI, path whitelist/blacklist regex in the CLI, concurrency, and MCP server changes.
