# Plan

- [x] T1 Define and implement optional authentication configuration and redaction. *(AC1-AC4)* — commits `5246739`, `8bcfc70`, `f58c9aa`, `93308b9`
  - **Files**: `cli/auth.py` (new), `cli/aegis_cli.py`, `profiles/schema.json`, `tests/test_auth.py` (new)
  - **Change**: Resolve environment/file references for headers, cookies, and basic auth; enforce expiry and allowed-domain scope; keep browser hand-off explicit and non-automated; never archive authentication headers.
  - **Verify**: `python3 -m unittest tests.test_auth`; `python3 cli/aegis_cli.py --help`.
  - **Done when**: All strategies, expiry, scope, redaction, and unauthenticated behavior are covered.
  - **Do not**: store secrets, automate MFA, add dependencies, or add provider-specific names.
