# USB capture storage

The user requires the application, archives and diagnostics to remain on the USB. The browser console previously used OPFS in the browser profile and download-location exports. Bundled Python alone did not satisfy that requirement.

- AC1: Launcher capture streams WARC bytes into a server-controlled directory under `archive/captures/`; CDX and JSON receipt are saved there before reporting successful storage.
- AC2: Launcher capture does not use OPFS or persistent browser checkpoints and reports storage failure without a successful-save claim.
- AC3: Storage endpoints require the existing station token, accept bounded writes at validated offsets, and never accept arbitrary filesystem paths.
- AC4: Browser and Python regressions verify actual stored bytes and failure behavior; Windows bundled-runtime checks and final-head CI pass before merge.
- AC5: Requirement audit distinguishes implemented behavior from corporate policy, authentication and target acceptance evidence.
