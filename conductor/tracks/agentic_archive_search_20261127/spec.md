# Opt-in agentic search for saved archives

## Authoritative inputs

- [Offline intelligence plan](../../archive/portable_intelligence_suite/spec.md)
- [Document lifecycle and search policy](../../../docs/DOCUMENT_LIFECYCLE.md)
- [Existing revision search](../../../portable/document_search.py)

## Requirements and acceptance

- **R1** Keep ordinary indexed search as the default. The agentic mode requires an explicit local model manifest.
- **R2** Use the saved archive's indexed text and current visibility rules for every lookup. Return source, revision, original-content hash, and locator information from the index.
- **R3** If the first lookup is empty, allow one local model call and one alternate keyword lookup. Give the model the question alone. Report engine and response failures without echoing model output.
- **AC1** An existing catalogue can be searched through a read-only CLI. Both ordinary keyword mode and an opt-in query with early matches leave the planner idle.
- **AC2** An alternate query recovers a fixture missed by the first lookup. Results carry real revision citations. Source and revision filters and restrictions apply to the follow-up.
- **AC3** A missing index, invalid model reply or unavailable model has a clear outcome. Searching leaves the saved database unchanged.
- **AC4** Later slices establish intake from saved WARC files and compare retrieval quality and latency against ordinary indexed search.

## Delivery

T1 uses the standard library and the existing offline model adapter with user-provisioned assets. T2 and T3 have separate acceptance checks.
