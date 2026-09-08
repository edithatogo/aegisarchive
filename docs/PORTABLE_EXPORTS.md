# Portable exports

`cli.export_mirror` writes a deterministic directory and ZIP from captured URL/payload pairs. Paths are origin scoped, query identities are preserved in names, traversal and non HTTP URLs are rejected, and `manifest.json` records SHA-256 and byte counts. ZIP timestamps and member order are fixed for reproducible hashes.

Original WARC/CDX bytes remain authoritative. This exporter does not claim WACZ/CDXJ interoperability; those formats require an independent validator before being added.
