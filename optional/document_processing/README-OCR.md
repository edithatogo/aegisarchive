# Optional local OCR (T5)

Explicit OCR derivative API, independent of native extraction and T4 parsers:

```python
from portable.document_extract import extract_ocr
result = extract_ocr(content, 'image/png', optional_python='/absolute/venv/bin/python',
    tesseract_path='/opt/homebrew/bin/tesseract', tessdata_dir='/opt/homebrew/share/tessdata')
```

The standalone alternate is `optional.document_processing.ocr.extract_ocr` with
the same arguments. The portable API additionally provides a separate `ocr:`
derivative identity, `locator_space='derivative_text'` and
`offset_unit='unicode_codepoint'`.
The parent uses only stdlib and may default to sys.executable. Engine and model
paths must be explicit absolute paths. There is no PATH discovery, shell, network,
model download or automatic fallback from native extraction. Provision separately:

Provision the native executable from the [Tesseract 5.5.3 release](https://github.com/tesseract-ocr/tesseract/releases/tag/5.5.3)
and obtain English data using the [official traineddata documentation](https://tesseract-ocr.github.io/tessdoc/Data-Files.html).
The supplied `eng.traineddata` must match the manifest hash below. The package
does not install the native engine or obtain language data during extraction.

```sh
python3 -m venv /tmp/aegis-ocr-venv
/tmp/aegis-ocr-venv/bin/python -m pip install --only-binary=:all: -r optional/document_processing/requirements-ocr.lock
# For combined lifecycle acceptance, retain all T4 pins as well:
/tmp/aegis-ocr-venv/bin/python -m pip install --only-binary=:all: -r optional/document_processing/requirements.lock -r optional/document_processing/requirements-ocr.lock
python3 -m unittest optional.document_processing.test_ocr
AEGIS_OCR_TEST_PYTHON=/tmp/aegis-ocr-venv/bin/python AEGIS_OCR_TEST_TESSERACT=/opt/homebrew/bin/tesseract AEGIS_OCR_TEST_TESSDATA=/opt/homebrew/share/tessdata /tmp/aegis-ocr-venv/bin/python -m unittest optional.document_processing.test_ocr -v
# Run the same configured interpreter against the complete lifecycle module:
AEGIS_OCR_TEST_PYTHON=/tmp/aegis-ocr-venv/bin/python AEGIS_OCR_TEST_TESSERACT=/opt/homebrew/bin/tesseract AEGIS_OCR_TEST_TESSDATA=/opt/homebrew/share/tessdata /tmp/aegis-ocr-venv/bin/python -m unittest tests.test_document_lifecycle
```

Only explicit provisioning accesses PyPI. Version metadata sources:
https://pypi.org/pypi/pypdfium2/json and https://pypi.org/pypi/Pillow/json
(checked 2026-10-16). Binary wheels avoid source-build downloads. Requirements are
exact version pins, not a cross-platform wheel integrity lock. Existing T4 venvs
and their pins are independent. Python 3.10+ and POSIX resource limits are required;
other platforms report unsupported until separately qualified.

`ocr-runtime.json` pins Tesseract 5.5.3, English traineddata SHA256 and package
versions. English model hash is from installed public local model bytes:
7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2.
No model is vendored. Version/model mismatch is unsupported. Binary SHA256 is
returned as platform provenance, never hardcoded as a portable approval hash.
The observed macOS binary SHA256 was
16020f485da1f534089d82608797d98f71322c67dee772438fb755ad9b4f79b5.

Result fields: status, reason, text, locators, output_hash, extractor, coverage,
kind='ocr', confidence, source_hash, engines. Hashes are SHA256 hex; output_hash
covers UTF-8 text and source_hash covers unchanged input bytes. Invalid or oversized
input returns source_hash=None without hashing rejected content. Page locators use
1-based page numbers and Unicode character start/end offsets. Confidence is the
arithmetic mean of Tesseract TSV word confidences (also retained per page), or
None without words. It measures engine confidence, never correctness or source
truth. TSV words are joined with spaces and pages with newlines; layout, tables,
reading order, handwriting and multilingual accuracy are not guaranteed.

Coverage records total/visited pages, pages with text, missing text pages and
raster pixels. Blank pages yield partial/no_text or pages_without_text. Bounds
yield partial coverage; malformed or timed-out processing yields failed with no
text. Encrypted PDF is explicit, never decrypted. PNG/JPEG/TIFF and PDF only;
image MIME/decoder disagreement fails. PDF raster uses PDFium at scale 2,
16 pages, 16 million pixels/page and 64 million total. TIFF frames are pages.
Input is capped at 32 MiB, text at 1 MiB, TSV per page at 1 MiB, response at 4 MiB.
Worker wall timeout is 60 seconds; each Tesseract invocation gets 15 seconds.
CPU limit is 45 seconds per process, temporary file size 32 MiB, descriptors 64.
Only one raster file is reused. Stdout is drained with a byte cap; stderr is
discarded. Timeout kills process groups; temporary files are removed.
These bounds are containment, not an OS security sandbox. No real documents are
used by tests, which create PNG/JPEG/TIFF and image-only PDF fixtures in memory.
Configured acceptance tests require exact package pins and explicit test-only
environment variables; the stdlib suite always exercises unsupported paths.

No publication, substantive review, clearance or source replacement is implied.
