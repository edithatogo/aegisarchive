# Track Plan: Core Engine & Server Preservation Suite

## Status: COMPLETED

### Objectives
- Implement Token-Bucket and Leaky-Bucket rate limiting.
- Implement decorrelated full-jitter exponential back-off.
- Implement real-time EWMA response latency tracking.
- Implement autonomous circuit breaker with nominal, throttled, tripped, and probe states.
- RFC 9110 compliant Retry-After header parsing (delta-seconds & HTTP-dates).
- Parameter scrubbing and crawler trap detection.

## Review Fixes

- [ ] Rev-1 Make output pacing explicit and bound unusually long Retry-After values.
  - **Files**: `web/lib/politeness_engine.js`, `cli/politeness.py`, `tests/js/politeness_engine.test.js`.
  - **Change**: reserve leaky-bucket output slots alongside token admission; keep the existing single-flight crawler; parse finite decimal Retry-After delays.
  - **Verify**: `node --test tests/js/politeness_engine.test.js`; `python3 -m unittest tests.test_politeness`; `python3 scripts/gate.py test`.
  - **Done when**: overlapping browser gate calls have distinct output slots and existing port tests pass.
  - **Do not**: enable concurrent crawling or relax configured delays.
