# Agentic Pairing & Development Guidelines: AegisArchive

This document provides context engineering instructions for autonomous agents and AI pair programmers working on the **AegisArchive** repository.

---

## 🎯 Architectural Invariants

1. **Zero External Dependencies at Runtime**:
   * The core application must run entirely in modern web browsers via standard Web APIs (`Fetch`, `Streams`, `Web Cryptography`, `OPFS`).
   * The CLI launcher and utilities must use **Python 3 standard library only** (`http.server`, `urllib`, `socket`, `hashlib`). Do NOT introduce `pip` requirements (`requests`, `flask`, `beautifulsoup`) unless explicitly placed in an optional, isolated subdirectory.

2. **Server Preservation & Ethical Politeness**:
   * Every network request flow must be gated by the `PolitenessEngine`.
   * Never bypass rate limits, exponential backoff, or `Retry-After` headers.
   * Frame features around server preservation, anti-DDoS protection, and forensic archival integrity.

3. **Standard-Compliant Archiving**:
   * Output must adhere strictly to **ISO 28500:2017 (WARC/1.1)** and **CDX-11**.
   * Payloads must be hashed with SHA-256 for content-addressable deduplication (`warc/revisit`).

4. **Multi-OS Turnkey Simplicity**:
   * Maintain the root 1-click launchers (`START_MAC.command`, `START_WINDOWS.cmd`, `START_LINUX.sh`).
   * Non-technical users must be able to run the tool by unzipping and double-clicking a single file.

---

## 🛠️ Testing & Verification Standards

* Before committing changes, verify:
  1. Python scripts run cleanly with `--help`:
     `python3 cli/launch.py --help`
     `python3 cli/aegis_cli.py --help`
     `python3 cli/warc_verify.py --help`
  2. JSON profiles validate against `profiles/schema.json`.
  3. Zero proprietary, client-specific, or healthcare-specific strings exist in code (`grep -i` for domain names or private identifiers).

---

## 🤖 Model Context Protocol (MCP) Maintenance

* When adding new tools to `mcp/server.py`:
  * Ensure inputs and outputs conform to standard JSON-RPC 2.0.
  * Update tool definitions in `tools/list` handler.

---

## 🔁 Improvement Protocol

Autonomous agents implementing planned work follow `conductor/implementation_contract.md` exactly. In short:

1. Start from a clean tree; read `conductor/index.md`, `conductor/backlog.md`, this file, then the chosen track's `spec.md` and `plan.md`.
2. Take the first unchecked task of the highest-priority unblocked track; touch only the files that task lists; never edit files owned by another active track.
3. Run the task's Verify commands verbatim, then the repository baseline (or `python3 scripts/gate.py test` when present); record results in the track's `evidence.jsonl`.
4. One task = one commit; never push without a `gate_authorized` G1 entry from the user.
5. On track completion append one entry to `conductor/lessons.md`.
6. New ideas go to `## Proposed` in `conductor/backlog.md`, never straight into code.

Parallel-owned files (never edit from another track): `cli/launch.py`, `cli/verify_bundle.py`, `cli/test_station_hardening.py`, `.github/workflows/ci.yml`, and `conductor/tracks/portable_station_hardening_20260905/`. Before commit, run `python3 cli/test_station_hardening.py` and `python3 -m py_compile` on touched Python files. Do not write client-specific strings.

The weekly `self-improvement` workflow audits documentation claims (`scripts/claims_audit.py`) and track hygiene (`scripts/track_health.py`) and reports to `audits/latest/self-improvement.md`.
