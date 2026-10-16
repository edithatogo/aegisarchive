# Plan: Cross-platform mirroring and capability acceptance

## Status: COMPLETED — qualified implementation 4255021; historical H1 disclosed

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

Final T2 verification reproduced a receipt-generation deadlock on the current
Python 3.15 runtime: process samples showed Python and Git both blocked writing
opposite sides of the batch pipe. T2 additionally owns
`tests/test_mirroring_acceptance.py` for a file-backed Git input regression;
no runtime version is silently excluded and no timeout is increased to hide
this failure. This is a necessary acceptance-harness prerequisite.

The coordinator's bounded repair was reconciled against the user's standing
instructions to address issues across the chats without routine permission
requests. T2 additionally owns `portable/document_extract.py` and
`tests/test_document_lifecycle.py` solely to restore the existing malformed-HTML
declaration contract across Python parser versions. The document-lifecycle track
is completed, so this does not conflict with an active writer. Preserve ordinary
comments, scripts, DOCTYPE and supported marked sections; retain fixed,
source-free failure diagnostics. This prerequisite does not authorise a push.

Execute tasks in order after metadata dependencies complete. Each functional task first adds its focused failing assertions, then implements and refactors that slice; commit only after its new assertions and existing regression gate pass. Each task may update its own plan, metadata and append-only evidence. No prior implementation tasks were completed when this plan was refined.

- [x] T1 Define platform receipt contract. (AC1) — v2 binds measured observations, archive bytes, runtime, fixture identities and committed provenance; unexecuted runs remain pending. Implementation commit recorded in the task completion receipt.
  - **Files**: `scripts/mirroring_acceptance.py`, `tests/test_mirroring_acceptance.py`, `tests/browser/fixtures/mirroring-site.json`; focused tests: `tests/browser/mirroring_acceptance.spec.js`.
  - **Change**: Bind revision, fixture hashes, runtime/browser versions, capture/readback results and traffic observations in a machine-readable receipt.
  - **Verify**: `python3 scripts/mirroring_acceptance.py --help; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/mirroring_acceptance.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Bind revision, fixture hashes, runtime/browser versions, capture/readback results and traffic observations in a machine-readable receipt. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T2 Build capture-disconnect-replay harness. (AC1, AC2) — final full baseline passed: 353 Python tests (12 skipped), 18 station tests and 85 JavaScript tests. All three final browser tests passed in 29.4 seconds with installed Chrome and pinned Playwright. Same-archive reload recovery, setup-failure retry, six payload hashes and 11 disconnected navigation visits passed. This completes the harness, not ordinary-launcher or Mac/Windows qualification.
  - **Files**: `scripts/mirroring_acceptance.py`, `tests/browser/mirroring_acceptance.spec.js`; necessary durable-recovery prerequisites: `cli/usb_archive.py`, `cli/capture_bridge.py`, `cli/politeness.py`, `web/lib/native_capture.js`, `web/lib/warc_writer.js`, `web/lib/core_crawler.js`, `web/lib/politeness_engine.js`, `web/index.html`, and replay fixes only if reproduced in `web/viewer.html` / `web/lib/warc_reader.js`; focused tests: `tests/browser/mirroring_acceptance.spec.js`, `tests/test_usb_archive.py`, `tests/test_capture_bridge.py`, `tests/test_politeness.py`, `tests/js/warc_writer.test.js`, `tests/js/core_crawler_checkpoint.test.js`, `tests/js/politeness_engine.test.js`.
  - **Change**: Start and stop a synthetic source, capture it and verify offline links/assets, auth expiry and resume behaviours.
  - **Verify**: `python3 scripts/mirroring_acceptance.py --help; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/mirroring_acceptance.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Start and stop a synthetic source, capture it and verify offline links/assets, auth expiry and resume behaviours. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T3 Verify relocated ordinary launchers. (AC1, AC3) — launcher harness implemented and verified on actual Darwin arm64/Python 3.15.0/Chromium 155.0.8059.82. Final full gate: 353 Python tests (12 skipped), 18 station tests, 85 JavaScript tests; final three browser cases passed, measured case 44.7s. Windows branch is statically reviewed but awaits T6 execution. POSIX test-package executable-mode preparation is explicit; existing ZIP readiness is not inferred.
  - **Files**: `tests/browser/mirroring_acceptance.spec.js`; focused tests: `tests/browser/mirroring_acceptance.spec.js`.
  - **Change**: Run from paths with spaces with supported Python/browser prerequisites; test missing-runtime diagnostics without changing launchers.
  - **Verify**: `python3 scripts/mirroring_acceptance.py --help; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/mirroring_acceptance.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Run from paths with spaces with supported Python/browser prerequisites; test missing-runtime diagnostics without changing launchers. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T4 Add isolated platform acceptance CI. (AC1, AC2) — actual launcher/capture/recovery/replay matrix, retained evidence and mandatory same-revision receipt comparison implemented and reviewed. Actionlint, semantic checks and final full gate pass (353 Python tests/12 skipped, 18 station, 85 JavaScript); final three browser cases pass, measured case 52.7s. This completes local workflow implementation, not hosted execution or Windows qualification; those remain T6.
  - **Files**: `.github/workflows/mirroring-acceptance.yml`; focused tests: `tests/browser/mirroring_acceptance.spec.js`.
  - **Change**: Reuse pinned tooling from the navigation track; run macOS and Windows against the same commit and retain receipts.
  - **Verify**: `python3 scripts/mirroring_acceptance.py --help; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/mirroring_acceptance.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Reuse pinned tooling from the navigation track; run macOS and Windows against the same commit and retain receipts. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T5 Record actual Apple Silicon acceptance. (AC1, AC2) — actual clean-source revision ff29f71389bd450c71cc4dcc09e03ceaa626b764 qualified on Darwin arm64/Python 3.15.0/Chromium 155.0.8059.82 with Playwright 1.63.0. Full gate passed (353 Python tests/12 skipped, 18 station, 85 JavaScript); all three browser cases passed in 36.0s. Positive receipt and complete proof retained under artifacts/qualification/ff29f71389bd450c71cc4dcc09e03ceaa626b764/darwin-arm64 and independently verified by two reviewers. This qualifies only the tested Mac/static-site scope; T6 remains pending.
  - **Files**: `scripts/mirroring_acceptance.py`; focused tests: `tests/browser/mirroring_acceptance.spec.js`.
  - **Change**: Execute the harness on the current Mac and retain hashes/results; mocked or hosted-only evidence is not this task.
  - **Verify**: `python3 scripts/mirroring_acceptance.py --help; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/mirroring_acceptance.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Execute the harness on the current Mac and retain hashes/results; mocked or hosted-only evidence is not this task. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T6 Record Windows acceptance. (AC1, AC2) — exact qualified revision 42550216efa5069870f011d9a9173c6a697ce1fb passes current local Apple Silicon Mac, hosted Mac and hosted Windows acceptance, all receipt checks, both comparisons and WARC/CDX integrity. Hosted run 38979330621 and all eight triggered workflows pass. Carver independently verified actual artifacts and archive bytes. The reverse-DNS startup defect was repaired and closed in its station owning track T9. Earlier failures remain historical evidence; T7/T8 remain open.
  - **Files**: `scripts/mirroring_acceptance.py`; focused tests: `tests/browser/mirroring_acceptance.spec.js`, `tests/test_mirroring_acceptance.py` (host-independent newline fixture prerequisite identified by actual Windows execution).
  - **Change**: Obtain a passing hosted Windows receipt on the same revision; failed or unavailable execution leaves this task pending.
  - **Verify**: `python3 scripts/mirroring_acceptance.py --help; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/mirroring_acceptance.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Obtain a passing hosted Windows receipt on the same revision; failed or unavailable execution leaves this task pending. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T7 Publish the scoped capability matrix. (AC3) — actual 4255021 evidence, scope and packaging/authentication/storage limitations documented; both panel reviewers approve. Receipt checks, comparisons, local links, claims/leak/health pass; runtime/workflow/test bytes unchanged since the qualified revision.
  - **Files**: `docs/MIRRORING_COMPATIBILITY.md`, `README.md`; focused tests: `tests/browser/mirroring_acceptance.spec.js`.
  - **Change**: Map each supported claim to a receipt; label optional extension tiers pending until independently qualified; document static and server-side limits. Documentation-only refinement: retain passing functional gates at exact qualified revision 4255021; do not rerun unchanged browser/baseline loops or claim a later documentation HEAD is newly qualified.
  - **Verify**: `python3 scripts/mirroring_acceptance.py --help`; validate all three retained 4255021 receipts with `--check` and both Mac/Windows pairs with `--compare`; `python3 scripts/claims_audit.py`; `python3 scripts/gate.py leak`; `python3 scripts/track_health.py --strict`; review documentation links and exact scope against observations. Any runtime change requires the full functional gates again.
  - **Done when**: Map each supported claim to a receipt; label optional extension tiers pending until independently qualified; document static and server-side limits. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Independent documentation review; verify no runtime bytes changed since 4255021 and retain that revision's full baseline and actual platform receipts.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T8 Final acceptance and claim reconciliation. (AC1–AC3) — R1–R4/AC1–AC3 map to reviewed actual 4255021 proof; all current references resolve, runtime/workflow/test bytes unchanged, claims/leak/health pass. Cicero/Carver approve final assessment and disclosed historical H1; no missing current acceptance evidence. No separate release publication claimed.
  - **Files**: this track’s plan, metadata, review and evidence; documentation explicitly owned by the tasks above.
  - **Change**: Review every requirement against completed slices and each acceptance criterion against retained receipts. Mark unavailable platform runs pending and report scoped limitations.
  - **Verify**: Revalidate the exact qualified 4255021 receipts and comparisons, all current acceptance hashes and canonical chains, requirement/AC mappings, documentation links, `python3 scripts/claims_audit.py`, `python3 scripts/gate.py leak`, and `python3 scripts/track_health.py --strict`. Confirm runtime/workflow/test bytes unchanged since the passing 4255021 baseline/browser/hosted run; preserve historical exceptions explicitly. This final documentation/evidence audit is not a new runtime qualification; changed runtime bytes require full functional gates again.
  - **Done when**: All required criteria pass, receipt hashes resolve, and no supported claim relies on an unexecuted test. No mandatory human sign-off for machine-verifiable behaviour.
