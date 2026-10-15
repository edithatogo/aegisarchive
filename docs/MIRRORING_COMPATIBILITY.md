# Mirroring compatibility

The current macOS and Windows workflow validates only generation and checking
of a synthetic receipt. It does not qualify end-to-end capture, disconnected
replay, launchers, authentication expiry, or recovery on either platform.
Accordingly, cross-platform mirroring acceptance remains pending. The core
product is intended to preserve HTML navigation and captured assets offline;
dynamic server-side behaviour is not reproduced. Authentication, resume,
packaging, and optional intelligence require their own evidence and do not
expand the mirroring claim.

Run `python scripts/mirroring_acceptance.py --output artifacts/receipt.json` to
create a local, hash-bound receipt and `--check` to validate it.
