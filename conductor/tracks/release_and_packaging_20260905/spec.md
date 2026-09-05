# Track Specification: Release Workflow, Provenance, and Dev Container

## Overview

Sibling tracks already own contributor docs (`contributor_experience_20260905`), the nine-section README and `pyproject.toml` (`repo_standards_alignment_20260905`), and security scanners (`security_gates_and_fuzzing_20260905`). This track only adds a reproducible local environment (`.devcontainer/`) and a tag-triggered release workflow that publishes checksums and SLSA provenance. Runtime stays zero-install: the container must not require `pip install` for `cli/` or `mcp/`.

## Authoritative inputs

- Repository invariants: `AGENTS.md`.
- Implementation contract: `conductor/implementation_contract.md`.
- Hardened launcher API (read-only): `cli/launch.py` from `portable_station_hardening_20260905` (token auth, Host check, no CORS, `--verify`, `--idle-timeout`).
- Packaging metadata: `pyproject.toml` is created by `repo_standards_alignment_20260905` T7; this track must not rewrite it.
- Do not modify `.github/workflows/ci.yml`.

## Requirements

- **R1 — Dev container**: `.devcontainer/devcontainer.json` and `.devcontainer/Dockerfile` (or an image reference) provide Python 3.11+, Node 18+, git, and the workspace mount. Post-create runs no `pip install` of runtime deps. Optional comments may mention `tests/requirements-dev.txt` as CI-only.
- **R2 — Release checksums**: on published GitHub release tags matching `v*`, `.github/workflows/release.yml` builds a source archive (or uses the GitHub-generated source tarball), writes `SHA256SUMS` of every attached artefact, and uploads `SHA256SUMS` as a release asset.
- **R3 — SLSA provenance**: the same workflow generates SLSA provenance for the attached artefacts (GitHub Actions generic generator or equivalent) and uploads it beside `SHA256SUMS`. Provenance subject digests must match the checksum file.
- **R4 — Least privilege**: `release.yml` does not use `pull_request` from forks with write tokens; permissions are `contents: write` and `id-token: write` only as required for provenance; `ci.yml` is untouched.
- **R5 — Honesty**: workflow comments and any new file under `.devcontainer/` must not claim WACZ, Compression Streams `.warc.gz`, or service-worker replay until `future_capabilities_20260905` ADRs say go.

## Acceptance criteria

- **AC1**: `test -f .devcontainer/devcontainer.json` succeeds. `python3 -c "import json; d=json.load(open('.devcontainer/devcontainer.json')); assert 'image' in d or 'build' in d; print('ok')"` prints `ok`.
- **AC2**: `.devcontainer/devcontainer.json` contains neither `pip install` of a runtime package name nor a `features` entry that installs a third-party Python HTTP client. Verify: `grep -nE 'pip install|requests==|flask==' .devcontainer/* || true` prints nothing.
- **AC3**: `.github/workflows/release.yml` exists, `on.release.types` includes `published` (or `on.push.tags` is `v*`), and the file contains the string `SHA256SUMS`. Verify: `python3 -c "import pathlib; t=pathlib.Path('.github/workflows/release.yml').read_text(); assert 'SHA256SUMS' in t; assert 'release' in t.lower(); print('ok')"` prints `ok`.
- **AC4**: `release.yml` mentions SLSA provenance generation (`slsa` case-insensitive) and uploads a provenance file. Verify: `grep -qi slsa .github/workflows/release.yml && echo yes` prints `yes`.
- **AC5**: `grep -n ci.yml .github/workflows/release.yml || true` prints nothing (this workflow must not include or replace `ci.yml`).
- **AC6**: `python3 -m py_compile $(git ls-files '*.py')` and `python3 cli/test_station_hardening.py` still pass; leak-prevention gate is clean.

## Gates

- **G1 (publication)**: no push without explicit user authorization recorded as `gate_authorized` in this track's `evidence.jsonl`.
- **G2**: companion-program harvest work is out of this repository; do not add harvest-host configuration here.

## Cross-track dependencies

- Land `repo_standards_alignment_20260905` T7 (`pyproject.toml`) before wiring console-script names into release notes; checksums of git archives do not require it.
- `warc_interop_20260905` before any future WACZ packaging (`future_capabilities_20260905`).
- `cli/launch.py` is a read-only API from `portable_station_hardening_20260905`.

## Out of scope

- `README.md` rewrite (nine-section contract is `repo_standards_alignment_20260905`).
- `CONTRIBUTING.md`, `docs/QUICKSTART.md`, `SUPPORT.md` (`contributor_experience_20260905`).
- `pyproject.toml` (`repo_standards_alignment_20260905` T7).
- `.github/workflows/ci.yml`, `cli/launch.py`, `cli/verify_bundle.py`, `cli/test_station_hardening.py`.
- `conductor/tracks/portable_station_hardening_20260905/`.
- Security scanners (`security_gates_and_fuzzing_20260905`).
