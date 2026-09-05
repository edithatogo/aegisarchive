# Retrospective specification: Cross-Platform Native Launchers & Multi-OS Hardening

This pack was reconstructed on 2026-09-05 from the existing objective-only plan; it does not assert a historical review.

## Scope and acceptance

- Python 3 stdlib universal launcher with port hunting (8000-8020).
- macOS double-click `.command` launcher.
- Windows `.cmd` and `.ps1` launchers with embedded Python auto-detection.
- Linux POSIX compliant `.sh` launcher.
- Root launchers for non-technical 1-click execution.


## Authoritative inputs

- AGENTS.md and conductor/workflow.md.
- Current implementation and named successor tracks, where their reviewed security requirements supersede original designs.

## Validation

Run `python3 scripts/gate.py test`, profile checks and CLI smoke checks. Record source coverage and limitations in review.md before archival.

## External boundary

Local review does not authorize publication. Hosted or native checks not run locally must be identified as such.
