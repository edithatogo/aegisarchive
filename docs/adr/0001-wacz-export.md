# ADR 0001: WACZ export

- Status: proposed
- Date: 2026-09-05
- Track: future_capabilities_20260905 / T1
- Deciders: maintainers

## Context

WACZ packages WARC payloads, CDXJ, pages JSONL, and a data package in a zip for standard replay tools. The current browser exports individual WARC and CDX files. A local-file writer paired with CompressionStream can preserve zero-install operation.

## Decision

Go — plan a new track `wacz_export_implementation`. Delivery shape: standard Web API or Python stdlib only; no vendored dependency is introduced by this research track.

## Consequences

The proposal improves interoperability or operator capability while keeping runtime and bundle size unchanged until a separate implementation track is approved. It adds documentation and future maintenance work; security review, fixtures, browser support, and reproducible verification remain mandatory. No product claim changes before implementation.

## Go/no-go checklist

- [ ] Zero-install feasibility confirmed: standard Web API / Python stdlib; no vendored file required *(mandatory)
- [ ] Prerequisite sibling tasks listed with track_id/T<n>: wacz_export_implementation *(mandatory)
- [ ] Verification method named (conformance tool, fixture, or test) that will prove the capability works: focused fixture and acceptance test *(mandatory)
- [ ] `datapackage.json` and `pages.jsonl` fields will follow the published format version
- [ ] Zip writer will use an OPFS-backed streaming design with a 2 GiB capture ceiling
- [ ] Depends on CDXJ (ADR 0002) and `warc_interop_20260905` payload-length/encoding fixes
- [ ] Conformance: open output in standard replay tools and validate with their checker
