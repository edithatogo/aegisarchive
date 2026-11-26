# Plan

- [x] T1 Implement structured diagnostic and regression workflow (AC1–AC4).
  - **Files**: `web/lib/core_crawler.js`, `web/lib/self_reflection.js`, `web/lib/native_capture.js`, `web/index.html`, `cli/capture_bridge.py`, `scripts/diagnostic_intake.py`, `tests/test_diagnostic_intake.py`, `tests/test_capture_diagnostics.py`, `tests/js/diagnostic_report.test.js`, `tests/browser/capture.spec.js`, `.agents/skills/capture-diagnostics/SKILL.md`, `docs/DIAGNOSTIC_WORKFLOW.md`, `AGENTS.md`, `.github/workflows/self-improvement.yml`.
  - **Change**: Add JSON diagnostic export and local persistence, failure stage and safe native cause classification, accurate metrics, and deduplicated agent intake with regression workflow.
  - **Verify**: `python3 scripts/gate.py test`; `node --test tests/js/diagnostic_report.test.js`; `AEGIS_BROWSER_CHANNEL=chrome npm run test:capture -- --grep 'HTTP denial'`; `python3 scripts/gate.py leak`.
  - **Done when**: Commands pass and JSON failure evidence is retained with zero captured responses.
  - **Do not**: Commit private reports, credentials, client names, or unrelated signed-in capture files.

- [x] T2 Fix existing workflow pinning failure exposed by PR validation.
  - **Files**: `.github/workflows/windows-portable-noadmin.yml`.
  - **Change**: Reuse repository-established immutable checkout/setup-python pins.
  - **Verify**: Hosted Workflow lint (zizmor) on updated PR head.
  - **Done when**: Workflow lint passes; hosted result pending.
  - **Do not**: Suppress the finding or change runtime behavior.

- [x] T3 Repair bounded checkpoint growth and retain actionable failure diagnostics (AC1–AC4), authorized by the user 2026-11-04.
  - **Owner**: chat 01a1a4fa-a107-7502-8670-7abc4e934613; `/Users/doughnut/Documents/aegisarchive`; branch `codex/capture-stop-diagnostics-20261104`. Sole source writer. Native scope: read-only retained logs; no capture restart. Earlier assignments retained above.
  - **Files**: `cli/usb_archive.py`, `cli/capture_bridge.py`, `cli/debug_journal.py`, `web/lib/native_capture.js`, `web/index.html`, `tests/test_usb_archive.py`, `tests/test_capture_bridge.py`, `tests/js/capture_failure.test.js`, `scripts/diagnostic_intake.py`, `tests/test_diagnostic_intake.py`, `docs/DIAGNOSTIC_WORKFLOW.md`, this track's plan and evidence.
  - **Change**: Reproduce growth across the former checkpoint boundary, align bounded storage and transport limits, preserve precise safe native failure reasons and browser failure context/counts, and verify recovery without native target access.
  - **Verify**: repo-local Python 3.15 unittest selectors for archive/bridge/diagnostics/debug journal; Node failure regressions; baseline gate and launcher help checks.
  - **Done when**: synthetic growth/recovery and diagnostics tests pass, private evidence stays outside source, and limits and native acceptance gaps are documented.
  - **Do not**: change launcher ownership, run a real capture, upload private evidence, or claim workstation acceptance from local checks.

- [x] T4 Prevent debug queue overflow from pausing capture (user authorized 2026-11-05).
  - Owner: chat 01a1a4fa-a107-7502-8670-7abc4e934613, existing repository and branch; sole writer. Scope: web/lib/debug_recorder.js, web/index.html, tests/js/debug_recorder.test.js, docs/DIAGNOSTIC_WORKFLOW.md and track evidence. Native scope: two application files; preserve saved archive and checkpoint.
  - Change: bounded diagnostic loss emits a counted gap warning without invoking pause; genuine storage/delivery failures retain existing handling.
  - Verify: focused debug/resume JS, archive Python, baseline gate; isolated reopen of retained checkpoint and prefix hashes; deployed source byte readback.

- [x] T5 Restore deployment resume settings (user authorized 2026-11-06).
  - Scope: web/index.html and track evidence. Optional private web/resume-settings.json maps archive identity to public capture settings; never commit the deployment file. Resume verifies the full settings hash against the selected archive before applying URL/profile/route/robots settings. Missing mapping retains existing manual flow. Credentials are not saved.
  - Verification: reconstructed existing settings hash exactly matches retained checkpoint; focused resume/failure tests5 PASS; native UI and private settings downloaded byte-identical after upload. Deployment cleanup uses recycling and preserves the selected archive and diagnostic logs.

- [x] T6 Discover declarative lazy media (user authorized 2026-11-06).
  - Scope: web/lib/mirror_resources.js, tests/js/mirror_capture.test.js and track evidence. Add data-src gallery/media references and data-srcset without executing scripts. Keep existing capture scope and pacing. Package only while user capture runs.
  - Verify: regression failed before fix, all6mirror tests pass afterward; full baseline gate PASS; leak and whitespace checks PASS. Private offline retained-byte audit confirms148previously undiscovered image references. Generic script-only rendering remains unresolved. No native application or capture state altered.

- [x] T7 Clarify capture controls and recovery — implementation `eaeafd214a9828f384fc32752b8068564e2483f8` ([PR #89](https://github.com/edithatogo/aegisarchive/pull/89)).
  - Original assignment was chat `01a1a4fa-a107-7502-8670-7abc4e934613`, branch `codex/capture-console-clarity-20261106`, checkout `/Users/doughnut/Documents/aegisarchive`. The deployment scope was package staging during an active capture.
  - The same chat owns closeout on `codex/aegis-t7-closeout-20261126` in `/Users/doughnut/Documents/Codex/2026-11-04/if-y/work/aegis-t7-closeout`. Scope is this plan, metadata and evidence. The native scope is review of the existing OneDrive readback. The next operation is review and merge of the track record.
  - The interface distinguishes a new capture from a saved capture, explains the controls, shows checkpoint progress and resource coverage, and copies a diagnostic summary.
  - PR #89 passed 26 checks and skipped two. Browser acceptance on the merged revision passed on Windows, macOS and Linux on the [second attempt](https://github.com/edithatogo/aegisarchive/actions/runs/45825898154/attempts/2). On the first attempt, Chromium returned `ERR_NO_BUFFER_SPACE` while connecting to the local launcher on Windows.
  - The 26 November 2026 OneDrive readback matched the five deployed files to the merged revision. The checkpoint, partial archive and saved settings retained their versions, and the saved settings hash matched the checkpoint. A successful resume and a new checkpoint on the target Windows workstation remain deployment acceptance checks.
