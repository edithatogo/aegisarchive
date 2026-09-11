# Plan

- [x] T1 Persist launcher captures directly on the USB. *(AC1–AC5)* — implementation a2e5178, Windows CI path repair ed25d59
  - **Files**: `cli/capture_bridge.py`, `cli/usb_archive.py`, `web/lib/native_capture.js`, `web/lib/core_crawler.js`, `web/index.html`, `tests/test_capture_bridge.py`, `tests/test_usb_archive.py`, `tests/js/`, `tests/browser/capture.spec.js`, `.gitignore`, `docs/WINDOWS_USB.md`, `docs/REQUIREMENTS_ACCEPTANCE.md`, `conductor/backlog.md`, `conductor/tracks.md`, `conductor/lessons.md`, `conductor/reviews/usb_capture_storage_20260911.md`.
  - **Change**: Add token-protected bounded USB archive streaming, wire the console to it, preserve honest failure reporting, and record evidence against user requirements.
  - **Additional regression file**: `tests/test_web_console_static.py` (retire the assertion requiring browser-profile checkpoint persistence).
  - **Additional files**: `.github/workflows/browser-capture.yml`, `scripts/windows_portable_acceptance.ps1`, `docs/WINDOWS_ENTERPRISE_ACCEPTANCE.md`, `docs/CAPTURE_ACCEPTANCE.md` (exercise the browser capture and storage checks with the actual bundled Windows runtime and correct stale acceptance claims).
  - **Verify**: `python3 scripts/gate.py test`; `npm run test:capture`; `python3 scripts/track_health.py --strict`; final-head GitHub Actions.
  - **Done when**: Actual synthetic captures save WARC/CDX/receipt under the application with browser storage disabled; regressions and review pass.
  - **Do not**: Install target-machine dependencies, use arbitrary filesystem paths from requests, or claim authenticated corporate capture from CI.
