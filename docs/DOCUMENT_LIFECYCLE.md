# Document lifecycle

The portable catalogue records URL identity, immutable content hashes, MIME type,
acquisition history and revisions in SQLite. `portable.document_extract` provides
bounded built-in extraction for text and HTML; optional PDF, Office and OCR engines
remain provisioned separately and report `unsupported` when absent. Derivatives
retain locators, extractor and output hashes. `portable.document_search.SearchIndex`
provides offline FTS5 search linked to source and revision identifiers.

Original bytes remain authoritative. Extraction is a derivative and can be partial,
failed or unsupported. Handling labels are carried on derivatives; callers must
apply their own retention and deletion authority before removing source material.
