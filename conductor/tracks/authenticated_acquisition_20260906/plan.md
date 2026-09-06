# Plan: Explicit authenticated acquisition routes

## Status: NEW

Execute tasks in order after metadata dependencies complete. Each functional task first adds its focused failing assertions, then implements and refactors that slice; commit only after its new assertions and existing regression gate pass. Each task may update its own plan, metadata and append-only evidence. No prior implementation tasks were completed when this plan was refined.

- [ ] T1 Define session contracts and auth fixtures. (AC1, AC2)
  - **Files**: `tests/fixtures/auth/`, `cli/session_scope.py`; focused tests: `tests/test_session_scope.py`.
  - **Change**: Specify opt-in cookie/basic-auth input, origin allowlists, expiry states and synthetic secret sentinels.
  - **Verify**: `python3 -m unittest tests.test_session_scope`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Specify opt-in cookie/basic-auth input, origin allowlists, expiry states and synthetic secret sentinels. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T2 Load explicit local session material. (AC1, AC2)
  - **Files**: `cli/session_scope.py`; focused tests: `tests/test_session_scope.py`.
  - **Change**: Validate private local inputs and exact scope without reading browser profiles; reject ambiguous credentials.
  - **Verify**: `python3 -m unittest tests.test_session_scope`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Validate private local inputs and exact scope without reading browser profiles; reject ambiguous credentials. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T3 Enforce redirect credential isolation. (AC1, AC2)
  - **Files**: `cli/session_scope.py`, `cli/aegis_cli.py`; focused tests: `tests/test_session_scope.py`.
  - **Change**: Attach credentials only to approved origins and never forward them to a newly redirected origin.
  - **Verify**: `python3 -m unittest tests.test_session_scope`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Attach credentials only to approved origins and never forward them to a newly redirected origin. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T4 Detect login and session expiry. (AC1, AC3)
  - **Files**: `cli/aegis_cli.py`; focused tests: `tests/test_session_scope.py`.
  - **Change**: Distinguish 401/403, login HTML and unsupported interactive SSO from successful content; preserve resumable failure state.
  - **Verify**: `python3 -m unittest tests.test_session_scope`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Distinguish 401/403, login HTML and unsupported interactive SSO from successful content; preserve resumable failure state. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T5 Redact all secret-bearing artefacts. (AC2)
  - **Files**: `cli/aegis_cli.py`, `cli/session_scope.py`; focused tests: `tests/test_session_scope.py`.
  - **Change**: Scan WARC request records, logs and receipts for supplied sentinel credentials; allow only non-secret provenance.
  - **Verify**: `python3 -m unittest tests.test_session_scope`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Scan WARC request records, logs and receipts for supplied sentinel credentials; allow only non-secret provenance. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T6 Expose supported acquisition routes. (AC3)
  - **Files**: `web/index.html`, `docs/ACQUISITION_ROUTES.md`; focused tests: `tests/test_session_scope.py`.
  - **Change**: Explain public CLI, same-origin browser and explicit session routes; no automatic Chrome-login inheritance claim.
  - **Verify**: `python3 -m unittest tests.test_session_scope`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Explain public CLI, same-origin browser and explicit session routes; no automatic Chrome-login inheritance claim. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T7 Final acceptance and claim reconciliation. (AC1–AC3)
  - **Files**: this track’s plan, metadata, review and evidence; documentation explicitly owned by the tasks above.
  - **Change**: Review every requirement against completed slices and each acceptance criterion against retained receipts. Mark unavailable platform runs pending and report scoped limitations.
  - **Verify**: `python3 -m unittest tests.test_session_scope`; `python3 scripts/gate.py test`; full Conductor validation.
  - **Done when**: All required criteria pass, receipt hashes resolve, and no supported claim relies on an unexecuted test. No mandatory human sign-off for machine-verifiable behaviour.
