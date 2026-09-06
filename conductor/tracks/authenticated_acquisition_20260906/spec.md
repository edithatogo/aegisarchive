# Explicit authenticated acquisition routes

## Overview

Make public CLI acquisition and explicitly authorised session acquisition usable without pretending browser CORS or login boundaries disappear.

## Authoritative inputs

Baseline revision `4f41c8de9419c01eda6b7dddc9eac7d53069822d`: `AGENTS.md`, `conductor/product.md`, `conductor/product-guidelines.md`, `conductor/workflow.md`, `conductor/implementation_contract.md`, `web/lib/warc_reader.js`, `web/lib/core_crawler.js`, `cli/aegis_cli.py`. User request: create tracks covering the previously identified mirroring and platform gaps.

## Requirements

- R1: Document and expose route capabilities: unauthenticated CLI, same-origin browser, and explicit caller-supplied session material for supported HTTP authentication. Never auto-read browser profiles or cookie stores.
- R2: Implement opt-in local session input with exact-origin allowlists; prevent credential forwarding across redirects, strip secrets from logs/receipts/request records and keep session files out of archives.
- R3: Detect login pages, 401/403, expired sessions and unsupported interactive SSO. Pause at actual login when needed; do not bypass certificate, access or CORS controls. Dynamic browser automation or extensions require a separately reviewed future design.

## Acceptance criteria

- AC1: Synthetic cookie/basic-auth fixtures succeed with explicit credentials and fail clearly without them; cross-origin redirects receive no secrets.
- AC2: Secret sentinel scans find no credentials in WARC, CDX, logs, checkpoints or receipts; expiry is a resumable explicit failure.
- AC3: UI/docs make supported and unsupported session routes clear; no claim that signing into a browser authenticates the CLI.

## Constraints and external gates

Core runtime remains Python standard library and native browser APIs. Preserve archive bytes, politeness, scope and sandbox controls. Use synthetic fixtures and reserved domains only; no organisation or real target is part of this contract. Development browser-test dependencies must be isolated and locked before use. No mandatory manual sign-off for machine-verifiable behaviour. Hosted execution evidence is required where named; unavailable environments remain pending. Publication, release and unrequested credential access are not authorised implementation tasks.

## Dependencies

mirror_capture_20260906

## Out of scope

General JavaScript application emulation, server-side business logic, bypassing access controls, automatic browser-cookie extraction, source publication, and claiming all websites are supported. Optional AI functionality is not a mirroring acceptance substitute.
