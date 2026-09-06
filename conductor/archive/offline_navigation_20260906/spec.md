# Safe offline page navigation and assets

## Overview

Replace inert replay navigation with archive-local navigation while keeping captured content untrusted and preventing live-origin requests.

## Authoritative inputs

Baseline revision `4f41c8de9419c01eda6b7dddc9eac7d53069822d`: `AGENTS.md`, `conductor/product.md`, `conductor/product-guidelines.md`, `conductor/workflow.md`, `conductor/implementation_contract.md`, `web/lib/warc_reader.js`, `web/lib/core_crawler.js`, `cli/aegis_cli.py`. User request: create tracks covering the previously identified mirroring and platform gaps.

## Requirements

- R1: Resolve links, fragments, redirects and history against archived canonical identities. Show a clear missing-resource state rather than visiting the live website.
- R2: Rewrite HTML and nested CSS requisites including fonts, images and srcset to archive-local resources; preserve originals and manage blob URL lifetime.
- R3: Design a narrowly validated navigation bridge or isolated local replay route. Keep scripts and forms disabled by default; never grant same-origin privileges to captured content. Test malicious navigation and messages.

## Acceptance criteria

- AC1: With the source server stopped, automated browser tests traverse at least three pages, back/forward and fragments, and verify rendered image/style/font fixtures.
- AC2: Browser network instrumentation observes zero source-origin or other non-loopback requests during replay, including adversarial HTML/CSS.
- AC3: Original payload hashes remain unchanged; missing links remain visible and existing sandbox/CSP regression tests pass.

## Constraints and external gates

Core runtime remains Python standard library and native browser APIs. Preserve archive bytes, politeness, scope and sandbox controls. Use synthetic fixtures and reserved domains only; no organisation or real target is part of this contract. Development browser-test dependencies must be isolated and locked before use. No mandatory manual sign-off for machine-verifiable behaviour. Hosted execution evidence is required where named; unavailable environments remain pending. Publication, release and unrequested credential access are not authorised implementation tasks.

## Dependencies

mirror_capture_20260906

## Out of scope

General JavaScript application emulation, server-side business logic, bypassing access controls, automatic browser-cookie extraction, source publication, and claiming all websites are supported. Optional AI functionality is not a mirroring acceptance substitute.

## Granular implementation mapping

- T1: Provision isolated browser acceptance tooling → AC1, AC2.
- T2: Specify archive navigation and hostile fixtures → AC1, AC2.
- T3: Implement canonical archive-local resolution → AC1, AC3.
- T4: Implement isolated navigation signalling → AC1, AC2.
- T5: Wire viewer navigation and history → AC1, AC2.
- T6: Rewrite nested assets and manage lifetime → AC1, AC3.
- T7: Prove disconnected-source replay → AC1, AC2, AC3.

The final task reconciles all R requirements and AC1–AC3. Shared browser-test provisioning is owned by offline_navigation_20260906/T1; later tracks consume its locked configuration and add only their own test files. Changes to shared tooling require an explicit integration refinement.
