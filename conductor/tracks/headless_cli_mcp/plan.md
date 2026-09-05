# Track Plan: Headless CLI & Model Context Protocol (MCP) Server

## Status: COMPLETED

### Objectives
- Pure Python stdlib CLI runner (`cli/aegis_cli.py`) for CI/cron/Docker.
- Cryptographic WARC/CDX validator (`cli/warc_verify.py`).
- JSON-RPC 2.0 stdio Model Context Protocol server (`mcp/server.py`).
- Expose `list_profiles`, `search_archive`, and `validate_profile` tools.

## Review Fixes

- [ ] Rev-1 Validate profiles against the bundled schema instead of checking two fields.
  - **Files**: `mcp/server.py`, `mcp/profile_schema.py`, `tests/test_mcp_profile_review.py`.
  - **Change**: validate the schema vocabulary used by bundled profiles with standard-library code; fail closed if the schema is unavailable.
  - **Verify**: `python3 -m unittest tests.test_mcp_profile_review`; `python3 scripts/gate.py test`.
  - **Done when**: invalid rates, invalid enums, booleans as integers, and incomplete profiles are rejected.
  - **Do not**: add runtime dependencies or claim generic JSON Schema support.
