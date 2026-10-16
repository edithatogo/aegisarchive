# Mirroring compatibility

## Qualified scope

The native capture route passes actual ordinary-launcher, capture, reload/recovery
and disconnected replay at **`42550216efa5069870f011d9a9173c6a697ce1fb`**.
Later documentation/Conductor commits are not new platform qualifications.
[Hosted run 38979330621](https://github.com/edithatogo/aegisarchive/actions/runs/38979330621)
passed Mac, Windows and mandatory comparison; the current Apple Silicon Mac was
measured separately at the same revision.

| Environment | Python / Chromium | Retained receipt |
| --- | --- | --- |
| Current Mac, Darwin arm64 | 3.15.0 / 155.0.8059.82 | [Local Mac](../artifacts/qualification/42550216efa5069870f011d9a9173c6a697ce1fb/darwin-arm64/receipt.json) |
| Hosted Mac, Darwin arm64 | 3.11.9 / 152.0.7977.83 | [Hosted Mac](../artifacts/qualification/42550216efa5069870f011d9a9173c6a697ce1fb/hosted-darwin-arm64/receipt.json) |
| Hosted Windows, AMD64 | 3.11.9 / 155.0.8059.40 | [Windows](../artifacts/qualification/42550216efa5069870f011d9a9173c6a697ce1fb/windows-amd64/receipt.json) |

All used locked Playwright 1.63.0 as development tooling. `artifacts/` is retained
locally, not committed source; these receipt links resolve in the evidence
checkout, not a fresh source-only clone. Hosted artifacts expire after 30 days.
Preserve each complete local qualification directory, including observations,
WARC/CDX, launcher manifest and logs.

## Capability matrix

| Capability | Measured outcome and boundary |
| --- | --- |
| Static HTML and requisite assets | Six payload hashes and WARC/CDX integrity pass. No completeness claim for arbitrary sites. |
| Disconnected navigation, CSS and images | Eleven visits, repeated navigation/back-forward and asset checks pass with the source stopped and unreachable; zero source/unexpected requests and page errors. Missing destinations remain local. |
| Reload/interruption recovery | Native folder capture reopens the same archive and preserves bytes/writer/frontier state; setup-failure retry passes. Other storage modes and arbitrary update scenarios are not qualified by this fixture. |
| Authentication failures | Synthetic denied and client/server-expired sessions and secret redaction pass. Real SSO/MFA, client certificates and organisation-specific login flows remain outside this proof. |
| Ordinary launchers | Actual entrypoints work from relocated paths containing spaces; missing-runtime diagnostics pass. POSIX executable permission is prepared explicitly. Python and a compatible installed browser are prerequisites. |
| Packaging | Source ZIPs omit Python and do not guarantee POSIX executable permission. [Windows portable preparation](WINDOWS_USB.md) has separate acceptance; this fixture does not qualify every USB/runtime bundle. |
| Dynamic/server-side applications | Not reproduced: transactions, live databases or general JavaScript application emulation. Captured pages are not working copies of their original applications. |
| Other browsers, architectures and Linux mirroring | Not qualified by this platform pair. |
| Optional/extended capabilities | AI assets, rendered capture, jobs, exports and document lifecycle have separate track receipts; they do not expand this static mirroring qualification. |

Only authorised targets and supplied authentication are supported. This does not
authorise access-control bypass, automatic credential extraction, or release
publication, and is not a universal website-compatibility claim.

## Reproduce and verify

Use the qualified revision, a clean checkout, locked development tooling and
installed Chrome. Run the actual harness, not receipt generation alone:

```sh
AEGIS_BROWSER_CHANNEL=chrome npx --no-install playwright test --config tests/browser/playwright.config.js tests/browser/mirroring_acceptance.spec.js
python3 scripts/mirroring_acceptance.py --check --output artifacts/mirroring-darwin-arm64/receipt.json
```

On Windows, set `AEGIS_BROWSER_CHANNEL=chrome` in the shell, use `python`, and
check `artifacts/mirroring-win32-x64/receipt.json`. The test creates a synthetic
source; no real intranet or credentials are needed. Compare retained proof:

```sh
python3 scripts/mirroring_acceptance.py --compare artifacts/qualification/42550216efa5069870f011d9a9173c6a697ce1fb/darwin-arm64/receipt.json artifacts/qualification/42550216efa5069870f011d9a9173c6a697ce1fb/windows-amd64/receipt.json
```

Generating a receipt without measured observations remains pending and cannot
qualify a platform. Preserve the receipt with its entire artifact directory.
