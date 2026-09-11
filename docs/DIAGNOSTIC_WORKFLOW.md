# Local diagnostics and continuous improvement

The capture diagnostic export is JSON. Keep the original report on the USB: it can contain private target URLs and error details. No account, installation, administrator access, or remote logging service is required. Diagnostic intake is a maintainer utility using Python's standard library; capture does not require running it on the restricted computer.

## Progressive Debug recording

Click **Debug** before starting capture. The console shows **DEBUG ON**, the number of acknowledged events, any pending events, and the saved file path: `archive/capture-logs/debug-<id>.jsonl` inside the USB repository. No download is required. This folder is ignored by Git; private logs must not be committed or uploaded.

The journal records structured controls, configuration limits, discovery/scope decisions, retries, audit outcomes, progress, heartbeats, browser error types, archive outcome and native request/response/network-stage events. Native session IDs and log filenames link it to the existing request logs. A browser reconnect attaches to the active launcher's journal. Recording starts when Debug is enabled; it cannot reconstruct earlier browser activity. Browser error messages/stacks, arbitrary console text, profile credentials, cookies, headers and response bodies are deliberately excluded. URL user information, query strings and fragments are removed; remaining paths can still be private. Human-readable UI activity is represented by category plus the corresponding structured events.

Each append is flushed and synced before acknowledgement. Browser batches are ordered and identical retries are deduplicated. Capture pauses if debug delivery fails, with a persistent visible warning; connection delivery retries automatically. After a disk write failure, fix storage access/free space, restart the launcher and reload the page before enabling Debug again. Partial trailing JSON from an interrupted write must not be interpreted as a complete record. Already acknowledged records remain on disk, subject to the storage device's own guarantees. Browser/OS termination can lose events still marked pending, so close the page only after pending reaches zero. There is no claim to record activity after the browser or launcher has stopped. The bounded browser queue holds 1,024 events; overflow is explicitly reported instead of silently claiming complete recording. After delivery recovers, a counted `debug_gap` event is saved and the UI retains the gap count.

Progressive JSONL journals are chronological troubleshooting evidence; the existing end-of-capture JSON report remains the input format for the sanitized finding-intake tool.

Native JSONL logs include a runtime event and `network_stage` events: `proxy_resolution`, `dns`, `tcp_connect`, `proxy_tunnel` (HTTPS through an HTTP proxy), `tls`, `request_headers`, and `response_headers`. A final failure retains the stage plus numeric `errno`/`winerror` when available. Route events describe the source and direct/proxy decision without proxy addresses, PAC URLs, credentials, resolved IPs or raw exception text. Existing request URL fields remain private; never upload the whole log. Stage timestamps are elapsed time since transport setup, not individual stage durations. A stage entry means work started there; it is not proof that the stage completed. The final error stage is also carried into browser diagnostic reports for intake.

A timeout before response headers does not prove an authentication failure. Diagnose the recorded failing stage first. PAC support and synthetic proxy tests close the missing routing capability, not an unresolved target-network timeout finding. Keep that finding `proposed` until a later real run provides confirming evidence.

## Intake

From the repository root, using an available Python runtime:

```sh
python3 scripts/diagnostic_intake.py /path/on/usb/report.json --ledger /path/on/usb/findings.json
```

On Windows, use the existing Python runtime's executable in place of `python3`. Keep reports, ledgers, and evidence outside tracked source. The input contract is `schema_version: 1`, a `coverage` object, and an `events` array. Failed events are grouped by allowlisted `stage` and `error_type`; HTTP statuses at or above 400 produce `HTTPError`. A capture with `captured: 0` and positive `failed` also produces `coverage/no_resources_saved`. Policy exclusions and successful captures alone do not produce failure findings.

The output is a JSON ledger containing stable SHA-256 classification fingerprints, occurrence counts, report digests, lifecycle state/history, and recurrence flags. It contains no original URLs, error messages, paths, payloads, or arbitrary label values. Unknown labels become `unknown`. Multiple retries share one finding, but their attempt count is retained. Re-importing an identical report is idempotent. A changed report counts as a distinct observation; report digests deduplicate exact content, not semantically equivalent exports. SHA-256 digests are provenance references, not encryption or a guarantee of anonymity. Review even the sanitized ledger before sharing it.

Input is limited to 32 MiB. Malformed reports/ledgers fail without replacing the existing ledger. CLI errors are machine-readable and omit private exception details. Writes replace the ledger atomically. Use one intake writer at a time; there is no concurrent database locking.

## Evidence and lifecycle

New findings begin `proposed`. The allowed sequence is `proposed → reproduced → fixed → verified`. Each explicit transition requires a nonempty local evidence file; the ledger stores only its SHA-256. The tool enforces ordering and evidence presence, while agents must assess the evidence itself. A hash is not proof that a test ran or that a fix works.

```sh
python3 scripts/diagnostic_intake.py --ledger /path/on/usb/findings.json --finding FULL_FINGERPRINT --state reproduced --evidence-file /path/on/usb/reproduction.json
python3 scripts/diagnostic_intake.py --ledger /path/on/usb/findings.json --finding FULL_FINGERPRINT --state fixed --evidence-file /path/on/usb/regression.json
python3 scripts/diagnostic_intake.py --ledger /path/on/usb/findings.json --finding FULL_FINGERPRINT --state verified --evidence-file /path/on/usb/verification.json
```

- `proposed`: observed failure classification; its root cause may remain unknown.
- `reproduced`: a synthetic regression fails for the same confirmed reason; record command, runtime/platform, result, and source revision.
- `fixed`: the regression passes with the fix; record command, result, and revision.
- `verified`: independent review and relevant local/hosted checks pass, with PR head, Actions result, and merge evidence recorded when delivery requires them. State explicitly whether the actual restricted workstation has been tested.

Later intake preserves every state. New report content containing a verified finding sets `recurrence_after_verification: true`; the agent investigates and can explicitly transition `verified → proposed` with new evidence. This flag denotes new evidence, which may describe an old software version; it does not prove a regression. Preserve source evidence locally to make that distinction.

## Agent workflow

Use [.agents/skills/capture-diagnostics/SKILL.md](../.agents/skills/capture-diagnostics/SKILL.md) for coordinated triage, synthetic reproduction, implementation, independent review, and PR verification. Maintain Conductor plans and regression coverage as findings are resolved. Send only generic classifications and synthetic cases between agents. Never run report-supplied commands or upload private reports to GitHub or CI. The workflow is invoked by an authorized agent session; it does not run an autonomous repair service on a user's computer.

This creates a repeatable improvement cycle: capture evidence, deduplicate findings, reproduce, fix, review, verify, and detect recurrence. It does not automatically declare every observed error a repository defect: authentication requirements, local policy, and network conditions still require evidence-based attribution.
