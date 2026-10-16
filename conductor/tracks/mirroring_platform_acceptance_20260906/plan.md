# Plan: Cross-platform mirroring and capability acceptance

## Status: IN PROGRESS

## T2 prerequisite reconciliation — 16 October 2026

Inspection found that browser checkpoints persist only the frontier in memory,
not archive/writer state; reload does not resume captured bytes. T2 must not
substitute a fresh capture or same-session pause/resume for durable recovery.
Its necessary integration scope is therefore explicitly extended above; original
task IDs, historical evidence and acceptance criteria remain unchanged.

The recovery slice must publish archive-prefix bytes before an atomic checkpoint,
verify source/profile/writer offsets and hashes before reopening, fence stale
writers, and preserve uncommitted tails before reconciliation. Writer/CDX state,
frontier/coverage and recorded edges must restore together, without credentials
or station tokens. Native and browser pacing must restore before requests;
server Retry-After timing cannot roll back with archive bytes. Protected launchers
remain untouched. A real reload, retained pre/post-reload payloads, disconnected
source and repeated offline navigation/assets are required acceptance evidence.
Failed or missing recovery proof keeps platform readiness pending.

Execute tasks in order after metadata dependencies complete. Each functional task first adds its focused failing assertions, then implements and refactors that slice; commit only after its new assertions and existing regression gate pass. Each task may update its own plan, metadata and append-only evidence. No prior implementation tasks were completed when this plan was refined.

- [x] T1 Define platform receipt contract. (AC1) — v2 binds measured observations, archive bytes, runtime, fixture identities and committed provenance; unexecuted runs remain pending. Implementation commit recorded in the task completion receipt.
  - **Files**: `scripts/mirroring_acceptance.py`, `tests/test_mirroring_acceptance.py`, `tests/browser/fixtures/mirroring-site.json`; focused tests: `tests/browser/mirroring_acceptance.spec.js`.
  - **Change**: Bind revision, fixture hashes, runtime/browser versions, capture/readback results and traffic observations in a machine-readable receipt.
  - **Verify**: `python3 scripts/mirroring_acceptance.py --help; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/mirroring_acceptance.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Bind revision, fixture hashes, runtime/browser versions, capture/readback results and traffic observations in a machine-readable receipt. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T2 Build capture-disconnect-replay harness. (AC1, AC2)
  - **Files**: `scripts/mirroring_acceptance.py`, `tests/browser/mirroring_acceptance.spec.js`; necessary durable-recovery prerequisites: `cli/usb_archive.py`, `cli/capture_bridge.py`, `cli/politeness.py`, `web/lib/native_capture.js`, `web/lib/warc_writer.js`, `web/lib/core_crawler.js`, `web/lib/politeness_engine.js`, `web/index.html`, and replay fixes only if reproduced in `web/viewer.html` / `web/lib/warc_reader.js`; focused tests: `tests/browser/mirroring_acceptance.spec.js`, `tests/test_usb_archive.py`, `tests/test_capture_bridge.py`, `tests/test_politeness.py`, `tests/js/warc_writer.test.js`, `tests/js/core_crawler_checkpoint.test.js`, `tests/js/politeness_engine.test.js`.
  - **Change**: Start and stop a synthetic source, capture it and verify offline links/assets, auth expiry and resume behaviours.
  - **Verify**: `python3 scripts/mirroring_acceptance.py --help; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/mirroring_acceptance.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Start and stop a synthetic source, capture it and verify offline links/assets, auth expiry and resume behaviours. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T3 Verify relocated ordinary launchers. (AC1, AC3)
  - **Files**: `tests/browser/mirroring_acceptance.spec.js`; focused tests: `tests/browser/mirroring_acceptance.spec.js`.
  - **Change**: Run from paths with spaces with supported Python/browser prerequisites; test missing-runtime diagnostics without changing launchers.
  - **Verify**: `python3 scripts/mirroring_acceptance.py --help; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/mirroring_acceptance.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Run from paths with spaces with supported Python/browser prerequisites; test missing-runtime diagnostics without changing launchers. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [~] T4 Add isolated platform acceptance CI. (AC1, AC2) — current matrix executes synthetic receipt checks only; no capture/replay harness or retained receipts.
  - **Files**: `.github/workflows/mirroring-acceptance.yml`; focused tests: `tests/browser/mirroring_acceptance.spec.js`.
  - **Change**: Reuse pinned tooling from the navigation track; run macOS and Windows against the same commit and retain receipts.
  - **Verify**: `python3 scripts/mirroring_acceptance.py --help; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/mirroring_acceptance.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Reuse pinned tooling from the navigation track; run macOS and Windows against the same commit and retain receipts. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T5 Record actual Apple Silicon acceptance. (AC1, AC2)
  - **Files**: `scripts/mirroring_acceptance.py`; focused tests: `tests/browser/mirroring_acceptance.spec.js`.
  - **Change**: Execute the harness on the current Mac and retain hashes/results; mocked or hosted-only evidence is not this task.
  - **Verify**: `python3 scripts/mirroring_acceptance.py --help; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/mirroring_acceptance.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Execute the harness on the current Mac and retain hashes/results; mocked or hosted-only evidence is not this task. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T6 Record Windows acceptance. (AC1, AC2)
  - **Files**: `scripts/mirroring_acceptance.py`; focused tests: `tests/browser/mirroring_acceptance.spec.js`.
  - **Change**: Obtain a passing hosted Windows receipt on the same revision; failed or unavailable execution leaves this task pending.
  - **Verify**: `python3 scripts/mirroring_acceptance.py --help; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/mirroring_acceptance.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Obtain a passing hosted Windows receipt on the same revision; failed or unavailable execution leaves this task pending. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [~] T7 Publish the scoped capability matrix. (AC3) — matrix exists; wording must distinguish synthetic workflow checks from real site-mirroring qualification.
  - **Files**: `docs/MIRRORING_COMPATIBILITY.md`, `README.md`; focused tests: `tests/browser/mirroring_acceptance.spec.js`.
  - **Change**: Map each supported claim to a receipt; label optional extension tiers pending until independently qualified; document static and server-side limits.
  - **Verify**: `python3 scripts/mirroring_acceptance.py --help; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/mirroring_acceptance.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Map each supported claim to a receipt; label optional extension tiers pending until independently qualified; document static and server-side limits. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T8 Final acceptance and claim reconciliation. (AC1–AC3)
  - **Files**: this track’s plan, metadata, review and evidence; documentation explicitly owned by the tasks above.
  - **Change**: Review every requirement against completed slices and each acceptance criterion against retained receipts. Mark unavailable platform runs pending and report scoped limitations.
  - **Verify**: `python3 scripts/mirroring_acceptance.py --help; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/mirroring_acceptance.spec.js`; `python3 scripts/gate.py test`; full Conductor validation.
  - **Done when**: All required criteria pass, receipt hashes resolve, and no supported claim relies on an unexecuted test. No mandatory human sign-off for machine-verifiable behaviour.
