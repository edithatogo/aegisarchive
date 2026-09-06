# Crawl controls, previews and site reports

## Overview

Extend the generic mirroring roadmap under the user request for additional copying, document lifecycle and automation features. Planning only.

## Authoritative inputs

`AGENTS.md`, `conductor/product.md`, `conductor/product-guidelines.md`, `conductor/implementation_contract.md` and `conductor/archive/future_capabilities_20260905/spec.md`, baseline `4f41c8de9419c01eda6b7dddc9eac7d53069822d`. Functional requirements below are the implementation contract; no vendor or deployment is a runtime dependency.

## Requirements

- R1: Separate discover, traverse and download decisions; support ordered include/exclude rules by URL/path, MIME, size and depth, download-without-traversal, sitemap seeds, bounded domain aliases and query/fragment policy.
- R2: Provide deterministic rule preview and dry-run reports without fetching excluded bodies; bound regex execution or use safe matching. Explain which rule selected each URL.
- R3: Produce filterable internal/external link graphs and machine-readable reports of failures, redirects, missing assets, duplicates, resource totals and estimated/actual storage. Escape labels and export diagrams without source scripts.

## Acceptance criteria

- AC1: Synthetic rule precedence and cyclic sitemap fixtures yield exact expected discovery/download sets.
- AC2: Report totals reconcile with capture receipts; inaccessible pages remain failures, never evidence of absence.
- AC3: Rule previews are deterministic, adversarial patterns are bounded, and graph/report rendering cannot execute source markup.

## Dependencies

mirror_capture_20260906

## Constraints, gates and exclusions

Use synthetic fixtures and reserved domains, preserve security/politeness and original archive bytes. No core runtime dependency expansion: optional browser/parser/OCR tools require isolated pinned environments and explicit provisioning documentation. Machine-verifiable acceptance does not require extra manual sign-off. Credentials, runtime availability and hosted platform evidence are genuine execution boundaries, not automatic success. No release, publication, production schedule activation, external notification or sensitive-data egress is included. No specific organisation, target website or assessment method is in scope.

## Granular implementation mapping

- T1: Define ordered rule schema and vectors → AC1, AC3.
- T2: Implement bounded rule evaluation → AC1, AC3.
- T3: Add bounded sitemap and alias discovery → AC1.
- T4: Integrate rule decisions into both crawlers → AC1, AC2.
- T5: Implement preview and reconciled reports → AC2, AC3.
- T6: Render and export safe link graphs → AC2, AC3.

The final task reconciles all R requirements and AC1–AC3. Shared browser-test provisioning is owned by offline_navigation_20260906/T1; later tracks consume its locked configuration and add only their own test files. Changes to shared tooling require an explicit integration refinement.
