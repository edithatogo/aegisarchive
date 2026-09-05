# Retrospective specification: Headless CLI & Model Context Protocol (MCP) Server

This pack was reconstructed on 2026-09-05 from the existing objective-only plan; it does not assert a historical review.

## Scope and acceptance

- Pure Python stdlib CLI runner (`cli/aegis_cli.py`) for CI/cron/Docker.
- Cryptographic WARC/CDX validator (`cli/warc_verify.py`).
- JSON-RPC 2.0 stdio Model Context Protocol server (`mcp/server.py`).
- Expose `list_profiles`, `search_archive`, and `validate_profile` tools.


## Authoritative inputs

- AGENTS.md and conductor/workflow.md.
- Current implementation and named successor tracks, where their reviewed security requirements supersede original designs.

## Validation

Run `python3 scripts/gate.py test`, profile checks and CLI smoke checks. Record source coverage and limitations in review.md before archival.

## External boundary

Local review does not authorize publication. Hosted or native checks not run locally must be identified as such.
