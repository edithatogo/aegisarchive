# Plan: Generic document lifecycle, extraction and search

## Status: NEW

Execute tasks in order after metadata dependencies complete. Each functional task first adds its focused failing assertions, then implements and refactors that slice; commit only after its new assertions and existing regression gate pass. Each task may update its own plan, metadata and append-only evidence. No prior implementation tasks were completed when this plan was refined.

- [ ] T1 Define catalogue and derivative schemas. (AC1, AC2)
  - **Files**: `portable/document_catalogue.py`; focused tests: `tests/test_document_lifecycle.py`.
  - **Change**: Specify source/revision identity, unknown metadata, MIME, hashes, locators, handling flags and explicit processing states.
  - **Verify**: `python3 -m unittest tests.test_document_lifecycle`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Specify source/revision identity, unknown metadata, MIME, hashes, locators, handling flags and explicit processing states. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T2 Implement immutable registration and history. (AC2)
  - **Files**: `portable/document_catalogue.py`; focused tests: `tests/test_document_lifecycle.py`.
  - **Change**: Reconcile moved URLs, identical bytes and changed revisions; preserve acquisition history and originals.
  - **Verify**: `python3 -m unittest tests.test_document_lifecycle`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Reconcile moved URLs, identical bytes and changed revisions; preserve acquisition history and originals. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T3 Add bounded native text extraction. (AC1, AC3)
  - **Files**: `portable/document_extract.py`; focused tests: `tests/test_document_lifecycle.py`.
  - **Change**: Extract supported built-in text formats with stable locators and content-free failure diagnostics.
  - **Verify**: `python3 -m unittest tests.test_document_lifecycle`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Extract supported built-in text formats with stable locators and content-free failure diagnostics. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T4 Add optional PDF and Office adapters. (AC1, AC3)
  - **Files**: `portable/document_extract.py`, `optional/document_processing/`; focused tests: `tests/test_document_lifecycle.py`.
  - **Change**: Pin isolated parsers; record versions and text-layer coverage, reject encrypted or malformed inputs explicitly.
  - **Verify**: `python3 -m unittest tests.test_document_lifecycle`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Pin isolated parsers; record versions and text-layer coverage, reject encrypted or malformed inputs explicitly. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T5 Add optional OCR derivative processing. (AC1, AC3)
  - **Files**: `portable/document_extract.py`, `optional/document_processing/`; focused tests: `tests/test_document_lifecycle.py`.
  - **Change**: Keep OCR output distinct from original text; retain page locators/confidence and unsupported-engine outcomes.
  - **Verify**: `python3 -m unittest tests.test_document_lifecycle`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Keep OCR output distinct from original text; retain page locators/confidence and unsupported-engine outcomes. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T6 Implement revision-aware offline search. (AC1, AC2)
  - **Files**: `portable/document_search.py`; focused tests: `tests/test_document_lifecycle.py`.
  - **Change**: Reuse generic search contracts after review; index only eligible derivatives with original/version links.
  - **Verify**: `python3 -m unittest tests.test_document_lifecycle`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Reuse generic search contracts after review; index only eligible derivatives with original/version links. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T7 Implement revision changes and duplicates. (AC2)
  - **Files**: `portable/document_catalogue.py`, `portable/document_search.py`; focused tests: `tests/test_document_lifecycle.py`.
  - **Change**: Compare revisions without confusing movement with change; emit immutable change receipts.
  - **Verify**: `python3 -m unittest tests.test_document_lifecycle`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Compare revisions without confusing movement with change; emit immutable change receipts. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T8 Enforce handling and retention boundaries. (AC3)
  - **Files**: `portable/document_catalogue.py`, `portable/document_search.py`, `docs/DOCUMENT_LIFECYCLE.md`; focused tests: `tests/test_document_lifecycle.py`.
  - **Change**: Propagate restrictions to search/cache/export, quarantine flags and expose explicit deletion semantics without automatic privacy clearance.
  - **Verify**: `python3 -m unittest tests.test_document_lifecycle`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Propagate restrictions to search/cache/export, quarantine flags and expose explicit deletion semantics without automatic privacy clearance. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T9 Final acceptance and claim reconciliation. (AC1–AC3)
  - **Files**: this track’s plan, metadata, review and evidence; documentation explicitly owned by the tasks above.
  - **Change**: Review every requirement against completed slices and each acceptance criterion against retained receipts. Mark unavailable platform runs pending and report scoped limitations.
  - **Verify**: `python3 -m unittest tests.test_document_lifecycle`; `python3 scripts/gate.py test`; full Conductor validation.
  - **Done when**: All required criteria pass, receipt hashes resolve, and no supported claim relies on an unexecuted test. No mandatory human sign-off for machine-verifiable behaviour.
