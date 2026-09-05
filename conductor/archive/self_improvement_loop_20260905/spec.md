# Track Specification: Self-Improving System Loop

## Overview

The repository's documentation has, at several points in its history, described capabilities before the code existed, and its Conductor tracks have drifted from their plans without anyone noticing. This track adds a weekly, fully automated loop that (a) audits documentation claims against code symbols, (b) audits Conductor track hygiene, (c) writes a report into the repository, and (d) keeps exactly one open GitHub issue up to date with the findings, so that planners and small implementing agents always start from verified facts. It also makes the governance protocol (`conductor/implementation_contract.md`) discoverable from `AGENTS.md` and establishes the `conductor/lessons.md` ledger as part of track completion.

## Authoritative inputs

- Repository invariants: `AGENTS.md` (zero-install; stdlib-only runtime; development tooling only in CI and `tests/requirements-dev.txt`).
- Workflow guardrails: `conductor/workflow.md`, `conductor/implementation_contract.md`.
- Ownership: `.github/workflows/ci.yml` and the `cli/launch.py`, `cli/verify_bundle.py`, `cli/test_station_hardening.py` files belong to `portable_station_hardening_20260905` and are not modified; all automation in this track lives in a new workflow file.
- Related tracks: `security_gates_and_fuzzing_20260905` (owns `scripts/gate.py`, `tests/requirements-dev.txt`), `repo_standards_alignment_20260905` (owns Scorecard/zizmor workflows), `contributor_experience_20260905` (owns `CONTRIBUTING.md`, good-first-issue labelling).

## Requirements

- **R1 — Claims audit**: a stdlib Python script maps each user-facing capability claim to a mechanical check (symbol grep or a writer run) and prints a Markdown table; non-zero exit on mismatch, `--allow-fail` for report mode.
- **R2 — Track health audit**: a stdlib Python script parses every track's `metadata.json`, `plan.md`, `evidence.jsonl`, plus `conductor/backlog.md` and `conductor/lessons.md`, and reports stale `in_progress` tracks, `completed` tracks with unticked boxes or without a lesson, `planned` tracks without spec, missing evidence, and backlog rows pointing to non-existent tracks. Legacy tracks (plan only) are informational, not findings.
- **R3 — Scheduled loop**: a new workflow runs weekly and on demand, executes the baseline tests, both audits, writes `audits/latest/self-improvement.md`, commits it with `[skip ci]`, and upserts a single issue labelled `self-improvement`.
- **R4 — Intake**: an issue form whose fields map 1:1 to `conductor/backlog.md` columns so external proposals can be moved into the backlog without rewriting.
- **R5 — Governance wiring**: `AGENTS.md` gains an additive "Improvement protocol" section pointing at the implementation contract; `conductor/lessons.md` gains explicit maintenance rules referenced by the contract and enforced by the track-health audit.

## Acceptance criteria

- **AC1**: `python3 scripts/claims_audit.py` prints a Markdown table with at least 7 rows and exits 1 on the current repository (known mismatches: OPFS streaming, request records, IndexedDB persistence, CDX field count); `--allow-fail` exits 0 with the same table.
- **AC2**: `python3 scripts/track_health.py` exits 0 on the current repository, lists every directory under `conductor/tracks/`, and reports the legacy plan-only tracks under "Informational" rather than "Findings".
- **AC3**: `python3 scripts/track_health.py --strict` exits 1 when a fixture track has `status: completed` and an unticked box (verified with a temporary copy of the tracks directory).
- **AC4**: The workflow `.github/workflows/self-improvement.yml` passes `python3 -c "import yaml"`-free structural validation (it is parsed by `actionlint` in the security track's gate if available, otherwise by a stdlib line check for the required keys `schedule`, `workflow_dispatch`, `permissions`), and on its first `workflow_dispatch` run produces `audits/latest/self-improvement.md` and one open issue labelled `self-improvement`.
- **AC5**: A second run of the workflow updates the existing issue body instead of opening a second issue (`gh issue list --label self-improvement --state open` returns exactly one).
- **AC6**: `.github/ISSUE_TEMPLATE/improvement_proposal.yml` has input ids `priority`, `track_id`, `task`, `status`, `owner`, `blocked_by`, matching the backlog columns.
- **AC7**: `AGENTS.md` contains a heading `## 🔁 Improvement Protocol` that links `conductor/implementation_contract.md`, `conductor/backlog.md`, and `conductor/lessons.md`; no existing lines of `AGENTS.md` are altered.
- **AC8**: CI leak-prevention gate passes; all new Python passes `py_compile`; no new runtime dependency.

## Non-functional constraints

- Scripts under `scripts/` use the Python standard library only and run from any working directory.
- The workflow uses only `actions/checkout`, `actions/setup-python`, and the preinstalled `gh` CLI; it needs `contents: write` and `issues: write` and nothing else.
- Reports must not include repository secrets, tokens, or environment dumps.

## External gates

- **G1 (publication)**: pushing commits requires explicit user authorization; this track does not push.
- **G3 (labels)**: creating the `self-improvement` label on the remote repository requires `issues: write`; the workflow creates it if missing (`gh label create --force`).

## Out of scope

- Fixing the mismatches the claims audit finds (owned by `warc_interop_20260905` for request records and CDX fields, `web_console_security_20260905` for OPFS/IndexedDB wiring).
- Scorecard/zizmor deltas (owned by `repo_standards_alignment_20260905`); the report links to their workflow runs only.
- Fuzz smoke tests (owned by `security_gates_and_fuzzing_20260905`).
