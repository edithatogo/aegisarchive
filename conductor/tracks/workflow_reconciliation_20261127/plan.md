# Implementation plan

Owner is chat 01a1a4fa-a107-7502-8670-7abc4e934613 on codex/aegis-maintenance-20261127 at /Users/doughnut/Documents/Codex/2026-11-04/if-y/work/aegis-maintenance. GitHub scope is the listed PRs and workflow runs in AegisArchive. That assignment covered exact-head validation and merge.

The same chat records closeout on `codex/aegis-maintenance-evidence-20261127` in `/Users/doughnut/Documents/Codex/2026-11-04/if-y/work/aegis-t7-closeout`. Scope is the track plan, metadata, evidence and backlog status. The next operation is publication of verified run receipts.

- [x] T1 Reconcile dependency, security and workflow changes. (AC1, AC2) — [PR #97](https://github.com/edithatogo/aegisarchive/pull/97).
  - **Files**: README.md, .github/workflows/ci.yml, browser-capture.yml, mirroring-acceptance.yml, portable-full-native.yml, portable-native.yml, scorecard.yml, security.yml, self-improvement.yml, standards-ci.yml, windows-portable-noadmin.yml and release.yml in the same directory, package.json, package-lock.json, pyproject.toml, portable/windows-python.json, scripts/gate.py, scripts/install_opengrep.py, scripts/mirroring_acceptance.py, web/lib/mirror_resources.js, docs/opengrep-migration.md, tests/requirements-dev.txt, tests/requirements-fuzz.txt, tests/test_opengrep_migration.py, tests/test_mirroring_acceptance.py, tests/browser/mirroring_acceptance.spec.js and tests/js/mirror_resources_opengrep.test.js.
  - **Change**: Verify action pins and retain required check identities. Derive browser versions from the source lockfile. Route audit and release-preview output to Actions artifacts.
  - **Verify**: .venv/bin/python -m unittest tests.test_mirroring_acceptance tests.test_opengrep_migration tests.test_security_review tests.test_windows_runtime; node --test tests/js/mirror_resources_opengrep.test.js; exact-head Actions including measured mirroring.
  - **Done when**: All required checks pass and the compatible original PRs have a verified disposition.
  - **Do not**: Bypass review, change branch protection, drop coverage-guided fuzzing or publish a release from manual qualification.
  - PR #97 passed 26 checks with two skips. Windows and macOS mirroring and the platform comparison passed. OpenGrep ran 473 rules on 58 files with zero findings. Coverage-guided fuzzing ran all three harnesses, and CodeQL runner egress auditing ran successfully. PRs #84, #85, #92 and #93 were closed as superseded. [Security](https://github.com/edithatogo/aegisarchive/actions/runs/45842386546) · [Mirroring](https://github.com/edithatogo/aegisarchive/actions/runs/45842386158)

- [x] T2 Verify the audit, release preview and optional native qualification. (AC2, AC3)
  - **Files**: This plan and evidence.jsonl.
  - **Change**: Dispatch the self-improvement and release preview jobs. Qualify the existing optional full-native profile and retain each platform result.
  - **Verify**: gh run view for the exact manual runs, followed by release checksum verification and the hosted native receipt gates.
  - **Done when**: Audit and release preview are readable and each full-native runner has a terminal result with any failure evidence retained.
  - **Do not**: Create a tag or a release in preview verification.
  - The audit passed on candidate 3d4c71f and the checksum-verified release preview passed on 568ad7e. The workflow files match main. The Linux and Windows native gates passed on 3d4c71f at the same portable source bytes as main. The retired macOS 14 job was cancelled before execution. The Mac-only replacement passed on macOS 15 at final head 71063ae, whose tree matches the merge. The qualified optional bundle still pins Python 3.12. [Audit](https://github.com/edithatogo/aegisarchive/actions/runs/45841330323) · [Release preview](https://github.com/edithatogo/aegisarchive/actions/runs/45841828553) · [Linux and Windows](https://github.com/edithatogo/aegisarchive/actions/runs/45841330138) · [macOS](https://github.com/edithatogo/aegisarchive/actions/runs/45842374745)

- [ ] T3 Qualify the Atheris gate on Python 3.15. (AC3)
  - **Files**: .github/workflows/security.yml, tests/requirements-fuzz.txt.
  - **Change**: Pin a supported CPython 3.15 Atheris build and align the existing runner only after it imports and executes. Atheris 3.1.0 has no published CPython 3.15 wheel. [Publisher files](https://pypi.org/project/atheris/3.1.0/#files)
  - **Verify**: Hosted Fuzz smoke executes all three libFuzzer harnesses and the current JavaScript property tests. Confirm actual Python version, Atheris import and libFuzzer startup in retained logs.
  - **Done when**: The existing required Fuzz smoke check passes with actual coverage-guided execution on Python 3.15.
  - **Do not**: Substitute deterministic smoke tests for the coverage-guided engine.

- [ ] T4 Qualify the offline AI caller. (AC3)
  - **Files**: .github/workflows/offline-ai-security.yml and this plan and evidence.
  - **Change**: Revisit PR #91 after repository-standards PR #126 qualifies. Pin the verified upstream commit and execute the isolated scanner and agent behavioral checks.
  - **Verify**: Upstream exact-head policy, image and behavioral checks succeed, followed by successful controls in the AegisArchive caller run at that pin.
  - **Done when**: The qualified caller succeeds with the current required security coverage retained.
  - **Do not**: Adopt an unqualified upstream image or infer scanner success from a wrapper status.

- [ ] T5 Qualify the shared privacy scanner on Python 3.15. (AC3)
  - **Files**: .github/workflows/privacy-secrets.yml.
  - **Change**: Update to the shared privacy action only after its pinned dependency lock and controls qualify on Python 3.15. The current lock contains Presidio Analyzer 2.2.366, which declares Python below 3.15. [Publisher metadata](https://pypi.org/project/presidio-analyzer/2.2.366/)
  - **Verify**: Exact-head hosted privacy and secret controls detect the existing synthetic identifier and secret fixtures and record the selected evaluator runtime.
  - **Done when**: The audited shared action preserves both gates with a qualified Python 3.15 lock.
  - **Do not**: Drop identifier coverage or change the shared action's ownership from this repository.

- [ ] T6 Qualify the optional native bundle on Python 3.15. (AC3)
  - **Files**: portable/native_platform_probe.py, portable/provision_native.py, portable/provision_speech.py, portable/requirements-embeddings.txt, portable/test_native_assets.py, .github/workflows/portable-full-native.yml.
  - **Change**: Qualify the optional embedded runtime and compatible speech and embeddings wheels as a locked bundle. The existing ONNX Runtime pin and the checked current public release have no CPython 3.15 wheels. [Publisher files](https://pypi.org/project/onnxruntime/1.32.0/#files)
  - **Verify**: Dispatch the full native workflow for Linux x64, Windows x64 and macOS arm64 on the candidate. Verify each relocated offline receipt, executable version and inference result.
  - **Done when**: All three independently identify Python 3.15 and preserve the full qualification checks.
  - **Do not**: Promote an unsupported binary or change the existing verified bundle while the replacement is incomplete.
