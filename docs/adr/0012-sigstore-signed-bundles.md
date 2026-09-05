# ADR 0012: Sigstore-signed release bundles

- Status: proposed
- Date: 2026-09-05
- Track: future_capabilities_20260905 / T12
- Deciders: maintainers

## Context

Release archives and SHA256SUMS can receive keyless signatures and bundles from a CI identity. Verification needs a client, while the application itself remains zero-install. The design complements provenance and keeps stdlib verification limited to hashes.

## Decision

Defer until `release_and_packaging_20260905` lands. Delivery shape: standard Web API or Python stdlib only; no vendored dependency is introduced by this research track.

## Consequences

The proposal improves interoperability or operator capability while keeping runtime and bundle size unchanged until a separate implementation track is approved. It adds documentation and future maintenance work; security review, fixtures, browser support, and reproducible verification remain mandatory. No product claim changes before implementation.

## Go/no-go checklist

- [ ] Zero-install feasibility confirmed: standard Web API / Python stdlib; no vendored file required *(mandatory)
- [ ] Prerequisite sibling tasks listed with track_id/T<n>: Defer until release_and_packaging_20260905 lands *(mandatory)
- [ ] Verification method named (conformance tool, fixture, or test) that will prove the capability works: focused fixture and acceptance test *(mandatory)
- [ ] Archives and SHA256SUMS are the signed artefacts and bundles attach to the release
- [ ] User verification instructions separate optional verification tooling from running the app
- [ ] Depends on `release_and_packaging_20260905` SHA256SUMS/provenance tasks
