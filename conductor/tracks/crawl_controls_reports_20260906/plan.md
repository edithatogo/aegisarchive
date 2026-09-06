# Plan: Crawl controls, previews and site reports

## Status: NEW

Dependencies must complete before shared-file edits. Listed integration files may be added only after inspecting the owning module contract; extend these lists explicitly rather than editing unrelated files. Each task owns this track’s metadata, plan and evidence.

- [ ] T1 Specify fixture contracts and RED tests. (AC1–AC3)
  - **Files**: `cli/crawl_rules.py`, `web/lib/crawl_rules.js`, `web/reports.html`, `tests/test_crawl_rules.py`, `tests/js/crawl_rules.test.js`.
  - **Change**: Define schema, positive/negative fixtures and measurable expectations for all requirements. Provision locked development-only tools where needed; record expected new assertion failures and keep the existing baseline green.
  - **Verify**: `python3 -m unittest tests.test_crawl_rules && node --test tests/js/crawl_rules.test.js`; `python3 scripts/gate.py test`; full Conductor validation. T1 records expected RED failures separately.
  - **Done when**: The fixture contract and explicit baseline failures are recorded.
  - **Do not**: weaken security, fabricate acceptance, or introduce deployment identifiers.

- [ ] T2 Implement requirements and make focused tests pass. (AC1–AC3)
  - **Files**: `cli/crawl_rules.py`, `web/lib/crawl_rules.js`, `web/reports.html`, `tests/test_crawl_rules.py`, `tests/js/crawl_rules.test.js`.
  - **Change**: Implement each R requirement within the owned files; include security, failure, compatibility and resource-limit cases. Unsupported optional capabilities remain explicit.
  - **Verify**: `python3 -m unittest tests.test_crawl_rules && node --test tests/js/crawl_rules.test.js`; `python3 scripts/gate.py test`; full Conductor validation. T1 records expected RED failures separately.
  - **Done when**: All named acceptance criteria pass with automated review evidence; unexecuted platforms remain pending.
  - **Do not**: weaken security, fabricate acceptance, or introduce deployment identifiers.

- [ ] T3 Review and qualify the feature. (AC1–AC3)
  - **Files**: `cli/crawl_rules.py`, `web/lib/crawl_rules.js`, `web/reports.html`, `tests/test_crawl_rules.py`, `tests/js/crawl_rules.test.js`.
  - **Change**: Run focused tests, full baseline and required platform/browser acceptance; record exact revision, tool versions, fixture hashes and result counts. Update capability reporting only for verified features.
  - **Verify**: `python3 -m unittest tests.test_crawl_rules && node --test tests/js/crawl_rules.test.js`; `python3 scripts/gate.py test`; full Conductor validation. T1 records expected RED failures separately.
  - **Done when**: All named acceptance criteria pass with automated review evidence; unexecuted platforms remain pending.
  - **Do not**: weaken security, fabricate acceptance, or introduce deployment identifiers.

