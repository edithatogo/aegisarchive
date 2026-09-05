# ADR 0004: Service-worker replay

- Status: proposed
- Date: 2026-09-05
- Track: future_capabilities_20260905 / T4
- Deciders: maintainers

## Context

The current viewer uses a base URL that can cause live-origin requests and weakens offline fidelity. A service worker can intercept requests within a replay scope and serve captured bytes. Secure-context and iframe sandbox constraints must be respected.

## Decision

Defer until `web_console_security_20260905` lands. Delivery shape: standard Web API or Python stdlib only; no vendored dependency is introduced by this research track.

## Consequences

The proposal improves interoperability or operator capability while keeping runtime and bundle size unchanged until a separate implementation track is approved. It adds documentation and future maintenance work; security review, fixtures, browser support, and reproducible verification remain mandatory. No product claim changes before implementation.

## Go/no-go checklist

- [ ] Zero-install feasibility confirmed: standard Web API / Python stdlib; no vendored file required *(mandatory)
- [ ] Prerequisite sibling tasks listed with track_id/T<n>: Defer until web_console_security_20260905 lands *(mandatory)
- [ ] Verification method named (conformance tool, fixture, or test) that will prove the capability works: focused fixture and acceptance test *(mandatory)
- [ ] Fallback for `file://` opening is blob rewriting; otherwise the feature is unavailable
- [ ] Worker URL rewriting rules cover HTML, CSS, and script references
- [ ] Depends on `web_console_security_20260905` iframe sandbox and CSP tasks
