# CDXJ index for compressed WARC

[ADR 0002](../../../docs/adr/0002-cdxj-index.md) · [CDXJ specification](https://specs.webrecorder.net/cdxj/0.1.0/)

- **R1** Produce a sorted standalone CDXJ index using the compressed WARC spans, actual URL and capture time, content digest, MIME type, status and WARC filename plus its compressed byte offset and length.
- **R2** Reuse the project’s URL identity rules for retained metadata, and implement only the ordering and key transformation required by the CDXJ format.
- **AC1** Each index row identifies a real, independently decompressible record. Colliding timestamps, query strings and distinct captures retain their recorded identities.
- **AC2** A malformed or out-of-range reference prevents publication. CDX-11 output and its existing readers keep their contract.
