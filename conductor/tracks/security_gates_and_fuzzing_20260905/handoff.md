# Security Track Handoff Notes

These items concern files owned by parallel tracks (specifically `ci.yml` and `cli/launch.py` under `portable_station_hardening_20260905`). They are documented here to maintain drift guards and avoid cross-track merge conflicts.

## 1. `cli/launch.py:170` (Bandit B310 / Semgrep audit rule)
- **Finding**: Audit url open for permitted schemes on the station status query:
  `with urllib.request.urlopen(f"http://127.0.0.1:{port}/__station/status", timeout=timeout)`
- **Recommendation**: Add `# nosec B310  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected` to the `urlopen` invocation (it targets only local loopback).
- **Cleanup**: Once added, `.bandit-baseline.json` can be deleted, and the `--exclude-rule` removed from `.github/workflows/security.yml` and `scripts/gate.py`.

## 2. `.github/workflows/ci.yml` (Workflow hardening & SHA pinning)
- **Finding**: Unpinned actions and missing top-level workflow permissions.
- **Recommendation**:
  - SHA-pin `actions/checkout` (`3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`) and `actions/setup-python` (`5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0`) across all 4 job sites.
  - Add top-level `permissions: contents: read`, `concurrency`, and `timeout-minutes: 15`.
- **Cleanup**: Once hardened, the two `ci.yml` ignores in `.github/zizmor.yml` can be deleted.

## 3. Leak Gate Integration (Optional)
- `ci.yml` may optionally invoke `python3 scripts/gate.py leak` instead of the inline grep once both are on `main`.
