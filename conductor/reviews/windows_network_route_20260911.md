# Windows routing review panel

Two independent agents reviewed the routing adapter, transport stage instrumentation and safe diagnostic boundaries.

- API/transport reviewer: approve bounded implementation; pointer types and ownership, HTTPS context/MRO, CONNECT destination and fail-closed routing checked. Native Windows execution remains a required hosted gate. Requested explicit limits on discovery timing and proxy failover; documented.
- Privacy/regression reviewer: approve with fix; move the acceptance-success message after all checks. Applied. No demonstrated transport or privacy blocker.
- Coordinator recommendation: merge the scoped routing and diagnostics change after final-head Actions pass, under standing owner approval. This closes a confirmed missing PAC capability; it does not prove the cause of the observed target timeout.

Options considered: retain default urllib routing (leaves the confirmed PAC gap); implement current-user automatic routing plus diagnostics (recommended); implement full browser-session/Windows-integrated authentication (separate work requiring evidence that authentication is the failing stage).

Validation includes allocated string cleanup, no PAC domain auto-logon, per-destination direct/proxy selection, DNS/TCP failure attribution, proxy CONNECT refusal, TLS verification and supplied-context behavior, and sanitized intake compatibility. Native PAC evaluation runs on hosted Windows with the prepared embedded Python. Corporate workstation acceptance remains unverified.
