# ADR 0011: PyPI Trusted Publishing

- Status: proposed
- Date: 2026-09-05
- Track: future_capabilities_20260905 / T11
- Deciders: maintainers

## Context

OIDC-based publishing avoids long-lived package tokens. It requires an index-side pending publisher and a protected environment in the release workflow. The repository can document these prerequisites without changing hosted settings.

## Decision

Defer until `release_and_packaging_20260905` lands. Delivery shape: standard Web API or Python stdlib only; no vendored dependency is introduced by this research track.

## Consequences

The proposal improves interoperability or operator capability while keeping runtime and bundle size unchanged until a separate implementation track is approved. It adds documentation and future maintenance work; security review, fixtures, browser support, and reproducible verification remain mandatory. No product claim changes before implementation.

## Go/no-go checklist

- [ ] Zero-install feasibility confirmed: standard Web API / Python stdlib; no vendored file required *(mandatory)
- [ ] Prerequisite sibling tasks listed with track_id/T<n>: Defer until release_and_packaging_20260905 lands *(mandatory)
- [ ] Verification method named (conformance tool, fixture, or test) that will prove the capability works: focused fixture and acceptance test *(mandatory)
- [ ] Index-side G5 settings are listed step by step
- [ ] Package name availability and CalVer versioning are confirmed before implementation
- [ ] Depends on `release_and_packaging_20260905` release workflow and pyproject tasks
