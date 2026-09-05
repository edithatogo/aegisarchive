# ADR 0009: In-browser text extraction

- Status: proposed
- Date: 2026-09-05
- Track: future_capabilities_20260905 / T9
- Deciders: maintainers

## Context

Extracting text from captured PDFs and HTML enables local search. A PDF renderer typically needs a main file and worker, so the single-file rule requires either an inline blob worker or a documented two-file exception. The feature must be opt-in and size-bounded.

## Decision

Defer until text corpus requirements are accepted. Delivery shape: standard Web API or Python stdlib only; no vendored dependency is introduced by this research track.

## Consequences

The proposal improves interoperability or operator capability while keeping runtime and bundle size unchanged until a separate implementation track is approved. It adds documentation and future maintenance work; security review, fixtures, browser support, and reproducible verification remain mandatory. No product claim changes before implementation.

## Go/no-go checklist

- [ ] Zero-install feasibility confirmed: standard Web API / Python stdlib; no vendored file required *(mandatory)
- [ ] Prerequisite sibling tasks listed with track_id/T<n>: Defer until text corpus requirements are accepted *(mandatory)
- [ ] Verification method named (conformance tool, fixture, or test) that will prove the capability works: focused fixture and acceptance test *(mandatory)
- [ ] Worker delivery is inline blob with a 3 MiB compressed ceiling
- [ ] `web/lib/VENDORED.json` schema is `{file,version,sha256,source,license}`
- [ ] Verification extends the bundle hash check to the manifest; task proposed to `security_gates_and_fuzzing_20260905`
