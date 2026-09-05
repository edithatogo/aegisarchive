# Retrospective specification: ISO 28500 WARC/1.1 Archival & Deduplication Engine

This pack was reconstructed on 2026-09-05 from the existing objective-only plan; it does not assert a historical review.

## Scope and acceptance

- Build standard ISO 28500:2017 WARC/1.1 serializer.
- Generate standard 11-field CDX index files.
- Implement SHA-256 payload digests for content-addressable storage.
- Support ISO 28500 `warc/revisit` records for deduplicated assets.
- Support OPFS and Web Streams API chunked writing.


## Authoritative inputs

- AGENTS.md and conductor/workflow.md.
- Current implementation and named successor tracks, where their reviewed security requirements supersede original designs.

## Validation

Run `python3 scripts/gate.py test`, profile checks and CLI smoke checks. Record source coverage and limitations in review.md before archival.

## External boundary

Local review does not authorize publication. Hosted or native checks not run locally must be identified as such.
