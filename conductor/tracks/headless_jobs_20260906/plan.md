# Plan: Headless jobs, scheduling and automation contracts

## Status: NEW

Execute tasks in order after metadata dependencies complete. Each functional task first adds its focused failing assertions, then implements and refactors that slice; commit only after its new assertions and existing regression gate pass. Each task may update its own plan, metadata and append-only evidence. No prior implementation tasks were completed when this plan was refined.

- [ ] T1 Define versioned job state and exit contracts. (AC1, AC2)
  - **Files**: `cli/jobs.py`; focused tests: `tests/test_headless_jobs.py`.
  - **Change**: Specify complete/partial/auth-required/failed states, idempotency keys, events and synthetic transition fixtures.
  - **Verify**: `python3 -m unittest tests.test_headless_jobs`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Specify complete/partial/auth-required/failed states, idempotency keys, events and synthetic transition fixtures. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T2 Implement persistent leases and run identity. (AC1)
  - **Files**: `cli/jobs.py`; focused tests: `tests/test_headless_jobs.py`.
  - **Change**: Prevent overlapping workers from duplicating capture; recover stale leases without stealing live work.
  - **Verify**: `python3 -m unittest tests.test_headless_jobs`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Prevent overlapping workers from duplicating capture; recover stale leases without stealing live work. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T3 Implement lifecycle CLI operations. (AC1, AC2)
  - **Files**: `cli/jobs.py`; focused tests: `tests/test_headless_jobs.py`.
  - **Change**: Provide start/status/pause/resume/cancel with bounded retries and checkpoint integration.
  - **Verify**: `python3 -m unittest tests.test_headless_jobs`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Provide start/status/pause/resume/cancel with bounded retries and checkpoint integration. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T4 Add scoped MCP job operations. (AC2)
  - **Files**: `mcp/server.py`; focused tests: `tests/test_headless_jobs.py`.
  - **Change**: Expose schema-validated job operations with no unrestricted shell; preserve transport/security contracts.
  - **Verify**: `python3 -m unittest tests.test_headless_jobs`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Expose schema-validated job operations with no unrestricted shell; preserve transport/security contracts. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T5 Implement opt-in schedule adapters. (AC1, AC3)
  - **Files**: `cli/jobs.py`; focused tests: `tests/test_headless_jobs.py`.
  - **Change**: Use portable job definitions, handle missed/overlapping schedules and never activate schedules at install time.
  - **Verify**: `python3 -m unittest tests.test_headless_jobs`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Use portable job definitions, handle missed/overlapping schedules and never activate schedules at install time. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T6 Add redacted optional notifications. (AC2, AC3)
  - **Files**: `cli/jobs.py`; focused tests: `tests/test_headless_jobs.py`.
  - **Change**: Keep notifications disabled by default; permit configured destinations and summary/hash payloads only.
  - **Verify**: `python3 -m unittest tests.test_headless_jobs`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Keep notifications disabled by default; permit configured destinations and summary/hash payloads only. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T7 Test restart and schedule behaviour on both platforms. (AC1, AC2, AC3)
  - **Files**: `tests/test_headless_jobs.py`, `docs/HEADLESS_JOBS.md`; focused tests: `tests/test_headless_jobs.py`.
  - **Change**: Record actual macOS/Windows runs for cancellation, retries, crash recovery and overlap prevention.
  - **Verify**: `python3 -m unittest tests.test_headless_jobs`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Record actual macOS/Windows runs for cancellation, retries, crash recovery and overlap prevention. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T8 Final acceptance and claim reconciliation. (AC1–AC3)
  - **Files**: this track’s plan, metadata, review and evidence; documentation explicitly owned by the tasks above.
  - **Change**: Review every requirement against completed slices and each acceptance criterion against retained receipts. Mark unavailable platform runs pending and report scoped limitations.
  - **Verify**: `python3 -m unittest tests.test_headless_jobs`; `python3 scripts/gate.py test`; full Conductor validation.
  - **Done when**: All required criteria pass, receipt hashes resolve, and no supported claim relies on an unexecuted test. No mandatory human sign-off for machine-verifiable behaviour.
