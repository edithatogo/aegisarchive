# Track Specification: WARC/CDX Interoperability & Integrity

## Overview

The browser writer (`web/lib/warc_writer.js`), the CLI writer (`cli/aegis_cli.py`), the replay reader (`web/lib/warc_reader.js`), the MCP index search (`mcp/server.py`) and the verifier (`cli/warc_verify.py`) each deviate from ISO 28500 / CDX conventions in ways that break replay in standard replay tools and hide corruption. Seven defects were reproduced. This track brings the containers into conformance without changing the zero-dependency posture and adds stdlib-only regression tests. Tasks are written for a small implementation model: exact snippets, exact commands, exact expected output.

## Authoritative inputs

- Repository invariants: `AGENTS.md`; workflow guardrails: `conductor/workflow.md`.
- Template conventions: `conductor/tracks/portable_station_hardening_20260905/`.
- ISO 28500:2017 (WARC 1.1) record semantics; CDX 11-field legacy layout ` CDX N b a m s k r M S V g`.

## Reproduced defects

- **Da** The reconstructed HTTP header block copies `content-encoding`, `transfer-encoding` and the wire `content-length` verbatim although the stored body is the decoded payload (browser `fetch` and `urllib` both deliver decoded bytes). Replay tools then try to gunzip plain text or truncate the body.
- **Db** The CDX header declares 11 fields (`N b a m s k r M S V g`) but lines emit 10: the record length `S` is missing before offset `V`, so consumers read the filename as the offset. Same defect in `warc_writer.js` and `aegis_cli.py`; the reader and `mcp/server.py` compensate with wrong indices.
- **Dc** `sha256Hex` falls back to a 32-bit FNV-1a value zero-padded to 64 hex characters and labels it `sha256:` when `crypto.subtle` is missing — a false integrity claim.
- **Dd** Revisit records carry `WARC-Refers-To-Target-URI`/`-Date` but not `WARC-Refers-To: <recordId>`, although the original record id is already stored in `payloadMap`.
- **De** `warc_reader.js` ignores `revisit` records entirely, so de-duplicated pages are missing from the viewer.
- **Df** `warc_verify.py` accepts `--cdx` but never uses it, and cannot open `.warc.gz` files although the viewer advertises `.warc.gz`.
- **Dg** The console help and README claim "HTTP request and response records", but no `request` records are written.

## Requirements

- **R1 — Header hygiene**: both writers omit `content-encoding`, `transfer-encoding` and the wire `content-length` from the reconstructed HTTP header block and append `Content-Length: <stored payload byte length>`.
- **R2 — CDX-11**: both writers emit 11 fields with `S` = record length in bytes (including the trailing `\r\n\r\n`) before `V` = record offset; `warc_reader.js` `parseCdx` and `mcp/server.py` `search_cdx` read `parts[8]` = length, `parts[9]` = offset, `parts[10]` = filename and require 11 fields.
- **R3 — Honest digests**: `sha256Hex` throws `Error('WebCrypto SHA-256 is unavailable; refusing to write an unverifiable digest')` when `crypto.subtle.digest` is missing; the helper is exposed as `WarcWriter.sha256Hex` for testing.
- **R4 — Revisit linkage**: revisit records include `WARC-Refers-To: <original record id>` in both writers.
- **R5 — Revisit replay**: the reader resolves revisit records to the referred record (by `WARC-Refers-To-Target-URI`, falling back to payload digest), exposes the shared body, and marks `isRevisit: true` and `refersTo`.
- **R6 — Verifier**: `warc_verify.py --cdx` checks every CDX line has 11 fields and, for plain `.warc`, that `(offset, length)` matches a record boundary starting with `WARC/1.1`; `.warc.gz` inputs (multi-member) are read via the `gzip` module; request records are counted.
- **R7 — Request records**: both writers can emit a `WARC-Type: request` record synthesised from the request (method, path, `Host`, headers sent) with reciprocal `WARC-Concurrent-To` links; the browser crawler and the CLI pass their request metadata; request records do not produce CDX lines.
- **R8 — Tests**: `node --test tests/js/` and `python3 -m unittest discover -s tests` cover R1–R7 with no third-party packages.

## Acceptance criteria

- **AC1**: For a response with `content-encoding: gzip`, `transfer-encoding: chunked`, `content-length: 999` and a 5-byte body, the stored HTTP header block contains none of the first two, and exactly `Content-Length: 5` (both writers) (R1).
- **AC2**: A fresh writer with one response produces a CDX line of 11 whitespace-separated fields where field 9 equals the response record's byte length and field 10 equals the warcinfo record's byte length; `parseCdx` and `search_cdx` return `length`, `offset`, `filename` from positions 8/9/10 (R2).
- **AC3**: With `globalThis.crypto = {}` the promise from `WarcWriter.sha256Hex` rejects with the R3 message (R3).
- **AC4**: The second of two identical 600-byte payloads yields a revisit record containing `WARC-Refers-To: ` followed by the first record's `recordId` (both writers) (R4).
- **AC5**: Loading that container in `WarcReader` yields `totalRecords === 2`, and `getRecord(secondUrl)` has `isRevisit === true`, `bodyBytes.length === 600`, `refersTo === firstUrl` (R5).
- **AC6**: `warc_verify.py t.warc --cdx t.cdx` exits 0 and prints `CDX entries verified:    3/3`; the same for `t.warc.gz` (offset check skipped) exits 0; a CDX with one tampered offset exits 1 (R6).
- **AC7**: With `options.request` (JS) / `request_headers=` (Python) one `WARC-Type: request` record precedes the response, both records carry `WARC-Concurrent-To`, the request block starts with `GET /p?q=1 HTTP/1.1\r\nHost: h.test`, the CDX offset points at the response record, and the CDX still has exactly one data line (R7).
- **AC8**: `node --test tests/js/` reports `# fail 0`; `python3 -m unittest discover -s tests -p 'test_*.py'` ends with `OK`; CI leak-prevention gate passes (R8).

## Non-functional constraints

- Python 3 standard library only; vanilla ES6+ in the browser; no build step.
- `WarcWriter`/`WarcReader` public method names are preserved; new parameters are optional with backwards-compatible defaults.
- Each task changes fewer than ~60 lines and leaves the repository green.

## Gates

- **G1 (publication)**: pushing requires explicit user authorization; this track does not push.
- **G2 (registry)**: `conductor/tracks.md` / `conductor/index.md` registration is performed by the integrator.
- **G3 (CI wiring)**: the integrator adds the test commands to `.github/workflows/ci.yml`.
- **G4 (external conformance)**: validating output with third-party WARC tooling is a dev-only, optional check outside this repository's zero-install rule; it is not a task here.

## Cross-track dependencies

- `cli_parity_20260905` tests assert 11 CDX fields and pass request headers to `write_response`; W2 and W6 of this track must land before that track's `tests/test_cli.py` is run.
- `web_console_security_20260905` (task S5) replaces `this.records.push(...)` in `warc_writer.js` with a streamer-aware append and makes `getWarcBlob()` async; it must be applied after W1–W6 of this track (S5 lists all push sites including the request record added here). The reader-side render changes of that track (S1/S2) touch `renderPage` only, which this track does not modify.
- `engine_correctness_20260905` edits `web/lib/core_crawler.js` on other lines (fetch options, retry); W6 here edits the fetch header literal and the `addResponseRecord` call. Apply either order; re-locate by snippet.

## Out of scope

- WARC `metadata` records, `WARC-IP-Address`, gzip-compressed output from the writers, CDXJ, and viewer rendering (owned by `web_console_security_20260905`); README/help wording (docs track — with R7 implemented the "request and response records" claim becomes true and needs no removal).
