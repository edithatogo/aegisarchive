# Track Plan: Release Workflow, Provenance, and Dev Container

## Status: COMPLETE

Implementers follow `conductor/implementation_contract.md`. One task = one commit. `cli/launch.py` was hardened by `portable_station_hardening_20260905` (token auth, Host check, no CORS, `--verify`, `--idle-timeout`) and is a **read-only API**.

## Implementation notes for a small model

Touch only: `.devcontainer/devcontainer.json`, `.devcontainer/Dockerfile` (if used), `.github/workflows/release.yml`. Optionally a short `docs/release.md` if a task lists it.

Do not touch: `README.md`, `CONTRIBUTING.md`, `pyproject.toml`, `.github/workflows/ci.yml`, `cli/launch.py`, `cli/verify_bundle.py`, `cli/test_station_hardening.py`, `cli/aegis_cli.py`, `web/`, `mcp/`, `profiles/`, `START_*`, `SECURITY.md`, `conductor/tracks/portable_station_hardening_20260905/`.

Depends on: nothing for T1; T2/T3 should not assume `pyproject.toml` exists until `repo_standards_alignment_20260905` T7 is ticked. Future WACZ packaging is `future_capabilities_20260905` after `warc_interop_20260905`.

## Phase 1 — Dev container

- [x] T1 Add `.devcontainer/devcontainer.json`. *(AC1, AC2)*
  - **Files**: `.devcontainer/devcontainer.json` (new)
  - **Change**: create a JSON file with `name` `AegisArchive`, either `image` (`mcr.microsoft.com/devcontainers/python:3.11`) or `build.dockerfile` `Dockerfile`, `remoteUser` `vscode` if the image has that user, and `customizations.vscode.extensions` empty or limited to Python/JSON. No `postCreateCommand` that runs `pip install` for runtime libraries. Optional comment: runtime is Python stdlib + browser; scanners live in `tests/requirements-dev.txt` for CI only.
  - **Verify**:
    ```bash
    test -f .devcontainer/devcontainer.json
    python3 -c "import json; d=json.load(open('.devcontainer/devcontainer.json')); assert 'image' in d or 'build' in d; print('ok')"
    grep -nE 'pip install|requests==|flask==' .devcontainer/* || true
    ```
    Expected: first command silent success; second prints `ok`; third prints nothing.
  - **Done when**: AC1 and AC2 hold; leak gate clean.
  - **Do not**: add Docker Compose; install Node via a second image unless needed for `node --test`; edit `README.md`.

## Phase 2 — Release checksums

- [x] T2 Add `.github/workflows/release.yml` that writes and uploads `SHA256SUMS`. *(AC3, AC5)*
  - **Files**: `.github/workflows/release.yml` (new)
  - **Change**: workflow `on: release: types: [published]` (and optionally `workflow_dispatch`). Job on `ubuntu-latest`. Checkout. Produce or download the release source archive. Compute SHA-256 for each artefact into a file named `SHA256SUMS`. Upload `SHA256SUMS` with `gh release upload` or `softprops/action-gh-release` **pinned by SHA**. Permissions: `contents: write`. Do not `uses:` any unpinned floating tag. Do not `workflow_call` into `ci.yml`.
  - **Verify**:
    ```bash
    python3 -c "import pathlib; t=pathlib.Path('.github/workflows/release.yml').read_text(); assert 'SHA256SUMS' in t; assert 'release' in t.lower(); print('ok')"
    grep -n ci.yml .github/workflows/release.yml || true
    ```
    Expected: `ok`; second command prints nothing.
  - **Done when**: AC3 and AC5 hold.
  - **Do not**: edit `.github/workflows/ci.yml`; add Trusted Publishing to a language index in this task (Scorecard/Trusted Publishing research is `future_capabilities_20260905`).

## Phase 3 — SLSA provenance

- [x] T3 Attach SLSA provenance whose subjects match `SHA256SUMS`. *(AC4, AC6)*
  - **Files**: `.github/workflows/release.yml` (edit)
  - **Change**: add a job or step that generates SLSA provenance for the uploaded artefacts (GitHub generic SLSA generator, pinned by commit SHA). Upload the provenance attestation next to `SHA256SUMS`. `id-token: write` only on that job.
  - **Verify**:
    ```bash
    grep -qi slsa .github/workflows/release.yml && echo yes
    python3 -m py_compile $(git ls-files '*.py')
    python3 cli/test_station_hardening.py
    ```
    Expected: `yes`; compile silent success; station tests pass.
  - **Done when**: AC4 and AC6 hold; leak gate clean (step 3.4 of `conductor/implementation_contract.md`).
  - **Do not**: rename existing CI jobs; vendor product names that trip the leak gate.

## Phase 4 — Completion

- [x] F1 Tick remaining boxes only after T1–T3 Verify commands pass. Update `metadata.json` status via the implementation contract when the last task is done. Registry update is the integrator's job (already listed in `conductor/tracks.md`).
