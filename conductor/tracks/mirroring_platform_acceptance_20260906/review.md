# Cross-platform mirroring review record

## T6 hosted-execution prerequisites — 17 October 2026

Candidate base: `07f50057c39e09717a8ec94bea431b7db3b4e5a0`.
Reviewed two-file implementation diff SHA-256:
`e21e585d895d75beadabaaab70cf65715193b8bc504b6d1a84ef6356f6ba3533`.

Actual hosted run `38972650979` at published `8c692ec` failed Windows
receipt-contract testing and hosted Mac launcher readiness. It did not qualify
either hosted platform or the pair. Local Mac acceptance at `8c692ec` passed;
its immutable receipt is retained under `artifacts/qualification/8c692ecce819fb81ec09d94ac8c438d6fe83dfe4/darwin-arm64/`.

### Panel decisions

- Pasteur (`01a144a0-55b5-70c2-8b44-c18fcc12c1bd`): approve the
  host-independent newline fixture. Windows `write_text()` produced CRLF;
  replacing LF blindly doubled CR. Use explicit LF bytes and construct the
  positive conversion from the committed blob. Retain content-mutation,
  CRCRLF and mixed-newline rejection. The production validator is unchanged.
- Cicero (`01a144a0-4b38-7853-8395-d9154471fb82`): initially hold because
  diagnostic-write failure could bypass launcher cleanup and replace the
  original exception. Approve after revision: cleanup is always attempted,
  diagnostic/cleanup failures are appended, and the original error is rethrown.
  Hosted Mac's pre-readiness root cause remains unproven; retain child output
  before making a behavioural fix. No timeout increase is approved.

Recommendation: deliver these bounded test-harness corrections after required
baseline/browser checks pass, then inspect a fresh hosted run. Standing owner
approval and the direct G1 approval cover reviewed programme fixes; neither
waives technical acceptance. These are local panel reviews, not GitHub review
approvals. T6 stays in progress until actual matching platform receipts pass.

### Focused validation before the full gate

The first 26-test run exposed one stale one-line fixture expectation, not a
production failure. Updating its literal to the new two-line fixture was
followed by both affected tests passing (2 tests, 6.963 seconds). The newline
case also passed with inherited Git `core.autocrlf=true` (7.452 seconds) and
`false` (6.977 seconds). Python compilation, Node syntax and diff checks passed.
Full baseline/browser results are recorded separately in the evidence ledger;
this review is not itself a platform-qualification receipt.

### Actual Windows evidence review and remaining hosted exception

Carver (`01a144a5-cc9e-7472-95db-da90370ac9c1`) independently approved
the named local-Mac/hosted-Windows pair at `bec9a8236c10e97dc51ca39cb28b60b5c1d61566`.
Both receipts, their comparison and Windows WARC/CDX validation passed. All
11 retained Windows files matched hosted artifact `12079092295` from successful
job `117226519282` in run `38976319916`. Its logs show three browser tests and
mandatory receipt validation passed. This is not an overall CI pass: the
additional hosted Mac job failed and the hosted comparison was skipped.

Cicero approved a further failure-only diagnostic: sample only the owned,
still-live Darwin launcher before cleanup, with bounded process/stack commands
and retained command results. The readiness deadline, production launcher,
original exception and unconditional cleanup remain unchanged. That diagnostic
is awaiting full validation and publication; approval alone is not execution.
