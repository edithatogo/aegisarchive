# Document lifecycle

The portable catalogue records URL identity, immutable content hashes, MIME type,
acquisition history and revisions in SQLite. `portable.document_extract` provides
bounded built-in extraction for text and HTML; optional PDF, Office and OCR engines
remain provisioned separately and report `unsupported` when absent. Derivatives
retain locators, extractor and output hashes. `portable.document_search.SearchIndex`
provides offline FTS5 search linked to source and revision identifiers.

Original bytes remain authoritative. Extraction is a derivative and can be partial,
failed or unsupported. OCR is an explicit, separately provisioned operation; its
confidence measures the engine output, not source truth. Native extraction does
not fall back to OCR automatically.

## History and comparisons

`Catalogue.compare_revisions(before_revision_id, after_revision_id)` compares
recorded original-byte hashes and source identities. `duplicates(revision_id)`
lists exact matching revisions without merging source identities or inferring a
move. `register(..., moved_from=...)` records a caller-declared URL relationship;
movement and changed bytes are separate facts. Each new acquisition has an
immutable, fingerprint-verified receipt. Read it with `change_receipt(receipt_id)`
or list receipts with `change_receipts(source_id=None)`.

Receipts snapshot the destination's prior head, or the declared origin's head
when the destination is new. They are not an invented chronological sequence:
backdated acquisitions may not advance the URL head. Old acquisitions are not
backfilled with fabricated move declarations.

`SearchIndex.compare(before_derivative_id, after_derivative_id)` returns a bounded
display diff and both derivatives' citations, coverage and warnings. Equal
extracted text does not mean equal original bytes. The diff is not an applicable
patch. Inputs above 32,768 characters or 1,000 lines are not diffed; different
derivative kinds are not mixed. Output above 65,536 characters is explicitly
partial. Comparisons do not extract, OCR, persist changes or rebuild the corpus.

## Handling and quarantine

Search, comparison and safe exports require a public, unflagged, non-withdrawn
source. Nonpublic acquisition or derivative observations also deny access.
Search additionally requires nonblank complete/partial text. Unknown, restricted,
quarantined, revoked and unrecognised labels are not clearance. Partial extraction
remains labelled partial, with its reason and coverage.

Use the catalogue's explicit policy operations with a meaningful reason:

```python
catalogue.set_handling(source_id, 'restricted', reason='Recorded local classification')
catalogue.flag_source(source_id, 'review_required', reason='Source needs review')
```

Restriction changes propagate to existing and new derivatives. Flagged sources
are quarantined. SQLite triggers invalidate active FTS cache entries, including
restrictions written by another catalogue connection. Reopening removes ineligible
legacy cache entries; it does not re-extract or rebuild the corpus. Legacy flags
and nonpublic observations are carried forward conservatively.

`handling_history(source_id)` returns immutable policy-operation receipts. Failed
operations roll back their policy, derivative and cache changes together. Direct
SQL is a trusted administration interface, not the audited policy workflow.
This release has no API for clearing nonpublic labels, flags or a withdrawal.
Re-adding text, reacquiring public bytes or editing retention does not clear them.
No automated process establishes privacy clearance or organisational approval.

## Retention and explicit withdrawal

Retention timestamps are finite nonnegative Unix seconds (UTC); `None` means no
recorded deadline. Omitted fields retain their existing values. A hold is not
silently released by changing a date, and expiry never schedules or performs deletion.

```python
catalogue.set_retention(source_id, retain_until=deadline, legal_hold=True,
                        reason='Recorded retention decision')
# A hold release is a separate, explicit caller decision; it preserves the date.
catalogue.set_retention(source_id, legal_hold=False, reason='Recorded hold release')
```

The caller is responsible for authority to set/release holds and withdraw data;
these local APIs are not an authentication or approval service. No default legal
retention period is inferred. A future deadline or legal hold blocks withdrawal.

`remove_source(source_id, confirm_source_id=source_id, reason=...)` requires exact
source confirmation. It permanently marks that source withdrawn and deletes its
derived text, derivative metadata and active search-cache entries. It blocks later
registration under that source's known URLs and rejects stale derivative writes.
The operation is transactional and records counts in its policy receipt.

This is **logical withdrawal and derivative removal**, not physical original-byte
erasure. Immutable originals, revisions, acquisition/change receipts and source
identity remain available to trusted local administration. Identical bytes shared
by other source identities are retained; those sources keep their own policy.
There is no source-restoration API. Re-extraction may recover text from preserved
originals in an independently authorised recovery process, but does not itself
restore this source's eligibility.

No source files, WARC records, existing export files, backups or external systems
are deleted by these operations. SQLite free pages, journals, backups and storage
media may retain old bytes: secure erasure is not claimed. Physical archival
disposal requires a separately scoped, authorised process; immutable-history
guards are not silently disabled to perform it.

## Safe exports and administration boundary

Use `catalogue.export_original(revision_id)` for an in-memory original-byte export
with its hash, revision, captured URL, MIME and current handling. Use
`index.export(derivative_id)` for an in-memory derivative export with its locators,
source/original references, processing status and extraction/OCR provenance.
Both routes recheck the same current revision policy, deny disallowed sources,
and include `handling='public'` and `flags=[]` on successful snapshots. They do not
write files, publish content or fetch live URLs.

Already returned snapshots cannot be recalled after a later restriction. A caller
must request a fresh export and enforce handling on its own destination, cached
copies and access controls. These guarantees cover the catalogue's lifecycle
exports, not unrelated WARC/ZIP exporters or arbitrary file copies.

Raw `original()`, revision/acquisition/receipt inspection, duplicate metadata and
`catalogue.db` remain trusted local administration interfaces. They are not safe
export routes and do not enforce application-level handling on an administrator
who already has access to the database. Use OS permissions and appropriate local
storage controls; this library is not an OS security sandbox.
