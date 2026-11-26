# Portable exports

`cli.export_mirror` writes a deterministic directory and ZIP from captured URL/payload pairs. Paths are origin scoped, query identities are preserved in names, traversal and non HTTP URLs are rejected, and `manifest.json` records SHA-256 and byte counts. ZIP timestamps and member order are fixed for reproducible hashes.

Original WARC and CDX-11 files remain authoritative.

## Export a record-compressed WARC

Run from the source checkout with its Python 3.15 environment active.

```sh
python -m cli.export_mirror warc-gzip archive.warc export.warc.gz
```

Select a finalized uncompressed WARC and a new output path. Each gzip member
contains one complete WARC record. The command checks the saved member ranges
and the source SHA-256 before publishing. For native captures with a receipt,
the receipt must mark the capture complete and match the selected WARC.
The JSON output lists the actual compressed offsets and lengths.
