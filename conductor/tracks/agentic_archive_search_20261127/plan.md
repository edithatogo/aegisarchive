# Implementation plan

For T1, chat 01a1a4fa-a107-7502-8670-7abc4e934613 owned `codex/aegis-agentic-search-20261127` in `/Users/doughnut/Documents/Codex/2026-11-04/if-y/work/aegis-t7-closeout`. Scope was T1 source and docs, this track, and its protected repository publication.

The same chat owns T2 and T3 on `codex/aegis-warc-search-20261127` in that worktree. Scope is local WARC intake, the fixed-corpus comparison, and protected publication of those changes.

- [x] T1 Search an indexed saved catalogue with one opt-in follow-up. (AC1, AC2, AC3)
  - **Files**: `portable/document_catalogue.py`, `portable/document_search.py`, `tests/test_agentic_search.py`, `docs/DOCUMENT_LIFECYCLE.md`, `docs/adr/README.md`.
  - **Change**: Open the saved catalogue in SQLite read-only mode. Expose ordinary keyword search by default and an explicit local model option that can supply one alternate keyword query after an empty first lookup. Reuse the documented search eligibility and citation logic.
  - **Verify**: `.venv/bin/python -m unittest tests.test_agentic_search tests.test_document_lifecycle.RevisionSearchTests` and `.venv/bin/python -m portable.document_search --help`. Run the repository baseline and leak gate.
  - **Done when**: Ordinary search returns the same hits as before with no model calls. Agentic search can recover a missed result with its exact revision reference, honours filters, and gives an explicit outcome on model failure. The saved catalogue hash matches across CLI calls.
  - **Do not**: Read live sources, reindex the catalogue, send archive text to the model, or add a third-party dependency.

- [x] T2 Index eligible text from an explicitly selected saved WARC. (AC4)
  - **Files**: `cli/warc_verify.py` for shared framing, `portable/archive_search_intake.py`, `tests/test_archive_search_intake.py`, `docs/DOCUMENT_LIFECYCLE.md`.
  - **Change**: Reuse verified WARC record framing and the existing text extraction and catalogue APIs. Keep the capture URL, time, original hash and record reference. Require an explicit handling designation and report skipped records.
  - **Verify**: `.venv/bin/python -m unittest tests.test_archive_search_intake tests.test_warc_python tests.test_warc_review tests.test_agentic_search`. Search a newly indexed HTML fixture by source revision. Compare WARC hash before and after intake.
  - **Done when**: Plain text and HTML from a saved WARC are searchable, a restricted or unknown record is ineligible, duplicates preserve their recorded identity, and a corrupt record is rejected.
  - **Do not**: Fetch missing resources or assign public handling automatically.

- [ ] T3 Measure incremental retrieval value on a fixed fixture corpus. (AC4)
  - **Files**: `tests/benchmark_agentic_search.py`, `docs/DOCUMENT_LIFECYCLE.md`, and `benchmark.json` in this track.
  - **Change**: Record expected revisions for exact, paraphrased and out-of-scope questions. Run both modes on the same prepared index. Record relevant results, incorrect citations, model calls and elapsed time.
  - **Verify**: `.venv/bin/python -m unittest tests.test_agentic_search` and `.venv/bin/python -m tests.benchmark_agentic_search /path/to/manifest.json` using the qualified offline Scout model.
  - **Done when**: A repeatable comparison quantifies additional useful hits and lookup time. Use the results to decide whether vector or graph lookups belong in the agentic mode.
  - **Do not**: Change the default mode or infer quality from the number of model calls.
