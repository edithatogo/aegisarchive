# Plan: Safe offline page navigation and assets

## Status: NEW

Tasks are sequential. Dependencies must complete first. This contract explicitly transfers ownership of the listed shared runtime files from completed historical tracks for these tasks only; do not modify their archived evidence. Later new tracks wait for earlier owners to finish. Existing launcher and CI files remain read-only; the acceptance track owns its new workflow.

- [ ] T1 Freeze acceptance fixtures and failing regression tests. (AC1–AC3)
  - **Files**: `web/viewer.html`, `web/lib/warc_reader.js`, `web/lib/offline_navigation.js`, `tests/js/offline_navigation.test.js`, `tests/browser/offline_replay.spec.js`; this track’s plan, metadata and evidence.
  - **Change**: Define the exact fixture URL/resource/hash graph and failure cases for AC1–AC3. Add test-only browser tooling/configuration when required; lock dependencies and document provisioning before invoking npx --no-install. Record expected baseline failures; distinguish RED evidence from the passing completion gate.
  - **Verify**: `node --test tests/js/offline_navigation.test.js && npx --no-install playwright test tests/browser/offline_replay.spec.js`; `python3 scripts/gate.py test`; full Conductor validation. For T1, record expected failing new assertions and require existing baseline tests to pass.
  - **Done when**: Fixtures and explicit failing assertions are recorded; development test tooling is available without altering core runtime dependencies.
  - **Do not**: substitute mocks or launcher smoke tests for required real browser/platform acceptance; weaken security to pass tests.

- [ ] T2 Implement the specified behaviour. (AC1–AC3)
  - **Files**: `web/viewer.html`, `web/lib/warc_reader.js`, `web/lib/offline_navigation.js`, `tests/js/offline_navigation.test.js`, `tests/browser/offline_replay.spec.js`; this track’s plan, metadata and evidence.
  - **Change**: Implement R1 onward within the owned files and make the T1 contract pass. Retain explicit unsupported cases and all existing security/politeness guarantees.
  - **Verify**: `node --test tests/js/offline_navigation.test.js && npx --no-install playwright test tests/browser/offline_replay.spec.js`; `python3 scripts/gate.py test`; full Conductor validation. For T1, record expected failing new assertions and require existing baseline tests to pass.
  - **Done when**: All applicable acceptance criteria and checkpoint review pass; evidence distinguishes local and hosted execution.
  - **Do not**: substitute mocks or launcher smoke tests for required real browser/platform acceptance; weaken security to pass tests.

- [ ] T3 Review, validate and record acceptance. (AC1–AC3)
  - **Files**: `web/viewer.html`, `web/lib/warc_reader.js`, `web/lib/offline_navigation.js`, `tests/js/offline_navigation.test.js`, `tests/browser/offline_replay.spec.js`; this track’s plan, metadata and evidence.
  - **Change**: Review hostile input, source disconnect, missing assets, redirects, secrets and failure semantics. Run focused tests and the baseline, retain revision-bound receipts and update capability claims only to the tested scope.
  - **Verify**: `node --test tests/js/offline_navigation.test.js && npx --no-install playwright test tests/browser/offline_replay.spec.js`; `python3 scripts/gate.py test`; full Conductor validation. For T1, record expected failing new assertions and require existing baseline tests to pass.
  - **Done when**: All applicable acceptance criteria and checkpoint review pass; evidence distinguishes local and hosted execution.
  - **Do not**: substitute mocks or launcher smoke tests for required real browser/platform acceptance; weaken security to pass tests.

