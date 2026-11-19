# OpenGrep SAST migration (2026-11-20)

The GitHub Actions security job and `python scripts/gate.py static` now use
OpenGrep instead of the Semgrep Python CLI. The separate CodeQL, Bandit,
Gitleaks, Zizmor and fuzz jobs remain unchanged. OpenGrep is mandatory for a
complete local static gate rather than silently skipped.

- Scanner: stable upstream v1.33.1 `opengrep_manylinux_x86`, SHA-256
  `46e8133cc490f9f50518061590ce2f6be5a08afaeda034471c0ceda4b3899808`;
  the installer verifies every byte and rejects oversized, empty or incompatible assets.
- Scan: `--strict --error --severity WARNING --severity ERROR`; the same four
  registry packs, target directories and the pre-existing Bandit-duplicate rule
  exclusion are retained. Any scanner fatal error, unparseable file, positive
  synthetic test or negative synthetic test failure fails CI.
- The registry packs are **live, not version pinned**, as they were under the
  previous Semgrep invocation. This preserves existing scope without
  misleading claims of rule-byte parity. Before declaring replacement
  equivalent or pinning new rules, record both engines' exact rule IDs,
  target/skip inventories, parse coverage and finding differences on the
  same source revision. Do not add blanket suppressions.
- CI presently uses Linux x86_64. Local non-Linux installs should provide a
  separately verified OpenGrep executable on PATH; the CI installer correctly
  fails instead of silently using an unverified variant.
- The scanner runs in the GitHub runner; no API token is required. Registry
  rule downloads require outbound network access and will fail closed if
  unavailable. Do not upload source or raw findings to third-party services.
- Branch protection may still refer to the renamed
  `Static analysis (Semgrep)` check; update it to `Static analysis (OpenGrep)`
  **only after** the new check has actually completed and passed.
- Promotion depends on a real hosted run, current finding review, and the
  binary/rule-source attestations. This PR alone is not evidence of
  scan execution or a clean security result.
