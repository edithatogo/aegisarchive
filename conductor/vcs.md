# VCS workflow

- Git is the repository source of truth. Use focused review-fix commits and separate evidence/archive commits.
- This review uses the existing main checkout; isolation is off (no isolation configuration or lease).
- Preserve unrelated changes and historical evidence. Rename track directories only after successful review.
- Pushes, hosted settings and service activation require their recorded external gate; local archive authorization does not grant them.
- Canonical evidence is hash-chained when metadata declares evidence_schema 1.0. Original ts/kind ledgers are preserved as evidence.legacy.jsonl; never append legacy events to the new chain.
