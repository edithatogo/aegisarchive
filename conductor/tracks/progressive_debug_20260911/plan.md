# Plan

## Status: IN PROGRESS

- [ ] T1 Implement progressive Debug recording. *(AC1–AC4)*
  - **Files**: `cli/debug_journal.py`, `cli/capture_bridge.py`, `web/lib/debug_recorder.js`, `web/lib/native_capture.js`, `web/lib/core_crawler.js`, `web/index.html`, `tests/test_debug_journal.py`, `tests/js/debug_recorder.test.js`, `tests/browser/capture.spec.js`, `docs/DIAGNOSTIC_WORKFLOW.md`, `conductor/backlog.md`, `conductor/tracks.md`, `conductor/lessons.md`, `conductor/reviews/progressive_debug_20260911.md`.
  - **Change**: Add token-protected progressive journal endpoints and a visible Debug control; write structured operational evidence durably and automatically, with bounded retry handling and explicit failure status.
  - **Verify**: `python3 -m unittest discover -s tests -p test_debug_journal.py -v`; `node --test tests/js/debug_recorder.test.js`; `python3 scripts/gate.py test`; `npm run test:capture`; `python3 scripts/track_health.py --strict`; final-head Actions.
  - **Done when**: The actual journal can be read during capture and after reload, errors are visible and private headers/bodies never enter the debug journal.
  - **Do not**: Upload private logs, install runtime dependencies, change target policy, or claim OS termination cannot lose pending events.
