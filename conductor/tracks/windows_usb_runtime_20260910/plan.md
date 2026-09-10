# Plan

- [x] T1 Bundle and validate the Windows USB runtime. *(AC1, AC2, AC3)* — implementation a744c05, verification 093e525
  - **Files**: `portable/windows-python.json`, `scripts/prepare_windows_runtime.py`, `scripts/prepare_windows_runtime.ps1`, `scripts/windows_portable_acceptance.ps1`, `tests/test_windows_runtime.py`, `.github/workflows/windows-portable-noadmin.yml`, `.gitignore`, `START_WINDOWS.cmd`, `START_WINDOWS.ps1`, `docs/WINDOWS_USB.md`, `conductor/tracks.md`, `conductor/backlog.md`, `conductor/lessons.md`, `conductor/reviews/windows_usb_runtime_20260910.md`.
  - **Additional files**: `README.md` (review-requested setup correction).
  - **Change**: Pin official embedded Python; prepare the runtime with checksum validation and an isolated trusted application import path; replace fixed receipt CI with actual launcher and capture regressions; document USB deployment.
  - **Verify**: `python3 -m unittest discover -s tests -p test_windows_runtime.py -v`; `python3 scripts/gate.py test`; Windows portable acceptance on final PR head.
  - **Done when**: Local tests and final-head Windows CI pass, reviewed PR merges, and the verified runtime exists on the USB.
  - **Do not**: Install software on the target machine, upload private diagnostics, or claim corporate-workstation acceptance from CI.
