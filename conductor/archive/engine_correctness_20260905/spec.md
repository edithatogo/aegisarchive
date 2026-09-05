# Track Specification: Politeness Engine & Crawler Correctness

## Overview

A code review of the browser crawler (`web/lib/politeness_engine.js`, `web/lib/core_crawler.js`) and the profile schema (`profiles/schema.json`) reproduced ten defects that make the engine either impolite (unbounded schema values, no robots.txt handling, cached first sample distorting the latency baseline) or incomplete (page requisites never captured, failed URLs never retried, un-cancellable waits). This track fixes them in small, independently verifiable steps and adds stdlib-only automated tests. Every task is written so that a small implementation model can apply it without design decisions.

## Authoritative inputs

- Repository invariants: `AGENTS.md` (zero-install, stdlib-only Python, vanilla ES6+ browser code, all crawler egress through `PolitenessEngine`).
- Workflow guardrails: `conductor/workflow.md`.
- Template conventions: `conductor/tracks/portable_station_hardening_20260905/`.
- Reproduced defects (2026-09-05 review), enumerated as D1–D10 below.

## Reproduced defects

- **D1** `recordSuccess` sets `baselineLatencyMs` from the first sample. With `fetch(..., {cache:'default'})` the first response is often served from the HTTP cache (~5 ms), so `strainRatio` saturates, the delay is stretched 3x and the circuit stays `THROTTLED` for the whole run.
- **D2** `recordFailure` is called for every non-2xx status; three `404`s trip the breaker although a missing page is not a server-strain signal.
- **D3** URLs are added to `visited` before the fetch and are never re-queued; a transient `429`/`5xx`/network error loses the URL permanently.
- **D4** `acquirePermission` waits with bare `setTimeout` (cooldown, Retry-After, token wait, jitter); `stop()` cannot interrupt a 60 s cooldown, and a hostile `Retry-After: 999999` blocks the tab for days.
- **D5** `fetch` uses `cache:'default'`, so latency samples and archived bytes may come from the browser cache instead of the origin.
- **D6** `profiles/schema.json` accepts `min_delay_ms: 0` and `max_requests_per_minute: 100000`; unknown top-level keys are accepted silently.
- **D7** The schema advertises `concurrency` and `jitter_distribution: "decorrelated"`, neither of which the engine implements (the engine is single-flight by design; `calculateJitter` only knows `gaussian`/`uniform`).
- **D8** No robots.txt handling exists.
- **D9** `extractLinks` only matches quoted `<a href>`; stylesheets, images, scripts, iframes, `srcset` candidates and unquoted `href` values are never queued, so archived pages are incomplete.
- **D10** `canonicalizeUrl` strips the trailing slash (changing resource identity: `/docs/` and `/docs` can be different resources) and removes the generic `ref` and `source` query parameters, which are frequently functional rather than tracking parameters.

## Requirements

- **R1 — Latency baseline warm-up**: the baseline must be the median of the first 10 success samples and afterwards drift slowly (`baseline = 0.98*baseline + 0.02*sample`); no strain-based throttling before the warm-up completes.
- **R2 — Failure classification**: only status `0` (network), `429`, and `5xx` count toward the consecutive-error tripwire and back-off; other `4xx` are recorded in the audit ledger only.
- **R3 — Retry budget**: URLs failing with a countable failure are re-queued with a `retries` counter (max 3) and served under the engine's back-off; after the budget is exhausted the URL is logged as abandoned.
- **R4 — Cancellable waits**: every wait in `acquirePermission` must be interruptible via an `AbortController` owned by the engine; `CoreCrawler.stop()` must abort it; `Retry-After` is capped at `cooldown_seconds * 10`.
- **R5 — Origin fetches**: crawler fetches use `cache: 'no-store'`.
- **R6 — Schema bounds**: `profiles/schema.json` gains `minimum`/`maximum` on every numeric politeness and target limit, `additionalProperties: false` at the top level, and all bundled profiles validate against the tightened schema.
- **R7 — Schema honesty**: `decorrelated` is removed from the `jitter_distribution` enum; `concurrency` is marked deprecated (description + `deprecated: true`) and documented as ignored.
- **R8 — robots.txt**: new `politeness.robots_policy` enum `["respect", "ignore_authorised"]`, default `respect`; `/robots.txt` is fetched once per origin through the politeness gate, `Disallow` rules for the effective agent token (`aegisarchive`, falling back to `*`) are honoured, and the policy decision plus each skip is written to the audit ledger.
- **R9 — Requisite extraction**: link discovery covers `a[href]`, `link[href]`, `area[href]`, `img[src]`, `script[src]`, `iframe[src]`, `source/video/audio[src]`, `img/source[srcset]` and unquoted attribute values, using `DOMParser` when available and a regex fallback otherwise; discovered requisites keep the parent's tier and `depth + 1`.
- **R10 — Canonicalization fidelity**: keep the trailing slash; remove `ref` and `source` from `TRACKING_PARAMS`.
- **R11 — Tests**: `node --test tests/js/` and `python3 -m unittest discover -s tests` cover R1–R10 with no third-party packages.

## Acceptance criteria

- **AC1**: After samples `[5, 300 x9]` the baseline is `300`; one further sample of `1000` moves it to `314`; `baselineLatencyMs` is `null` until 10 samples exist (R1).
- **AC2**: Three `404` failures leave the circuit `NOMINAL` with `consecutiveErrors === 0`; three `503` failures trip it (R2).
- **AC3**: A `503` response re-queues the task with `retries: 1` and removes it from `visited`; the fourth failure abandons it (R3).
- **AC4**: `acquirePermission` returns `{ aborted: true }` within one second after `abort()` even when a cooldown or Retry-After wait is pending; `Retry-After: 999999` yields a cooldown of at most `cooldown_seconds * 10 * 1000` ms (R4).
- **AC5**: `core_crawler.js` contains `cache: 'no-store'` and no `cache: 'default'` (R5).
- **AC6**: The schema has `additionalProperties: false`, `min_delay_ms.minimum == 250`, `max_requests_per_minute.maximum == 300`, `burst_limit.maximum == 20`, and every `profiles/*.json` passes the stdlib bounds check (R6).
- **AC7**: `decorrelated` is absent from the enum; `concurrency.deprecated === true` (R7).
- **AC8**: With a robots.txt of `Disallow: /private/` and `Disallow: /tmp*`, `isAllowedByRobots` returns `true/false/false` for `/public/a`, `/private/x`, `/tmpfile`, fetches robots.txt exactly once per origin, and writes a `robots_txt` ledger entry (R8).
- **AC9**: `extractLinks` on the fixture in T8 queues exactly the seven expected URLs and ignores `mailto:` (R9).
- **AC10**: `canonicalizeUrl('https://Example.org/docs/?ref=nav&utm_x=1&b=2')` returns `https://example.org/docs/?b=2&ref=nav` (R10).
- **AC11**: `node --test tests/js/` and `python3 -m unittest discover -s tests -p 'test_*.py'` pass; CI leak-prevention gate passes (R11).

## Non-functional constraints

- No new runtime dependencies; no npm packages; no build step at runtime.
- Public method names of `PolitenessEngine` and `CoreCrawler` are preserved; new members are additive.
- Each task changes fewer than ~60 lines and leaves the repository green (`node -e` require checks and `python3 -m py_compile` continue to pass).

## Gates

- **G1 (publication)**: pushing commits to the remote requires explicit user authorization; this track does not push.
- **G2 (registry)**: registration in `conductor/tracks.md` / `conductor/index.md` is performed by the integrator, not by this track.
- **G3 (CI wiring)**: adding the new test commands to `.github/workflows/ci.yml` is owned by the integrator; this track only creates the tests.

## Cross-track dependencies

- `web_console_security_20260905` regenerates `web/profiles.bundle.js` from `profiles/*.json`; T6 of this track edits `profiles/rapid_research.json` (min delay 200 -> 250), so the bundle must be regenerated after T6 (that track's build script handles it; no action here).
- `cli_parity_20260905` mirrors R2, R3 and R10 in Python; it reads the `TRACKING_PARAMS` set from `web/lib/core_crawler.js` in a parity test, so T9 here should land before that track's tests are run.

## Out of scope

- Concurrency (the engine stays single-flight); CLI changes; README/AGENTS.md wording; WARC record format (owned by `warc_interop_20260905`); UI changes in `web/index.html` beyond none (owned by `web_console_security_20260905`).
