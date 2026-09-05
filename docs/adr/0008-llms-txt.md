# ADR 0008: llms.txt

- Status: proposed
- Date: 2026-09-05
- Track: future_capabilities_20260905 / T8
- Deciders: maintainers

## Context

A root llms.txt can give agent harnesses a curated map of the project and its authoritative documents. It must describe only capabilities proven by the repository. A claims-audit link provides a maintenance check.

## Decision

Go — plan a new track `llms_txt_implementation`. Delivery shape: standard Web API or Python stdlib only; no vendored dependency is introduced by this research track.

## Consequences

The proposal improves interoperability or operator capability while keeping runtime and bundle size unchanged until a separate implementation track is approved. It adds documentation and future maintenance work; security review, fixtures, browser support, and reproducible verification remain mandatory. No product claim changes before implementation.

## Go/no-go checklist

- [ ] Zero-install feasibility confirmed: standard Web API / Python stdlib; no vendored file required *(mandatory)
- [ ] Prerequisite sibling tasks listed with track_id/T<n>: llms_txt_implementation *(mandatory)
- [ ] Verification method named (conformance tool, fixture, or test) that will prove the capability works: focused fixture and acceptance test *(mandatory)
- [ ] Section list and link targets are enumerated
- [ ] A claims-audit row is defined so the file cannot advertise unimplemented features
