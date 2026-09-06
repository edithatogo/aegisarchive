# Plan: Durable mirror resume and incremental updates

## Status: NEW

Execute tasks in order after metadata dependencies complete. Each functional task first adds its focused failing assertions, then implements and refactors that slice; commit only after its new assertions and existing regression gate pass. Each task may update its own plan, metadata and append-only evidence. No prior implementation tasks were completed when this plan was refined.

- [ ] T1 Define checkpoint schema and fault fixtures. (AC1, AC2)
  - **Files**: `cli/mirror_checkpoint.py`, `web/lib/mirror_checkpoint.js`; focused tests: `tests/test_mirror_resume.py`; `tests/js/mirror_resume.test.js`.
  - **Change**: Version profile/segment/hash state and specify interruption points, corruption and mismatch rejection.
  - **Verify**: `python3 -m unittest tests.test_mirror_resume; node --test tests/js/mirror_resume.test.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Version profile/segment/hash state and specify interruption points, corruption and mismatch rejection. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T2 Persist CLI archive segments atomically. (AC1)
  - **Files**: `cli/mirror_checkpoint.py`, `cli/aegis_cli.py`; focused tests: `tests/test_mirror_resume.py`; `tests/js/mirror_resume.test.js`.
  - **Change**: Commit segment bytes before checkpoint references; recover truncated writes without losing completed records.
  - **Verify**: `python3 -m unittest tests.test_mirror_resume; node --test tests/js/mirror_resume.test.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Commit segment bytes before checkpoint references; recover truncated writes without losing completed records. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T3 Persist browser bytes and frontier together. (AC1, AC3)
  - **Files**: `web/lib/mirror_checkpoint.js`, `web/lib/opfs_streamer.js`, `web/lib/core_crawler.js`; focused tests: `tests/test_mirror_resume.py`; `tests/js/mirror_resume.test.js`.
  - **Change**: Coordinate durable storage and checkpoint updates; explicitly disable durable claims on memory-only fallback.
  - **Verify**: `python3 -m unittest tests.test_mirror_resume; node --test tests/js/mirror_resume.test.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Coordinate durable storage and checkpoint updates; explicitly disable durable claims on memory-only fallback. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T4 Implement verified resume and cancellation. (AC1, AC3)
  - **Files**: `cli/aegis_cli.py`, `web/lib/core_crawler.js`; focused tests: `tests/test_mirror_resume.py`; `tests/js/mirror_resume.test.js`.
  - **Change**: Reverify prior bytes and profile before resuming; preserve completed records and record cancellation/storage failures.
  - **Verify**: `python3 -m unittest tests.test_mirror_resume; node --test tests/js/mirror_resume.test.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Reverify prior bytes and profile before resuming; preserve completed records and record cancellation/storage failures. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T5 Implement conditional incremental refresh. (AC2)
  - **Files**: `cli/aegis_cli.py`, `web/lib/core_crawler.js`; focused tests: `tests/test_mirror_resume.py`; `tests/js/mirror_resume.test.js`.
  - **Change**: Use validators when available and preserve old revisions; identify missing resources without silently deleting evidence.
  - **Verify**: `python3 -m unittest tests.test_mirror_resume; node --test tests/js/mirror_resume.test.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Use validators when available and preserve old revisions; identify missing resources without silently deleting evidence. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T6 Resolve revisit lineage across segments. (AC2)
  - **Files**: `cli/mirror_checkpoint.py`, `web/lib/mirror_checkpoint.js`; focused tests: `tests/test_mirror_resume.py`; `tests/js/mirror_resume.test.js`.
  - **Change**: Ensure every revisit resolves to retained payload bytes and expose broken references as validation failures.
  - **Verify**: `python3 -m unittest tests.test_mirror_resume; node --test tests/js/mirror_resume.test.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Ensure every revisit resolves to retained payload bytes and expose broken references as validation failures. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T7 Exercise interruption and recovery matrix. (AC1, AC2, AC3)
  - **Files**: `tests/test_mirror_resume.py`, `tests/js/mirror_resume.test.js`; focused tests: `tests/test_mirror_resume.py`; `tests/js/mirror_resume.test.js`.
  - **Change**: Compare killed/restarted fixture runs with uninterrupted URL/hash sets across storage exhaustion and corrupt state.
  - **Verify**: `python3 -m unittest tests.test_mirror_resume; node --test tests/js/mirror_resume.test.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Compare killed/restarted fixture runs with uninterrupted URL/hash sets across storage exhaustion and corrupt state. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T8 Final acceptance and claim reconciliation. (AC1–AC3)
  - **Files**: this track’s plan, metadata, review and evidence; documentation explicitly owned by the tasks above.
  - **Change**: Review every requirement against completed slices and each acceptance criterion against retained receipts. Mark unavailable platform runs pending and report scoped limitations.
  - **Verify**: `python3 -m unittest tests.test_mirror_resume; node --test tests/js/mirror_resume.test.js`; `python3 scripts/gate.py test`; full Conductor validation.
  - **Done when**: All required criteria pass, receipt hashes resolve, and no supported claim relies on an unexecuted test. No mandatory human sign-off for machine-verifiable behaviour.
