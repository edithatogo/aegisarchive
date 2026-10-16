# Document lifecycle — T9 final acceptance

Date: 16 October 2026. Corrected implementation: `6275f97`.

## Scope and decision

Local synthetic functional acceptance covers R1–R4 and AC1–AC3. This is not
publication, real-corpus processing, or a new Windows/Linux qualification.
The machine-readable [acceptance manifest](../tracks/document_lifecycle_20260906/acceptance.json)
records the requirement matrix, executed checks and a version-resolved evidence
snapshot. Final panel disposition is recorded in the track plan and ledger.

| Requirement | Completed tasks | Acceptance proof |
|---|---|---|
| R1: catalogue and immutable source history | T1–T2 | CatalogueSchemaTests and RegistrationHistoryTests; immutable originals, distinct source identities, acquisitions and explicit moves |
| R2: bounded, provenance-preserving extraction | T3–T5 | Native, optional parser and OCR fixture suites; locators, coverage, original-byte preservation and explicit unavailable/failure states |
| R3: revision-aware retrieval and comparison | T6–T7 | RevisionSearchTests, RevisionChangeTests and DerivativeComparisonTests; citations, duplicate identities and immutable receipts |
| R4: handling and retention | T8 | HandlingRetentionTests; restriction inheritance, quarantine, cache/export denial, retention/holds and logical withdrawal |

AC1 is supported by text-layer/scan fixtures, exact locators and unchanged original
round trips; AC2 by equal-byte, changed/reverted revision, move and searchable
history cases; AC3 by bounded/adversarial inputs and handling/export controls.
The T8 review race was reproduced before correction. The corrected add operation
reserves the SQLite writer before policy reads; the real two-connection regression
covers both INSERT and retry UPDATE. A later restriction propagates correctly.

## Executed verification

- Standard-library lifecycle suite: 91 tests, 9 expected optional-runtime skips.
- Configured parser/OCR lifecycle suite: 102 tests, zero skips.
- Repository test gate: 245 Python tests, 12 expected skips; 18 station tests;
  72 JavaScript tests. Passed.
- Strict Conductor health: zero findings across 35 tracks before final status
  reconciliation; rerun required after completion edits.
- Touched Python compilation, whitespace and leak gates passed.
- Nietzsche independently approved the concurrency correction after 32 focused
  tests and all 102 configured lifecycle tests, zero skips.

Reproduce the standard checks from the repository root:

```sh
python3 -m unittest tests.test_document_lifecycle
python3 scripts/gate.py test
python3 scripts/track_health.py --strict
python3 scripts/gate.py leak
git diff --check
```

Configured acceptance used the pinned environment provisioned under
`/tmp/aegis-ocr-t3weZK/venv`, with `AEGIS_OCR_TEST_PYTHON` pointing to its Python,
`AEGIS_OCR_TEST_TESSERACT=/opt/homebrew/bin/tesseract` and
`AEGIS_OCR_TEST_TESSDATA=/opt/homebrew/share/tessdata`. Reprovisioning instructions
and exact dependency pins are maintained in `optional/document_processing/`.

## Evidence reconciliation

The manifest freezes a 38-event ledger prefix with 77 artifact references:
76 resolve to retained Git bytes; one inherited status-only reference does not.
Every functional artifact reference resolves. Early T1–T3 individual receipts
lack attachments, but the later collective T1–T4 receipt binds retained proof.

Historical event `f82be030-3ffa-40a5-a746-24a359086a37` references an unavailable
fingerprint of `conductor/status-reconciliation-20261015.md`. Existing exception
`ce2edb67-c8a1-40cd-bc5c-133e3c491c70` and the T9 exception preserve and quarantine
that reference. It is not accepted as functional proof. No historical receipt was
rewritten; this acceptance does not certify an exception-free historical ledger.

The snapshot is a prefix, not a promise that the ledger stops there. To verify it,
recompute each canonical event hash excluding `entry_sha256`, check predecessor
links, compare the snapshot prefix count/tip, then hash `git show
<resolved_commit>:<path>` for each version-verified reference. The only permitted
unresolved snapshot reference is the quarantined event above. Later acceptance
receipts must independently resolve to their committed artifacts.

## Retained boundaries and documentation

OCR qualification is pinned English/POSIX only; Windows OCR is unsupported.
Other platform/native acceptance remains in its existing track. Optional parser
format limits and unavailable-engine states remain explicit.

Withdrawal deletes derivative text/metadata and active retrieval rows, not
immutable originals, independent shared payloads, backups or forensic remnants.
Raw catalogue/database administration is trusted local access, not a permission
sandbox. Safe lifecycle exports enforce current eligibility and return labelled
snapshots; previously returned bytes cannot be recalled.

Maintained lifecycle documentation includes these boundaries. Product definition,
technology stack and product guidelines require no strategic changes. No push,
publication, real source deletion or organisational approval is claimed.
