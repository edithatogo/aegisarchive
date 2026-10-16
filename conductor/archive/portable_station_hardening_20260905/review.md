# Scoped station repair review — 17 October 2026

Original completed/archive tasks remain historical. T9 is a narrowly reopened
owning-track repair, claimed in `68d2307`; it does not transfer launcher
ownership to the mirroring track.

## Evidence and proposed repair

Hosted mirroring run `38977432488`, Mac job `117230142215`, captured a live
startup stack blocked in reverse DNS before readiness. The regression failed
before implementation at stdlib `HTTPServer.server_bind()` calling
`socket.getfqdn()` (1 test, 0.005 seconds).

The repair overrides only `server_bind()` in the exported threaded HTTP server
class, calling stdlib `TCPServer.server_bind()` and using the numeric bound
address/port for server metadata. Production `main()` still constructs that
same exported class on `127.0.0.1`. No Host/token/path check or timeout changes.

## Panel

- Cicero (`01a144a0-4b38-7853-8395-d9154471fb82`): approve; TCP binding,
  actual socket address/port, inherited threading, loopback bind and Host
  validation are retained. No blockers.
- Pasteur (`01a144a0-55b5-70c2-8b44-c18fcc12c1bd`): approve subject to
  focused tests; production uses the exported class covered by the regression.
  No blockers. The focused tests subsequently passed.

Reviewed launcher/test diff SHA-256:
`b9159ebc68a63a32131714acfc9d048bb11c6774f2eeba45edbf2ba452620152`.

## Validation status

All 19 station tests passed in 1.759 seconds, including forbidden reverse DNS,
actual status serving and foreign Host rejection. Python compilation and
launcher `--help` passed. Full baseline and actual clean-source platform
qualification were initially pending the coordinated validation slot; these reviews
are not GitHub approvals or overall CI acceptance.

The reserved full gate subsequently passed: 353 Python tests (12 skipped,
106.687 seconds), 19 station tests (2.356 seconds), and 85 JavaScript tests
(7.559 seconds). All three browser behaviour tests passed (1.3 minutes total;
measured case 54.8 seconds). Leak and strict Conductor health checks passed.
The uncommitted behaviour run is not a clean-source platform qualification;
that is recorded separately after the implementation commit.
