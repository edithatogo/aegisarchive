# Portable mirror exports and interoperability

## Overview

Extend the generic mirroring roadmap under the user request for additional copying, document lifecycle and automation features. Planning only.

## Authoritative inputs

`AGENTS.md`, `conductor/product.md`, `conductor/product-guidelines.md`, `conductor/implementation_contract.md` and `conductor/archive/future_capabilities_20260905/spec.md`, baseline `4f41c8de9419c01eda6b7dddc9eac7d53069822d`. Functional requirements below are the implementation contract; no vendor or deployment is a runtime dependency.

## Requirements

- R1: Implement a deterministic static-directory/ZIP export with rewritten local links and resource names safe on Windows and macOS; preserve query identity, case collisions and long-path mapping in a manifest.
- R2: Advance existing WACZ/CDXJ research only through an explicit format contract and validator-backed implementation; retain WARC/CDX originals and reproducible hashes. Unsupported formats remain labelled pending.
- R3: Provide portable inventory, checksums, import/readback and repair diagnostics; distinguish an export from a published release. Test accessibility of viewer controls and clear missing-resource states.
- R4: Create an offline-first operator guide for choosing static versus rendered acquisition, configuring scope, inspecting coverage and validating exports. No remote telemetry by default.

## Acceptance criteria

- AC1: Exports navigate correctly after relocation to paths with spaces on macOS and Windows with source disconnected.
- AC2: Traversal, reserved filenames, case collisions and Unicode fixtures remain inside export root and retain distinct content identities.
- AC3: Independent readback/format validation reproduces payload hashes; packaging does not claim runtime/model assets are bundled when absent.

## Dependencies

offline_navigation_20260906, mirror_resume_20260906

## Constraints, gates and exclusions

Use synthetic fixtures and reserved domains, preserve security/politeness and original archive bytes. No core runtime dependency expansion: optional browser/parser/OCR tools require isolated pinned environments and explicit provisioning documentation. Machine-verifiable acceptance does not require extra manual sign-off. Credentials, runtime availability and hosted platform evidence are genuine execution boundaries, not automatic success. No release, publication, production schedule activation, external notification or sensitive-data egress is included. No specific organisation, target website or assessment method is in scope.

## Granular implementation mapping

- T1: Specify export mappings and adversarial fixtures → AC2.
- T2: Implement deterministic directory export → AC1, AC2.
- T3: Add deterministic ZIP and readback → AC2, AC3.
- T4: Specify WACZ/CDXJ format contract → AC3.
- T5: Implement and independently validate interoperable package → AC3.
- T6: Qualify relocation and accessible offline use → AC1, AC2.
- T7: Document prerequisites and repair diagnostics → AC3.

The final task reconciles all R requirements and AC1–AC3. Shared browser-test provisioning is owned by offline_navigation_20260906/T1; later tracks consume its locked configuration and add only their own test files. Changes to shared tooling require an explicit integration refinement.
