# Track: Headless CLI Parity with the Browser Engine (`cli_parity_20260905`)

* [Specification](./spec.md)
* [Plan](./plan.md)
* [Metadata](./metadata.json)
* [Evidence Ledger](./evidence.jsonl)

Type: fix. Status: completed. Created: 2026-09-05.

Brings `cli/aegis_cli.py` to parity with the browser crawler: case-insensitive response headers, browser-identical URL canonicalisation that keeps query strings, an O(1) frontier, a stdlib-only port of the politeness engine (`cli/politeness.py`: token bucket, decorrelated full jitter, EWMA with warm-up, circuit breaker, capped Retry-After, interruptible waits) wired in with a retry budget, and `unittest` coverage with an ephemeral loopback `http.server` fixture. Registration in the track registry is performed by the integrator.
