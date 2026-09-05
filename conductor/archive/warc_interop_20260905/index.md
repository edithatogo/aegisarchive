# Track: WARC/CDX Interoperability & Integrity (`warc_interop_20260905`)

- [Specification](./spec.md)
- [Implementation Plan](./plan.md)
- [Metadata](./metadata.json)
- [Evidence](./evidence.jsonl)

Type: fix. Status: completed. Created: 2026-09-05.

Brings the browser and CLI WARC writers, the replay reader, the MCP CDX search and the verifier into ISO 28500 / CDX-11 conformance: decoded-payload header hygiene, the missing CDX `S` (length) field, fail-closed digests, `WARC-Refers-To` on revisits, revisit resolution in the reader, `--cdx` and `.warc.gz` support in `warc_verify.py`, and synthesised request records with `WARC-Concurrent-To`. Adds stdlib-only tests. Registration in the track registry is performed by the integrator.

- [Historical evidence](./evidence.legacy.jsonl)

- [Post-implementation Review](./review.md)

Archived 2026-09-05T08:00:02Z after the recorded post-implementation review passed.
