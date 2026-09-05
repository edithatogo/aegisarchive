# ADR 0002: CDXJ index alongside CDX-11

- Status: proposed
- Date: 2026-09-05
- Track: future_capabilities_20260905 / T2
- Deciders: maintainers

## Context

CDXJ stores SURT, timestamp, and JSON metadata per line, while the current exporter emits CDX-11. Emitting both formats improves interoperability while retaining existing consumers. SURT, digest, offsets, and lengths must be specified before implementation.

## Decision

Go — plan a new track `cdxj_index_implementation`. Delivery shape: standard Web API or Python stdlib only; no vendored dependency is introduced by this research track.

## Consequences

The proposal improves interoperability or operator capability while keeping runtime and bundle size unchanged until a separate implementation track is approved. It adds documentation and future maintenance work; security review, fixtures, browser support, and reproducible verification remain mandatory. No product claim changes before implementation.

## Go/no-go checklist

- [ ] Zero-install feasibility confirmed: standard Web API / Python stdlib; no vendored file required *(mandatory)
- [ ] Prerequisite sibling tasks listed with track_id/T<n>: cdxj_index_implementation *(mandatory)
- [ ] Verification method named (conformance tool, fixture, or test) that will prove the capability works: focused fixture and acceptance test *(mandatory)
- [ ] SURT canonicalisation differences between current `toSURT` and CDXJ expectations are documented
- [ ] Digest encoding is base32, with an explicit conversion rule for `warc_verify.py`
- [ ] Depends on `warc_interop_20260905` CDX `S` field task
