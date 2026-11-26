# OpenGrep SAST migration (2026-11-20)

The GitHub Actions security job and `python scripts/gate.py static` now use
OpenGrep instead of the Semgrep Python CLI. The separate CodeQL, Bandit,
Gitleaks, Zizmor and coverage-guided fuzz checks retain their gates. OpenGrep is mandatory for a
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
- The required status context is `Static analysis (Semgrep)`. Its job runs OpenGrep and the stage logs identify the engine and version.
- Promotion depends on a real hosted run, current finding review, and the
  binary/rule-source attestations. This PR alone is not evidence of
  scan execution or a clean security result.

### Qualified parser remediation

The first hosted OpenGrep run (commit ec0d550) loaded 1,098 community
rules and reported zero findings, but correctly failed strict analysis on
`web/lib/mirror_resources.js` line 26 because its JavaScript parser
partially analysed a complex regex literal. The revised source expresses
the **same constant regex** through `new RegExp(String.raw`...`, 'gi')`.
Native Node.js verification compared original and replacement `.source`,
`.flags` and match captures on seven synthetic inputs; the focused JS
regression tests also cover comments, quoted greater-than signs, script
bodies and CSS extraction. No file or rule has been excluded to make the
scan pass. CI must independently verify the new exact head.
