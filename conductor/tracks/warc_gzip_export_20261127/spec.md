# Record-at-a-time compressed WARC export

[ADR 0003](../../../docs/adr/0003-warc-gz-compression-streams.md) · [WARC 1.1 Annex D](https://iipc.github.io/warc-specifications/specifications/warc-format/warc-1.1/#record-at-time-compression)

- **R1** Export a finalized uncompressed WARC through an explicit CLI operation, using one gzip member per complete WARC record and retaining the source bytes.
- **R2** Validate record framing and use bounded streaming and atomic publication. Each result supplies member lengths and compressed offsets for an index.
- **AC1** Decompressing the full output reproduces the original bytes. Each indexed slice decompresses to exactly its referenced response, request, warcinfo or revisit record.
- **AC2** A malformed or incomplete source and an interrupted write leave the original and any existing export intact. Repeated exports of the same fixture on the same qualified runtime are byte-identical.
- **Boundary** Existing capture, uncompressed WARC and CDX-11 defaults, and live recovery files retain their supported behavior. Browser-side encoding is outside this slice.
