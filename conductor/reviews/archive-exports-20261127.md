# Review of compressed WARC, CDXJ and WACZ export

Two independent reviewers assessed candidate `30e8f20` for file publication,
interoperability and qualification. They found four issues.

- Finalized native captures with incomplete crawl coverage were rejected.
- A WARC could be opened for export while the native CDX was still being finalized.
- CDXJ dropped semicolon path parameters and accepted a mismatched archived HTTP length.
- A revisit with no HTTP headers invented a successful status and page entry.

Both reviewers confirmed the fixes on `5a84e7f`. The receipt now verifies
the source bytes even when crawl coverage is incomplete. The CDXJ tests check
the full path, reject malformed body lengths and preserve unknown revisit status.
The final compatibility check accepts bodyless responses, including HEAD, whose
numeric HTTP Content-Length describes the selected representation.

Python 3.15.2, py-wacz 0.6.0 and warcio 1.8.2 verified the WACZ fixture and
rejected a changed index. Chromium rendered the sampled page and stylesheet
without requests to the source in the [Linux capture job](https://github.com/edithatogo/aegisarchive/actions/runs/45899487250/job/140181473459).

Recommendation is to merge the export chain once the final head passes its
required and hosted browser acceptance checks. The repository owner's standing
approval in the [review policy](../review-policy.md) covers this scope.
