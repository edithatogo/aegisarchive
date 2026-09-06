# Plan: Safe offline page navigation and assets

## Status: COMPLETED (2026-09-07 — archive-local navigation and disconnected replay verified)

Execute tasks in order after metadata dependencies complete. Each functional task first adds its focused failing assertions, then implements and refactors that slice; commit only after its new assertions and existing regression gate pass. Each task may update its own plan, metadata and append-only evidence. No prior implementation tasks were completed when this plan was refined.

- [x] T1 Provision isolated browser acceptance tooling. (AC1, AC2) — commit fa2cd6c
  - **Files**: `package.json`, `package-lock.json`, `tests/browser/playwright.config.js`; focused tests: `tests/js/offline_navigation.test.js`; `tests/browser/offline_replay.spec.js`.
  - **Change**: Pin test-only browser tooling, document browser provisioning and network isolation, and create a deterministic loopback fixture harness.
  - **Verify**: `node --test tests/js/offline_navigation.test.js; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/offline_replay.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Pin test-only browser tooling, document browser provisioning and network isolation, and create a deterministic loopback fixture harness. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T2 Specify archive navigation and hostile fixtures. (AC1, AC2) — commit ee0cfb3
  - **Files**: `tests/browser/fixtures/`; focused tests: `tests/js/offline_navigation.test.js`; `tests/browser/offline_replay.spec.js`.
  - **Change**: Define expected page/fragment/history transitions plus malicious messages, refresh, forms, scripts and missing targets.
  - **Verify**: `node --test tests/js/offline_navigation.test.js; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/offline_replay.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Define expected page/fragment/history transitions plus malicious messages, refresh, forms, scripts and missing targets. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T3 Implement canonical archive-local resolution. (AC1, AC3) — commit 34d3c4c
  - **Files**: `web/lib/offline_navigation.js`; focused tests: `tests/js/offline_navigation.test.js`; `tests/browser/offline_replay.spec.js`.
  - **Change**: Resolve archived redirects and query identities; expose missing destinations without live fallback.
  - **Verify**: `node --test tests/js/offline_navigation.test.js; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/offline_replay.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Resolve archived redirects and query identities; expose missing destinations without live fallback. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T4 Implement isolated navigation signalling. (AC1, AC2) — commit 5e51a34
  - **Files**: `web/lib/warc_reader.js`, `web/lib/offline_navigation.js`; focused tests: `tests/js/offline_navigation.test.js`; `tests/browser/offline_replay.spec.js`.
  - **Change**: Use a narrow nonce/source-bound navigation contract or equivalent isolated route; captured scripts remain disabled and cannot gain parent privileges.
  - **Verify**: `node --test tests/js/offline_navigation.test.js; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/offline_replay.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Use a narrow nonce/source-bound navigation contract or equivalent isolated route; captured scripts remain disabled and cannot gain parent privileges. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T5 Wire viewer navigation and history. (AC1, AC2) — commit 363c4b4
  - **Files**: `web/viewer.html`; focused tests: `tests/js/offline_navigation.test.js`; `tests/browser/offline_replay.spec.js`.
  - **Change**: Connect the validated navigation contract, back/forward, fragments and accessible missing-resource status.
  - **Verify**: `node --test tests/js/offline_navigation.test.js; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/offline_replay.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Connect the validated navigation contract, back/forward, fragments and accessible missing-resource status. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T6 Rewrite nested assets and manage lifetime. (AC1, AC3) — commit 02783e2
  - **Files**: `web/lib/warc_reader.js`; focused tests: `tests/js/offline_navigation.test.js`; `tests/browser/offline_replay.spec.js`.
  - **Change**: Handle CSS dependencies, srcset, fonts and images without modifying original payloads; release obsolete blob resources safely.
  - **Verify**: `node --test tests/js/offline_navigation.test.js; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/offline_replay.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Handle CSS dependencies, srcset, fonts and images without modifying original payloads; release obsolete blob resources safely. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T7 Prove disconnected-source replay. (AC1, AC2, AC3) — commit 9d7ef48
  - **Files**: `tests/browser/offline_replay.spec.js`; focused tests: `tests/js/offline_navigation.test.js`; `tests/browser/offline_replay.spec.js`.
  - **Change**: Stop the source and traverse three pages plus assets; instrument requests and reject all unintended non-loopback traffic.
  - **Verify**: `node --test tests/js/offline_navigation.test.js; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/offline_replay.spec.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Stop the source and traverse three pages plus assets; instrument requests and reject all unintended non-loopback traffic. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T8 Final acceptance and claim reconciliation. (AC1–AC3)
  - **Files**: this track’s plan, metadata, review and evidence; documentation explicitly owned by the tasks above.
  - **Change**: Review every requirement against completed slices and each acceptance criterion against retained receipts. Mark unavailable platform runs pending and report scoped limitations.
  - **Verify**: `node --test tests/js/offline_navigation.test.js; npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/offline_replay.spec.js`; `python3 scripts/gate.py test`; full Conductor validation.
  - **Done when**: All required criteria pass, receipt hashes resolve, and no supported claim relies on an unexecuted test. No mandatory human sign-off for machine-verifiable behaviour.

- [x] T8 Final acceptance and claim reconciliation. (AC1–AC3) — commit a452f1d

## Review Fixes

- [x] R1 Preserve safe metadata and continuous click interception. (AC1, AC2) — commit e4be6f7
  - **Change**: remove only refresh metadata during replay and keep the navigation listener active for the page lifetime.
  - **Verify**: `node --test tests/js/offline_navigation.test.js tests/js`; full repository gate and Conductor validation.
