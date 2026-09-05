# Track Plan: Portable Station Hardening & Diagnostics

## Status: COMPLETED (2026-09-05 — all phases done; implementation commits recorded below; G2 closure verified via companion track `station_hardening_delegation_20260905`)

## Phase 1 — Specification & approval

- [x] Capture full-system review recommendations into the track specification (traces to R1–R6). *(evidence: spec.md)*
- [x] Record external gates for publication and cross-repo coordination (G1, G2). *(evidence: spec.md)*
- [x] Approval basis: user requested incorporation of the review recommendations into the conductor system (2026-09-05).

## Phase 2 — In-repository implementation

- [x] T1 Harden `cli/launch.py` web server: dot-path denial, `Host` validation, `Cache-Control: no-store`, threaded request handling; permissive CORS wildcard removed. *(AC1, AC2, AC3)* — commit 2054293
- [x] T2 Automated tests for T1 behaviors (scripted loopback requests with assertions). *(AC1–AC3)* — commit 2054293
- [x] T3 Per-session token authentication for control endpoints (fail-closed when unset), plus endpoint identity verification before port reuse. *(AC4)* — commit 7d4019f
- [x] T4 SHA-256 bundle manifest (`CHECKSUMS.sha256` template + `cli/verify_bundle.py`) with fail-closed verification and launcher `--verify` flag. *(AC5)* — commit b4c5392
- [x] T5 Station status/self-test surface (page + JSON endpoint) reporting runtime, engine, and station state. *(AC6)* — commit 7d4019f
- [x] T6 Windows launcher diagnostics: no silent exits, pause on failure, generic install guidance; graceful listener release in the launcher (no orphaned sockets). *(R5)* — commit 23da749
- [x] T7 Host-checked POST-only shutdown endpoint and optional `--idle-timeout` auto-stop surfaced via `web/status.html`. *(R6)* — commit 7d4019f
- [x] T8 Phase checkpoint: full automated review — `py_compile` all entry points, `--help` smoke tests, 17/17 tests pass, profile schema validation, leak-prevention gate and vendor sweep clean (2026-09-05T03:54:56Z). *(AC7, AC8)*

## Phase 3 — Cross-repository coordination (external gate G2)

- [x] C1 Handshake note delivered to the companion program's active conductor track listing delegated items: root launcher delegation, agent tool-argument guards and id-only staging, dynamic staging dates, inference endpoint authentication, bundle integrity manifest, encrypted-media guidance. *(delivered: companion commit `1837bb7`, file `conductor/tracks/intranet_acquisition_toolkit_20260904/handshake_portable_station_hardening_20260905.md`)*
- [x] C2 Verify delegated items appear as planned tasks in the companion conductor; record evidence reference. *(verified 2026-09-05: companion track `station_hardening_delegation_20260905` initialized with spec/plan/metadata/index/evidence and registry entry — companion commit `f2f51b7`; all six delegated items planned as tasks P1–P6 plus submodule pin refresh P7)*

## Phase 4 — Completion

- [x] F1 Final validation run (AC7, AC8) and evidence ledger update. *(validated 2026-09-05T03:54:56Z; ledger updated in this commit)*
- [x] F2 Update `metadata.json` status and the registry entry per lifecycle rules. *(status set to completed; G2 closure verified via companion track `station_hardening_delegation_20260905`)*

## Phase 5 — Conductor review & archive

- [x] Rev-1 Security: `/__station/status` no longer exposes the per-session token (unauthenticated endpoint; token only needed by token-gated POST shutdown). Regression test added. *(commit `913c611`; 18/18 suite passes)*
- [x] Rev-2 Documentation: corrected stale F2 note (previously claimed status was still in-progress pending G2).
- [x] Archive this track under `conductor/archive/portable_station_hardening_20260905/` and redirect the registry link (archive-eligible: completed, validated, review fixes applied).