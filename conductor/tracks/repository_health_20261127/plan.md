# Implementation plan

Chat 01a1a4fa-a107-7502-8670-7abc4e934613 owns `codex/aegis-repo-health-20261127` in `/Users/doughnut/Documents/Codex/2026-11-04/if-y/work/aegis-t7-closeout`. Scope includes the contributor checks, shared local Git hook and exact GitHub check protection. The pull request captures hosted acceptance. The next native operation is to verify the additional check requirements after a successful hosted run.

## Status: COMPLETED (2026-11-27 — local implementation and controls verified)

- [x] T1 Install repository safeguards and verify the community profile. (AC1, AC2, AC3)
  - **Files**: `.pre-commit-config.yaml`, `.alint.yml`, `.trufflehog-fixtures.json`, `scripts/trufflehog_gate.py`, `.github/workflows/repository-health.yml`, `.github/CODEOWNERS`, `.github/ISSUE_TEMPLATE/config.yml`, `.github/ISSUE_TEMPLATE/bug_report.md`, `CONTRIBUTING.md`, `SUPPORT.md`, `SECURITY.md`, `security-insights.yml`.
  - **Change**: Check staged secrets, whitespace and changed workflows. Add pinned TruffleHog, alint and RepoHealth to GitHub Actions. Review the eight historical URI fixtures against their immutable Git locations and both scanner value fields. Route contributors to support and private security reporting.
  - **Verify**: Run `pre-commit validate-config`, `actionlint`, a clean and a failing commit in a temporary repository, a TruffleHog history scan and synthetic control, `alint check --untrusted`, and `python scripts/gate.py test`. Check exact-head Actions, GitHub community health, vulnerability reporting and required check settings.
  - **Done when**: Hooks and hosted checks run, new triggers reject the positive controls, and native settings match the approved scope.
  - **Do not**: Publish diagnostic values, verify detected credentials over the network, exclude broad directories, or weaken the existing scan gates.
