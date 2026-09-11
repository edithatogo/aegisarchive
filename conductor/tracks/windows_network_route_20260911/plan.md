# Plan

## Status: COMPLETED (2026-09-11 — scoped routing and diagnostics verified; workstation acceptance remains separate)

- [x] T1 Add automatic Windows routing and staged diagnostics. *(AC1–AC4)* — commit c3c0b78
  - **Files**: `cli/windows_proxy.py`, `cli/network_transport.py`, `cli/capture_bridge.py`, `tests/test_network_transport.py`, `tests/test_windows_proxy.py`, `tests/test_capture_diagnostics.py`, `scripts/diagnostic_intake.py`, `scripts/windows_portable_acceptance.ps1`, `docs/WINDOWS_USB.md`, `docs/DIAGNOSTIC_WORKFLOW.md`, `conductor/backlog.md`, `conductor/tracks.md`, `conductor/lessons.md`, `conductor/reviews/windows_network_route_20260911.md`.
  - **Change**: Add stdlib native Windows PAC resolution with deterministic route decisions, fail-closed errors and safe JSON stage events; integrate into capture bridge and document limitations. Add failing regressions before implementation.
  - **Verify**: `python3 -m unittest discover -s tests -p 'test_*proxy.py' -v`; `python3 -m unittest discover -s tests -p 'test_network_transport.py' -v`; `python3 scripts/gate.py test`; `python3 scripts/track_health.py --strict`; final-head GitHub Actions.
  - **Done when**: Regressions, baseline, hosted Windows native bindings and agent review pass; no actual-workstation success claim.
  - **Do not**: Change machine settings, install dependencies, send implicit domain credentials, bypass pacing/TLS/scope, or publish private diagnostics.
