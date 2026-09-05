# Track Specification: Contributor Experience

## Overview

A new contributor (human or agent) should go from clone to a passing local gate in under five minutes, find a task without asking, and know exactly what a mergeable change looks like. Today `CONTRIBUTING.md` lists principles and a generic fork/PR flow, there is no support page, no quickstart shorter than the README, and no labelled entry-level work. This track rewrites `CONTRIBUTING.md` around the implementation contract and the backlog, adds a ten-line quickstart and a `SUPPORT.md`, and seeds eight `good first issue` items, each pointing to an existing planned task in a sibling track.

## Authoritative inputs

- Repository invariants: `AGENTS.md`.
- Governance: `conductor/implementation_contract.md`, `conductor/backlog.md` (created by the integrator), `conductor/lessons.md`.
- Sibling ownership: `scripts/gate.py` and `tests/requirements-dev.txt` belong to `security_gates_and_fuzzing_20260905`; `.devcontainer/` and `pyproject.toml` belong to `release_and_packaging_20260905`; `README.md` rewrite belongs to `repo_standards_alignment_20260905`; `.github/workflows/ci.yml` belongs to `portable_station_hardening_20260905`. This track references them and does not modify them.
- Good-first-issue sources: planned tasks in `warc_interop_20260905`, `web_console_security_20260905`, `engine_correctness_20260905`, `cli_parity_20260905`.

## Requirements

- **R1 — Five-minute setup**: `CONTRIBUTING.md` opens with clone, `python3 scripts/gate.py test`, and a pointer to the launcher; no package manager steps for the runtime path.
- **R2 — Task discovery**: `CONTRIBUTING.md` explains how to pick a row from `conductor/backlog.md`, how to read a track task block, and links the implementation contract as the authoritative procedure.
- **R3 — PR checklist**: an explicit list mirroring the contract's verification and commit rules (one task per PR, conventional commit format, evidence line, leak gate clean, no new dependencies).
- **R4 — Entry-level work**: eight small, well-bounded backlog items labelled `good first issue` on GitHub, each issue body linking the track task it implements and stating Files/Verify from that task.
- **R5 — Quickstart and support**: `docs/QUICKSTART.md` (ten lines, one per step) and `SUPPORT.md` (where to ask, what to include, what is out of support scope).

## Acceptance criteria

- **AC1**: `CONTRIBUTING.md` contains headings `## 5-minute setup`, `## Picking a task`, `## Making the change`, `## Pull request checklist`, in that order, and links `conductor/implementation_contract.md` and `conductor/backlog.md`.
- **AC2**: The three setup commands in `CONTRIBUTING.md` (`git clone`, `python3 scripts/gate.py test`, launcher) are the only commands before the "Picking a task" heading; none requires `pip`, `npm`, or Docker.
- **AC3**: `docs/QUICKSTART.md` exists, has exactly ten numbered steps, and each step is a single line.
- **AC4**: `SUPPORT.md` exists and links `SECURITY.md` for vulnerability reports and the issue templates for bugs/proposals.
- **AC5**: `gh issue list --label "good first issue" --state open --json number --jq length` returns 8 after T4; every issue body contains a `conductor/tracks/<track_id>/plan.md` link and a `T<n>` reference.
- **AC6**: CI leak-prevention gate passes on all new text; `CONTRIBUTING.md` contains no vendor, organisation, or product names outside the repository's own tooling.

## Non-functional constraints

- Plain language; each document readable in under two minutes.
- No duplication of README content beyond one-line pointers.
- Documents refer to `scripts/gate.py`; if it has not landed yet when a task is executed, the implementer records `blocked` on that task (blocked_by `security_gates_and_fuzzing_20260905`).

## External gates

- **G1 (publication)**: no push without user authorization.
- **G4 (GitHub issues)**: creating labels and issues on the remote requires `gh auth status` success with `issues: write`; T4 is executed by the integrator or a maintainer, not by an unauthenticated agent.

## Out of scope

- README rewrite (`repo_standards_alignment_20260905`); `.devcontainer/` and packaging (`release_and_packaging_20260905`); the dev runner itself (`scripts/gate.py`, `security_gates_and_fuzzing_20260905`); Code of Conduct changes.
