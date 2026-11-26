# Implementation plan

Use the repository-local Python 3.15 environment and the existing hosted browser test setup. Each task owns its listed files and the track record. Run the focused verification first and the existing repository baseline before publication. Keep archive and browser checks scoped to synthetic fixtures.

- [ ] T1 Encode the smallest required CDXJ record set.
  - **Files**: `cli/export_mirror.py`, `tests/test_cdxj_export.py`.
  - **Change**: Encode canonical lookup keys, capture timestamps and compact JSON from the validated compressed span metadata. Use deterministic binary order and retain the original target URL.
  - **Verify**: `.venv/bin/python -m unittest tests.test_cdxj_export.CdxjRowsTest`. Expected exit code 0.
  - **Done when**: Check exact reference rows for queries and escaped characters, stable order, and normal and revisit record identity.
  - **Do not**: Approximate compressed offsets, accept an unverified record reference, or change the CDX-11 entry point.

- [ ] T2 Verify every published index reference.
  - **Files**: `cli/export_mirror.py`, `cli/warc_verify.py`, `tests/test_cdxj_export.py`, `docs/PORTABLE_EXPORTS.md`.
  - **Change**: Read the output back and decompress each indexed byte range. Return a failure for missing members, incorrect digest or URL, and duplicate or out-of-range spans that violate the format.
  - **Verify**: `.venv/bin/python -m unittest tests.test_cdxj_export tests.test_warc_gzip_export tests.test_warc_python`. Expected exit code 0.
  - **Done when**: The CLI publishes an independently readable index for a valid archive and preserves existing outputs on a failed validation.
  - **Do not**: Approximate compressed offsets, accept an unverified record reference, or change the CDX-11 entry point.
