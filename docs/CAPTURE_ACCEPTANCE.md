# Capture through the local console

Launch AegisArchive with the operating system's START launcher. Enter a complete HTTP(S) address in **Quick capture address**, leave **Local Python** selected, and click **Start Harvest**. The quick address sets the host scope. Use **Configure Profile** or a custom profile for advanced scope and pacing.

The local route reads ordinary websites without requiring those sites to grant browser CORS access. It does not disable browser security, certificate validation, server permissions, or rate limiting. The optional browser route requires same-origin access or explicit CORS support from the source.

**URLs Attempted** is not a saved-page count. The final outcome reports saved responses, failures, exclusions and pending resources. Zero saved responses is a failure. After a successful or partial run, **Download WARC + CDX** saves the archive; open the WARC in **Offline WARC Viewer** to browse captured pages. Dynamic applications are not promised to behave as live sites.

## Access and robots

Respect robots.txt is the default. The optional authorised-ignore setting changes only robots policy; it cannot override HTTP 401/403, TLS errors, network restrictions or missing VPN access. A robots read failure remains visible in the audit log.

The local Python route uses this computer's network access. It does not inherit a logged-in browser's cookies. Authenticated acquisition requires an explicit `authentication` profile supported by `cli/auth.py`, scoped within the capture's allowed hosts. Session import, basic credentials, configured headers and client certificates are optional. Browser handoff itself does not acquire credentials or complete SSO/MFA.

The local transport accepts only scoped GET requests, does not automatically follow redirects, rejects requests to the station's own port, and caps each response at 32 MiB. Encoded responses that ignore identity encoding fail explicitly. No target page scripts execute on station origin.

If a tab was lost during capture and a new start fails, use **Stop previous local capture session**, then start again. Leaving a page also sends a best-effort session stop.

## Diagnostics

Each local capture writes request/response/failure JSONL to `archive/capture-logs/`, with the exact path shown in the UI. Status codes, byte counts and timing are retained. Credential headers and exception contents are not logged. URLs can contain private information: these logs are local and ignored by Git. Do not publish real-source logs without reviewing their contents.

## Reproducible acceptance

Install development dependencies with `npm ci` and `npx playwright install --with-deps chromium`. Run `npm run test:capture` on macOS, Windows or Linux. The acceptance suite uses only local synthetic fixtures; it never depends on an intranet or production site. To use an installed Chrome locally, set `AEGIS_BROWSER_CHANNEL=chrome` before the command. `AEGIS_TEST_PYTHON` can select the Python command.

Pull requests run the fast synthetic browser and multi-OS probe suites. The optional full native qualification downloads large runtime assets and is available through the `Portable full native qualification` workflow via `workflow_dispatch`.

The suite starts the actual launcher with isolated Python imports (`-I`) and a separate-origin HTTP fixture with no CORS headers, uses the visible profile/address/start controls, verifies USB-local WARC/CDX bytes and receipt hashes, and reopens the archive to navigate offline. OPFS and browser-storage writes are disabled in the storage regression. It also verifies 403 failures, robots exclusion/authorised ignore, optional imported-session authentication, and storage failures. The hosted Browser capture acceptance matrix uses the runner image's installed Chrome on all three platforms, recording its browser version; Windows uses the prepared embedded Python runtime.

Synthetic acceptance proves these workflows under known conditions. It does not establish access to a private deployment or completeness of an arbitrary site.
