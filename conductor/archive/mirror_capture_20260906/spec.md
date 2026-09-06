# Complete static-site capture

## Overview

Capture the complete declared static resource graph into verified WARC/CDX, with explicit omissions instead of a misleading success count.

## Authoritative inputs

Baseline revision `4f41c8de9419c01eda6b7dddc9eac7d53069822d`: `AGENTS.md`, `conductor/product.md`, `conductor/product-guidelines.md`, `conductor/workflow.md`, `conductor/implementation_contract.md`, `web/lib/warc_reader.js`, `web/lib/core_crawler.js`, `cli/aegis_cli.py`. User request: create tracks covering the previously identified mirroring and platform gaps.

## Requirements

- R1: Discover HTML links and requisites, base-relative URLs, srcset, CSS url() and recursive @import in both CLI and browser routes; handle cycles, fragments, query identities, redirects, MIME and encodings without silently broadening scope.
- R2: Apply existing robots, scope, rate-limit and retry controls to every discovered resource. Reject unsupported schemes and surface redirect/scope/auth failures.
- R3: Emit a capture coverage receipt enumerating expected, captured, excluded, failed and unsupported resources, archive hashes and extractor versions. Script-generated content is explicitly unsupported by static capture.

## Acceptance criteria

- AC1: A synthetic multi-page fixture with nested CSS, fonts, images, downloads, redirects and malformed inputs yields the exact declared URL/hash set on supported routes.
- AC2: An inaccessible requisite produces an explicit incomplete outcome; no success claim from HTTP status alone. Browser CORS failure is explicit; CLI remains the general HTTP route.
- AC3: WARC/CDX verification passes and existing politeness/security tests remain green.

## Constraints and external gates

Core runtime remains Python standard library and native browser APIs. Preserve archive bytes, politeness, scope and sandbox controls. Use synthetic fixtures and reserved domains only; no organisation or real target is part of this contract. Development browser-test dependencies must be isolated and locked before use. No mandatory manual sign-off for machine-verifiable behaviour. Hosted execution evidence is required where named; unavailable environments remain pending. Publication, release and unrequested credential access are not authorised implementation tasks.

## Dependencies



## Out of scope

General JavaScript application emulation, server-side business logic, bypassing access controls, automatic browser-cookie extraction, source publication, and claiming all websites are supported. Optional AI functionality is not a mirroring acceptance substitute.

## Granular implementation mapping

- T1: Freeze resource graph fixtures → AC1.
- T2: Parse HTML requisites consistently → AC1.
- T3: Traverse CSS imports and resource URLs → AC1.
- T4: Integrate CLI resource discovery → AC1, AC3.
- T5: Integrate browser resource discovery → AC1, AC2.
- T6: Write coverage and omission receipts → AC2, AC3.

The final task reconciles all R requirements and AC1–AC3. Shared browser-test provisioning is owned by offline_navigation_20260906/T1; later tracks consume its locked configuration and add only their own test files. Changes to shared tooling require an explicit integration refinement.
