# ADR 0007: Agent skills folder

- Status: proposed
- Date: 2026-09-05
- Track: future_capabilities_20260905 / T7
- Deciders: maintainers

## Context

Agent harnesses can discover focused instructions from skills/<name>/SKILL.md files. Candidate skills cover polite archiving, WARC verification, and Conductor task selection. The files should point to existing governance documents without copying them.

## Decision

Go — plan a new track `agent_skills_implementation`. Delivery shape: standard Web API or Python stdlib only; no vendored dependency is introduced by this research track.

## Consequences

The proposal improves interoperability or operator capability while keeping runtime and bundle size unchanged until a separate implementation track is approved. It adds documentation and future maintenance work; security review, fixtures, browser support, and reproducible verification remain mandatory. No product claim changes before implementation.

## Go/no-go checklist

- [ ] Zero-install feasibility confirmed: standard Web API / Python stdlib; no vendored file required *(mandatory)
- [ ] Prerequisite sibling tasks listed with track_id/T<n>: agent_skills_implementation *(mandatory)
- [ ] Verification method named (conformance tool, fixture, or test) that will prove the capability works: focused fixture and acceptance test *(mandatory)
- [ ] Skill list, one-line purpose, and target file are enumerated
- [ ] No skill restates content owned by AGENTS.md or the implementation contract
