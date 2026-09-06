# Plan: Complete static-site capture

## Status: COMPLETED (2026-09-07 — declared static graph and explicit coverage verified)

Execute tasks in order after metadata dependencies complete. Each functional task first adds its focused failing assertions, then implements and refactors that slice; commit only after its new assertions and existing regression gate pass. Each task may update its own plan, metadata and append-only evidence. No prior implementation tasks were completed when this plan was refined.

- [x] T1 Freeze resource graph fixtures. (AC1) — commit 5a3c139
  - **Files**: `tests/fixtures/mirror/`; focused tests: `tests/test_mirror_capture.py`; `tests/js/mirror_capture.test.js`.
  - **Change**: Declare exact resources, hashes, encodings and negative outcomes for links, CSS, srcset, redirects and missing assets.
  - **Verify**: `python3 -m unittest tests.test_mirror_capture; node --test tests/js/mirror_capture.test.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Declare exact resources, hashes, encodings and negative outcomes for links, CSS, srcset, redirects and missing assets. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T2 Parse HTML requisites consistently. (AC1) — commit 54bb55a
  - **Files**: `cli/mirror_resources.py`, `web/lib/mirror_resources.js`; focused tests: `tests/test_mirror_capture.py`; `tests/js/mirror_capture.test.js`.
  - **Change**: Handle quoted/unquoted attributes, base URLs, srcset and canonical URL resolution using parity vectors.
  - **Verify**: `python3 -m unittest tests.test_mirror_capture; node --test tests/js/mirror_capture.test.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Handle quoted/unquoted attributes, base URLs, srcset and canonical URL resolution using parity vectors. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T3 Traverse CSS imports and resource URLs. (AC1) — commit d36a91c
  - **Files**: `cli/mirror_resources.py`, `web/lib/mirror_resources.js`; focused tests: `tests/test_mirror_capture.py`; `tests/js/mirror_capture.test.js`.
  - **Change**: Resolve nested imports, escaped URLs and cycles with bounded recursion and MIME-aware parsing.
  - **Verify**: `python3 -m unittest tests.test_mirror_capture; node --test tests/js/mirror_capture.test.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Resolve nested imports, escaped URLs and cycles with bounded recursion and MIME-aware parsing. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T4 Integrate CLI resource discovery. (AC1, AC3) — commit d5e393b
  - **Files**: `cli/aegis_cli.py`; focused tests: `tests/test_mirror_capture.py`; `tests/js/mirror_capture.test.js`.
  - **Change**: Feed discovered resources through existing scope, robots and politeness controls; preserve redirects and response identity.
  - **Verify**: `python3 -m unittest tests.test_mirror_capture; node --test tests/js/mirror_capture.test.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Feed discovered resources through existing scope, robots and politeness controls; preserve redirects and response identity. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T5 Integrate browser resource discovery. (AC1, AC2) — commit 338edc6
  - **Files**: `web/lib/core_crawler.js`; focused tests: `tests/test_mirror_capture.py`; `tests/js/mirror_capture.test.js`.
  - **Change**: Use the same discovery contract; report opaque/CORS failures and never infer successful bytes from an unreadable response.
  - **Verify**: `python3 -m unittest tests.test_mirror_capture; node --test tests/js/mirror_capture.test.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Use the same discovery contract; report opaque/CORS failures and never infer successful bytes from an unreadable response. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T6 Write coverage and omission receipts. (AC2, AC3) — commit 36c6487
  - **Files**: `cli/aegis_cli.py`, `web/lib/core_crawler.js`; focused tests: `tests/test_mirror_capture.py`; `tests/js/mirror_capture.test.js`.
  - **Change**: Reconcile discovered/captured/excluded/failed/unsupported counts and archive hashes; fail completeness on a missing required resource.
  - **Verify**: `python3 -m unittest tests.test_mirror_capture; node --test tests/js/mirror_capture.test.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Reconcile discovered/captured/excluded/failed/unsupported counts and archive hashes; fail completeness on a missing required resource. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T7 Final acceptance and claim reconciliation. (AC1–AC3) — commit c60e47f
  - **Files**: this track’s plan, metadata, review and evidence; documentation explicitly owned by the tasks above.
  - **Change**: Review every requirement against completed slices and each acceptance criterion against retained receipts. Mark unavailable platform runs pending and report scoped limitations.
  - **Verify**: `python3 -m unittest tests.test_mirror_capture; node --test tests/js/mirror_capture.test.js`; `python3 scripts/gate.py test`; full Conductor validation.
  - **Done when**: All required criteria pass, receipt hashes resolve, and no supported claim relies on an unexecuted test. No mandatory human sign-off for machine-verifiable behaviour.

## Integration refinements

T4 also owns `tests/test_cli_review.py`: the existing exact request-list expectation omitted robots.txt because the old CLI lacked policy fetching. The regression now requires the robots request before the same redirect sequence; no assertion about scope or bytes is removed. T5 also owns `web/index.html` to load the new discovery module before the crawler. This is required runtime wiring, not a new UI feature.

T6 also owns `web/index.html` to expose coverage JSON in the existing downloadable diagnostic report. Chrome UI acceptance observed 8/8 readable static responses complete, and a separate redirect fixture explicitly incomplete because manual redirects are opaque. No cross-origin or authenticated browser capability is claimed.

## Review Fixes

- [x] R1 Resolve reproduced discovery and policy edge cases. (AC1, AC2) — commit 495c0be
  - **Files**: the discovery modules, crawler modules, shared discovery vectors and focused capture tests already owned by T2–T6.
  - **Change**: handle descriptor-free srcset commas and duplicate attributes; reject credential URLs; deny robots authentication failures.
  - **Verify**: focused Python and JavaScript capture tests, then full test gate.
  - **Done when**: all regression assertions pass with explicit negative coverage.
  - **Do not**: broaden static capture into rendered automation or alter another track.
