# Implementation plan

Chat 01a1a4fa-a107-7502-8670-7abc4e934613 owns the export chain on `codex/aegis-archive-exports-20261127` in `/Users/doughnut/Documents/Codex/2026-11-04/if-y/work/aegis-t7-closeout`. The next scope is standalone gzip, followed by CDXJ and WACZ.

Use the repository-local Python 3.15 environment and the existing hosted browser test setup. Each task owns its listed files and the track record. Run the focused verification first and the existing repository baseline before publication. Keep archive and browser checks scoped to synthetic fixtures.

- [x] T1 Compress finalized records as independent gzip members.
  - **Files**: `cli/warc_verify.py`, `cli/export_mirror.py`, `tests/test_warc_gzip_export.py`.
  - **Change**: Reuse the WARC framing and actual record length checks. Use the standard library to stream validated record bodies in bounded chunks. Use one complete gzip member per record, with no trailing data in a referenced range. Emit compressed spans from the writer itself.
  - **Verify**: `.venv/bin/python -m unittest tests.test_warc_gzip_export.GzipMembersTest`. Expected exit code 0.
  - **Done when**: Test independent compressed ranges, complete source-byte round trip, revisit data and bounded handling of a truncated final record.
  - **Do not**: Change the plain-WARC default or the CDX-11 index contract. Write to a partial capture.

- [ ] T2 Expose a safe export command and verify publication.
  - **Files**: `cli/export_mirror.py`, `cli/warc_verify.py`, `tests/test_warc_gzip_export.py`, `docs/PORTABLE_EXPORTS.md`.
  - **Change**: Add a narrow `python -m cli.export_mirror` entry point for explicit gzip export. Reject partial input or an invalid span and publish only after validated readback.
  - **Verify**: `.venv/bin/python -m unittest tests.test_warc_gzip_export tests.test_warc_python`. Expected exit code 0.
  - **Done when**: Check subprocess input validation, stable repeated output, interruption preservation, and exact compressed byte ranges from the final file.
  - **Do not**: Change the plain-WARC default or the CDX-11 index contract. Write to a partial capture.
