# Optional document adapters

Use the public document extraction API to opt into PDF, DOCX and XLSX parsing
with an explicitly provisioned interpreter:

```python
from portable.document_extract import extract

result = extract(content_bytes, mime, limit=33554432, optional=True,
                 optional_python="/absolute/isolated/venv/bin/python")
```

The public wrapper normalizes MIME and validates input bounds before dispatch.
Without `optional=True`, optional parsers are not used. If `optional_python` is
omitted, the worker uses `sys.executable`; environment variables never select a
runtime. Missing or mismatched parser dependencies return `unsupported`.
The parent process uses only stdlib. No dependencies are installed by extraction
or by the core launchers.

For standalone adapter use, `optional.document_processing.extract(content_bytes,
mime, limit=33554432, optional_python=...)` accepts a normalized MIME directly;
calling that API is itself the opt-in, so it has no `optional` argument.

Explicit provisioning (Python >=3.9; network required only for provisioning):

```sh
python3 -m venv /absolute/isolated/venv
/absolute/isolated/venv/bin/python -m pip install --only-binary=:all: -r optional/document_processing/requirements.lock
/absolute/isolated/venv/bin/python -m pip check
/absolute/isolated/venv/bin/python -m unittest optional.document_processing.test_adapters -v
```

On Windows use `Scripts/python.exe`. The lock pins direct and transitive runtime
dependencies; it is a version lock, not an artifact hash lock. Primary PyPI JSON
metadata checked during implementation: [pypdf](https://pypi.org/pypi/pypdf/6.20.1/json),
[python-docx](https://pypi.org/pypi/python-docx/1.2.0/json),
[openpyxl](https://pypi.org/pypi/openpyxl/3.1.5/json),
[lxml](https://pypi.org/pypi/lxml/6.1.3/json),
[et-xmlfile](https://pypi.org/pypi/et-xmlfile/2.0.0/json), and
[typing_extensions](https://pypi.org/pypi/typing_extensions/4.15.0/json).
Workers check relevant installed versions and reject mismatches or missing packages.

Results always have `status`, `text`, `locators`, `output_hash`, `extractor`,
`reason`, `coverage`. SHA-256 hashes cover UTF-8 output text, including empty failure output.
Locators use zero-based, end-exclusive Unicode character offsets; PDF `page`
and DOCX `paragraph` numbers are one-based; XLSX uses sheet names and A1 cells.
Extractor values identify parser/version. Fixed reasons contain no source text
or exception messages. Failures discard any extracted text. Source bytes are
copied into a private temporary directory and never modified; cleanup follows
success, failure or timeout. Process crashes can leave OS temporary files.

Coverage is a dictionary on every result, including failures. Before assessment
it is `{"scope": "unassessed"}`. PDF scope `text_layer` records `total_pages`
(null when unknown), `visited_pages`, `pages_with_text`, and `missing_text_pages`
(one-based visited page numbers without non-whitespace text). Unvisited pages
are not classified as missing text; compare visited with total. Text can still
be truncated by output limits, so coverage counts do not supersede partial status.
DOCX scope `body_paragraphs` records `total_paragraphs`, `visited_paragraphs`,
`nonempty_paragraphs` and omission counts for tables, drawings, embedded objects,
tracked changes, notes, alternate content, content controls (`w:sdt`), headers
and footers. Header/footer omissions follow document relationship types and are
independent of package part filenames. Body paragraphs inside content controls are omitted and their
presence produces partial status. Counts describe
body elements/part references, not an exhaustive semantic inventory.
XLSX scope `stored_cells` records `total_sheets`, `visited_sheets`, `visited_cells`
and `nonempty_cells`; fabricated empty grid slots do not count as stored cells,
but still consume the traversal limit. Omission counts identify detected chart,
image, external-link, comment and macro package parts; positive counts produce
partial status. Counts are part counts, not rendered object counts. Unknown
Office features may remain outside this inventory. Parent validation checks the
coverage schema, count relationships, and exact scalar locator fields.

Real parser tests skip unless all installed versions match the lock exactly.
Dependency rejection tests run independently of optional parser availability.

Limits: 32 MiB input hard ceiling (caller can lower), 20 second parent wall
timeout, 4 MiB worker JSON, 524288 text characters, 10000 locators, 100000
spreadsheet cell visits. POSIX additionally attempts 15 CPU seconds and 1 GiB
address space. ZIP preflight limits 4096 entries, 64 MiB expanded total,
16 MiB per entry, compression ratio 200; rejects traversal, duplicate names,
symlinks, encryption, unsupported compression, XML DTD/entity declarations and
bad CRC before third-party parsing. No archive entries are extracted to disk.
DTD/entity marker checks inspect every bounded entry after NUL stripping,
regardless of filename, extension or case, because package references can rename
XML parts. Binary entries containing these markers are conservatively rejected
with `unsafe_xml`; this deliberate false-positive tradeoff prevents filename
changes from bypassing XML preflight.

PDF extracts existing text only: empty/scanned pages yield `partial` with
`no_text_layer` or `incomplete_text_layer`; text presence is not visual coverage
proof. Encrypted PDFs yield `encrypted`; no password attempts occur. DOCX covers
body paragraphs; tables, headers/footers and drawings trigger partial coverage.
Notes, embedded objects, tracked changes and complex layout are not reconstructed.
XLSX covers stored cells, including hidden sheets; formulas are returned literally,
never evaluated. Charts, images, macros and external links are not rendered or
executed. Legacy/encrypted OLE Office envelopes fail explicitly as
`encrypted_or_legacy_office` because this adapter does not distinguish them.
Malformed data returns `failed`; missing parsers return `unsupported`.

No OCR, external services, models, or runtime downloads. Subprocess isolation and
`-I` reduce accidental coupling; they are not an OS security sandbox. Run under
an appropriately restricted OS account for hostile inputs. The parent bounds
stdout while draining it; stderr is discarded. Native parser allocations are
subject to platform resource-limit support and the portable wall timeout.
