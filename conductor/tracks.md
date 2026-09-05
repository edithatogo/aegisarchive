# AegisArchive Track Registry

- [x] **Track: Core Engine & Server Preservation Suite**
  *Status: Completed*
  *Plan: [./tracks/core_engine_politeness/plan.md](./tracks/core_engine_politeness/plan.md)*
  *Token-bucket rate limiting, decorrelated jitter, EWMA latency tracking, and circuit breaker.*

- [x] **Track: ISO 28500 WARC/1.1 Archival & Deduplication Engine**
  *Status: Completed*
  *Plan: [./tracks/warc_iso28500_engine/plan.md](./tracks/warc_iso28500_engine/plan.md)*
  *Standards-compliant WARC streaming, CDX-11 indexing, and SHA-256 revisit records.*

- [x] **Track: In-Browser Sandboxed WARC Replay Viewer**
  *Status: Completed*
  *Plan: [./tracks/in_browser_replay_viewer/plan.md](./tracks/in_browser_replay_viewer/plan.md)*
  *Offline browsing of captured archives directly in browser iframe.*

- [x] **Track: Cross-Platform Native Launchers & Multi-OS Hardening**
  *Status: Completed*
  *Plan: [./tracks/cross_platform_hardening/plan.md](./tracks/cross_platform_hardening/plan.md)*
  *Universal Python 3 stdlib launcher with port hunting and 1-click launchers for Mac, Windows, Linux.*

- [x] **Track: Headless CLI & Model Context Protocol (MCP) Server**
  *Status: Completed*
  *Plan: [./tracks/headless_cli_mcp/plan.md](./tracks/headless_cli_mcp/plan.md)*
  *Zero-dependency CLI runner and stdio JSON-RPC MCP server for AI agents.*

- [x] **Track: CI/CD & Repository Security Hardening**
  *Status: Completed*
  *Plan: [./tracks/ci_cd_repo_hardening/plan.md](./tracks/ci_cd_repo_hardening/plan.md)*
  *GitHub Actions CI matrix, compilation checks, schema validation, and leak prevention gate.*

- [ ] **Track: Portable Platform Compatibility & Offline Intelligence Suite**
  *Status: Roadmap Planned*
  *Plan: [./tracks/portable_intelligence_suite/plan.md](./tracks/portable_intelligence_suite/plan.md)*
  *Windows embeddable Python auto-detection, portable Git and console runtimes, local multi-tier LLMs (llama.cpp), Whisper transcription, Piper TTS, and local GraphRAG memory.*

- [x] **Track: Portable Station Hardening & Diagnostics**
  *Status: Completed* | *Archived*
  *Link: [./archive/portable_station_hardening_20260905/index.md](./archive/portable_station_hardening_20260905/index.md)*
  *Hardened loopback server, session-token-guarded control endpoints, bundle SHA-256 verification, status/self-test surface, operator diagnostics, and controlled shutdown; G2 delegations registered in the companion program as track `station_hardening_delegation_20260905`.*

---

- [x] **Track: Politeness Engine & Crawler Correctness**
  *Status: Completed*
  *Link: [./tracks/engine_correctness_20260905/](./tracks/engine_correctness_20260905/)*
  *EWMA baseline warm-up, 404-safe breaker, retry budget, abortable waits, cache no-store, schema bounds, robots policy, requisite extraction, canonicalization fidelity.*

- [x] **Track: WARC/CDX Interoperability & Integrity**
  *Status: Completed*
  *Link: [./tracks/warc_interop_20260905/](./tracks/warc_interop_20260905/)*
  *Decoded-payload header hygiene, CDX `S` field, fail-closed digests, WARC-Refers-To, request records, reader revisit resolution, verifier CDX offset and `.warc.gz`.*

- [x] **Track: Web Console Security & Persistence Claims**
  *Status: Completed*
  *Link: [./tracks/web_console_security_20260905/](./tracks/web_console_security_20260905/)*
  *Sandbox and CSP, blob replay, output encoding, generated profile bundle, OPFS/checkpoint honesty, `?profile=` consumer in `index.html` only.*

- [ ] **Track: Headless CLI Parity with the Browser Engine**
  *Status: Planned*
  *Link: [./tracks/cli_parity_20260905/](./tracks/cli_parity_20260905/)*
  *Case-insensitive headers, query-string fidelity, stdlib politeness port, set-based queue, shared loopback fixture.*

- [ ] **Track: Repository Standards Alignment**
  *Status: Planned*
  *Link: [./tracks/repo_standards_alignment_20260905/](./tracks/repo_standards_alignment_20260905/)*
  *Renovate, CITATION.cff, CalVer changelog, security-insights, Scorecard/zizmor copies, thin standards CI, pyproject with zero runtime deps, README nine-section contract.*

- [ ] **Track: Security Gates & Fuzzing**
  *Status: Planned*
  *Link: [./tracks/security_gates_and_fuzzing_20260905/](./tracks/security_gates_and_fuzzing_20260905/)*
  *New `security.yml` only (do not edit `ci.yml`): secret scan, CodeQL, Semgrep, Bandit, fuzz harnesses; fail on medium-or-higher findings.*

- [ ] **Track: Self-Improving System Loop**
  *Status: Planned*
  *Link: [./tracks/self_improvement_loop_20260905/](./tracks/self_improvement_loop_20260905/)*
  *Claims audit, track health, weekly workflow, improvement issue form; governance docs already seeded.*

- [ ] **Track: Contributor Experience**
  *Status: Planned*
  *Link: [./tracks/contributor_experience_20260905/](./tracks/contributor_experience_20260905/)*
  *Five-minute CONTRIBUTING setup, QUICKSTART, SUPPORT, good-first-issue seeds. Does not rewrite README or add `release.yml`.*

- [ ] **Track: Release Workflow, Provenance, and Dev Container**
  *Status: Planned*
  *Link: [./tracks/release_and_packaging_20260905/](./tracks/release_and_packaging_20260905/)*
  *`.devcontainer`, `release.yml` with SHA256SUMS and SLSA provenance. Does not own README, CONTRIBUTING, or pyproject.toml.*

- [ ] **Track: Future Capabilities (Research-First)**
  *Status: Planned*
  *Link: [./tracks/future_capabilities_20260905/](./tracks/future_capabilities_20260905/)*
  *ADR spikes only (WACZ+CDXJ, Compression Streams, service-worker replay, MCP resources, in-browser PDF and embeddings later, OPFS wiring, task scheduling, provenance score). Depends on `warc_interop_20260905` before WACZ.*
