# ADR 0005: Prioritized Task Scheduling

- Status: proposed
- Date: 2026-09-05
- Track: future_capabilities_20260905 / T5
- Deciders: maintainers

## Context

Pause and stop currently wait on in-flight timers. Scheduler task priorities and cooperative yields may improve input responsiveness, but must not shorten politeness delays. Feature detection with a timer fallback preserves existing behavior.

## Decision

Go — plan a new track `prioritized_scheduling_implementation`. Delivery shape: standard Web API or Python stdlib only; no vendored dependency is introduced by this research track.

## Consequences

The proposal improves interoperability or operator capability while keeping runtime and bundle size unchanged until a separate implementation track is approved. It adds documentation and future maintenance work; security review, fixtures, browser support, and reproducible verification remain mandatory. No product claim changes before implementation.

## Go/no-go checklist

- [ ] Zero-install feasibility confirmed: standard Web API / Python stdlib; no vendored file required *(mandatory)
- [ ] Prerequisite sibling tasks listed with track_id/T<n>: prioritized_scheduling_implementation *(mandatory)
- [ ] Verification method named (conformance tool, fixture, or test) that will prove the capability works: focused fixture and acceptance test *(mandatory)
- [ ] Feature detection and a timer fallback are specified with no unsupported-browser behavior change
- [ ] Verification proves politeness delays are never shortened by rescheduling
