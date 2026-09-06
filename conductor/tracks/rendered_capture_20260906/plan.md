# Plan: Optional rendered-browser capture and headless automation

## Status: NEW

Execute tasks in order after metadata dependencies complete. Each functional task first adds its focused failing assertions, then implements and refactors that slice; commit only after its new assertions and existing regression gate pass. Each task may update its own plan, metadata and append-only evidence. No prior implementation tasks were completed when this plan was refined.

- [ ] T1 Specify adapter and rendered fixture contract. (AC1, AC3)
  - **Files**: `optional/browser_capture/`; focused tests: `tests/browser/rendered_capture.spec.js`.
  - **Change**: Define optional runtime boundary, capture recipe schema, pinned browser versions and rendered-vs-original provenance.
  - **Verify**: `npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/rendered_capture.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Define optional runtime boundary, capture recipe schema, pinned browser versions and rendered-vs-original provenance. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T2 Implement isolated browser lifecycle. (AC3)
  - **Files**: `optional/browser_capture/`; focused tests: `tests/browser/rendered_capture.spec.js`.
  - **Change**: Bound process lifetime, temporary state and cleanup; core runtime still works without the adapter.
  - **Verify**: `npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/rendered_capture.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Bound process lifetime, temporary state and cleanup; core runtime still works without the adapter. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T3 Enforce subrequest scope and pacing. (AC2)
  - **Files**: `optional/browser_capture/`; focused tests: `tests/browser/rendered_capture.spec.js`.
  - **Change**: Intercept frames, popups, service workers and redirects; deny paths that cannot be controlled and protect session material.
  - **Verify**: `npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/rendered_capture.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Intercept frames, popups, service workers and redirects; deny paths that cannot be controlled and protect session material. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T4 Implement bounded rendered interaction recipes. (AC1, AC2)
  - **Files**: `optional/browser_capture/`; focused tests: `tests/browser/rendered_capture.spec.js`.
  - **Change**: Support explicit scrolling, pagination and downloads with time/page/byte limits; reject source-authored tool instructions.
  - **Verify**: `npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/rendered_capture.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Support explicit scrolling, pagination and downloads with time/page/byte limits; reject source-authored tool instructions. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T5 Implement opt-in login recipes. (AC2, AC3)
  - **Files**: `optional/browser_capture/`; focused tests: `tests/browser/rendered_capture.spec.js`.
  - **Change**: Support authorised login forms and CSRF/session expiry without unrelated profile access or arbitrary mutating actions.
  - **Verify**: `npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/rendered_capture.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Support authorised login forms and CSRF/session expiry without unrelated profile access or arbitrary mutating actions. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T6 Write response and rendered derivative receipts. (AC1, AC3)
  - **Files**: `optional/browser_capture/`; focused tests: `tests/browser/rendered_capture.spec.js`.
  - **Change**: Separate original responses from DOM/screenshot derivatives and record incomplete streaming/backend behaviour.
  - **Verify**: `npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/rendered_capture.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Separate original responses from DOM/screenshot derivatives and record incomplete streaming/backend behaviour. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T7 Qualify visible and headless platform runs. (AC1, AC2, AC3)
  - **Files**: `tests/browser/rendered_capture.spec.js`; focused tests: `tests/browser/rendered_capture.spec.js`.
  - **Change**: Prove declared content parity and zero scope/credential escapes on macOS and Windows with pinned fixtures.
  - **Verify**: `npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/rendered_capture.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Prove declared content parity and zero scope/credential escapes on macOS and Windows with pinned fixtures. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T8 Final acceptance and claim reconciliation. (AC1–AC3)
  - **Files**: this track’s plan, metadata, review and evidence; documentation explicitly owned by the tasks above.
  - **Change**: Review every requirement against completed slices and each acceptance criterion against retained receipts. Mark unavailable platform runs pending and report scoped limitations.
  - **Verify**: `npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/rendered_capture.spec.js`; `python3 scripts/gate.py test`; full Conductor validation.
  - **Done when**: All required criteria pass, receipt hashes resolve, and no supported claim relies on an unexecuted test. No mandatory human sign-off for machine-verifiable behaviour.
