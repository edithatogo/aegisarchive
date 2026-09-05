# Track Plan: Portable Station Hardening & Diagnostics

## Status: NEW (initialized 2026-09-05)

## Phase 1 — Specification & approval

- [x] Capture full-system review recommendations into the track specification (traces to R1–R6). *(evidence: spec.md)*
- [x] Record external gates for publication and cross-repo coordination (G1, G2). *(evidence: spec.md)*
- [x] Approval basis: user requested incorporation of the review recommendations into the conductor system (2026-09-05).

## Phase 2 — In-repository implementation

- [ ] T1 Harden `cli/launch.py` web server: dot-path denial, `Host` validation, `Cache-Control: no-store`, threaded request handling. *(AC1, AC2, AC3)*
- [ ] T2 Automated tests for T1 behaviors (scripted loopback requests with assertions). *(AC1–AC3)*
- [ ] T3 Per-session token authentication for the bundled inference server, plus endpoint identity verification before reuse. *(AC4)*
- [ ] T4 SHA-256 bundle manifest (`CHECKSUMS.sha256` template + `cli/verify_bundle.py`) with fail-closed verification and first-run prompt. *(AC5)*
- [ ] T5 Station status/self-test surface (page + JSON endpoint) reporting runtime, engine, model, and index state. *(AC6)*
- [ ] T6 Windows launcher diagnostics: no stderr suppression, pause on failure, atexit/orphan cleanup for inference processes. *(R5)*
- [ ] T7 Host-checked POST-only shutdown endpoint and optional idle timer surfaced in the web console. *(R6)*
- [ ] T8 Phase checkpoint: full automated review — `py_compile` all entry points, `--help` smoke tests, profile schema validation, leak-prevention grep. *(AC7, AC8)*

## Phase 3 — Cross-repository coordination (external gate G2)

- [ ] C1 Handshake note delivered to the companion program's active conductor track listing delegated items: root launcher delegation, agent tool-argument guards and id-only staging, dynamic staging dates, encrypted-media guidance. Owner: parallel agent / user decision.
- [ ] C2 Verify delegated items appear as planned tasks in the companion conductor; record evidence reference.

## Phase 4 — Completion

- [ ] F1 Final validation run (AC7, AC8) and evidence ledger update.
- [ ] F2 Update `metadata.json` status and the registry entry per lifecycle rules.