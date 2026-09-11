# Windows network routing and diagnostics

Observed evidence: native acquisition timed out before an HTTP response; the actual network cause is unresolved. Source inspection confirms default urllib does not evaluate Windows PAC settings.

## Requirements
- R1: Support per-user Windows automatic proxy discovery using only built-in APIs, without administrator access or installation.
- R2: Record allowlisted route and connection-stage diagnostics locally, without proxy addresses, credentials or raw exceptions.
- R3: Preserve scope, redirect refusal, TLS verification and pacing; do not implicitly inherit browser authentication.

## Acceptance criteria
- AC1: Windows PAC selection is evaluated per destination, with explicit environment proxies retaining precedence; discovery errors never silently fall back to direct access.
- AC2: Regression fixtures exercise routing decisions, failure attribution and redaction; actual Windows bundled-runtime tests exercise native API bindings.
- AC3: JSON diagnostics distinguish route resolution, DNS, TCP, proxy tunnel, TLS and HTTP response stages and remain accepted by diagnostic intake.
- AC4: Independent agent review and final-head Actions pass before merge; documentation distinguishes synthetic evidence from target acceptance.

## Gates
- G1: User says Proceed under standing authorization for implementation, PR and merge.
- G2: Restricted-workstation acceptance remains unverified; no local or hosted fixture closes that deployment-specific finding.
