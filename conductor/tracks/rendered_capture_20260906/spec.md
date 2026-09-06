# Optional rendered-browser capture and headless automation

## Overview

Extend the generic mirroring roadmap under the user request for additional copying, document lifecycle and automation features. Planning only.

## Authoritative inputs

`AGENTS.md`, `conductor/product.md`, `conductor/product-guidelines.md`, `conductor/implementation_contract.md` and `conductor/archive/future_capabilities_20260905/spec.md`, baseline `4f41c8de9419c01eda6b7dddc9eac7d53069822d`. Functional requirements below are the implementation contract; no vendor or deployment is a runtime dependency.

## Requirements

- R1: Design an optional isolated browser automation adapter for JavaScript-rendered pages, bounded scrolling/lazy loading, pagination and downloadable documents. Core CLI/browser operation must remain usable without it.
- R2: Use explicit session scope and caller-authorised authentication recipes, including bounded login forms and CSRF/session expiry handling. Never import unrelated browser cookies or execute arbitrary instructions from page content; no purchases, submissions or destructive form actions in capture recipes.
- R3: Intercept and scope every browser subrequest, redirect, popup and service-worker path; route authorised requests through pacing limits, cap runtime/pages/bytes, and fail closed when interception cannot guarantee scope. Preserve TLS verification.
- R4: Distinguish original HTTP responses from rendered DOM/screenshot derivatives with versioned recipes and provenance. Record unsupported streaming, DRM, backend-dependent and non-deterministic behaviour; do not claim full application emulation.

## Acceptance criteria

- AC1: Pinned synthetic dynamic fixtures capture lazy-loaded content, pagination and downloads with reproducible recipes on macOS and Windows.
- AC2: Network records prove scope and rate limits across subresources; adversarial scripts/popups and third-party redirects cannot leak credentials or escape controls.
- AC3: Headless and visible modes produce declared equivalent content where expected; unavailable runtime and interactive authentication return actionable machine-readable outcomes.

## Dependencies

authenticated_acquisition_20260906, crawl_controls_reports_20260906

## Constraints, gates and exclusions

Use synthetic fixtures and reserved domains, preserve security/politeness and original archive bytes. No core runtime dependency expansion: optional browser/parser/OCR tools require isolated pinned environments and explicit provisioning documentation. Machine-verifiable acceptance does not require extra manual sign-off. Credentials, runtime availability and hosted platform evidence are genuine execution boundaries, not automatic success. No release, publication, production schedule activation, external notification or sensitive-data egress is included. No specific organisation, target website or assessment method is in scope.
