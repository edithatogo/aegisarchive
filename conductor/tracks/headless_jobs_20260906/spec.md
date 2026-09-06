# Headless jobs, scheduling and automation contracts

## Overview

Extend the generic mirroring roadmap under the user request for additional copying, document lifecycle and automation features. Planning only.

## Authoritative inputs

`AGENTS.md`, `conductor/product.md`, `conductor/product-guidelines.md`, `conductor/implementation_contract.md` and `conductor/archive/future_capabilities_20260905/spec.md`, baseline `4f41c8de9419c01eda6b7dddc9eac7d53069822d`. Functional requirements below are the implementation contract; no vendor or deployment is a runtime dependency.

## Requirements

- R1: Expose versioned job specifications and JSON status/events for start, status, pause, resume, cancel and verification; deterministic exit codes distinguish complete, partial, auth-required and failed runs.
- R2: Add bounded concurrency, idempotent run identities, leases/locking, retry budgets and restart recovery. Provide explicit opt-in scheduling using platform-neutral job definitions and documented platform adapters; no scheduled job activates during installation.
- R3: Add scoped CLI/MCP orchestration using existing transport and authentication contracts, never unrestricted shell execution. Notifications/webhooks are opt-in, redact secrets and carry summary/hash references rather than source bodies.
- R4: Retain provenance, storage budgets and retention status for scheduled incremental runs; report missed/overlapping schedules without duplicate capture.

## Acceptance criteria

- AC1: Crash/restart, overlapping schedules, cancellation and retry tests produce exactly the declared completed records.
- AC2: CLI and MCP return matching schema-validated states and exit semantics; no credential-bearing logs.
- AC3: Synthetic scheduled runs execute on both macOS and Windows; no external schedule or notification endpoint is enabled by default.

## Dependencies

mirror_resume_20260906, crawl_controls_reports_20260906

## Constraints, gates and exclusions

Use synthetic fixtures and reserved domains, preserve security/politeness and original archive bytes. No core runtime dependency expansion: optional browser/parser/OCR tools require isolated pinned environments and explicit provisioning documentation. Machine-verifiable acceptance does not require extra manual sign-off. Credentials, runtime availability and hosted platform evidence are genuine execution boundaries, not automatic success. No release, publication, production schedule activation, external notification or sensitive-data egress is included. No specific organisation, target website or assessment method is in scope.

## Granular implementation mapping

- T1: Define versioned job state and exit contracts → AC1, AC2.
- T2: Implement persistent leases and run identity → AC1.
- T3: Implement lifecycle CLI operations → AC1, AC2.
- T4: Add scoped MCP job operations → AC2.
- T5: Implement opt-in schedule adapters → AC1, AC3.
- T6: Add redacted optional notifications → AC2, AC3.
- T7: Test restart and schedule behaviour on both platforms → AC1, AC2, AC3.

The final task reconciles all R requirements and AC1–AC3. Shared browser-test provisioning is owned by offline_navigation_20260906/T1; later tracks consume its locked configuration and add only their own test files. Changes to shared tooling require an explicit integration refinement.
