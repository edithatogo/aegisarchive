# Architecture Decision Records

One file per decision: `docs/adr/NNNN-<slug>.md`, four-digit zero-padded, never renumbered. Headings are fixed: `## Context`, `## Decision`, `## Consequences`, `## Go/no-go checklist`.

Status vocabulary (first bullet under the title):

- `proposed` — written, not yet reviewed.
- `accepted` — approved; a follow-up track may be planned from it.
- `rejected` — decided against; keep the file.
- `superseded by NNNN` — replaced by a later ADR.

Rules:

1. An ADR is research output. It never ships code and never changes documentation claims.
2. Implementation happens in a separate Conductor track whose `spec.md` cites the ADR in "Authoritative inputs".
3. Every browser-library candidate states the zero-install delivery shape: standard Web API, Python standard library, or a single vendored file pinned by SHA-256 in `web/lib/VENDORED.json`.
4. Editing an accepted ADR is not allowed; write a new one that supersedes it.

Index: the files in this directory, sorted by number, are the index.
