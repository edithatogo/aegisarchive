# Track Specification: Web Console Security & Persistence Claims

## Overview

The browser console (`web/index.html`) and the replay viewer (`web/viewer.html` + `web/lib/warc_reader.js`) run untrusted archived content and display crawled strings. A review reproduced a sandbox escape, live-network egress during "offline" replay, HTML injection through crawled URLs/titles, a drifted duplicate of the profile catalogue, and two persistence claims (OPFS streaming, resumable checkpoints) that the code does not deliver. The `?profile=` query parameter set by the launcher is never read. This track closes each gap with small, verifiable steps and stdlib-only tests.

## Authoritative inputs

- Repository invariants: `AGENTS.md`; workflow guardrails: `conductor/workflow.md`.
- Template conventions: `conductor/tracks/portable_station_hardening_20260905/`.
- Files in scope: `web/viewer.html`, `web/index.html`, `web/lib/warc_reader.js`, `web/lib/warc_writer.js`, `web/lib/core_crawler.js`, `web/lib/opfs_streamer.js` (read-only reference), new `scripts/build_profile_bundle.py`, generated `web/profiles.bundle.js`.

## Reproduced defects

- **V1** `viewer.html` line 166: `<iframe sandbox="allow-same-origin allow-scripts">` with `srcdoc` content. A sandboxed document that has both flags can reach `window.parent` and remove its own sandbox — a documented escape. Archived pages must be treated as hostile.
- **V2** `WarcReader.renderPage` injects `<base href="<live URL>">`, so every relative `img/link/script` in the archived page is fetched from the live origin during "offline" replay (network egress, privacy leak, and the replay is not the archive).
- **V3** `index.html` `addDocumentRow` and `viewer.html` `renderUrlList`/`loadWarcFile` interpolate crawled URLs, titles, MIME types and file names into `innerHTML` unescaped (`escapeHtml` exists but is used only for log lines and does not escape quotes).
- **V4** `index.html` `BUILTIN_PROFILES` duplicates `profiles/*.json` and has drifted (e.g. `rapid_research` delays, missing `taxonomy`, `enable_opfs_streaming`, whitelist regex), so the console and the CLI/MCP disagree about what a profile is.
- **V5** `OpfsStreamer` is loaded by `index.html` but never instantiated; `WarcWriter` keeps every record in memory, contradicting the "memory-safe disk streaming" claim and the `enable_opfs_streaming` profile option.
- **V6** The README architecture diagram shows "IndexedDB State Persistence" and the crawler header claims "Crash-Safe Session Checkpointing", but no state is persisted; a page reload loses the frontier.
- **V7** `cli/launch.py --profile` appends `?profile=<absolute filesystem path>` to the console URL; `index.html` never reads the parameter.

## Requirements

- **R1 — Sandbox**: the replay iframe uses `sandbox=""` (no flags) and every rendered page starts with `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src blob: data:; style-src 'unsafe-inline' blob:;">` injected as the first child of `<head>` (or prepended when no `<head>`); any `<base>` tags in the archived HTML are removed.
- **R2 — Offline replay**: `renderPage` rewrites `src`/`href` of requisite elements (`link, img, script, iframe, source, video, audio`) to `blob:` URLs created from archived records in `recordsByUrl`; requisites not in the archive become `data:,`; anchors become `href="#"` with `data-archived-href`; `srcset` is neutralised to `data-archived-srcset`; the original absolute URL is preserved in a `data-archived-*` attribute for inspection.
- **R3 — Output encoding**: all crawled/archived strings rendered by `index.html` and `viewer.html` pass through `escapeHtml` (which must also escape `"` and `'`), or are assigned via `textContent`; anchor `href` values are restricted to `http(s)`.
- **R4 — Single profile source**: `scripts/build_profile_bundle.py` (stdlib) generates `web/profiles.bundle.js` from `profiles/*.json` (skipping `schema.json` and `._*` artefacts), exposes `AEGIS_BUNDLED_PROFILES` in browsers and `module.exports` in Node, and supports `--check` (exit 1 when stale); `index.html` drops its inline `BUILTIN_PROFILES` literal and builds the `<select>` from the bundle.
- **R5 — OPFS streaming**: `WarcWriter` gains `attachStreamer(streamer)`, appends each finished record to the streamer, and `getWarcBlob()` becomes `async`, returning the streamer's file (or the in-memory Blob when no streamer); `CoreCrawler` instantiates `OpfsStreamer` when `archival.enable_opfs_streaming !== false` and `OpfsStreamer` is defined, attaching it in `start()`; `getFinalResults()` becomes `async`.
- **R6 — Checkpoint/resume**: `CoreCrawler` exposes `exportCheckpoint()`/`importCheckpoint(cp)` (version 1: `profile_id`, `savedAt`, `queue`, `visited`) and an `onCheckpoint` callback fired every 10 processed URLs, on `pause()`/`stop()`, and with `null` on completion; `index.html` persists it in `localStorage` under `aegis.checkpoint.v1`, shows a resume banner on load when an unfinished frontier exists, and imports it before `start()` when the operator clicks Resume. (WARC records captured before a reload are not restored; the banner says so.)
- **R7 — `?profile=`**: `index.html` reads `URLSearchParams.get('profile')`; a bundled id (or a path whose basename minus `.json` is a bundled id) selects that profile; otherwise a same-origin `http(s)` URL is fetched with `cache: 'no-store'` and validated; anything else is logged and ignored.
- **R8 — Tests**: `node --test tests/js/` and `python3 -m unittest discover -s tests` cover R1–R7 without third-party packages.

## Acceptance criteria

- **AC1**: `grep -c 'sandbox=""' web/viewer.html` = 1 and `allow-same-origin` absent; `renderPage` output has no `<base` and the CSP meta immediately after `<head>` (R1).
- **AC2**: For a page referencing an archived stylesheet, an archived image, a missing image, an anchor and a script, the rendered HTML contains exactly one `href="blob:`, exactly one `src="blob:`, two `src="data:,"`, one `href="#"` with `data-archived-href="http://h.test/p2"`, and no `srcset=` (R2).
- **AC3**: `escapeHtml('<a href="x">\'')` returns `&lt;a href=&quot;x&quot;&gt;&#39;` in both pages; no `${url}`, `${doc.url}`, `${doc.title` or `${file.name}` remains inside an `innerHTML` template in either page (R3).
- **AC4**: `python3 scripts/build_profile_bundle.py --check` exits 0 after generation; `require('./web/profiles.bundle.js')` yields keys `default_polite,enterprise_intranet,rapid_research`; `index.html` contains `profiles.bundle.js` and no `BUILTIN_PROFILES = {` literal (R4).
- **AC5**: In Node (memory fallback), a crawl of one stubbed page reports `streamerAttached === true`, `warcBlob.size === warc.currentOffset`, and `warc.records.length === 0` (R5).
- **AC6**: `importCheckpoint(JSON.parse(JSON.stringify(exportCheckpoint())))` restores `queue` and `visited`; `stop()` fires `onCheckpoint` with the current frontier; `index.html` references `aegis.checkpoint.v1` and a `resumeBanner` (R6).
- **AC7**: `index.html` contains `URLSearchParams(location.search).get('profile')` and the same-origin guard; the id-derivation expression maps `/abs/path/profiles/default_polite.json` to `default_polite` (R7).
- **AC8**: `node --test tests/js/` reports `# fail 0`; unittest ends `OK`; CI leak-prevention gate passes (R8).

## Non-functional constraints

- Vanilla ES6+, no bundler, no npm; Python stdlib only for the bundle script; the generated bundle is committed so the console remains zero-install.
- Public API: `WarcReader.renderPage(url)` keeps its signature; `WarcWriter.getWarcBlob()` and `CoreCrawler.getFinalResults()` become `async` (the only call sites are `core_crawler.js` and `index.html`, both updated here).
- Sandboxed frames cannot host plug-in PDF viewers; binary records remain available through "Open In Tab" (unchanged).

## Gates

- **G1 (publication)**: pushing requires explicit user authorization; this track does not push.
- **G2 (registry)**: registration in `conductor/tracks.md` / `conductor/index.md` is performed by the integrator.
- **G3 (CI wiring)**: adding `node --test`, `unittest` and `build_profile_bundle.py --check` to `.github/workflows/ci.yml` is owned by the integrator.
- **G4 (launcher)**: `cli/launch.py` belongs to another active track; this track handles whatever `?profile=` value it sends (absolute path -> basename id) and recommends, via the integrator, that the launcher pass the profile id instead of a filesystem path.

## Cross-track dependencies

- `warc_interop_20260905` (W1–W6) edits `web/lib/warc_writer.js` and the `addResponseRecord` call in `core_crawler.js`; apply those first, then S5 here (S5 lists every `this.records.push` site including the request record added by W6).
- `engine_correctness_20260905` (T6) changes `profiles/rapid_research.json`; regenerate the bundle (`python3 scripts/build_profile_bundle.py`) after that task lands. Its `core_crawler.js` edits are on other lines than S5/S6 here.
- `web_console_security` does not touch `cli/launch.py`, `README.md` or `AGENTS.md`; the README wording about IndexedDB is for the documentation track to align with R6 (`localStorage`).

## Out of scope

- Service-worker based replay, CDXJ, full URL-rewriting of CSS `url()` references inside stylesheets, PDF rendering inside the sandboxed frame, IndexedDB storage of WARC bytes, and any change to the politeness engine.
