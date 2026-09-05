# Track Specification: Security Gates & Fuzzing

## Overview

Add automated security gates and fuzzing to this repository as a **new** workflow (`.github/workflows/security.yml`) plus supporting configuration, harnesses, and a local stdlib mirror, without modifying the existing `ci.yml`. Every gate is fail-closed at the medium severity level.

## Severity semantics (normative)

**Gates FAIL if any medium-or-higher finding persists.** Concretely:

| Tool | Medium-or-higher means | Enforcement |
| --- | --- | --- |
| gitleaks | any finding (secrets have no "low") | action exit code |
| CodeQL | result whose rule has `properties.security-severity >= 4.0` (CVSS medium) **or** whose effective `level` is `error` | `scripts/sarif_gate.py` (stdlib) on the SARIF produced with `upload: never` |
| Semgrep | severity `WARNING` (medium) or `ERROR` (high) | `--severity WARNING --severity ERROR --error` |
| Bandit | severity medium+ **and** confidence medium+ | `-ll -ii`; one baselined finding in a file owned by another track |
| zizmor | severity medium+ and confidence medium+ | `--min-severity medium --min-confidence medium` |
| Fuzzing | any crash, uncaught exception, timeout, or assertion in a harness | libFuzzer/atheris exit code; `node --test` failure |

Thresholds are part of this specification. Raising a threshold, adding `nosec`/`nosemgrep`/ignore entries, or extending baselines/allowlists requires a recorded justification in `plan.md` and `evidence.jsonl`; the only pre-approved exceptions are listed under "Pre-approved exceptions".

## Authoritative inputs

- `AGENTS.md`: zero-install runtime (Python stdlib, vanilla ES6+). All scanner/fuzz tooling is dev-only, declared in `tests/requirements-dev.txt`, installed only inside CI jobs or a developer venv.
- Parallel-agent ownership (never modified by this track): `.github/workflows/ci.yml`, `cli/launch.py`, `cli/verify_bundle.py`, `cli/test_station_hardening.py`, `conductor/tracks/portable_station_hardening_20260905/**`.
- Leak-prevention gate in `ci.yml`: mirrored locally by `scripts/gate.py leak` reading the encoded pattern from `ci.yml` (single source of truth).
- `tests/requirements-dev.txt` is created by `repo_standards_alignment_20260905` T7 (with `coverage`); this track appends to it, or creates it if the standards track has not landed yet.

## Facts verified during planning (2026-09-05)

- Current tree, random-input probes (300–2000 inputs): `cli/warc_verify.verify_warc` raises `ValueError` (non-numeric `Content-Length`) and `IndexError` (negative `Content-Length`); `mcp/server.search_cdx` never raised; JS `canonicalizeUrl`, `isUrlInScope`, `parseRetryAfter`, `WarcReader.loadWarcBuffer` never threw. Hence R2 (hardening) precedes the fuzz job.
- `mcp/server.py` dispatches JSON-RPC inline inside `main()`; no importable dispatch function exists. R1 extracts `handle_request(req) -> dict | None` and `process_line(line) -> str | None` without behaviour change.
- Bandit `-ll -ii` on `cli mcp`: exactly two findings, both `B310` (dynamic `urllib.request.urlopen`): `cli/aegis_cli.py:194` (this track fixes it with a scheme allow-list) and `cli/launch.py:170` (loopback literal URL; file owned by another track → baselined).
- Semgrep `p/default p/python p/javascript p/owasp-top-ten` at WARNING+: the same two `dynamic-urllib-use-detected` sites, plus four `github-actions-mutable-action-tag` findings in `ci.yml`. Semgrep therefore scans code directories only (`cli mcp web scripts tests`); workflow files are zizmor's responsibility.
- zizmor 1.30 at medium+: `ci.yml` has 4 `unpinned-uses` (high) and 3 `excessive-permissions` (medium). Handled by a per-file ignore in `.github/zizmor.yml` with handoff to the owner. The new workflows in this and sibling tracks lint clean (verified with zizmor 1.30.0 and actionlint).
- gitleaks (default rules, `--no-git` directory scan) on the current tree: no findings. The action honours `GITLEAKS_CONFIG`.
- atheris 3.1.0 publishes Linux x86_64 wheels only for CPython 3.12–3.14; the fuzz job uses Python 3.12 and the requirement carries `sys_platform == "linux"`.
- Pinned SHAs (resolved from tags): `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1` (v7.0.1), `actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97` (v7.0.0), `actions/setup-node@820762786026740c76f36085b0efc47a31fe5020` (v7.0.0), `gitleaks/gitleaks-action@ff98106e4c7b2bc287b24eaf42907196329070c7` (v2.3.9), `github/codeql-action@cdf488f595d80d6e07e03d4674febd5ab45fa938` (v4.37.9), `google/clusterfuzzlite@884713a6c30a92e5e8544c39945cd7cb630abcd1` (v1).

## Requirements

- **R1 — Importable MCP dispatch**: `mcp/server.py` exposes `handle_request(req: dict)` and `process_line(line: str)`; `main()` becomes a thin loop. Wire-level behaviour is unchanged (verified by the existing `ci.yml` MCP smoke test and a scripted transcript).
- **R2 — Parser hardening**: `verify_warc` treats a non-digit `Content-Length` as a corrupt record (warning, `corrupt_count += 1`, stop) and clamps the body end to the file size; never raises on arbitrary bytes.
- **R3 — Secrets gate**: gitleaks with `.gitleaks.toml` allow-listing `tests/fixtures/**` only.
- **R4 — CodeQL gate**: `python` and `javascript-typescript`, `upload: never` + `output: sarif-results`, then `scripts/sarif_gate.py` (stdlib) fails on medium-or-higher; SARIF is still uploaded afterwards for visibility.
- **R5 — Semgrep gate**: rulesets `p/default p/python p/javascript p/owasp-top-ten`, WARNING+ fails, vendored `web/lib/minisearch.min.js` excluded.
- **R6 — Bandit gate**: `bandit -r cli mcp -ll -ii -b .bandit-baseline.json`; baseline contains exactly the one `cli/launch.py` B310 finding.
- **R7 — Workflow lint gate**: zizmor medium+ over `.github/workflows` with `.github/zizmor.yml` ignoring only `ci.yml` for `unpinned-uses` and `excessive-permissions`.
- **R8 — Fuzz harnesses**: `tests/fuzz/fuzz_warc_parse.py`, `fuzz_cdx_search.py`, `fuzz_mcp_rpc.py` (atheris; stdlib `--smoke N` fallback), each run 60 s in CI with `-max_total_time=60 -atheris_runs=500000`; `tests/js/fuzz_props.test.js` property tests via `node --test` with an inline LCG generator (no npm).
- **R9 — ClusterFuzzLite**: `.clusterfuzzlite/{project.yaml,Dockerfile,build.sh}` and `.github/workflows/cflite_pr.yml` (code-change mode, address sanitizer, 300 s) on PRs touching parser code.
- **R10 — Local mirror**: `scripts/gate.py` (stdlib) with subcommands `leak`, `test`, `static`, `fuzz`, `all`; runs whichever of bandit/semgrep/gitleaks/zizmor is installed and reports skips explicitly.
- **R11 — Dev tooling isolation**: `tests/requirements-dev.txt` lists `bandit`, `semgrep`, `zizmor`, `atheris` (Linux marker); nothing is imported at runtime.

## Acceptance criteria

- **AC1**: `printf` transcript of `initialize`, `notifications/initialized`, `tools/list`, malformed JSON, `tools/call`, unknown method through `python3 mcp/server.py` yields 5 response lines with ids `1, 2, null, 3, 4` and error codes `-32603` (malformed) and `-32601` (unknown). `ci.yml` MCP smoke test still passes.
- **AC2**: `python3 tests/fuzz/fuzz_warc_parse.py --smoke 2000` and `FUZZ_SEED=7 ... --smoke 2000` print `smoke OK`; the pre-fix tree fails the same command (regression evidence).
- **AC3**: `python3 scripts/sarif_gate.py` exits 1 on a SARIF containing a `security-severity: 7.5` result or a rule with `defaultConfiguration.level: error`, exits 0 on an empty run, exits 2 on an unreadable file.
- **AC4**: `bandit -r cli mcp -ll -ii -b .bandit-baseline.json` exits 0 and the baseline contains exactly one result (`cli/launch.py`, `B310`).
- **AC5**: `semgrep scan ... cli mcp web scripts tests` (exact command in `security.yml`) exits 0 locally.
- **AC6**: `zizmor --min-severity medium --min-confidence medium --offline .github/workflows` exits 0 locally; `actionlint` passes on every new workflow.
- **AC7**: `node --test tests/js/` passes (4 tests); `python3 scripts/gate.py` prints `gate: PASS`.
- **AC8**: `security.yml` runs green on `main` with all six jobs (`Secrets scan (gitleaks)`, `CodeQL (python)`, `CodeQL (javascript-typescript)`, `Static analysis (Semgrep)`, `Static analysis (Bandit)`, `Workflow lint (zizmor)`, `Fuzz smoke`) — observed after the integrator pushes (G1).
- **AC9**: No parallel-agent-owned file differs from `origin/main`; `ci.yml` leak gate stays clean; `pyproject.toml` (if present) still has `dependencies = []`.

## Pre-approved exceptions (the only ones)

1. `.bandit-baseline.json`: one `B310` at `cli/launch.py` (loopback literal URL; owner asked to add `# nosec B310` — see handoff). Remove the baseline when that lands.
2. Semgrep `--exclude-rule python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected`: duplicates Bandit B310; the true positive in `aegis_cli.py` is fixed by a scheme allow-list; the `launch.py` site is loopback-literal. Remove when the owner adds `# nosemgrep` inline.
3. `.github/zizmor.yml`: `unpinned-uses` and `excessive-permissions` ignored for `ci.yml` only (owner handoff: SHA-pin actions, add `permissions: contents: read`).
4. `.gitleaks.toml`: `tests/fixtures/**` allow-listed (synthetic data). The directory does not exist yet; the allow-list is forward-looking.
5. CodeQL `paths-ignore: web/lib/minisearch.min.js` (vendored, minified third-party library).

## External gates

- **G1 (publication)**: pushing to the remote requires explicit user authorisation; this track does not push. CI results (AC8) can only be observed after the integrator pushes.
- **G2 (cross-track)**: `ci.yml`/`launch.py` remediation requests are delivered as a handoff note to the parallel agent, not implemented here.

## Out of scope

- Editing `ci.yml`; PyPI publishing; Scorecard (managed by `repo_standards_alignment_20260905`); release provenance (`release_and_packaging_20260905`); fixing findings inside `cli/launch.py`; fuzzing the browser crawler's network path (no network in fuzzing).
