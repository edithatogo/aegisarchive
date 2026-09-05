# Lessons Ledger

Append-only. One entry per completed track (required by `conductor/implementation_contract.md` step 5), plus any entry a planner or reviewer considers worth keeping. Never edit or delete earlier entries; if a lesson turns out to be wrong, add a new entry that supersedes it and says so.

Entry format (four fields, in this order):

```markdown
## <YYYY-MM-DD> — <track_id or "repo">
- **Surprise**: what happened that the plan did not anticipate.
- **Change for the next planner**: a concrete rule, check, or task shape that would have prevented it.
```

Keep entries generic: no organisation names, hostnames, credentials, or personal blame. Reference commits by short SHA when useful. The weekly self-improvement report (`audits/latest/self-improvement.md`) lists tracks completed without a lesson, so an entry here is part of "done".

---

## 2026-09-05 — repo
- **Surprise**: Documentation described capabilities before the code existed. The README's architecture diagram and text advertised OPFS streaming, IndexedDB state persistence, and full request/response capture, yet at the time of writing `web/` contains no `new OpfsStreamer`, no `indexedDB` usage, and no `WARC-Type: request` record. The gap survived several commits because nothing mapped prose claims to code symbols.
- **Change for the next planner**: every capability claim in user-facing docs must have a row in `scripts/claims_audit.py` (claim -> mechanical check). A track that adds a feature adds the row in the same commit; a track that adds prose without code is a documentation defect, not progress.

## 2026-09-05 — portable_station_hardening_20260905
- **Surprise**: The same data was defined twice and drifted. Profile presets exist as JSON under `profiles/` and again as an inline `BUILTIN_PROFILES` object in `web/index.html`; the two copies were edited independently and no longer agree. Similarly, three launchers (macOS, Windows, Linux) duplicated logic that then needed manual syncing during the hardening track (commit `23da749`).
- **Change for the next planner**: when a plan introduces a second copy of any definition, the plan must include either a generation step (single source, generated artifact committed) or a conformance test that diffs the copies. "Keep them in sync" as a prose instruction is not a task.

## 2026-09-05 — repo
- **Surprise**: The CDX header declares 11 fields (` CDX N b a m s k r M S V g`) while both writers emit 10 values per line (the `S` length field is missing) in `web/lib/warc_writer.js` and `cli/aegis_cli.py`. The verifier never compared header arity to row arity, so the mismatch was invisible to CI for the whole project history.
- **Change for the next planner**: any format the project claims to conform to (WARC/1.1, CDX-11, MCP protocol version) needs a conformance test that exercises the writer and checks structural invariants, not just `--help` and `py_compile`. Acceptance criteria should name the invariant ("every CDX data row has exactly as many fields as the header").

## 2026-09-05 — engine_correctness_20260905
- **Surprise**: Failure classifications (404 tripping the circuit breaker) and single-flight assumptions were conflated with concurrency settings in profiles (`concurrency: 4` in `rapid_research.json` while the engine operated strictly single-flight). Furthermore, tracking parameter scrubbing was overly aggressive (stripping standard navigational queries like `ref` and `source`).
- **Change for the next planner**: profile schema properties must reflect actual runtime mechanics (mark unused/misleading options deprecated or bound them with strict constraints), and web crawler tests must assert preservation of critical routing queries and requisite tags rather than relying on happy-path smoke runs.

## 2026-09-05 — warc_interop_20260905
- **Surprise**: Multiple interoperability subtleties were undetected: revisit records lacked `WARC-Refers-To`, the reader lacked revisit record resolution against payload digests, hop-by-hop/encoding headers were copied verbatim into WARC HTTP headers alongside decoded payloads, and CDX offset validation was completely absent in the verifier.
- **Change for the next planner**: Archival formats require bidirectional roundtrip verification (writer -> reader resolution, writer -> verifier CDX span/offset audit, multi-member gzip decompression) in automated test suites rather than isolated unit mocks.

## 2026-09-05 — web_console_security_20260905
- **Surprise**: Web console security assumptions relied on an iframe with `allow-scripts` and `allow-same-origin` on `srcdoc`, which completely bypasses the browser sandbox. Additionally, live origin `<base href>` tags leaked egress traffic during local replays, crawled string interpolations risked XSS, and client-side persistence (OPFS streaming, frontier checkpointing) was claimed in documentation but was unwired in `core_crawler.js`.
- **Change for the next planner**: Web UI replay containers must enforce strict isolation from day one (flagless `sandbox=""`, default-src 'none' CSP, requisite rewriting to blobs/data URIs, and robust HTML entity escaping). All UI state persistence claims must be backed by concrete automated round-trip tests and static assertion test cases.

## 2026-09-05 — cli_parity_20260905
- **Surprise**: The headless CLI diverged sharply from the browser engine in subtle but critical ways: Python `http.client` preserves response header casing so checking `Content-Type` directly missed headers sent as `Content-type` (suppressing link discovery and emitting `application/octet-stream` in CDX), URL canonicalisation stripped query strings completely, queue membership tests were `O(N)` linear searches over full URL lists, and politeness was merely a naive uniform random sleep with no back-off or circuit breaker.
- **Change for the next planner**: Multi-surface engines (CLI vs Web) must share algorithmic parity specs and integration test fixtures from inception (e.g. tracking param regex parity tests, ephemeral loopback servers asserting identical crawl frontiers and 11-field CDX records).
## 2026-09-05 — repo_standards_alignment_20260905
- **Surprise**: `pyproject.toml` packaging required mapping top-level `cli` and `mcp` folders to non-shadowing distribution package names (`aegisarchive_cli`, `aegisarchive_mcp`) so as not to conflict with PyPI packages like the official `mcp` SDK, and editable installs (`pip install -e .`) generated untracked `.egg-info` artifacts that require explicit `.gitignore` rules.
- **Change for the next planner**: When introducing standard Python packaging to existing folder hierarchies without renaming on-disk directories, specify `package-dir` mappings explicitly in `pyproject.toml`, test entry point executables in an isolated virtual environment, and ensure build artifacts (`.coverage`, `coverage.xml`, `*.egg-info/`) are ignored before running package tests.

## 2026-09-05 — security_gates_and_fuzzing_20260905
- **Surprise**: Static scanners (Bandit, Semgrep, CodeQL) flag standard-library network calls (such as `urllib.request.urlopen`) even on hardcoded loopback URLs or allow-listed HTTP schemes unless audited with explicit inline scanner pragmas (`# nosec B310`). Furthermore, native coverage-guided fuzzers like Atheris require specific CPython architectures and Linux wheels, which fail in diverse developer environments without a deterministic fallback.
- **Change for the next planner**: Security analysis rules must be backed by a tightly scoped baseline file (`.bandit-baseline.json`) for parallel-owned code and inline pragmas on verified paths; and all fuzz harnesses must provide a deterministic stdlib smoke mode (`--smoke`) alongside Node property tests (`node --test`) so all gates pass locally with zero third-party dependencies.
