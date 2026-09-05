# Track Specification: Repository Standards Alignment

## Overview

Bring this repository into conformance with the `edithatogo/repository-standards` control plane. The standards were read on 2026-09-05 (commit `ad67bedaa0c4d0769bd54fd76354bac65b25b88c`): `README.md`, `AGENTS.md`, `docs/solo-maintainer-standard.md`, `docs/repository-product-metadata-standard.md`, `docs/continuous-conformance-standard.md`, `docs/openssf-scorecard-standard.md`, `docs/automation-innovation-standard.md`, `managed-files/manifest.json`, `managed-files/templates/{scorecard,zizmor}.yml`, `profiles/archetype-profiles.json`, `renovate.json`, `security-insights.yml`, `CITATION.cff`, and the `workflow_call` inputs of `.github/workflows/{python-ci,coverage-evidence,supply-chain-evidence}.yml`.

This repository is classified as archetype `python`, supply-chain profile `published` (public, releases planned), which per the archetype profile requires: dependency review, Scorecard, SBOM, provenance, checksums, `security-insights.yml`, one authoritative version source (tag-derived), zero human approvals, force-push/deletion blocking, conversation resolution, immutable action pins.

Everything here is additive. No existing workflow is edited.

## Authoritative inputs

- Repository invariants: `AGENTS.md` (zero-install, stdlib-only runtime, vanilla ES6+ web). Development/CI tooling is allowed only in `tests/requirements-dev.txt` or inside CI jobs.
- Workflow guardrails: `conductor/workflow.md`.
- Parallel-agent ownership (must not be modified by this track): `.github/workflows/ci.yml`, `cli/launch.py`, `cli/verify_bundle.py`, `cli/test_station_hardening.py`, `conductor/tracks/portable_station_hardening_20260905/**`.
- CI leak-prevention gate in `ci.yml`: no organisation-specific names, hostnames, or vendor names may appear in any file.

## Facts verified from the standards repo (2026-09-05)

| Item | Verified value |
| --- | --- |
| Renovate preset | `renovate.json` = `{"$schema": "https://docs.renovatebot.com/renovate-schema.json", "extends": ["github>edithatogo/renovate-config"]}`; `edithatogo/renovate-config` exists (default branch `main`) |
| `security-insights.yml` | OpenSSF Security Insights **schema-version 2.2.0** (the standards repo's own file uses 2.2.0, not 1.x) |
| `CITATION.cff` | CFF 1.2.0; `version`/`date-released` only when release automation keeps them aligned; never invent ORCIDs/DOIs |
| Managed `scorecard.yml` | Template `managed-files/templates/scorecard.yml`, strategy `materialise_public_published_or_high_risk_if_missing`; uses `ossf/scorecard-action@2d1146689b8cda280b9bc96326124645441f03bc # v2.4.4`, `publish_results: true` |
| Managed `zizmor.yml` | Template `managed-files/templates/zizmor.yml`; manifest scopes it to profile `repository-infrastructure`, adopted here anyway as it is harmless and lints our new workflows |
| `python-ci.yml` inputs | `python-version` (string, default `"3.14"`), `install-command` (string, default `python -m pip install -e ".[test]"`), `test-command` (string, default `python -m pytest --cov --cov-report=xml`); job `test`; uploads to Codecov via OIDC with `fail_ci_if_error: true` |
| `coverage-evidence.yml` inputs | `files` (required string), `flags` (default `unit`), `fail-ci-if-error` (boolean, default true); it checks out the repo itself, so it can only upload committed files — **not called** by this track (python-ci already uploads coverage) |
| `supply-chain-evidence.yml` inputs | `artifact-path` (required string); it checks out the repo itself, so `artifact-path` must be a committed path; produces SPDX + CycloneDX SBOMs, `CHECKSUMS.sha256`, build-provenance attestation |
| Version authority (python) | `pyproject_or_tag_derived`; standard says derive from tags with `setuptools-scm` or equivalent |
| README contract | 9 sections in order: name+purpose, badge row, status/scope, install, usage, dev/verify, security reporting, citation, licence/third-party rights; only actionable badges |
| Rulesets | block force-push and deletion, require stable automated checks and conversation resolution, 0 approvals, no CODEOWNERS, explicit owner recovery (admin bypass) |
| Repo identity | description present; topics present but missing `solo-maintainer` |

## Requirements

- **R1 — Renovate preset**: `renovate.json` extends `github>edithatogo/renovate-config`.
- **R2 — Citation metadata**: `CITATION.cff` (CFF 1.2.0) with accurate title, type, author, repository URL, licence; no invented identifiers; no `version`/`date-released` until release automation maintains them.
- **R3 — CalVer changelog**: `CHANGELOG.md` in Keep-a-Changelog layout with CalVer `YYYY.MM.DD` headings, seeded from the existing `git log`.
- **R4 — Security Insights**: `security-insights.yml` (schema 2.2.0) describing this repository's vulnerability-reporting and security posture.
- **R5 — Managed workflows**: `.github/workflows/scorecard.yml` and `.github/workflows/zizmor.yml` copied byte-for-byte from the standards templates.
- **R6 — Packaging**: `pyproject.toml` with zero runtime dependencies, tag-derived version, and console scripts `aegisarchive`, `aegisarchive-verify`, `aegisarchive-mcp`; package names must not shadow PyPI packages (`mcp` is the official MCP SDK; `cli` is a generic name), so the installed import names are `aegisarchive_cli` and `aegisarchive_mcp` via `package-dir` mapping while on-disk folders stay `cli/` and `mcp/`.
- **R7 — Thin standards CI**: `.github/workflows/standards-ci.yml` calling `python-ci.yml` and `supply-chain-evidence.yml` from the standards repo with correct inputs, plus dependency review on pull requests.
- **R8 — Test scaffold**: `tests/` with a stdlib `unittest` smoke suite so `python-ci` has something to run and cover; `tests/requirements-dev.txt` for dev-only tooling (`coverage`).
- **R9 — README contract**: README restructured to the 9-section order with an honest Status table (implemented vs planned).
- **R10 — Rulesets and repo identity**: `main` ruleset (deletion + non-fast-forward blocked, PR with 0 approvals + conversation resolution, required stable checks, admin bypass) and topic `solo-maintainer`, applied through `gh api`.

## Acceptance criteria

- **AC1**: `python3 -c "import json;d=json.load(open('renovate.json'));assert d['extends']==['github>edithatogo/renovate-config']"` succeeds.
- **AC2**: `CITATION.cff` parses as YAML-subset key/value text, contains `cff-version: 1.2.0`, `type: software`, `license: Apache-2.0`, `repository-code: "https://github.com/edithatogo/aegisarchive"`, and no `doi:`/`orcid:` keys.
- **AC3**: `CHANGELOG.md` contains `## [Unreleased]`, the CalVer convention sentence (`vYYYY.MM.DD`), and one bullet per existing non-conductor commit from `git log`; no tagged section is invented (no tag exists yet).
- **AC4**: `security-insights.yml` contains `schema-version: 2.2.0` and `reports-accepted: true`.
- **AC5**: `scorecard.yml` and `zizmor.yml` are byte-identical to the standards templates (`gh api ... | cmp -`).
- **AC6**: `pip install -e .` in a throwaway venv exposes three console scripts; `aegisarchive --help`, `aegisarchive-verify --help` exit 0; `aegisarchive-mcp` answers `initialize`; `tomllib` confirms `dependencies == []`.
- **AC7**: `python3 -m unittest discover -s tests -t . -p "test_*.py"` passes locally; `standards-ci.yml` parses and references only the verified reusable-workflow inputs.
- **AC8**: README has the nine H2 sections in order and a Status table; existing quick-start content is preserved under "Install".
- **AC9**: `gh api repos/edithatogo/aegisarchive/rulesets` lists one active ruleset on `~DEFAULT_BRANCH` containing `deletion`, `non_fast_forward`, `pull_request` (0 approvals, thread resolution) and `required_status_checks`.
- **AC10**: Existing `ci.yml` leak-prevention gate remains clean; no parallel-agent-owned file is modified (`git diff --stat` shows none of them).

## Gates and severity semantics

- **G1 (remote writes)**: Applying rulesets and repository topics writes to GitHub and requires explicit user authorisation. T11 must not run without it.
- **G2 (Codecov OIDC)**: `python-ci.yml` fails if the repository is not activated on Codecov (OIDC). Activation is a user action outside the repo. Until done, `standards-ci.yml` is expected to fail at the Codecov step and MUST NOT be listed as a required check.
- Standards' Scorecard score is diagnostic, not a gate. Nothing in this track lowers any security gate threshold defined in `security_gates_and_fuzzing_20260905`.

## Out of scope

- Registering the repository in `edithatogo/repository-standards:registry/repositories.json` (external repository; recorded as a follow-up in `plan.md`).
- Renaming `cli/` or `mcp/` folders on disk (would break `START_*` launchers and `ci.yml` smoke tests owned by the parallel agent).
- Security scanners and fuzzing (`security_gates_and_fuzzing_20260905`); release workflow and devcontainer (`release_and_packaging_20260905`).
- Editing `ci.yml` to SHA-pin its actions (parallel-agent file; note handed over instead).
