# Native browser capture and cross-platform UI acceptance

## Problem and scope
The normal local console attempts browser cross-origin fetches against sites that do not grant CORS access. A failed robots fetch can produce one attempted URL, zero saved responses and a misleading finalized status.

User-directed repair: provide an optional token-gated, scoped local Python GET transport while retaining the browser route. Use the same UI for start, pause, stop, diagnostics and WARC export. Preserve rate limiting, TLS validation, redirect scope and explicit credential boundaries. Add real browser acceptance across three operating systems.

## Acceptance
- AC1: Real UI capture against a separate-origin HTTP fixture without CORS follows three pages, a redirect and assets; exported WARC contains their actual bytes.
- AC2: The exported archive can be reopened and navigated without source network requests.
- AC3: HTTP denial and robots exclusions cannot be labelled saved pages. Respect remains default; authorised ignore is optional. Explicit imported session can access a protected synthetic fixture; browser login is never implicitly inherited.
- AC4: Native transport rejects missing tokens, cross-origin requests, scope expansion and station self-fetch; credentials are absent from response metadata and persistent logs.
- AC5: The same browser suite passes locally on macOS Chrome and in hosted Linux, macOS and Windows Chrome jobs.

## Integration ownership
This user-requested repair includes the minimal transport dispatch in cli/launch.py, plus a new module and focused tests. It deliberately extends the completed launcher integration contract; station hardening remains mandatory. No deployment URL or private source material enters this repository. The remaining crawl-controls roadmap is unchanged.

## Limits
The transport uses the host network and explicit authentication profile. It cannot override HTTP access denial, TLS validation, VPN requirements, or execute source-side application workflows. Responses are capped at 32 MiB each. It does not automatically acquire browser cookies or automate SSO/MFA. Logs remain local.
