# Plan: Crawl controls, previews and site reports

## Status: COMPLETED (2026-10-16 — local R1–R3/AC1–AC3 acceptance)

## T4 cold-console prerequisite correction — 16 October 2026

Three fresh Chromium contexts reproduced resets during parallel console component
loads. T4 now loads trusted local components sequentially, retaining the single
static generated profile bundle. Controls remain inert until required exports,
module methods and bootstrap completion are verified. Missing files, HTTP-200
empty components and execution failures keep controls inactive with an explicit
startup message. Protected launcher files were not edited.

Chandrasekhar independently approved after real-browser normal/HTTP-200 failure
probes. Coordinator final combined browser run passed 25 tests: 12 maintained
native-capture cases, 9 crawler/report/graph cases and 4 startup cases (including
three cold contexts). This supersedes the earlier cold-console limitation for
this tested macOS/Chromium runtime, not for unexecuted platforms. The full local
gate passed 301 Python (12 optional skips), 18 station and 80 JS tests; final-head
checks are repeated during T7. No runtime dependency or launcher change was added.

Execute tasks in order after metadata dependencies complete. Each functional task first adds its focused failing assertions, then implements and refactors that slice; commit only after its new assertions and existing regression gate pass. Each task may update its own plan, metadata and append-only evidence. No prior implementation tasks were completed when this plan was refined.

- [x] T1 Define ordered rule schema and vectors. (AC1, AC3) — commit 580cdb2 (reconciled from 6bb387c)
  - **Files**: `cli/crawl_rules.py`, `web/lib/crawl_rules.js`; focused tests: `tests/test_crawl_rules.py`; `tests/js/crawl_rules.test.js`.
  - **Change**: Specify discover/traverse/download decisions and precedence by URL, MIME, depth and bytes with safe matcher limits.
  - **Verify**: `python3 -m unittest tests.test_crawl_rules; node --test tests/js/crawl_rules.test.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Specify discover/traverse/download decisions and precedence by URL, MIME, depth and bytes with safe matcher limits. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T2 Implement bounded rule evaluation. (AC1, AC3) — commit 7149730 (reconciled from e0483b0)
  - **Files**: `cli/crawl_rules.py`, `web/lib/crawl_rules.js`; focused tests: `tests/test_crawl_rules.py`; `tests/js/crawl_rules.test.js`.
  - **Change**: Return deterministic decisions with explanation IDs; prevent expensive unbounded patterns.
  - **Verify**: `python3 -m unittest tests.test_crawl_rules; node --test tests/js/crawl_rules.test.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Return deterministic decisions with explanation IDs; prevent expensive unbounded patterns. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T3 Add bounded sitemap and alias discovery. (AC1) — commit b0b92b6 (reconciled from 6e58539)
  - **Files**: `cli/crawl_rules.py`, `web/lib/crawl_rules.js`; focused tests: `tests/test_crawl_rules.py`; `tests/js/crawl_rules.test.js`.
  - **Change**: Parse sitemap indexes without cycles or scope expansion and distinguish explicit alias policy from redirects.
  - **Verify**: `python3 -m unittest tests.test_crawl_rules; node --test tests/js/crawl_rules.test.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Parse sitemap indexes without cycles or scope expansion and distinguish explicit alias policy from redirects. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T4 Integrate rule decisions into both crawlers. (AC1, AC2) — CLI, browser and native bridge enforce URL/header decisions before body reads; aliases, bounded sitemaps, traversal, safe legacy matching and query policy verified. Two independent reviewers approved after fixes; 2 isolated browser fixtures passed.
  - **Files**: `cli/aegis_cli.py`, `web/lib/core_crawler.js`, `web/index.html`, `web/lib/native_capture.js`, `cli/capture_bridge.py`; focused tests: `tests/test_crawl_rules.py`; `tests/test_capture_bridge.py`; `tests/js/crawl_rules.test.js`; `tests/browser/crawl_controls.spec.js`; `tests/browser/crawl_startup.spec.js` (cold-start prerequisite regression).
  - **Change**: Apply download-without-traversal and exclude rules before body retrieval; preserve politeness for discovery.
  - **Verify**: `python3 -m unittest tests.test_crawl_rules; node --test tests/js/crawl_rules.test.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Apply download-without-traversal and exclude rules before body retrieval; preserve politeness for discovery. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T5 Implement preview and reconciled reports. (AC2, AC3) — deterministic no-network previews, fail-closed totals, exact source-JSON identity (including fractional timestamp metadata), report export and stale-load protection verified. Python/browser parity and five real-browser cases pass; independent UI/Python reviews approved.
  - **Files**: `cli/crawl_rules.py`, `web/reports.html`, `web/index.html` (report/preview navigation); focused tests: `tests/test_crawl_rules.py`; `tests/js/crawl_rules.test.js`; `tests/browser/crawl_controls.spec.js`.
  - **Change**: Expose decision previews, errors, missing resources and totals tied to capture receipt identities.
  - **Verify**: `python3 -m unittest tests.test_crawl_rules; node --test tests/js/crawl_rules.test.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Expose decision previews, errors, missing resources and totals tied to capture receipt identities. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T6 Render and export safe link graphs. (AC2, AC3) — deterministic recorded-scope filters, receipt-bound JSON and inert SVG exports verified in browser; 10,000-edge input bound and explicit 500-edge diagram clipping; unknown scope denied classification. Independent security/readability review approved.
  - **Files**: `web/reports.html`; focused tests: `tests/test_crawl_rules.py`; `tests/js/crawl_rules.test.js`; `tests/browser/crawl_controls.spec.js`.
  - **Change**: Filter internal/external edges and export diagrams with escaped labels and bounded graph size.
  - **Verify**: `python3 -m unittest tests.test_crawl_rules; node --test tests/js/crawl_rules.test.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Filter internal/external edges and export diagrams with escaped labels and bounded graph size. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T7 Final acceptance and claim reconciliation. (AC1–AC3) — current-source requirements and receipts reconciled; full gate 301 Python/18 station/80 JS and 25 browser tests passed; independent panel accepted. Historical exceptions preserved and excluded from current proof; local scope only.
  - **Files**: this track’s plan, metadata, review and evidence (including `acceptance.json`); specification status wording only (R/AC unchanged); documentation explicitly owned by the tasks above.
  - **Change**: Review every requirement against completed slices and each acceptance criterion against retained receipts. Mark unavailable platform runs pending and report scoped limitations.
  - **Verify**: `python3 -m unittest tests.test_crawl_rules; node --test tests/js/crawl_rules.test.js`; `python3 scripts/gate.py test`; full Conductor validation.
  - **Done when**: All required criteria pass, receipt hashes resolve, and no supported claim relies on an unexecuted test. No mandatory human sign-off for machine-verifiable behaviour.
