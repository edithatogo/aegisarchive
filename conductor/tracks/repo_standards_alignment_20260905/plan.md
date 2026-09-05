# Track Plan: Repository Standards Alignment

## Status: COMPLETED

Implementation contract for every task: touch only the files under **Files**; write exactly the content under **Change**; run the **Verify** command from the repository root and require the stated result; stop when **Done when** holds; never do anything listed under **Do not**. Tasks are ordered so the repository stays green after each one. Commit after each task with the conventional-commit message given (do not push; pushing is gate G1 and belongs to the integrator).

Global drift guards (apply to every task):
- Never modify `.github/workflows/ci.yml`, `cli/launch.py`, `cli/verify_bundle.py`, `cli/test_station_hardening.py`, or anything under `conductor/tracks/portable_station_hardening_20260905/`.
- Never add runtime dependencies. `pyproject.toml` `dependencies` stays `[]`.
- Never write organisation names, hostnames, or vendor names (the `ci.yml` leak gate fails the build). Run `python3 scripts/gate.py leak` if it exists, otherwise the grep step copied from `ci.yml`.
- Never create files whose names start with `._`.
- New workflow files pin every third-party action to a full commit SHA with a `# vX.Y.Z` comment (standards requirement; also required by the Semgrep/zizmor gates of the security track).

## Phase 1 — Specification & approval

- [x] Capture standards requirements into the track specification (traces to R1–R10). *(evidence: spec.md)*
- [x] Approval basis: user requested alignment with `edithatogo/repository-standards` (2026-09-05). Tracks-only scope; implementation by a later agent.

## Phase 2 — Additive metadata files (no CI impact)

- [x] **T1 Renovate preset** *(R1, AC1)* (a7b56e7)

  **Files**: create `renovate.json`. Nothing else.

  **Change**: complete file content:

  ```json
  {
    "$schema": "https://docs.renovatebot.com/renovate-schema.json",
    "extends": ["github>edithatogo/renovate-config"]
  }
  ```

  **Verify**: `python3 -c "import json;d=json.load(open('renovate.json'));assert d['extends']==['github>edithatogo/renovate-config'],d;print('ok')"` prints `ok`.

  **Done when**: file exists with exactly the two keys above. Commit: `chore: add renovate preset (T1, AC1)`.

  **Do not**: add `packageRules`, schedules, or automerge settings here (they live in the shared preset). Do not create `.github/renovate.json`.

- [x] **T2 Citation metadata** *(R2, AC2)* (87c09e8)

  **Files**: create `CITATION.cff`.

  **Change**: complete file content:

  ```yaml
  cff-version: 1.2.0
  message: "If you use AegisArchive, please cite it using the metadata in this file."
  title: "AegisArchive"
  abstract: "Zero-install, server-preserving web archiver and ISO 28500 (WARC/1.1) forensic engine with CDX-11 indexing, an in-browser replay viewer, a Python standard-library CLI, and a Model Context Protocol server."
  type: software
  authors:
    - family-names: Mordaunt
      given-names: Dylan
  repository-code: "https://github.com/edithatogo/aegisarchive"
  url: "https://github.com/edithatogo/aegisarchive"
  license: Apache-2.0
  keywords:
    - web-archiving
    - warc
    - cdx
    - digital-preservation
    - iso-28500
  ```

  **Verify**: `python3 -c "t=open('CITATION.cff').read();assert 'cff-version: 1.2.0' in t and 'type: software' in t and 'license: Apache-2.0' in t and 'repository-code: \"https://github.com/edithatogo/aegisarchive\"' in t;assert 'doi:' not in t and 'orcid' not in t.lower();print('ok')"` prints `ok`. If `cffconvert` is installed: `cffconvert --validate` exits 0.

  **Done when**: verify passes. Commit: `docs: add CITATION.cff (T2, AC2)`.

  **Do not**: add `version`, `date-released`, `doi`, `orcid`, or `affiliation` (standards: only when release automation maintains them / only when real).

- [x] **T3 CalVer changelog seeded from git history** *(R3, AC3)* (ea5997e)

  **Files**: create `CHANGELOG.md`.

  **Change**: run `git log --reverse --date=short --pretty='%ad %h %s'` and write this file, replacing the bullet list under Unreleased with one bullet per commit whose subject does not start with `chore(conductor)`, in chronological order, formatted `- <subject> (<short hash>)`. As of 2026-09-05 the list is exactly:

  ```markdown
  # Changelog

  All notable changes to AegisArchive are recorded here. The format follows
  Keep a Changelog. Versions use calendar versioning: git tags are `vYYYY.MM.DD`
  (for example `v2026.09.05`), with `vYYYY.MM.DD.N` for a second release on the
  same day. The tag is the single authoritative version source; `pyproject.toml`
  derives its version from the tag.

  ## [Unreleased]

  No CalVer tag has been created yet. Everything below is unreleased history.

  ### Added
  - feat: Initial release of AegisArchive v1.0 (ISO 28500:2017, MCP, Zero-Install) (6f1cf70)
  - feat: Add portable-platform roadmap, offline AI capabilities, and embeddable Python launcher fallback (4869443)
  - ci: Add GitHub Actions CI workflow, security policies, issue templates, and Conductor track plans (48169c6)
  - ci: Expand automated leak prevention pattern to include regional and departmental identifiers (77bd47c)
  - feat: harden local station server (T1/T2, AC1-AC3) (2054293)
  - feat: station runtime services (T3/T5/T7, AC4/AC6) (7d4019f)
  - feat: fail-closed bundle integrity verification (T4, AC5) (b4c5392)

  ### Changed
  - chore: remove third-party organisation and website references; extend leak-prevention gate (21ff421)
  - chore: launcher operator diagnostics; drop remaining website references (T6) (23da749)
  ```

  Then append, at the end of the file, one bullet per commit made after `3f00f46` (excluding `chore(conductor)` commits) under the matching heading (`feat:` → Added, `fix:` → Fixed, everything else → Changed). Create `### Fixed` only if needed.

  **Verify**: `python3 -c "t=open('CHANGELOG.md').read();assert '## [Unreleased]' in t and 'vYYYY.MM.DD' in t and '(6f1cf70)' in t;import re;assert not re.search(r'^## \[\d{4}\.\d{2}\.\d{2}',t,re.M);print('ok')"` prints `ok`.

  **Done when**: verify passes and the leak grep from `ci.yml` finds nothing. Commit: `docs: add CalVer changelog seeded from git history (T3, AC3)`.

  **Do not**: invent a tagged release section; do not paraphrase commit subjects except the single case already applied above: the original subject of commit `4869443` contains a product name that the `ci.yml` leak gate blocks, so the bullet must use `portable-platform` exactly as shown (never copy that subject verbatim from `git log`).

- [x] **T4 OpenSSF Security Insights** *(R4, AC4)* (7bf08fd)

  **Files**: create `security-insights.yml`.

  **Change**: complete file content (schema 2.2.0, matching the standards repo's own file shape):

  ```yaml
  header:
    schema-version: 2.2.0
    last-updated: '2026-09-05'
    last-reviewed: '2026-09-05'
    url: https://github.com/edithatogo/aegisarchive/blob/main/security-insights.yml
    comment: |
      Machine-readable security posture for AegisArchive. Runtime is browser
      Web APIs plus the Python standard library; no third-party runtime
      dependencies exist. Development tooling is confined to CI and
      tests/requirements-dev.txt.

  project:
    name: AegisArchive
    administrators:
      - name: Dylan Mordaunt
        primary: true
    repositories:
      - name: aegisarchive
        url: https://github.com/edithatogo/aegisarchive
        comment: Zero-install web archiver, WARC/1.1 forensic engine, CLI and MCP server.
    vulnerability-reporting:
      reports-accepted: true
      bug-bounty-available: false
      security-policy: https://github.com/edithatogo/aegisarchive/blob/main/SECURITY.md
      comment: |
        Report privately through GitHub Security Advisories (see SECURITY.md).
        Acknowledgement target is 48 hours.

  repository:
    url: https://github.com/edithatogo/aegisarchive
    status: active
    accepts-change-request: true
    accepts-automated-change-request: true
    core-team:
      - name: Dylan Mordaunt
    license:
      url: https://github.com/edithatogo/aegisarchive/blob/main/LICENSE
      expression: Apache-2.0
    security:
      assessments:
        self:
          comment: |
            Automated evidence: CI validation and leak-prevention gate, secret
            scanning, CodeQL, Semgrep, Bandit, workflow linting, fuzzing,
            Scorecard, SBOM and provenance on release. Sole maintainer; zero
            mandatory human approvals by design.
      tools:
        - name: CodeQL
          type: SCA
          version: latest
          rulesets:
            - built-in
          integration:
            adhoc: false
            ci: true
            release: false
        - name: gitleaks
          type: secret
          version: latest
          rulesets:
            - built-in
          integration:
            adhoc: true
            ci: true
            release: false
  ```

  **Verify**: `python3 -c "t=open('security-insights.yml').read();assert 'schema-version: 2.2.0' in t and 'reports-accepted: true' in t and 'expression: Apache-2.0' in t;print('ok')"` prints `ok`. If PyYAML happens to be installed, also `python3 -c "import yaml;yaml.safe_load(open('security-insights.yml'))"`.

  **Done when**: verify passes. Commit: `docs: add security-insights.yml (T4, AC4)`.

  **Do not**: use schema 1.x; do not list tools that are not actually configured by the security track (only CodeQL and gitleaks are named).

## Phase 3 — Managed workflows (copied verbatim)

- [x] **T5 Managed Scorecard workflow** *(R5, AC5)* (fcfd09e)

  **Files**: create `.github/workflows/scorecard.yml`.

  **Change**: exact byte-for-byte copy of the standards template. Preferred: `gh api repos/edithatogo/repository-standards/contents/managed-files/templates/scorecard.yml -H "Accept: application/vnd.github.raw" > .github/workflows/scorecard.yml`. If offline, write this content (verified copy as of 2026-09-05):

  ```yaml
  name: Scorecard supply-chain security

  on:
    branch_protection_rule:
    schedule:
      - cron: "23 19 * * 1"
    push:
      branches: [main]
    workflow_dispatch:

  permissions: read-all

  concurrency:
    group: scorecard-${{ github.ref }}
    cancel-in-progress: true

  jobs:
    analysis:
      if: github.event.repository.default_branch == github.ref_name || github.event_name == 'workflow_dispatch' || github.event_name == 'schedule' || github.event_name == 'branch_protection_rule'
      runs-on: ubuntu-latest
      timeout-minutes: 15
      permissions:
        security-events: write
        id-token: write
        contents: read
        actions: read
      steps:
        - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
          with:
            persist-credentials: false
        - uses: ossf/scorecard-action@2d1146689b8cda280b9bc96326124645441f03bc # v2.4.4
          with:
            results_file: results.sarif
            results_format: sarif
            publish_results: true
        - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
          with:
            name: scorecard-sarif-${{ github.run_id }}
            path: results.sarif
            retention-days: 30
        - uses: github/codeql-action/upload-sarif@f205ea1c3313d32999d8d6a48b4f6530d4437b38 # v4.37.4
          with:
            sarif_file: results.sarif
  ```

  **Verify**: `gh api repos/edithatogo/repository-standards/contents/managed-files/templates/scorecard.yml -H "Accept: application/vnd.github.raw" | cmp - .github/workflows/scorecard.yml && echo identical` prints `identical`. Offline fallback: `python3 -c "t=open('.github/workflows/scorecard.yml').read();assert 'ossf/scorecard-action@2d1146689b8cda280b9bc96326124645441f03bc' in t and 'publish_results: true' in t;print('ok')"`.

  **Done when**: identical to the template. Commit: `ci: add managed Scorecard workflow (T5, AC5)`.

  **Do not**: edit any line (the file is centrally managed and drift is audited); do not add a Scorecard badge to the README until a published result exists (T9 leaves a placeholder comment instead).

- [x] **T6 Managed zizmor workflow** *(R5, AC5)* (41e4830)

  **Files**: create `.github/workflows/zizmor.yml`.

  **Change**: exact copy: `gh api repos/edithatogo/repository-standards/contents/managed-files/templates/zizmor.yml -H "Accept: application/vnd.github.raw" > .github/workflows/zizmor.yml`. Verified content as of 2026-09-05:

  ```yaml
  name: GitHub Actions security lint

  on:
    pull_request:
    push:
      branches: [main]
    schedule:
      - cron: '17 3 * * 1'

  permissions:
    contents: read

  concurrency:
    group: zizmor-${{ github.workflow }}-${{ github.ref }}
    cancel-in-progress: true

  jobs:
    zizmor:
      runs-on: ubuntu-latest
      timeout-minutes: 10
      steps:
        - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        - name: Audit workflows
          uses: zizmorcore/zizmor-action@dc57e305f08a25141d9b9f7c4ce7e4d72208d732 # main (2026-08-01)
  ```

  **Verify**: `gh api repos/edithatogo/repository-standards/contents/managed-files/templates/zizmor.yml -H "Accept: application/vnd.github.raw" | cmp - .github/workflows/zizmor.yml && echo identical` prints `identical`.

  **Done when**: identical. Commit: `ci: add managed zizmor workflow (T6, AC5)`.

  **Do not**: change the action pin even though a tagged `zizmor-action` release exists; the managed copy must match the template.

## Phase 4 — Packaging and thin standards CI

- [x] **T7 `pyproject.toml`, package markers, test scaffold, dev requirements** *(R6, R8, AC6, AC7)* (de4e132)

  **Files**: create `pyproject.toml`, `cli/__init__.py` (empty), `tests/__init__.py` (empty), `tests/test_smoke.py`, `tests/requirements-dev.txt`. `mcp/__init__.py` already exists — leave it.

  **Change**:

  `pyproject.toml` (complete; verified to build a wheel and expose all three scripts with `pip install -e .` on Python 3.14):

  ```toml
  [build-system]
  requires = ["setuptools>=77", "setuptools-scm>=8"]
  build-backend = "setuptools.build_meta"

  [project]
  name = "aegisarchive"
  description = "Zero-install, server-preserving web archiver and ISO 28500 (WARC/1.1) forensic engine with CDX-11 indexing and an MCP server."
  readme = "README.md"
  requires-python = ">=3.9"
  license = "Apache-2.0"
  license-files = ["LICENSE", "NOTICE"]
  authors = [{ name = "Dylan Mordaunt" }]
  keywords = ["warc", "cdx", "web-archiving", "digital-preservation", "iso-28500", "mcp"]
  classifiers = [
    "Programming Language :: Python :: 3",
    "Operating System :: OS Independent",
    "Topic :: System :: Archiving",
  ]
  # Zero runtime dependencies is an architectural invariant (AGENTS.md). Keep this empty.
  dependencies = []
  dynamic = ["version"]

  [project.urls]
  Homepage = "https://github.com/edithatogo/aegisarchive"
  Repository = "https://github.com/edithatogo/aegisarchive"
  Issues = "https://github.com/edithatogo/aegisarchive/issues"
  Changelog = "https://github.com/edithatogo/aegisarchive/blob/main/CHANGELOG.md"

  [project.scripts]
  aegisarchive = "aegisarchive_cli.aegis_cli:main"
  aegisarchive-verify = "aegisarchive_cli.warc_verify:main"
  aegisarchive-mcp = "aegisarchive_mcp.server:main"

  # On-disk folders stay cli/ and mcp/ (launchers and ci.yml depend on them).
  # Installed import names are prefixed so they never shadow the PyPI packages
  # "mcp" (the official MCP SDK) or "cli".
  [tool.setuptools]
  packages = ["aegisarchive_cli", "aegisarchive_mcp"]
  include-package-data = false

  [tool.setuptools.package-dir]
  aegisarchive_cli = "cli"
  aegisarchive_mcp = "mcp"

  [tool.setuptools_scm]
  # Version comes from the CalVer git tag (vYYYY.MM.DD). Shallow CI checkouts fall back to 0.0.0.
  fallback_version = "0.0.0"
  ```

  `tests/requirements-dev.txt` (complete; the security track appends to this file later):

  ```text
  # Development-only tooling. Never imported at runtime (AGENTS.md zero-install invariant).
  coverage>=7.6
  ```

  `tests/test_smoke.py` (complete):

  ```python
  """Stdlib smoke tests: import paths, WARC verifier, CDX search, MCP dispatch."""
  import contextlib
  import io
  import json
  import os
  import subprocess
  import sys
  import tempfile
  import unittest

  ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  sys.path.insert(0, ROOT)

  from cli import warc_verify  # noqa: E402
  from mcp import server  # noqa: E402

  MINIMAL_WARC = (
      b"WARC/1.1\r\nWARC-Type: warcinfo\r\nWARC-Record-ID: <urn:uuid:1>\r\n"
      b"Content-Type: application/warc-fields\r\nContent-Length: 2\r\n\r\nok\r\n\r\n"
  )


  class SmokeTests(unittest.TestCase):
      def test_verify_warc_accepts_minimal_container(self):
          with tempfile.NamedTemporaryFile(suffix=".warc", delete=False) as fh:
              fh.write(MINIMAL_WARC)
          try:
              with contextlib.redirect_stdout(io.StringIO()):
                  self.assertTrue(warc_verify.verify_warc(fh.name))
          finally:
              os.unlink(fh.name)

      def test_verify_warc_missing_file_is_false(self):
          with contextlib.redirect_stdout(io.StringIO()):
              self.assertFalse(warc_verify.verify_warc(os.path.join(ROOT, "does-not-exist.warc")))

      def test_search_cdx_reports_matches(self):
          line = " CDX N b a m s k r M S V g\ncom,example)/ 20260905000000 https://example.com/ text/html 200 X - - 0 0 a.warc\n"
          with tempfile.NamedTemporaryFile("w", suffix=".cdx", delete=False) as fh:
              fh.write(line)
          try:
              result = server.search_cdx("example", fh.name)
          finally:
              os.unlink(fh.name)
          self.assertEqual(result["total_matches"], 1)
          self.assertEqual(result["matches"][0]["status"], "200")

      def test_mcp_initialize_over_stdio(self):
          proc = subprocess.run(
              [sys.executable, os.path.join(ROOT, "mcp", "server.py")],
              input=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}) + "\n",
              capture_output=True, text=True, timeout=30,
          )
          reply = json.loads(proc.stdout.splitlines()[0])
          self.assertEqual(reply["result"]["serverInfo"]["name"], "aegisarchive-mcp")


  if __name__ == "__main__":
      unittest.main()
  ```

  **Verify** (all from repo root):
  1. `python3 -c "import tomllib;d=tomllib.load(open('pyproject.toml','rb'));assert d['project']['dependencies']==[];assert set(d['project']['scripts'])=={'aegisarchive','aegisarchive-verify','aegisarchive-mcp'};print('ok')"` prints `ok`.
  2. `python3 -m unittest discover -s tests -t . -p "test_*.py"` reports `OK` (4 tests).
  3. `python3 -m venv /tmp/aa-venv && /tmp/aa-venv/bin/python -m pip -q install -e . && /tmp/aa-venv/bin/aegisarchive --help >/dev/null && /tmp/aa-venv/bin/aegisarchive-verify --help >/dev/null && echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | /tmp/aa-venv/bin/aegisarchive-mcp | python3 -c "import sys,json;assert json.loads(sys.stdin.readline())['result']['serverInfo']['name']=='aegisarchive-mcp';print('ok')"` prints `ok`.
  4. `python3 cli/test_station_hardening.py` still passes (adding `cli/__init__.py` must not affect it).
  5. `git status --short` shows only the five new files.

  **Done when**: all five checks pass. Commit: `build: add pyproject packaging, test scaffold and dev requirements (T7, AC6, AC7)`.

  **Do not**: add `[project.optional-dependencies]`; rename folders; add `pytest`; put `coverage` anywhere except `tests/requirements-dev.txt`; edit `mcp/__init__.py`. Known/accepted: the wheel also ships `cli/test_station_hardening.py` and `cli/launch.py` as modules (harmless; excluding single modules via package-dir is not supported); `aegisarchive-mcp` looks for `profiles/` relative to the source tree, so an installed copy lists zero profiles unless run from a checkout (document in README T9).

- [x] **T8 Thin standards CI caller** *(R7, AC7)* (7f688d4)

  **Files**: create `.github/workflows/standards-ci.yml`.

  **Change**: complete file content. Reusable workflows are pinned to the standards repo `main` commit verified on 2026-09-05; Renovate (T1 preset) updates them. Inputs match the `workflow_call` definitions recorded in `spec.md`.

  ```yaml
  name: Standards CI

  on:
    push:
      branches: [main]
    pull_request:
      branches: [main]
    workflow_dispatch:

  permissions:
    contents: read

  concurrency:
    group: standards-ci-${{ github.workflow }}-${{ github.ref }}
    cancel-in-progress: true

  jobs:
    python-ci:
      # Reusable workflow: tests with coverage and uploads to Codecov via OIDC.
      # Requires the repository to be activated on Codecov (gate G2); until then this job fails at the upload step.
      permissions:
        contents: read
        id-token: write
      uses: edithatogo/repository-standards/.github/workflows/python-ci.yml@ad67bedaa0c4d0769bd54fd76354bac65b25b88c # main 2026-09-05
      with:
        python-version: "3.11"
        install-command: python -m pip install -e . -r tests/requirements-dev.txt
        test-command: python -m coverage run --source=cli,mcp -m unittest discover -s tests -t . -p "test_*.py" && python -m coverage xml

    dependency-review:
      if: github.event_name == 'pull_request'
      runs-on: ubuntu-latest
      timeout-minutes: 10
      permissions:
        contents: read
      steps:
        - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
          with:
            persist-credentials: false
        - uses: actions/dependency-review-action@a1d282b36b6f3519aa1f3fc636f609c47dddb294 # v5.0.0
          with:
            fail-on-severity: moderate

    supply-chain-evidence:
      # SBOM (SPDX + CycloneDX), checksums and build-provenance attestation for committed project metadata.
      # The reusable workflow checks out the repository itself, so artifact-path must be a committed path;
      # release artefacts get their own provenance in release.yml (release_and_packaging_20260905).
      if: github.event_name != 'pull_request'
      permissions:
        contents: read
        id-token: write
        attestations: write
      uses: edithatogo/repository-standards/.github/workflows/supply-chain-evidence.yml@ad67bedaa0c4d0769bd54fd76354bac65b25b88c # main 2026-09-05
      with:
        artifact-path: pyproject.toml
  ```

  **Verify**:
  1. `python3 -c "t=open('.github/workflows/standards-ci.yml').read();assert t.count('@ad67bedaa0c4d0769bd54fd76354bac65b25b88c')==2;assert 'python-version: \"3.11\"' in t and 'artifact-path: pyproject.toml' in t and 'fail-on-severity: moderate' in t;print('ok')"` prints `ok`.
  2. `python3 -m coverage --version >/dev/null 2>&1 && python3 -m coverage run --source=cli,mcp -m unittest discover -s tests -t . -p "test_*.py" && python3 -m coverage xml && test -f coverage.xml && echo ok` prints `ok` when `coverage` is installed (install it in a venv from `tests/requirements-dev.txt` if not); then `rm -f coverage.xml .coverage`.
  3. If `actionlint` is installed: `actionlint .github/workflows/standards-ci.yml` exits 0. If `zizmor` is installed: `zizmor --min-severity medium .github/workflows/standards-ci.yml` exits 0.

  **Done when**: checks pass; add `coverage.xml` and `.coverage` to `.gitignore` if they are not already ignored (append two lines under the `# Python` block). Commit: `ci: add thin standards CI calling reusable workflows (T8, AC7)`.

  **Do not**: call `coverage-evidence.yml` (python-ci already uploads; the reusable workflow cannot see files produced by another job); use `@main` for the reusable workflows; add this workflow's checks to rulesets before G2 is cleared.

## Phase 5 — README contract

- [x] **T9 README nine-section restructure with honest Status table** *(R9, AC8)* (1a39f86)

  **Files**: modify `README.md` only.

  **Change**: reorganise existing content (do not delete the quick-start commands, MCP tool list, or Ethical Archival Charter text; move them) into exactly these H2 sections in this order, each starting with `## `:

  1. `## AegisArchive` — one sentence: "Zero-install, server-preserving web archiver and ISO 28500 (WARC/1.1) forensic engine for offline replication and digital preservation." (This replaces the current H1 subtitle; keep a single H1 `# AegisArchive` above it.)
  2. `## Badges` — exactly these, relative links, no decorative badges:
     `[![CI](../../actions/workflows/ci.yml/badge.svg)](../../actions/workflows/ci.yml)`
     `[![Security gates](../../actions/workflows/security.yml/badge.svg)](../../actions/workflows/security.yml)`
     `[![Standards CI](../../actions/workflows/standards-ci.yml/badge.svg)](../../actions/workflows/standards-ci.yml)`
     `[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)`
     followed by an HTML comment `<!-- Scorecard badge: add only after a published result exists (standards rule). -->`. Remove the existing Format/Index/Zero-Install/MCP decorative badges.
  3. `## Status and scope` — the table below plus the sentence "Evidence limitation: features marked Planned are described in `conductor/` tracks and are not yet present in code." Copy the table verbatim; if you believe a row is wrong, mark it Planned rather than Implemented.

     ```markdown
     | Capability | Status |
     | --- | --- |
     | In-browser crawler with politeness engine (rate limits, backoff, `Retry-After`) | Implemented |
     | WARC/1.1 writer with SHA-256 payload digests and `revisit` deduplication | Implemented |
     | CDX-11 index generation | Implemented |
     | In-browser replay viewer | Implemented |
     | Headless Python CLI crawl (`cli/aegis_cli.py`) | Implemented |
     | WARC/CDX integrity verifier (`cli/warc_verify.py`) | Implemented |
     | MCP server with `list_profiles`, `search_archive`, `validate_profile` | Implemented |
     | Hardened loopback station server, status page, bundle checksum verification | Implemented |
     | OPFS streaming of large archives to disk | Planned |
     | IndexedDB crawl checkpoint/resume | Planned |
     | WARC `request` records and `.warc.gz` output | Planned |
     | WACZ export and service-worker replay | Planned |
     | Bundled portable runtimes and offline AI features | Planned |
     ```
  4. `## Install` — move the existing per-OS 1-minute quick start here unchanged, then add a "Python package (optional)" paragraph: `pipx install git+https://github.com/edithatogo/aegisarchive` gives `aegisarchive`, `aegisarchive-verify`, `aegisarchive-mcp`; note that the installed MCP server only lists profiles when run from a checkout.
  5. `## Usage` — move the existing CLI and MCP sections here (keep the tool list).
  6. `## Development and verification` — the commands: `python3 -m unittest discover -s tests -t . -p "test_*.py"`, `python3 cli/test_station_hardening.py`, `node --test tests/js/` (state "once the security track lands"), `python3 scripts/gate.py` (same caveat), and the `--help` smoke commands from `AGENTS.md`. Link to `conductor/index.md` for the planning system.
  7. `## Security` — two sentences pointing to `SECURITY.md` (private disclosure via GitHub Security Advisories) and `security-insights.yml`.
  8. `## Citation` — "Cite using `CITATION.cff` (GitHub's *Cite this repository* button)."
  9. `## Licence and third-party rights` — Apache-2.0 (`LICENSE`, `NOTICE`); `web/lib/minisearch.min.js` is third-party MIT-licensed (state that its licence header is retained in the file). Move the Ethical Archival Charter under this section as a sub-heading `### Ethical archival charter`. Move the roadmap content into `## Status and scope` as a short "Roadmap" paragraph linking to `conductor/tracks.md`; delete the old roadmap section and the old System Architecture section only if their content is preserved elsewhere (otherwise keep Architecture as a sub-heading under Usage).

  **Verify**: `python3 -c "import re;t=open('README.md').read();h=[l[3:].strip() for l in t.splitlines() if l.startswith('## ')];want=['AegisArchive','Badges','Status and scope','Install','Usage','Development and verification','Security','Citation','Licence and third-party rights'];assert h==want,h;assert '| Capability | Status |' in t;print('ok')"` prints `ok`; leak grep from `ci.yml` clean; no link target in README refers to a file that does not exist (`python3 -c "import re,os;t=open('README.md').read();missing=[p for p in re.findall(r'\]\(((?!http|#|\.\./)[^)]+)\)',t) if not os.path.exists(p)];assert not missing,missing;print('ok')"`).

  **Done when**: both checks print `ok`. Commit: `docs: restructure README to the nine-section standards contract (T9, AC8)`.

  **Do not**: add badges for services not yet active (Codecov, Scorecard, PyPI); claim any Planned capability as Implemented; remove the per-OS quick start; introduce any organisation or vendor names.

## Phase 6 — Remote configuration (external gate G1)
 
- [x] **T10 Handshake notes** *(AC10)* (67ded2c)
 
   **Files**: create `conductor/tracks/repo_standards_alignment_20260905/handoff.md`.
 
   **Change**: a short note with two items for other owners: (a) parallel agent — `ci.yml` uses mutable major tags for `actions/checkout` and `actions/setup-python`; the standards require SHA pins (`3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`, `5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0`); requested, not done here. (b) integrator — register this repository in `edithatogo/repository-standards:registry/repositories.json` as archetype `python`, supply-chain profile `published`, sole developer, once T8's checks are stable (external repository; out of scope here).
 
   **Verify**: file exists; leak grep clean.
 
   **Done when**: committed: `chore(conductor): record standards handoff notes (T10)`.
 
   **Do not**: edit `ci.yml` or the external registry yourself.
 
- [-] **T11 Rulesets and repository topics via `gh api`** *(R10, AC9)* — **gated by G1: do not run without explicit user authorisation recorded in `evidence.jsonl` as `gate_authorized`.** Run only after T1–T9 and the security track's `security.yml` have been pushed to `main` and have completed at least one successful run (check names must resolve).
 
   **Files**: none in the repo except appending to `evidence.jsonl`; writes GitHub settings.
 
   **Change**:
   1. List real check names: `gh api "repos/edithatogo/aegisarchive/commits/main/check-runs?per_page=100" --jq '.check_runs[].name' | sort -u`. Keep only checks that have passed on `main` at least twice. Expected stable names as of planning: `Code & Schema Validation`, `Multi-OS CLI Execution Test (ubuntu-latest)`, `Multi-OS CLI Execution Test (macos-latest)`, `Multi-OS CLI Execution Test (windows-latest)`, plus the security track's `Secrets scan (gitleaks)`, `Static analysis (Bandit)`, `Static analysis (Semgrep)`, `CodeQL (python)`, `CodeQL (javascript-typescript)`, `Workflow lint (zizmor)`, `Fuzz smoke`. Exclude anything from `standards-ci.yml` until G2 (Codecov) is cleared.
   2. Write `/tmp/ruleset.json` with the list from step 1 substituted into `required_status_checks`:
 
      ```json
      {
        "name": "main protection (solo maintainer)",
        "target": "branch",
        "enforcement": "active",
        "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
        "bypass_actors": [
          { "actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always" }
        ],
        "rules": [
          { "type": "deletion" },
          { "type": "non_fast_forward" },
          {
            "type": "pull_request",
            "parameters": {
              "required_approving_review_count": 0,
              "dismiss_stale_reviews_on_push": false,
              "require_code_owner_review": false,
              "require_last_push_approval": false,
              "required_review_thread_resolution": true
            }
          },
          {
            "type": "required_status_checks",
            "parameters": {
              "strict_required_status_checks_policy": false,
              "required_status_checks": [
                { "context": "Code & Schema Validation" },
                { "context": "Multi-OS CLI Execution Test (ubuntu-latest)" }
              ]
            }
          }
        ]
      }
      ```
 
      `actor_id: 5` is the Repository admin role — the explicit owner recovery path required by the solo-maintainer standard.
   3. `gh api -X POST repos/edithatogo/aegisarchive/rulesets --input /tmp/ruleset.json`.
   4. Topics: `gh api -X PUT repos/edithatogo/aegisarchive/topics -f 'names[]=anti-ddos' -f 'names[]=cdx' -f 'names[]=digital-preservation' -f 'names[]=iso-28500' -f 'names[]=mcp-server' -f 'names[]=offline-first' -f 'names[]=python' -f 'names[]=server-preservation' -f 'names[]=warc' -f 'names[]=web-archiving' -f 'names[]=solo-maintainer'` (existing ten topics plus `solo-maintainer`).
 
   **Verify**: `gh api repos/edithatogo/aegisarchive/rulesets --jq '.[] | select(.enforcement=="active") | .name'` prints the ruleset name; `gh api repos/edithatogo/aegisarchive/rulesets/$(gh api repos/edithatogo/aegisarchive/rulesets --jq '.[0].id') --jq '[.rules[].type]'` contains `deletion`, `non_fast_forward`, `pull_request`, `required_status_checks`; `gh api repos/edithatogo/aegisarchive/topics --jq '.names | index("solo-maintainer")'` is not `null`.
 
   **Done when**: verify passes and `evidence.jsonl` gets a `remote_config_applied` line listing the required check contexts. No repo commit other than the ledger: `chore(conductor): record ruleset application (T11, AC9)`.
 
   **Do not**: set `required_approving_review_count` above 0; add CODEOWNERS; require `standards-ci` checks before G2; enable `strict_required_status_checks_policy` (would force rebases on a solo repo); delete or replace an existing ruleset if one appears — update it with `PUT .../rulesets/{id}` instead.
 
## Phase 7 — Completion
 
- [x] **F1** Final validation: `python3 -m unittest discover -s tests -t . -p "test_*.py"`, `python3 cli/test_station_hardening.py`, `--help` smoke tests from `AGENTS.md`, leak grep, `git diff --stat origin/main -- .github/workflows/ci.yml cli/launch.py cli/verify_bundle.py cli/test_station_hardening.py` empty. *(AC7, AC10)*
- [x] **F2** Update `metadata.json` (`status`, `updated_at`), append `track_completed` to `evidence.jsonl`; the integrator updates `conductor/tracks.md`.

## Review Fixes

- [ ] Rev-1 Reconcile capability documentation with the implemented browser and CLI.
  - **Files**: `README.md`, `conductor/tech-stack.md`, `profiles/schema.json`.
  - **Change**: separate gzip input from planned output, identify localStorage frontier-only resume, mark OPFS/request records implemented, use portable JS test expansion, correct deprecated concurrency default to its allowed value.
  - **Verify**: `python3 scripts/build_profile_bundle.py --check`; `python3 -m unittest tests.test_profile_schema`; README nine-section check.
  - **Done when**: documented scope matches the reviewed code. T11 and G2 remain external gates.
  - **Do not**: claim hosted success, release, or ruleset activation.
