# Plan: Cross-platform mirroring and capability acceptance

## Status: NEW

Execute tasks in order after metadata dependencies complete. Each functional task first adds its focused failing assertions, then implements and refactors that slice; commit only after its new assertions and existing regression gate pass. Each task may update its own plan, metadata and append-only evidence. No prior implementation tasks were completed when this plan was refined.

- [ ] T1 Define platform receipt contract. (AC1)
  - **Files**: `scripts/mirroring_acceptance.py`; focused tests: `tests/browser/mirroring_acceptance.spec.js`.
  - **Change**: Bind revision, fixture hashes, runtime/browser versions, capture/readback results and traffic observations in a machine-readable receipt.
  - **Verify**: `python3 scripts/mirroring_acceptance.py --help; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/mirroring_acceptance.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Bind revision, fixture hashes, runtime/browser versions, capture/readback results and traffic observations in a machine-readable receipt. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T2 Build capture-disconnect-replay harness. (AC1, AC2)
  - **Files**: `scripts/mirroring_acceptance.py`, `tests/browser/mirroring_acceptance.spec.js`; focused tests: `tests/browser/mirroring_acceptance.spec.js`.
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

- [ ] T4 Add isolated platform acceptance CI. (AC1, AC2)
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

- [ ] T7 Publish the scoped capability matrix. (AC3)
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
