# Document lifecycle T5: implementation and panel review

Date: 16 October 2026. Local baseline: `8b57a4b`; remote baseline: `b23fa3a`.
The owner explicitly selected T5. Work and provisioning remained local, using
synthetic fixtures. No source documents were processed and no push was made.

## Implemented scope

The public `portable.document_extract.extract_ocr` API creates an explicitly
requested OCR derivative, independent of native `extract`. It returns
`kind=ocr`, source and output hashes, engine/model provenance, a separate `ocr:`
derivative identifier, exact Unicode page offsets and engine confidence values.
Native extraction never invokes OCR automatically. Original bytes remain
unchanged; confidence is not a correctness rating or source validation.

Supported inputs are PDF, PNG, JPEG and TIFF. An isolated Python worker renders
PDF pages with PDFium and invokes a separately configured Tesseract executable.
Native engine and model paths must be explicit. Language is English, with
Tesseract 5.5.3, Pillow 12.3.0, pypdfium2 5.14.0 and pypdf 6.20.1 pinned in the
OCR manifest and lock. The current PDFium build identifies as 156.0.8076.0.
The English model hash is
`7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2`.
Engine binary fingerprints are returned as platform provenance. No model or
native executable is installed or downloaded by extraction.

Bounds cover compressed input, rendered pixels, pages, text, TSV output,
process output, CPU, temporary files and wall time. POSIX process-group cleanup
terminates OCR children on parent timeout. Missing or mismatched interpreters,
packages, engines and models are explicit unsupported outcomes; encrypted PDFs,
blank pages, zero-page PDFs, malformed data and incomplete processing have
specific non-success outcomes. Required POSIX resource controls are checked;
other platforms remain unsupported until separately implemented and qualified.

Storage/search policy remains in T6–T8. Consumers must preserve the OCR kind,
confidence and provenance when registering the new derivative. Usage, runtime
requirements and reproducible commands are in
`optional/document_processing/README-OCR.md`.

## Prerequisite and panel findings

The prior T4 review reproduced renamed DOCX headers/footers being omitted while
reported complete. Commit `ef663ef` changes omission detection to document
relationship types, with real renamed-part fixtures. Reviewer Nietzsche
(`01a142a1-cbea-79a0-b2cf-78949538b4f5`) approved that fix and independently approved
the T5 public API/provenance scope. All three API integration cases passed,
including configured real OCR.

Reviewer Chandrasekhar (`01a142a5-1928-72a2-b79e-fe0b8e20d608`) reviewed the OCR
parent/worker boundary and reproduced overlapping spans being accepted from a
worker response. The fix requires ordered pages, exact newline-separated spans,
full output coverage and finite non-null confidence for text-bearing results.
Regression cases reject overlaps, reversed pages, unlocated trailing text and
missing/invalid confidence. The reviewer independently reran all six core OCR
tests and approved the corrected finding; reviewed file hashes remained stable.

## Final verification

- Both lock files provisioned in a separate Python 3.11.6 environment; `pip check`
  reported no broken requirements.
- With explicit engine/model test configuration, the complete lifecycle module
  passed 54 tests with zero skips. Real fixtures cover ALPHA/BETA recognition in
  PNG/JPEG/TIFF and image-only multipage PDFs, exact page locations and source
  hashes, blank and encrypted documents, limits and unavailable tools.
- The core repository gate passed: 197 Python tests, 12 expected skips; 18 station
  tests; 72 JavaScript tests. OCR and optional-parser acceptance skips in the core
  interpreter are backed by the separate fully configured run above.
- Python compilation, whitespace and leak checks passed. Existing task receipts
  retain their versioned artifact hashes; the inherited status-reconciliation
  artifact exception remains recorded rather than rewritten.

An initial pull exposed a stale tracking reflog from the earlier local clone;
its rebase was aborted with all unpublished commits intact. Refreshing only the
remote-tracking cache restored the correct fork point at `b23fa3a`. Local task
commits were preserved, with no remote writes.

Recommendation: accept scoped local T5 completion. The overall track remains
in progress, with T6 next and T7–T9 retaining their recorded pending states.
