# Retrospective specification: Core Engine & Server Preservation Suite

This pack was reconstructed on 2026-09-05 from the existing objective-only plan; it does not assert a historical review.

## Scope and acceptance

- Implement Token-Bucket and Leaky-Bucket rate limiting.
- Implement decorrelated full-jitter exponential back-off.
- Implement real-time EWMA response latency tracking.
- Implement autonomous circuit breaker with nominal, throttled, tripped, and probe states.
- RFC 9110 compliant Retry-After header parsing (delta-seconds & HTTP-dates).
- Parameter scrubbing and crawler trap detection.


## Authoritative inputs

- AGENTS.md and conductor/workflow.md.
- Current implementation and named successor tracks, where their reviewed security requirements supersede original designs.

## Validation

Run `python3 scripts/gate.py test`, profile checks and CLI smoke checks. Record source coverage and limitations in review.md before archival.

## External boundary

Local review does not authorize publication. Hosted or native checks not run locally must be identified as such.
