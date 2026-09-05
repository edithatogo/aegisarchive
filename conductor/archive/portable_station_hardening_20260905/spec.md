# Track Specification: Portable Station Hardening & Diagnostics

## Overview

A full-system review of the portable USB station (this repository plus its companion portable-station program repository and shared root launcher assets) identified hardening, robustness, and feature gaps. This track captures the approved recommendations implementable in this repository, and records cross-repository items for coordinated delivery with the parallel agent working in the companion repository's conductor system.

## Authoritative inputs

- Repository invariants: `AGENTS.md` (zero-install, stdlib-only, polite networking, multi-OS turnkey launchers).
- Workflow guardrails: `conductor/workflow.md`.
- Review source: full-system portable station review, 2026-09-05; findings are summarized in the requirements below.

## Requirements

- **R1 — Hardened local web server**: deny requests resolving to dot-directories/dotfiles (`.git`, agent state, hidden metadata) and AppleDouble (`._*`) artifacts; validate the `Host` header (loopback DNS-rebinding defence); emit `Cache-Control: no-store` on all responses; use a threaded HTTP server for concurrent asset loading.
- **R2 — Local inference endpoint authentication**: launch the bundled local LLM server with a per-session generated API token; make the token discoverable to station tooling only; verify an already-running endpoint is actually the expected engine before reuse.
- **R3 — Supply-chain integrity**: provide a SHA-256 checksum manifest for all bundled binaries and models; add a verification step (CLI flag and/or first-run) that fails closed.
- **R4 — Station status/self-test surface**: a page/endpoint reporting detected runtime, engine, model presence/size, index state, and launcher diagnostics.
- **R5 — Operator diagnostics**: the Windows launcher must not suppress stderr and must pause on failure; orphaned inference processes must be detected at startup and cleaned up on exit.
- **R6 — Controlled shutdown**: a Host-checked POST-only shutdown endpoint plus an optional idle timer, so non-technical operators can stop the station from the browser.

## Acceptance criteria

- **AC1**: The local server refuses dotfile/dot-directory paths and serves no hidden metadata artifacts (automated test).
- **AC2**: Requests with a foreign `Host` header are rejected with HTTP 400 (automated test).
- **AC3**: All responses carry `Cache-Control: no-store` (automated test).
- **AC4**: The inference endpoint rejects unauthenticated requests when launched by the station; the session token is discoverable by station tooling only (automated test).
- **AC5**: Verification against a tampered artifact fails with non-zero exit and a clear message (automated test).
- **AC6**: The status surface correctly reports component presence/absence states (automated test).
- **AC7**: `--help` works for all Python entry points; JSON profiles validate against `profiles/schema.json`; CI leak-prevention gate passes (automated).
- **AC8**: No third-party organisation or website references are reintroduced (CI gate).

## Non-functional constraints

- Python 3 standard library only for `cli/`; no new runtime dependencies; browser features must be vanilla ES6+.
- Loopback-only binding for all local servers.
- The politeness engine remains the only network egress path for crawling.

## External gates

- **G1 (publication)**: pushing commits to the remote repository requires explicit user authorization; this track does not push.
- **G2 (cross-repo)**: companion-repository items — root launcher delegation fix, agent tool-argument guards and id-only staging, dynamic staging dates, encrypted-media guidance — are owned by the companion program's active conductor track and must be coordinated with the parallel agent; they are not implemented in this repository by this track.

## Out of scope

- Sensitive-data deployment approval; changes to crawling policy or politeness parameters; roadmap items already tracked under the Portable Platform Compatibility track.