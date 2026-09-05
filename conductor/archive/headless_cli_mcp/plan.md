# Track Plan: Headless CLI & Model Context Protocol (MCP) Server

## Status: COMPLETED (implementation; post-review disposition in review.md)

### Objectives
- [x] Pure Python stdlib CLI runner (`cli/aegis_cli.py`) for CI/cron/Docker.
- [x] Cryptographic WARC/CDX validator (`cli/warc_verify.py`).
- [x] JSON-RPC 2.0 stdio Model Context Protocol server (`mcp/server.py`).
- [x] Expose `list_profiles`, `search_archive`, and `validate_profile` tools.

## Review Fixes

- [x] Rev-1 Validate profiles against the bundled schema instead of checking two fields. — review evidence fb73595
  - **Files**: `mcp/server.py`, `mcp/profile_schema.py`, `tests/test_mcp_profile_review.py`.
  - **Change**: validate the schema vocabulary used by bundled profiles with standard-library code; fail closed if the schema is unavailable.
  - **Verify**: `python3 -m unittest tests.test_mcp_profile_review`; `python3 scripts/gate.py test`.
  - **Done when**: invalid rates, invalid enums, booleans as integers, and incomplete profiles are rejected.
  - **Do not**: add runtime dependencies or claim generic JSON Schema support.

- [x] Rev-2 Correct JSON-RPC error and notification semantics. — review evidence ebed0e2
  - **Files**: `mcp/server.py`, `tests/test_mcp_profile_review.py`.
  - **Change**: validate envelopes/params, preserve IDs on dispatch errors, suppress notification replies and tracebacks, return parse error -32700. This supersedes the historical security-track extraction test's -32603 parse-error expectation; that test preserved a protocol defect.
  - **Verify**: `python3 -m unittest tests.test_mcp_profile_review`; `python3 scripts/gate.py test`.
  - **Done when**: malformed inputs return protocol errors and valid notifications produce no response.
  - **Do not**: change advertised tools or protocol version.
