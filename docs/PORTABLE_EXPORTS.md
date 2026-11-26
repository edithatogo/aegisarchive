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
and the source SHA-256 before publishing. A native capture receipt must
match the selected WARC. A finalized capture can be exported even if its
receipt reports gaps in crawl coverage.
The JSON output lists the actual compressed offsets and lengths.

## Index a compressed WARC with CDXJ

```sh
python -m cli.export_mirror cdxj export.warc.gz export.cdxj
python -m cli.export_mirror verify-cdxj export.warc.gz export.cdxj
```

The sorted index retains the archived URL, a UTC timestamp at CDXJ precision,
MIME type, HTTP status when recorded, and payload digest. Keep the index with
the archive under its indexed filename. Each row points to one complete gzip member. Requests and other
auxiliary records stay in the archive. Revisits refer to a verified original
payload earlier in the same archive. The input must contain complete,
independently compressed WARC records with decoded HTTP transfer framing.
Complete responses with a body must agree with any archived HTTP Content-Length.
The verifier checks exact coverage and values for an index produced by this
command.

## Package a finalized capture as WACZ

```sh
python -m cli.export_mirror wacz archive.warc capture.wacz
python -m cli.export_mirror verify-wacz capture.wacz
```

The unsigned WACZ 1.1.1 bundle contains the original WARC records in
independent gzip members, a CDXJ index, a list of captured HTML pages and
SHA-256 hashes for all bundled resources. AegisArchive reads back the bundle
before publishing it. The reference validation runs on synthetic fixtures
with py-wacz and warcio. WACZ export accepts one finalized WARC at a time.

All three export commands need space for staged output beside the
destination. On macOS and Linux, use a destination filesystem that supports
hard links for atomic publication.
