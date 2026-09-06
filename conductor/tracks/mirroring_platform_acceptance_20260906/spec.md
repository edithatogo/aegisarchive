# Cross-platform mirroring and capability acceptance

## Overview

Qualify a precise static-site mirroring replacement scope on macOS and Windows; distinguish that from optional AI/runtime qualification.

## Authoritative inputs

Baseline revision `4f41c8de9419c01eda6b7dddc9eac7d53069822d`: `AGENTS.md`, `conductor/product.md`, `conductor/product-guidelines.md`, `conductor/workflow.md`, `conductor/implementation_contract.md`, `web/lib/warc_reader.js`, `web/lib/core_crawler.js`, `cli/aegis_cli.py`. User request: create tracks covering the previously identified mirroring and platform gaps.

## Requirements

- R1: Create a reproducible acceptance harness that starts a synthetic source, captures it, stops the source, then drives offline browsing and verifies expected content, links, assets and zero unintended network requests.
- R2: Run the same acceptance on the current Apple Silicon Mac and hosted Windows AMD64 using relocated paths with spaces, supported Python/browser versions and ordinary launchers. Add an isolated CI workflow; test tools are development-only.
- R3: Generate hash-bound platform receipts and an honest capability matrix covering capture, navigation, CSS/assets, authentication, resume/update, dynamic sites and packaging prerequisites. Run optional intelligence qualification separately when claiming advanced features; it cannot substitute for mirroring.
- R4: Reconcile stale README claims and publish a scoped readiness assessment in repository documentation only. Release publication is a separate action.

## Acceptance criteria

- AC1: Both macOS and Windows receipts pass on the same implementation revision and fixture hashes; failed or skipped platforms prevent replacement-ready status.
- AC2: A disconnected-source acceptance run proves navigation and assets, plus denied/expired auth and interruption recovery fixtures. Launcher help alone is insufficient.
- AC3: Documentation labels supported static scope, unsupported dynamic/server-side behaviour, Python/browser prerequisites and separately qualified optional assets. No blanket compatibility claim for every website or Windows machine.

## Constraints and external gates

Core runtime remains Python standard library and native browser APIs. Preserve archive bytes, politeness, scope and sandbox controls. Use synthetic fixtures and reserved domains only; no organisation or real target is part of this contract. Development browser-test dependencies must be isolated and locked before use. No mandatory manual sign-off for machine-verifiable behaviour. Hosted execution evidence is required where named; unavailable environments remain pending. Publication, release and unrequested credential access are not authorised implementation tasks.

## Dependencies

offline_navigation_20260906, authenticated_acquisition_20260906, mirror_resume_20260906

## Out of scope

General JavaScript application emulation, server-side business logic, bypassing access controls, automatic browser-cookie extraction, source publication, and claiming all websites are supported. Optional AI functionality is not a mirroring acceptance substitute.
