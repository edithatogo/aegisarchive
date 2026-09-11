# Deployment requirement acceptance

This checklist distinguishes implemented behavior, repeatable tests, and evidence that can only come from the target environment. A completed Conductor track is not evidence that every enterprise website can be cloned.

| Requirement | Evidence and boundary |
| --- | --- |
| One working USB application | Canonical checkout and launcher are `aegisarchive/START_WINDOWS.cmd`; retired local branch history is preserved separately before pruning. Archives and optional assets are not extra working checkouts. |
| Windows without installed Python | Official embedded Windows x64 Python is prepared inside `runtime/python/`, with pinned archive SHA-256 and per-file manifest. Windows Actions executes the CMD launcher with system Python removed from PATH. |
| No installation or administrator action at launch | Runtime is standard-library Python plus the existing browser. Launch does not install packages, services or drivers. CI does not prove that enterprise application control permits the executable or loopback listener. |
| USB-local capture output | Launcher capture persists WARC, CDX and JSON receipt under `archive/captures/`, without OPFS or persistent browser checkpoint fallback. Completion requires successful storage. Browser and Python regressions check the actual files. Optional manual exports still use the browser's chosen download location. |
| Resume behavior | Pause/resume works while the console remains open. The browser console holds its frontier in memory, not persistent host storage; reloading does not restore it. Partial USB archive bytes are preserved. Durable CLI resume is a separate route. |
| Visible operation and failure | Quick address entry, running/paused/failed/completed states, resource counts and JSON diagnostics exist. No saved-resource claim may be inferred from a fixed receipt or a zero-resource run. |
| Machine-readable diagnostics | Structured capture events and automatic reports are stored under `archive/capture-logs/`; the diagnostic intake workflow supports reproducible regression work without publishing private reports. |
| Follow pages and collect documents | Local browser fixtures exercise linked HTML, CSS, images and documents, plus scope, robots, denial and stop behavior. Coverage means the discovered static graph, not every dynamically reachable page. The native transport currently limits each response body to 32 MiB and reports oversized responses as failures. |
| Optional robots handling | Default respect and explicit authorized-ignore selection exist; pacing and server-preservation controls remain active. |
| Authentication | Explicit scoped header/cookie/session-file and client-certificate routes exist. The native Python route does not inherit the existing browser login. The browser-handoff adapter provides instructions, not an automatic authenticated transport. |
| Integrated enterprise SSO | Automatic NTLM/Negotiate/SSPI or reuse of an existing Chrome identity is not implemented. If the target requires it, the current native route is insufficient without a compatible explicit authenticated route. Manual browser access alone is not acceptance evidence. |
| Cross-platform tests | Windows, macOS and Linux browser fixtures plus Windows embedded-runtime tests are hosted-runner evidence. They are not Windows-container isolation or execution under the user's corporate non-admin account. |
| Fully USB-contained browser state | Application outputs are directed to the USB. The existing installed browser can still maintain its own cache, history and operating-system state; the application cannot promise zero host-machine writes by that browser. |

Target acceptance remains open until a real run confirms that the approved executable can run, authentication succeeds, multiple expected pages and documents are stored on the USB, and the saved files can be read offline. Report that boundary honestly; do not replace it with a simulated acceptance claim.
