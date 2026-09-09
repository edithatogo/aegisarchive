# Plan

- [x] T1 Implement structured diagnostic and regression workflow (AC1–AC4).
  - **Files**: `web/lib/core_crawler.js`, `web/lib/self_reflection.js`, `web/lib/native_capture.js`, `web/index.html`, `cli/capture_bridge.py`, `scripts/diagnostic_intake.py`, `tests/test_diagnostic_intake.py`, `tests/test_capture_diagnostics.py`, `tests/js/diagnostic_report.test.js`, `tests/browser/capture.spec.js`, `.agents/skills/capture-diagnostics/SKILL.md`, `docs/DIAGNOSTIC_WORKFLOW.md`, `AGENTS.md`, `.github/workflows/self-improvement.yml`.
  - **Change**: Add JSON diagnostic export and local persistence, failure stage and safe native cause classification, accurate metrics, and deduplicated agent intake with regression workflow.
  - **Verify**: `python3 scripts/gate.py test`; `node --test tests/js/diagnostic_report.test.js`; `AEGIS_BROWSER_CHANNEL=chrome npm run test:capture -- --grep 'HTTP denial'`; `python3 scripts/gate.py leak`.
  - **Done when**: Commands pass and JSON failure evidence is retained with zero captured responses.
  - **Do not**: Commit private reports, credentials, client names, or unrelated signed-in capture files.
