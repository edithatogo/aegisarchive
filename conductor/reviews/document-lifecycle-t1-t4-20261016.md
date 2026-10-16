# Document lifecycle T1–T4: implementation and panel review

Date: 16 October 2026. Baseline: `b23fa3a065b85213e4c2e921218ce508ffd50d1c`.
The owner selected this track and authorised T1–T3 followed by T4. Local work
uses a fresh clone of current remote main because the previous volume is absent.
The unassigned backlog row was claimed for that explicit selection. Historical
G1 approval applies only to the earlier reconciliation; this work remains local.

## Implemented scope

- T1 (`4b2a9e5`): unknown metadata stays null; supported derivative states and
  revision references are enforced; existing catalogue rows survive migration.
- T2 (`280c815`): original payloads are stored once per hash, revisions and
  acquisition observations are immutable, and caller-declared URL moves retain
  source identity. Equal bytes at separate URLs share storage without asserting
  that the sources moved. Legacy history and absent bytes are not fabricated;
  actual recapture can recover original bytes and add an observed acquisition.
- T3 (`46f56a8`): native text/HTML extraction has exact Unicode offsets and
  input, output, structural and paragraph bounds. Hidden and active HTML content
  is omitted. Invalid encoding produces partial text with a fixed diagnostic.
- T4: explicit opt-in PDF/DOCX/XLSX parsing runs in a separate interpreter with
  pinned dependencies. Results include parser versions, output hashes, source
  locators and coverage. Scans without text layers remain partial; encrypted,
  malformed and unsupported inputs are explicit. ZIP/XML preflight and process
  limits protect the parser boundary. Provisioning instructions are in
  `optional/document_processing/README.md`.

Review fixes are recorded in `7dde4da` and `6cfb950`. The remaining tasks T5–T9
retain their individual pending/partial states; this is not full-track acceptance.

## Panel

Reviewer Wegener (`01a1428f-22cb-7ad0-a51e-7025c8827f4e`) reviewed T1–T2.
Confirmed and resolved: replacement inserts bypassing immutable records via
primary and alternate unique keys, orphan derivative updates, and insufficient
legacy-migration coverage. Final verdict: approve for scoped T1–T2. Eleven
focused catalogue/history tests passed, including the alternate-key reproducer
with recursive triggers disabled.

Reviewer Popper (`01a1428f-2829-75e2-9730-7891130a31b8`) reviewed T3–T4.
Confirmed and resolved: malformed HTML declarations escaping as exceptions,
hidden subtree extraction, omitted HTML end tags, XML entity guards bypassed by
renamed package parts, and unreported DOCX content-control omissions. Final
verdict: approve for scoped T3–T4, with no remaining actionable findings.
All 16 optional adapter tests passed under exact dependency pins.

Coordinator recommendation: accept the scoped local implementation; continue
later tasks from their recorded states. No hosted review, merge, or target-system
qualification is claimed by the panel.

## Final verification

- `python3 -m unittest tests.test_document_lifecycle`: 27 passed, one expected
  optional-parser class skip in the core interpreter.
- Exact-pin interpreter, same lifecycle module: 37 passed, zero skips.
- `python3 scripts/gate.py test`: 181 Python tests, four skips; 18 station tests;
  72 JavaScript tests; gate passed. Existing negative integrity fixtures emit
  their expected diagnostics and do not represent gate failures.
- Pinned environment `pip check`: no broken requirements.
- Source compilation, whitespace checks, profile schema requirements, CLI help
  smoke checks and the repository leak pattern passed. Canonical track receipts
  are hash-chained and verified.

Validation uses synthetic fixtures on the current Mac. Optional parsers were
not executed on Windows in this round. Dependency absence is reported honestly
by the core suite; real parser acceptance is backed by the separate exact-pin run.
The optional README states coverage limits and resource-limit support. No OCR
execution, organisational data, external publication or new release is included.
