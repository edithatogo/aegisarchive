# Plan: Crawl controls, previews and site reports

## Status: NEW

Execute tasks in order after metadata dependencies complete. Each functional task first adds its focused failing assertions, then implements and refactors that slice; commit only after its new assertions and existing regression gate pass. Each task may update its own plan, metadata and append-only evidence. No prior implementation tasks were completed when this plan was refined.

- [ ] T1 Define ordered rule schema and vectors. (AC1, AC3)
  - **Files**: `cli/crawl_rules.py`, `web/lib/crawl_rules.js`; focused tests: `tests/test_crawl_rules.py`; `tests/js/crawl_rules.test.js`.
  - **Change**: Specify discover/traverse/download decisions and precedence by URL, MIME, depth and bytes with safe matcher limits.
  - **Verify**: `python3 -m unittest tests.test_crawl_rules; node --test tests/js/crawl_rules.test.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Specify discover/traverse/download decisions and precedence by URL, MIME, depth and bytes with safe matcher limits. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T2 Implement bounded rule evaluation. (AC1, AC3)
  - **Files**: `cli/crawl_rules.py`, `web/lib/crawl_rules.js`; focused tests: `tests/test_crawl_rules.py`; `tests/js/crawl_rules.test.js`.
  - **Change**: Return deterministic decisions with explanation IDs; prevent expensive unbounded patterns.
  - **Verify**: `python3 -m unittest tests.test_crawl_rules; node --test tests/js/crawl_rules.test.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Return deterministic decisions with explanation IDs; prevent expensive unbounded patterns. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T3 Add bounded sitemap and alias discovery. (AC1)
  - **Files**: `cli/crawl_rules.py`, `web/lib/crawl_rules.js`; focused tests: `tests/test_crawl_rules.py`; `tests/js/crawl_rules.test.js`.
  - **Change**: Parse sitemap indexes without cycles or scope expansion and distinguish explicit alias policy from redirects.
  - **Verify**: `python3 -m unittest tests.test_crawl_rules; node --test tests/js/crawl_rules.test.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Parse sitemap indexes without cycles or scope expansion and distinguish explicit alias policy from redirects. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T4 Integrate rule decisions into both crawlers. (AC1, AC2)
  - **Files**: `cli/aegis_cli.py`, `web/lib/core_crawler.js`; focused tests: `tests/test_crawl_rules.py`; `tests/js/crawl_rules.test.js`.
  - **Change**: Apply download-without-traversal and exclude rules before body retrieval; preserve politeness for discovery.
  - **Verify**: `python3 -m unittest tests.test_crawl_rules; node --test tests/js/crawl_rules.test.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Apply download-without-traversal and exclude rules before body retrieval; preserve politeness for discovery. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T5 Implement preview and reconciled reports. (AC2, AC3)
  - **Files**: `cli/crawl_rules.py`, `web/reports.html`; focused tests: `tests/test_crawl_rules.py`; `tests/js/crawl_rules.test.js`.
  - **Change**: Expose decision previews, errors, missing resources and totals tied to capture receipt identities.
  - **Verify**: `python3 -m unittest tests.test_crawl_rules; node --test tests/js/crawl_rules.test.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Expose decision previews, errors, missing resources and totals tied to capture receipt identities. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T6 Render and export safe link graphs. (AC2, AC3)
  - **Files**: `web/reports.html`; focused tests: `tests/test_crawl_rules.py`; `tests/js/crawl_rules.test.js`.
  - **Change**: Filter internal/external edges and export diagrams with escaped labels and bounded graph size.
  - **Verify**: `python3 -m unittest tests.test_crawl_rules; node --test tests/js/crawl_rules.test.js`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Filter internal/external edges and export diagrams with escaped labels and bounded graph size. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T7 Final acceptance and claim reconciliation. (AC1–AC3)
  - **Files**: this track’s plan, metadata, review and evidence; documentation explicitly owned by the tasks above.
  - **Change**: Review every requirement against completed slices and each acceptance criterion against retained receipts. Mark unavailable platform runs pending and report scoped limitations.
  - **Verify**: `python3 -m unittest tests.test_crawl_rules; node --test tests/js/crawl_rules.test.js`; `python3 scripts/gate.py test`; full Conductor validation.
  - **Done when**: All required criteria pass, receipt hashes resolve, and no supported claim relies on an unexecuted test. No mandatory human sign-off for machine-verifiable behaviour.
