# Product guidelines

Derived from AGENTS.md and the existing product/workflow contracts during the 2026-09-05 review.

- Keep runtime dependencies at Python standard library and native browser APIs.
- Rate-limit every crawler request; preserve archive identity and payload integrity.
- Treat replay content as untrusted. Preserve sandboxing and prevent live-origin fetches.
- Distinguish implemented code, local validation, hosted qualification and publication.
- Never store secrets or organisation-specific source content in this repository.
