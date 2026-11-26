# Implementation plan

Owner is chat 01a1a4fa-a107-7502-8670-7abc4e934613 on codex/aegis-maintenance-20261127 at /Users/doughnut/Documents/Codex/2026-11-04/if-y/work/aegis-maintenance. GitHub scope is the listed PRs and workflow runs in AegisArchive. The next operation is exact-head validation before merge.

- [ ] T1 Reconcile dependency, security and workflow changes. (AC1, AC2)
  - **Files**: .github/workflows/ci.yml, browser-capture.yml, mirroring-acceptance.yml, portable-full-native.yml, portable-native.yml, scorecard.yml, security.yml, self-improvement.yml, standards-ci.yml, windows-portable-noadmin.yml and release.yml in the same directory, package.json, package-lock.json, pyproject.toml, portable/windows-python.json, scripts/gate.py, scripts/install_opengrep.py, scripts/mirroring_acceptance.py, web/lib/mirror_resources.js, docs/opengrep-migration.md, tests/requirements-dev.txt, tests/requirements-fuzz.txt, tests/test_opengrep_migration.py, tests/test_mirroring_acceptance.py, tests/browser/mirroring_acceptance.spec.js and tests/js/mirror_resources_opengrep.test.js.
  - **Change**: Verify action pins and retain required check identities. Derive browser versions from the source lockfile. Route audit and release-preview output to Actions artifacts.
  - **Verify**: .venv/bin/python -m unittest tests.test_mirroring_acceptance tests.test_opengrep_migration tests.test_security_review tests.test_windows_runtime; node --test tests/js/mirror_resources_opengrep.test.js; exact-head Actions including measured mirroring.
  - **Done when**: All required checks pass and the compatible original PRs have a verified disposition.
  - **Do not**: Bypass review, change branch protection, drop coverage-guided fuzzing or publish a release from manual qualification.

- [ ] T2 Verify the operational workflows on the merged revision. (AC2, AC3)
  - **Files**: This plan and evidence.jsonl.
  - **Change**: Dispatch the self-improvement and release preview jobs. Qualify the existing optional full-native profile and retain each platform result.
  - **Verify**: gh run view for the exact manual runs, followed by release checksum and native receipt checks.
  - **Done when**: Audit and release preview are readable and each full-native runner has a terminal result with any failure evidence retained.
  - **Do not**: Create a tag or a release in preview verification.

- [ ] T3 Qualify remaining Python 3.15 dependencies independently. (AC3)
  - **Files**: .github/workflows/security.yml, .github/workflows/privacy-secrets.yml, tests/requirements-fuzz.txt and the optional portable provisioning sources and locks named by the native receipt.
  - **Change**: Qualify a supported Atheris CPython 3.15 build, the shared privacy runner, and the portable Python and native wheels in separate verified slices.
  - **Verify**: Run the existing coverage-guided harnesses, the same privacy controls and the native relocated-bundle qualification on Python 3.15.
  - **Done when**: Each job verifies its actual runtime and retains its coverage.
  - **Do not**: Substitute deterministic smoke tests for coverage-guided fuzzing or loosen privacy and native checks.

- [ ] T4 Qualify the offline AI caller. (AC3)
  - **Files**: .github/workflows/offline-ai-security.yml and this plan and evidence.
  - **Change**: Revisit PR #91 after repository-standards PR #126 qualifies. Pin the verified upstream commit and execute the isolated scanner and agent behavioral checks.
  - **Verify**: Upstream exact-head policy, image and behavioral checks succeed, followed by successful controls in the AegisArchive caller run at that pin.
  - **Done when**: The qualified caller succeeds with the current required security coverage retained.
  - **Do not**: Adopt an unqualified upstream image or infer scanner success from a wrapper status.
