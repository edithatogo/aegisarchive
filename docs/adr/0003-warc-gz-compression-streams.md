# ADR 0003: .warc.gz via Compression Streams

- Status: proposed
- Date: 2026-09-05
- Track: future_capabilities_20260905 / T3
- Deciders: maintainers

## Context

Per-record gzip members keep records independently readable and make offsets meaningful. CompressionStream is available in current evergreen browsers, with a capability check required. Python stdlib gzip can verify concatenated members.

## Decision

Go — plan a new track `warc_gzip_implementation`. Delivery shape: standard Web API or Python stdlib only; no vendored dependency is introduced by this research track.

## Consequences

The proposal improves interoperability or operator capability while keeping runtime and bundle size unchanged until a separate implementation track is approved. It adds documentation and future maintenance work; security review, fixtures, browser support, and reproducible verification remain mandatory. No product claim changes before implementation.

## Go/no-go checklist

- [ ] Zero-install feasibility confirmed: standard Web API / Python stdlib; no vendored file required *(mandatory)
- [ ] Prerequisite sibling tasks listed with track_id/T<n>: warc_gzip_implementation *(mandatory)
- [ ] Verification method named (conformance tool, fixture, or test) that will prove the capability works: focused fixture and acceptance test *(mandatory)
- [ ] Member-per-record layout is confirmed against the WARC/1.1 compression annex
- [ ] Python stdlib verifier strategy for multi-member gzip is defined
- [ ] Depends on `warc_interop_20260905` `.warc.gz` verifier task
