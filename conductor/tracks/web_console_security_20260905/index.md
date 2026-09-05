# Track: Web Console Security & Persistence Claims (`web_console_security_20260905`)

* [Specification](./spec.md)
* [Plan](./plan.md)
* [Metadata](./metadata.json)
* [Evidence Ledger](./evidence.jsonl)

Type: fix. Status: planned. Created: 2026-09-05.

Hardens the browser console and replay viewer: flagless iframe sandbox with an injected CSP, offline replay through `blob:` rewriting instead of a live `<base href>`, output encoding of crawled strings, a generated `web/profiles.bundle.js` as the single profile source, real OPFS streaming through `WarcWriter`, `localStorage` checkpoint/resume of the crawl frontier, and handling of the launcher's `?profile=` parameter. Adds stdlib-only tests. Registration in the track registry is performed by the integrator.
