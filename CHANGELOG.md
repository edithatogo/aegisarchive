# Changelog

All notable changes to AegisArchive are recorded here. The format follows
Keep a Changelog. Versions use calendar versioning: git tags are `vYYYY.MM.DD`
(for example `v2026.09.05`), with `vYYYY.MM.DD.N` for a second release on the
same day. The tag is the single authoritative version source; `pyproject.toml`
derives its version from the tag.

## [Unreleased]

No CalVer tag has been created yet. Everything below is unreleased history.

### Added
- feat: Initial release of AegisArchive v1.0 (ISO 28500:2017, MCP, Zero-Install) (6f1cf70)
- feat: Add portable-platform roadmap, offline AI capabilities, and embeddable Python launcher fallback (4869443)
- ci: Add GitHub Actions CI workflow, security policies, issue templates, and Conductor track plans (48169c6)
- ci: Expand automated leak prevention pattern to include regional and departmental identifiers (77bd47c)
- feat: harden local station server (T1/T2, AC1-AC3) (2054293)
- feat: station runtime services (T3/T5/T7, AC4/AC6) (7d4019f)
- feat: fail-closed bundle integrity verification (T4, AC5) (b4c5392)
- feat(web): single profile source via generated profiles.bundle.js (S4, AC4) [web_console_security_20260905] (66edb41)
- feat(web): OPFS streaming, frontier checkpointing, and ?profile= handoff (S5-S7, AC5-AC7) [web_console_security_20260905] (fc0c127)
- feat(cli): case-insensitive headers, canonicalisation with query preservation, and O(1) frontier (C1-C3, AC1-AC3) [cli_parity_20260905] (8986c5d)
- feat(cli): port politeness engine to stdlib Python and wire with retry budget (C4-C5, AC4-AC5) [cli_parity_20260905] (07598c2)

### Changed
- chore: remove third-party organisation and website references; extend leak-prevention gate (21ff421)
- chore: launcher operator diagnostics; drop remaining website references (T6) (23da749)
- Merge pull request #1 from edithatogo/renovate/configure (f9d5977)
- test(tests): add stdlib test coverage for politeness and crawler (T10, AC11) [engine_correctness_20260905] (d49c218)
- test(tests): add stdlib test coverage for WARC/CDX interoperability (W8, AC8) [warc_interop_20260905] (7b5f918)
- test(tests): add stdlib test coverage for web console security and persistence (S8, AC8) [web_console_security_20260905] (dfd6991)
- test(tests): add stdlib test coverage for CLI parity and politeness (C6, AC6) [cli_parity_20260905] (6d83405)
- chore: add renovate preset (T1, AC1) (a7b56e7)
- docs: add CITATION.cff (T2, AC2) (87c09e8)

### Fixed
- fix(conductor): do not expose session token via status endpoint (review Rev-1) (9c2b943)
- fix(web): politeness engine and crawler correctness (T1-T5, AC1-AC5) [engine_correctness_20260905] (c2a4cb4)
- fix(profiles): tighten schema bounds and deprecate concurrency (T6, AC6, AC7) [engine_correctness_20260905] (5c1bd0f)
- fix(web): requisite extraction, robots.txt, and canonicalization (T7-T9, AC8-AC10) [engine_correctness_20260905] (b7e452e)
- fix(warc): header hygiene, CDX-11 S field, fail-closed digests, and WARC-Refers-To (W1-W4, AC1-AC4) [warc_interop_20260905] (eeadbf6)
- fix(web): resolve revisit records in WarcReader (W5, AC5) [warc_interop_20260905] (e9af59d)
- fix(warc): request records with WARC-Concurrent-To and verifier CDX/gz support (W6-W7, AC6-AC7) [warc_interop_20260905] (7fc2b39)
- fix(viewer): flagless sandbox, replay CSP meta, and offline blob rewriting (S1-S2, AC1-AC2) [web_console_security_20260905] (2492222)
- fix(web): escape crawled strings in index.html and viewer.html (S3, AC3) [web_console_security_20260905] (6b3e254)
