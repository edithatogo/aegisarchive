# Generic document lifecycle, extraction and search

## Overview

Extend the generic mirroring roadmap under the user request for additional copying, document lifecycle and automation features. Planning only.

## Authoritative inputs

`AGENTS.md`, `conductor/product.md`, `conductor/product-guidelines.md`, `conductor/implementation_contract.md` and `conductor/archive/future_capabilities_20260905/spec.md`, baseline `4f41c8de9419c01eda6b7dddc9eac7d53069822d`. Functional requirements below are the implementation contract; no vendor or deployment is a runtime dependency.

## Requirements

- R1: Register discovered and downloaded documents using stable source identity, immutable content hashes, acquisition history, MIME detection and explicit unknown metadata; track moved URLs separately from changed bytes.
- R2: Create versioned text derivatives with page/paragraph locators, extractor/version/output hashes and explicit partial/failed/encrypted/unsupported outcomes. Optional PDF/Office/OCR engines are isolated, pinned and separately provisioned; OCR confidence never establishes source truth.
- R3: Provide offline full-text search with source/version filters, links to captured originals, duplicate detection, revision comparison and change receipts. Reuse existing generic search/SQLite components after a contract review; do not import a consuming project implementation blindly.
- R4: Inherit handling restrictions in derivatives, caches and exports; quarantine flagged content, document retention/deletion semantics, and make destructive removal explicit. No automatic privacy clearance or governance conclusions.

## Acceptance criteria

- AC1: Synthetic text-layer and scanned fixtures preserve original bytes and locators; missing optional engines produce honest unsupported states.
- AC2: Same bytes at multiple URLs and changed bytes at one URL have correct identity/history and searchable revision results.
- AC3: Malformed/archive-bomb inputs are bounded; flags and restrictions propagate through search/export; no sensitive test content or secrets are committed.

## Dependencies

mirror_capture_20260906, mirror_resume_20260906

## Constraints, gates and exclusions

Use synthetic fixtures and reserved domains, preserve security/politeness and original archive bytes. No core runtime dependency expansion: optional browser/parser/OCR tools require isolated pinned environments and explicit provisioning documentation. Machine-verifiable acceptance does not require extra manual sign-off. Credentials, runtime availability and hosted platform evidence are genuine execution boundaries, not automatic success. No release, publication, production schedule activation, external notification or sensitive-data egress is included. No specific organisation, target website or assessment method is in scope.

## Granular implementation mapping

- T1: Define catalogue and derivative schemas → AC1, AC2.
- T2: Implement immutable registration and history → AC2.
- T3: Add bounded native text extraction → AC1, AC3.
- T4: Add optional PDF and Office adapters → AC1, AC3.
- T5: Add optional OCR derivative processing → AC1, AC3.
- T6: Implement revision-aware offline search → AC1, AC2.
- T7: Implement revision changes and duplicates → AC2.
- T8: Enforce handling and retention boundaries → AC3.

The final task reconciles all R requirements and AC1–AC3. Shared browser-test provisioning is owned by offline_navigation_20260906/T1; later tracks consume its locked configuration and add only their own test files. Changes to shared tooling require an explicit integration refinement.
