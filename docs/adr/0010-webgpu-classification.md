# ADR 0010: WebGPU classification

- Status: proposed
- Date: 2026-09-05
- Track: future_capabilities_20260905 / T10
- Deciders: maintainers

## Context

On-device classification could label language, document type, and sensitivity without uploading captures. Runtime files can be pinned, but model weights are large and must be fetched only after consent, hashed, and cached in OPFS. WebAssembly provides the fallback.

## Decision

Defer until ADR 0009 is accepted. Delivery shape: standard Web API or Python stdlib only; no vendored dependency is introduced by this research track.

## Consequences

The proposal improves interoperability or operator capability while keeping runtime and bundle size unchanged until a separate implementation track is approved. It adds documentation and future maintenance work; security review, fixtures, browser support, and reproducible verification remain mandatory. No product claim changes before implementation.

## Go/no-go checklist

- [ ] Zero-install feasibility confirmed: standard Web API / Python stdlib; no vendored file required *(mandatory)
- [ ] Prerequisite sibling tasks listed with track_id/T<n>: Defer until ADR 0009 is accepted *(mandatory)
- [ ] Verification method named (conformance tool, fixture, or test) that will prove the capability works: focused fixture and acceptance test *(mandatory)
- [ ] Model acquisition requires explicit user consent and never downloads automatically
- [ ] WebGPU detection and WebAssembly fallback are specified
- [ ] OPFS cache has an explicit size limit and least-recently-used eviction
- [ ] Depends on ADR 0009 (text extraction) being accepted
