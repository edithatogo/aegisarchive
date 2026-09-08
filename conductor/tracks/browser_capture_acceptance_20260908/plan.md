# Plan

## Status: IN PROGRESS

- [x] T1 Reproduce and repair native UI acquisition with focused security regressions. (AC1, AC3, AC4)
  - Files: cli/launch.py, cli/capture_bridge.py, web/index.html, web/lib/core_crawler.js, web/lib/native_capture.js, tests/test_capture_bridge.py, .gitignore.
  - Verify: python3 -m unittest tests.test_capture_bridge; python3 scripts/gate.py test; real Chrome UI observation.
- [ ] T2 Add and execute portable browser capture/export/offline-navigation acceptance. (AC1–AC5)
  - Files: tests/browser/capture.spec.js, tests/browser/playwright.config.js, package.json, .github/workflows/browser-capture.yml, docs/CAPTURE_ACCEPTANCE.md.
  - Verify: AEGIS_BROWSER_CHANNEL=chrome npm run test:capture locally; npm run test:capture in hosted three-platform matrix.
- [ ] T3 Review, verify all hosted checks, merge, and reconcile completion evidence.
  - Files: track evidence, plan, metadata, registry and backlog.
  - Verify: full gate and exact PR head checks; preserve remaining roadmap tasks.
