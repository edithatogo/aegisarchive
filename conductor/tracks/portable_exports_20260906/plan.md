# Plan: Portable mirror exports and interoperability

## Status: NEW

Execute tasks in order after metadata dependencies complete. Each functional task first adds its focused failing assertions, then implements and refactors that slice; commit only after its new assertions and existing regression gate pass. Each task may update its own plan, metadata and append-only evidence. No prior implementation tasks were completed when this plan was refined.

- [ ] T1 Specify export mappings and adversarial fixtures. (AC2)
  - **Files**: `cli/export_mirror.py`; focused tests: `tests/test_mirror_export.py`; `tests/browser/export_acceptance.spec.js`.
  - **Change**: Define query identity, reserved filenames, Unicode/case collisions, long paths and traversal rejection.
  - **Verify**: `python3 -m unittest tests.test_mirror_export; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/export_acceptance.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Define query identity, reserved filenames, Unicode/case collisions, long paths and traversal rejection. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T2 Implement deterministic directory export. (AC1, AC2)
  - **Files**: `cli/export_mirror.py`; focused tests: `tests/test_mirror_export.py`; `tests/browser/export_acceptance.spec.js`.
  - **Change**: Write local paths and links using the frozen map; retain original archives and an inventory manifest.
  - **Verify**: `python3 -m unittest tests.test_mirror_export; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/export_acceptance.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Write local paths and links using the frozen map; retain original archives and an inventory manifest. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T3 Add deterministic ZIP and readback. (AC2, AC3)
  - **Files**: `cli/export_mirror.py`; focused tests: `tests/test_mirror_export.py`; `tests/browser/export_acceptance.spec.js`.
  - **Change**: Normalise timestamps/order, verify payload hashes on import and reject escaping/ambiguous members.
  - **Verify**: `python3 -m unittest tests.test_mirror_export; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/export_acceptance.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Normalise timestamps/order, verify payload hashes on import and reject escaping/ambiguous members. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T4 Specify WACZ/CDXJ format contract. (AC3)
  - **Files**: `docs/PORTABLE_EXPORTS.md`; focused tests: `tests/test_mirror_export.py`; `tests/browser/export_acceptance.spec.js`.
  - **Change**: Pin applicable specifications and independent validators before code; resolve existing ADR choices without assuming research equals delivery.
  - **Verify**: `python3 -m unittest tests.test_mirror_export; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/export_acceptance.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Pin applicable specifications and independent validators before code; resolve existing ADR choices without assuming research equals delivery. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T5 Implement and independently validate interoperable package. (AC3)
  - **Files**: `cli/export_mirror.py`; focused tests: `tests/test_mirror_export.py`; `tests/browser/export_acceptance.spec.js`.
  - **Change**: Produce the agreed format only when validators/readback confirm record and payload integrity.
  - **Verify**: `python3 -m unittest tests.test_mirror_export; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/export_acceptance.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Produce the agreed format only when validators/readback confirm record and payload integrity. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T6 Qualify relocation and accessible offline use. (AC1, AC2)
  - **Files**: `tests/browser/export_acceptance.spec.js`; focused tests: `tests/test_mirror_export.py`; `tests/browser/export_acceptance.spec.js`.
  - **Change**: Navigate exported pages/assets from relocated paths on both platforms and verify keyboard-accessible missing-resource states.
  - **Verify**: `python3 -m unittest tests.test_mirror_export; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/export_acceptance.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Navigate exported pages/assets from relocated paths on both platforms and verify keyboard-accessible missing-resource states. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T7 Document prerequisites and repair diagnostics. (AC3)
  - **Files**: `docs/PORTABLE_EXPORTS.md`; focused tests: `tests/test_mirror_export.py`; `tests/browser/export_acceptance.spec.js`.
  - **Change**: Explain validation/repair limits and static/rendered route choice; report runtime/model assets actually present.
  - **Verify**: `python3 -m unittest tests.test_mirror_export; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/export_acceptance.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Explain validation/repair limits and static/rendered route choice; report runtime/model assets actually present. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T8 Final acceptance and claim reconciliation. (AC1–AC3)
  - **Files**: this track’s plan, metadata, review and evidence; documentation explicitly owned by the tasks above.
  - **Change**: Review every requirement against completed slices and each acceptance criterion against retained receipts. Mark unavailable platform runs pending and report scoped limitations.
  - **Verify**: `python3 -m unittest tests.test_mirror_export; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/export_acceptance.spec.js`; `python3 scripts/gate.py test`; full Conductor validation.
  - **Done when**: All required criteria pass, receipt hashes resolve, and no supported claim relies on an unexecuted test. No mandatory human sign-off for machine-verifiable behaviour.
