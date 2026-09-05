# Track: Politeness Engine & Crawler Correctness (`engine_correctness_20260905`)

- [Specification](./spec.md)
- [Implementation Plan](./plan.md)
- [Metadata](./metadata.json)
- [Evidence](./evidence.jsonl)

Type: fix. Status: completed. Created: 2026-09-05.

Fixes ten reproduced defects in `web/lib/politeness_engine.js`, `web/lib/core_crawler.js` and `profiles/schema.json` (latency baseline warm-up, failure classification, retry budget, abortable waits, origin fetches, schema bounds, robots.txt policy, requisite extraction, canonicalization fidelity) and adds stdlib-only tests under `tests/`. Registration in the track registry is performed by the integrator.

- [Historical evidence](./evidence.legacy.jsonl)

- [Post-implementation Review](./review.md)
