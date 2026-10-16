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
was validated and published at `016bde64a1bb8f866c82f9cd5030892bf77196fb`.
The full baseline passed (353 Python tests, 12 skipped; station and 85 JavaScript
tests), followed by three behaviour tests and three clean-source Mac tests.
Both retained Mac receipt checks passed. Direct local diagnostic exercises
captured process state but stack sampling timed out at five seconds; this
limitation was retained rather than represented as stack-capture success.

Hosted run `38977432488` supplied the decisive evidence: Windows job
`117230142022` passed, while Mac job `117230142215` failed readiness. This time
both its process and stack diagnostic commands passed. The retained Mac stack
shows the main thread blocked in `socket_gethostbyaddr`, `gethostbyaddr`,
`mdns_hostbyaddr` and `kevent` during object initialisation before readiness.
Together with the launcher startup order, this supports the reverse-DNS call in
`HTTPServer.server_bind()` as the startup blocker. Browser launch occurs later.
The stack and process files are retained under
`artifacts/qualification/016bde64a1bb8f866c82f9cd5030892bf77196fb/hosted-darwin-failed/`.

The protected station owner has received the evidence and proposed bounded
repair: avoid reverse DNS when binding the numerical loopback server while
preserving loopback-only listening, Host checks and control-token validation.
No protected launcher edit was made from this track. Overall CI remains failed;
the passing required local-Mac/hosted-Windows comparison is kept separate.

### Final T6 qualification — 17 October 2026

Owning station T9 repaired numerical-loopback startup at
`42550216efa5069870f011d9a9173c6a697ce1fb`, without changing the readiness deadline
or Host/token controls. Local Mac acceptance and retained receipt checks passed.
Hosted run 38979330621 passed Mac 117236222685, Windows 117236222409 and
comparison 117236763137. All eight triggered workflows at that revision passed.

Carver independently approved T6: all three receipt checks, local-Mac/Windows
and hosted-Mac/Windows comparisons, and all three WARC/CDX verifiers passed.
Both downloaded hosted bundles exactly match GitHub artifacts (11 files each).
The observations share the same clean revision and implementation digest and
retain actual recovery, launcher, authentication and disconnected-replay proof.
Artifacts are retained under `artifacts/qualification/42550216efa5069870f011d9a9173c6a697ce1fb/`.
This supersedes the earlier red-CI blocker; it does not complete T7/T8 or claim
compatibility with every site or machine.
