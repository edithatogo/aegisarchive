# Retrospective specification: In-Browser Sandboxed WARC Replay Viewer

This pack was reconstructed on 2026-09-05 from the existing objective-only plan; it does not assert a historical review.

## Scope and acceptance

- Build pure client-side WARC reader (`viewer.html`).
- Drag-and-drop .warc container ingestion.
- URL filtering and MIME-type categorization.
- Sandboxed iframe with base-href and link interception.
- Zero server and zero internet offline browsing.


## Authoritative inputs

- AGENTS.md and conductor/workflow.md.
- Current implementation and named successor tracks, where their reviewed security requirements supersede original designs.

## Validation

Run `python3 scripts/gate.py test`, profile checks and CLI smoke checks. Record source coverage and limitations in review.md before archival.

## External boundary

Local review does not authorize publication. Hosted or native checks not run locally must be identified as such.

## Security supersession

The original base-href/link-interception objective is superseded by the reviewed web-console security specification: no live base URL, inert anchors, archived blob requisites and a flagless iframe. This is an intentional security correction, not a claim that live base-href replay is implemented.
