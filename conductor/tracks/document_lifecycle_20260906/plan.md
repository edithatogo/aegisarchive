# Plan: Generic document lifecycle, extraction and search

## Status: IN PROGRESS

Execute tasks in order after metadata dependencies complete. Each functional task first adds its focused failing assertions, then implements and refactors that slice; commit only after its new assertions and existing regression gate pass. Each task may update its own plan, metadata and append-only evidence. No prior implementation tasks were completed when this plan was refined.

- [x] T1 Define catalogue and derivative schemas. (AC1, AC2) — nullable source metadata, explicit processing states, revision references and legacy migration verified by 3 lifecycle tests; task_verified receipt records baseline counts.
  - **Files**: `portable/document_catalogue.py`; focused tests: `tests/test_document_lifecycle.py`.
  - **Change**: Specify source/revision identity, unknown metadata, MIME, hashes, locators, handling flags and explicit processing states.
  - **Verify**: `python3 -m unittest tests.test_document_lifecycle`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Specify source/revision identity, unknown metadata, MIME, hashes, locators, handling flags and explicit processing states. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T2 Implement immutable registration and history. (AC2) — canonical payload storage, append-only acquisitions and caller-declared URL moves verified; identical bytes alone do not merge source identities.
  - **Files**: `portable/document_catalogue.py`; focused tests: `tests/test_document_lifecycle.py`.
  - **Change**: Reconcile moved URLs, identical bytes and changed revisions; preserve acquisition history and originals.
  - **Verify**: `python3 -m unittest tests.test_document_lifecycle`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Reconcile moved URLs, identical bytes and changed revisions; preserve acquisition history and originals. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T3 Add bounded native text extraction. (AC1, AC3) — visible HTML, exact Unicode locators, explicit partial/unsupported outcomes and resource limits verified by 15 lifecycle cases plus the repository gate.
  - **Files**: `portable/document_extract.py`; focused tests: `tests/test_document_lifecycle.py`.
  - **Change**: Extract supported built-in text formats with stable locators and content-free failure diagnostics.
  - **Verify**: `python3 -m unittest tests.test_document_lifecycle`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Extract supported built-in text formats with stable locators and content-free failure diagnostics. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T4 Add optional PDF and Office adapters. (AC1, AC3) — opt-in pinned PDF/DOCX/XLSX workers verified using real synthetic fixtures, explicit coverage, resource bounds and failure states; 37 pinned-environment lifecycle tests passed with zero skips; panel approved.
  - **Files**: `portable/document_extract.py`, `optional/document_processing/`; focused tests: `tests/test_document_lifecycle.py`.
  - **Change**: Pin isolated parsers; record versions and text-layer coverage, reject encrypted or malformed inputs explicitly.
  - **Verify**: `python3 -m unittest tests.test_document_lifecycle`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Pin isolated parsers; record versions and text-layer coverage, reject encrypted or malformed inputs explicitly. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T5 Add optional OCR derivative processing. (AC1, AC3) — separate local OCR API and provenance-based derivative identity; pinned English engine/model, page confidence, strict locator coverage, unavailable states and resource bounds verified; configured lifecycle 54 tests passed with zero skips; panel findings resolved.
  - **Files**: `portable/document_extract.py`, `optional/document_processing/`; focused tests: `tests/test_document_lifecycle.py`.
  - **Change**: Keep OCR output distinct from original text; retain page locators/confidence and unsupported-engine outcomes.
  - **Verify**: `python3 -m unittest tests.test_document_lifecycle`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Keep OCR output distinct from original text; retain page locators/confidence and unsupported-engine outcomes. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T6 Implement revision-aware offline search. (AC1, AC2) — revision-bound idempotent FTS, source/revision/kind filters, original references, extraction provenance and fail-closed eligibility verified; 69 configured lifecycle tests passed with zero skips; two-agent panel approved after fixes.
  - **Files**: `portable/document_search.py`; focused tests: `tests/test_document_lifecycle.py`.
  - **Change**: Reuse generic search contracts after review; index only eligible derivatives with original/version links.
  - **Verify**: `python3 -m unittest tests.test_document_lifecycle`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Reuse generic search contracts after review; index only eligible derivatives with original/version links. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T7 Implement revision changes and duplicates. (AC2) — original-byte comparisons, exact duplicate references, atomic immutable acquisition receipts and bounded policy-checked text comparisons verified; 85 configured lifecycle tests passed with zero skips; two-agent panel approved.
  - **Files**: `portable/document_catalogue.py`, `portable/document_search.py`; focused tests: `tests/test_document_lifecycle.py`.
  - **Change**: Compare revisions without confusing movement with change; emit immutable change receipts.
  - **Verify**: `python3 -m unittest tests.test_document_lifecycle`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Compare revisions without confusing movement with change; emit immutable change receipts. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [x] T8 Enforce handling and retention boundaries. (AC3) — restrictive handling/quarantine, cache invalidation, safe lifecycle exports, retention/hold guards and confirmed logical withdrawal verified; 101 configured lifecycle tests passed with zero skips; two-agent panel approved. Immutable originals/history retained; no secure-erasure claim.
  - **Files**: `portable/document_catalogue.py`, `portable/document_search.py`, `docs/DOCUMENT_LIFECYCLE.md`; focused tests: `tests/test_document_lifecycle.py`.
  - **Change**: Propagate restrictions to search/cache/export, quarantine flags and expose explicit deletion semantics without automatic privacy clearance.
  - **Verify**: `python3 -m unittest tests.test_document_lifecycle`. Run the test subset added for this slice first; then the full focused module once provisioned. A fixture/schema-only task records its expected RED results separately and must not claim feature completion.
  - **Done when**: Propagate restrictions to search/cache/export, quarantine flags and expose explicit deletion semantics without automatic privacy clearance. Relevant assertions demonstrate the stated outcome and no regression is introduced.
  - **Checkpoint**: Automated review of this slice, then `python3 scripts/gate.py test`; record exact test counts, revision and any platform results.
  - **Do not**: edit files owned by unfinished dependencies, weaken source isolation, use production credentials in fixtures, or substitute mocked acceptance for named platform/browser execution.

- [ ] T9 Final acceptance and claim reconciliation. (AC1–AC3)
  - **Files**: this track’s plan, metadata, review and evidence; documentation explicitly owned by the tasks above.
  - **Change**: Review every requirement against completed slices and each acceptance criterion against retained receipts. Mark unavailable platform runs pending and report scoped limitations.
  - **Verify**: `python3 -m unittest tests.test_document_lifecycle`; `python3 scripts/gate.py test`; full Conductor validation.
  - **Done when**: All required criteria pass, receipt hashes resolve, and no supported claim relies on an unexecuted test. No mandatory human sign-off for machine-verifiable behaviour.

## T6 contract review and acceptance — 16 October 2026

Baseline `ac15294`, task claim `8c65226`. The owner explicitly selected T6;
other incomplete tracks were not taken over. Ownership checks found this track
alone owns the two implementation/test files. No runtime dependencies were added.

The existing FTS5 component is retained rather than importing the optional hybrid
memory store, whose document identity/schema lacks catalogue revisions and handling
controls. `add(result, source_id, revision_id, handling=None, kind=None)` checks the
source/revision association and hashes, keeps JSON locators and extraction metadata,
and assigns an identity scoped to revision plus extraction provenance. Repeated
adds replace only that derivative's cache entry, never another source's history.
Omitted handling inherits the source; omitted kind honours OCR metadata. Existing
positional source/limit search calls remain supported. New revision/kind filters
are keyword-only. Query length is bounded and limit must be an integer from 1–100.

Results include status, reason, coverage, locators, extractor/output hashes and
OCR confidence/engine/model provenance. An upstream OCR identity is exposed as
`extraction_derivative_id`, separately from the revision-bound search ID. The
`original` reference carries revision, captured URL, content hash and availability;
resolve it locally with `catalogue.original(hit['original']['revision_id'])`.
No live URL is fetched. Partial results remain explicitly partial.

Eligibility is intentionally conservative: only public, unflagged, nonblank
complete/partial text is indexed and returned. Source, acquisition and any
derivative restriction on the same revision deny retrieval, including legacy
restrictions. New extraction identities do not clear them. Query-time checks hide
stale cached hits without rebuilding the corpus. T8 retains explicit handling
reclassification, cache/export propagation, retention and deletion ownership.
Legacy rows remain unchanged and are not trusted for search until re-added from
validated extraction results; reopening performs no corpus rebuild. Corrupt
retrieved metadata fails with a content-free error rather than returning citations.

Regression tests first reproduced duplicate FTS rows, colliding output identities,
unlinked source/revision pairs, restricted and failed-output retrieval, lost OCR
metadata and unbounded inputs. Follow-up RED/GREEN checks cover original OCR identity,
legacy restriction bypass and malformed stored metadata. Persistent database tests
verify reopen, legacy preservation and explicit revalidation; configured real OCR
flows through search back to unchanged captured bytes.

Panel Nietzsche (`01a142a1-cbea-79a0-b2cf-78949538b4f5`) approved revision identity,
persistence and OCR integration after running 18 targeted/integration tests.
Panel Chandrasekhar (`01a142a5-1928-72a2-b79e-fe0b8e20d608`) initially held for the
legacy restriction bypass and malformed-metadata crash. Both received regression
tests and fixes; the reviewer approved after 16 tests and independent probes of
both legacy identity forms and query-time denial. Neither reviewer edited files.

Final checks: 15 new revision-search tests passed; the mandated stdlib lifecycle
command passed 58 tests with 9 expected optional-runtime skips; configured lifecycle
acceptance passed 69 tests with zero skips. Repository gate passed 212 Python tests
with 12 expected skips, 18 station tests and 72 JavaScript tests. Compilation,
CLI help smoke, profile checks, whitespace and leak gates passed. These are local
synthetic checks, not new hosted/platform qualification. No user documents were
processed, no source publication occurred, and no push gate was granted.

## T7 contract review and acceptance — 16 October 2026

Baseline `1d1b7d8`, task claim `0431644`. The owner selected T7 explicitly;
only this track's catalogue/search/test files and Conductor records were changed.
No dependencies, network capture, automatic extraction or corpus rebuild were added.

`Catalogue.compare_revisions(before_revision_id, after_revision_id)` compares
recorded original-byte fingerprints, source identities and sizes. Cross-source
matches are exact duplicates, not inferred moves or content changes within one
source. `Catalogue.duplicates(revision_id)` returns matching revision references,
excluding the queried revision, without merging identities. These are trusted
local catalogue metadata APIs, like `acquisitions`, not permission-filtered
export/search interfaces. Semantic/fuzzy equivalence is not claimed.

New acquisitions atomically emit a SHA-256-fingerprinted `change_receipts` row;
`register` adds `receipt_id` without removing existing result fields. Read receipts
with `change_receipt(receipt_id)` or `change_receipts(source_id=None)`. Each records
the acquisition, explicit move declaration, before/after revision/hash references,
baseline URL, byte-change flag, duplicate-storage observation, and whether the
destination URL head advanced. The baseline is the existing destination head,
otherwise the declared origin head. It is explicitly a pre-registration snapshot,
not an invented chronological predecessor; backdated acquisitions retain that
distinction. Initial observations have no invented previous revision/change.
Reversions reuse existing content/revisions but retain a new acquisition receipt.

Registration reserves the write transaction before baseline reads. A real
second-connection regression verifies that another writer cannot overtake them.
Original, revision, acquisition and receipt writes roll back together on failure.
Triggers reject receipt updates, deletion and replacement through either the
receipt primary key or unique acquisition key. Reads verify payload fingerprints.
Existing acquisitions receive no fabricated retrospective move receipts on upgrade.

`SearchIndex.compare(before_derivative_id, after_derivative_id)` applies current
T6 eligibility and metadata-integrity checks before returning either side. It
retains citations, original references, OCR provenance and partial extraction
warnings. Original-byte change and derivative-text equality are separate fields.
The unified display diff is not an applicable patch. Newline-only changes remain
visible, and differing terminal-linefeed states are annotated. Inputs above
32,768 characters or 1,000 lines are not diffed; different derivative kinds are
not mixed. Diff output is capped at 65,536 characters with explicit partial status.
Comparison performs no persistent writes, automatic OCR or extraction.

Test-first checks covered moves with/without byte changes, repeated declarations,
duplicates, unrelated sources, reversions, backdated observations, immutable and
atomic receipts, reopen, old-schema migration, malformed payloads, text-diff
bounds, newline-only changes and query-time restrictions. One intermediate
newline-marker regression failed and was fixed without changing its assertion;
all final verification commands passed.

Panel Nietzsche (`01a142a1-cbea-79a0-b2cf-78949538b4f5`) identified the repeated
move declaration baseline defect; a RED/GREEN regression and destination-head
precedence resolved it. The reviewer approved after all 16 T7 tests passed.
Panel Chandrasekhar (`01a142a5-1928-72a2-b79e-fe0b8e20d608`) independently approved
after 31 T7/T6 tests and probes of newline/output-limit behavior. Both rechecked
the final locking/baseline changes; neither edited repository files.

Final checks: mandated stdlib lifecycle command passed 74 tests with 9 expected
optional-runtime skips; configured lifecycle passed 85 tests with zero skips.
Repository gate passed 228 Python tests with 12 expected skips, 18 station tests
and 72 JavaScript tests. Compilation, CLI help, profiles, Conductor links,
whitespace and leak checks passed. Evidence remains local and synthetic; no user
documents were processed, no hosted platform acceptance is inferred and no push
was authorized. T8 handling/retention and T9 final acceptance remain pending.

## T8 contract review and acceptance — 16 October 2026

Baseline `65dbe9c`, task claim `eeb9484`. Implementation touched only the task's
catalogue, search, focused tests, lifecycle documentation and Conductor records.
All processing and deletion fixtures were synthetic; no real source documents
were deleted. No runtime dependency, network processing or publication was added.

Shared revision eligibility now governs derivative retrieval/comparison/export
and original lifecycle export. Public, unflagged, non-withdrawn sources must also
have no nonpublic acquisition/derivative observation. Source handling changes
propagate to derivatives; flagging quarantines content. Triggers invalidate active
FTS cache rows on source/flag/acquisition/derivative/withdrawal restrictions,
including other catalogue connections and direct metadata changes. Reopening
conservatively quarantines legacy flags, inherits prior restrictions and removes
ineligible cached text without extracting or rebuilding the corpus.

`set_handling(source_id, handling, reason=...)` restricts handling but cannot clear
a nonpublic source to public. `flag_source(source_id, flag, reason=...)` adds flags
and quarantines content. There is no automatic privacy clearance or API for
clearing flags/nonpublic evidence. Immutable `handling_history(source_id)` records
explicit policy operations; history and acquisition observations are not rewritten.

`set_retention(source_id, retain_until=..., legal_hold=..., reason=...)` records
caller decisions. Omitted fields are preserved, timestamps are validated and
expiry never deletes data. Explicit hold release does not clear the deadline.
Future retention and legal holds block `remove_source`; exact source confirmation
and a reason are required. Changes, active derived-store deletion and the audit
receipt are atomic; audit failure rolls the operation back.

`remove_source(source_id, confirm_source_id=source_id, reason=...)` performs logical
withdrawal and removes that source's derivative text, extraction metadata and active
cache rows. It preserves immutable originals, revision/acquisition/change records
and independently classified duplicate sources sharing the same payload. A permanent
tombstone blocks recapture under known source URLs; database guards reject stale
derivative insertions or reassignment after withdrawal. No restoration API exists.
This task does not delete WARC/source/export files, backups or original archive
bytes, and does not claim forensic/secure erasure of SQLite/media remnants.

`Catalogue.export_original(revision_id)` and `SearchIndex.export(derivative_id)`
return fresh, handling-labelled in-memory snapshots with lineage and hashes;
disallowed sources are denied. No files are written. Returned snapshots cannot be
recalled after subsequent policy changes; downstream consumers must enforce their
own destination access and retention. Raw catalogue/database administration remains
trusted local access, not an application permission sandbox or safe export route.
The maintained lifecycle documentation explicitly describes these boundaries.

Sixteen new test-first cases cover propagation, quarantine, direct-SQL cache
invalidation, acquisition history, export lineage/denial, no automatic clearance,
confirmation, retention/hold guards and omitted-field preservation, shared payloads,
withdrawal/audit rollback, stale writes and conservative migration. Initial RED
checks exposed missing controls; follow-up RED/GREEN tests hardened hold preservation,
withdrawn-source writes and legacy quarantine before final verification.

Panel Nietzsche (`01a142a1-cbea-79a0-b2cf-78949538b4f5`) approved code and docs after
16 T8 tests and an independent stale-writer probe. Panel Chandrasekhar
(`01a142a5-1928-72a2-b79e-fe0b8e20d608`) approved after all 47 handling/T7/T6 tests,
with no material findings. Both confirmed the logical-withdrawal, safe-export and
raw-administration boundaries. Neither reviewer edited files.

Final verification: mandated stdlib lifecycle command passed 90 tests with 9
expected optional-runtime skips; configured lifecycle passed 101 tests with zero
skips. Repository gate passed 244 Python tests with 12 expected skips, 18 station
tests and 72 JavaScript tests. Compilation, profile checks, CLI help, Conductor
links, whitespace and leak gates passed. These are local synthetic checks, not
hosted/platform qualification. No push was authorised. T9 remains pending.

## T8 post-review concurrency correction — 16 October 2026

The subsequent T8 review reproduced a stale-label race: another connection could
restrict a source after `SearchIndex.add` read its handling but before inserting
a derivative. Search and safe exports still denied the text, but the derivative's
stored public label violated inheritance. This supersedes the prior no-outstanding-
findings conclusion for that code revision; historical receipts remain unchanged.

The public add operation now reserves the writer before all policy reads, and
delegates validation/storage under that reservation. A real two-connection
regression failed for both new INSERT and retry UPDATE before the correction and
passes afterward. A later restriction propagates to the stored derivative. No
retrieval/clearance rule was weakened, and no corpus rebuild was added.

Reviewer Nietzsche independently approved the correction after 32 focused tests
and 102 configured lifecycle tests, with zero skips. Coordinator verification:
mandated stdlib lifecycle 91 tests with 9 optional skips; configured lifecycle
102 tests with zero skips; repository gate 245 Python tests with 12 expected
skips, 18 station tests and 72 JavaScript tests. Compilation, whitespace and leak
checks passed. T9 final reconciliation uses this corrected code, not the older
T8 code receipt alone.
