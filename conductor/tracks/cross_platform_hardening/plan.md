# Track Plan: Cross-Platform Native Launchers & Multi-OS Hardening

## Status: COMPLETED

### Objectives
- Python 3 stdlib universal launcher with port hunting (8000-8020).
- macOS double-click `.command` launcher.
- Windows `.cmd` and `.ps1` launchers with embedded Python auto-detection.
- Linux POSIX compliant `.sh` launcher.
- Root launchers for non-technical 1-click execution.

## Review Fixes

- [ ] Rev-1 Make the Linux wrapper POSIX-compatible as specified.
  - **Files**: `START_LINUX.sh`.
  - **Change**: use `/bin/sh` and replace the bash-only read prompt.
  - **Verify**: `sh -n START_LINUX.sh`; `bash -n START_MAC.command`; `python3 cli/test_station_hardening.py`.
  - **Done when**: syntax checks and station tests pass.
  - **Do not**: claim native Windows double-click validation from a macOS run.
