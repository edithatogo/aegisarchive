# Durable mirror resume and incremental updates

## Overview

Preserve prior archive bytes across interruption and updates, rather than restoring only the URL frontier.

## Authoritative inputs

Baseline revision `4f41c8de9419c01eda6b7dddc9eac7d53069822d`: `AGENTS.md`, `conductor/product.md`, `conductor/product-guidelines.md`, `conductor/workflow.md`, `conductor/implementation_contract.md`, `web/lib/warc_reader.js`, `web/lib/core_crawler.js`, `cli/aegis_cli.py`. User request: create tracks covering the previously identified mirroring and platform gaps.

## Requirements

- R1: Bind checkpoints to profile, version, archive segments, source identities and hashes; atomically persist bytes and state. Reject corrupt or mismatched state.
- R2: Resume interrupted runs without losing completed payloads or silently duplicating records. Handle cancellation, exhausted storage and partial writes.
- R3: Support incremental refresh with validators where supplied; retain historical revisions, record removals/failed revalidation explicitly, and resolve revisits without missing payloads. Never persist authentication secrets.

## Acceptance criteria

- AC1: Kill/restart tests at controlled write boundaries produce a verified archive equivalent to an uninterrupted fixture crawl.
- AC2: Changed, unchanged and removed fixture resources have correct retained lineage and explicit coverage; corrupt state fails closed.
- AC3: Browser persistent-storage availability and CLI disk requirements are explicit; unsupported persistence cannot report durable resume.

## Constraints and external gates

Core runtime remains Python standard library and native browser APIs. Preserve archive bytes, politeness, scope and sandbox controls. Use synthetic fixtures and reserved domains only; no organisation or real target is part of this contract. Development browser-test dependencies must be isolated and locked before use. No mandatory manual sign-off for machine-verifiable behaviour. Hosted execution evidence is required where named; unavailable environments remain pending. Publication, release and unrequested credential access are not authorised implementation tasks.

## Dependencies

mirror_capture_20260906, authenticated_acquisition_20260906

## Out of scope

General JavaScript application emulation, server-side business logic, bypassing access controls, automatic browser-cookie extraction, source publication, and claiming all websites are supported. Optional AI functionality is not a mirroring acceptance substitute.
