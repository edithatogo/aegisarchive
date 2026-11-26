# WACZ export from a finalized capture

[ADR 0001](../../../docs/adr/0001-wacz-export.md) · [WACZ 1.1.1](https://specs.webrecorder.net/wacz/1.1.1/) · [Reference validator v0.6.0](https://github.com/webrecorder/py-wacz/tree/v0.6.0)

- **R1** Package one finalized capture as WACZ with its validated archive and CDXJ index, page URL and capture time rows, and a profile `wacz` manifest with resource hashes.
- **R2** Use the existing deterministic ZIP patterns. Store compressed archive members without recompression and validate all package paths and hashes.
- **AC1** Two exports of the same fixture reproduce the same member bytes and order. Tampering, missing index entries and unsafe names fail validation.
- **AC2** A pinned independent reference validator and an offline replay client open the saved WACZ and resolve a sampled document and asset by index range.
- **Boundary** Support one capture and unsigned exports in the initial slice. General ZIP extraction, catalogue ingestion and signing have separate acceptance criteria.
