# ADR 0013: Scorecard target >= 7

- Status: proposed
- Date: 2026-09-05
- Track: future_capabilities_20260905 / T13
- Deciders: maintainers

## Context

The repository has a security scoring workflow whose first run supplies a baseline. This ADR maps checks such as branch protection, pinned dependencies, token permissions, fuzzing, SAST, and signed releases to owning tracks. Weekly review provides the cadence.

## Decision

Defer until `repo_standards_alignment_20260905` lands. Delivery shape: standard Web API or Python stdlib only; no vendored dependency is introduced by this research track.

## Consequences

The proposal improves interoperability or operator capability while keeping runtime and bundle size unchanged until a separate implementation track is approved. It adds documentation and future maintenance work; security review, fixtures, browser support, and reproducible verification remain mandatory. No product claim changes before implementation.

## Go/no-go checklist

- [ ] Zero-install feasibility confirmed: standard Web API / Python stdlib; no vendored file required *(mandatory)
- [ ] Prerequisite sibling tasks listed with track_id/T<n>: Defer until repo_standards_alignment_20260905 lands *(mandatory)
- [ ] Verification method named (conformance tool, fixture, or test) that will prove the capability works: focused fixture and acceptance test *(mandatory)
- [ ] Baseline score and per-check results are recorded from the first workflow run
- [ ] Each failing check maps to an owning track/task or an accepted risk
- [ ] Depends on `repo_standards_alignment_20260905` Scorecard workflow task
