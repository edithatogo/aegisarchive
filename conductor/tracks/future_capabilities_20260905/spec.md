# Track Specification: Future Capabilities (Research-First)

## Overview

The hardening review surfaced a set of bleeding-edge capabilities that would move AegisArchive from "produces standards-compliant files" to "interoperates with the wider web-archiving and agent ecosystems": WACZ export, CDXJ, gzip-compressed WARC, service-worker replay, a current MCP protocol version with resources and annotations, an agent skills folder, in-browser text extraction and classification, cooperative scheduling for pause responsiveness, `llms.txt`, and supply-chain signing and publishing. Each of these interacts with the zero-install invariant, the browser API surface, or the release process in ways that are not yet understood. This track is **research-first**: every item gets exactly one spike task whose only output is an Architecture Decision Record under `docs/adr/` with a go/no-go checklist. Implementation tasks are planned only afterwards, in new tracks, from an accepted ADR.

## Authoritative inputs

- Repository invariants: `AGENTS.md` (zero-install; stdlib-only runtime; vanilla browser code).
- Governance: `conductor/implementation_contract.md`, `conductor/lessons.md` (documentation must not run ahead of code).
- Vendoring rule (applies to every browser-library candidate here): only single-file vendored libraries under `web/lib/`, each pinned by SHA-256 in a `web/lib/VENDORED.json` manifest `{ "file": ..., "version": ..., "sha256": ..., "source": ..., "license": ... }`, verified by `cli/verify_bundle.py`-style checks; no package manager, no build step, opt-in at runtime.
- Sibling tracks: `warc_interop_20260905` (WARC/CDX correctness, prerequisite for WACZ/CDXJ/gzip), `web_console_security_20260905` (replay sandbox, prerequisite for service-worker replay), `release_and_packaging_20260905` (release workflow, prerequisite for signing and publishing), `repo_standards_alignment_20260905` (Scorecard workflow), `security_gates_and_fuzzing_20260905`.

## Requirements

- **R1 — One ADR per candidate**: each item below has a spike task producing `docs/adr/NNNN-<slug>.md` with the headings `## Context`, `## Decision`, `## Consequences` and a `## Go/no-go checklist`.
- **R2 — Zero-install assessment**: every ADR states explicitly whether the capability can be delivered with standard Web APIs / Python stdlib alone, or requires a vendored single file (with size, licence, and SHA-256 plan), or is impossible under the invariant.
- **R3 — Interop assessment**: ADRs for archive formats name the standard replay tools the output must open in, and the conformance check that will prove it.
- **R4 — Prerequisites**: each ADR lists the sibling-track tasks that must land first.
- **R5 — No implementation**: this track changes nothing under `web/`, `cli/`, `mcp/`, `.github/workflows/`; an accepted ADR leads to a new track with its own spec.

## Candidates

1. WACZ export (WARC + CDXJ + `pages.jsonl` in a zip built with `CompressionStream`), openable in standard replay tools.
2. CDXJ index emitted alongside CDX-11.
3. `.warc.gz` output via the Compression Streams API (per-record gzip members).
4. Service-worker based replay replacing `<base href>` injection.
5. MCP protocol upgrade to `2025-06-18`: `resources` (profiles, CDX), tool annotations (`readOnlyHint`, `destructiveHint`), `outputSchema` with structured content.
6. Agent `skills/` folder with `SKILL.md` files for agent harnesses.
7. In-browser text extraction (vendored single-file PDF renderer) as an opt-in vendored library.
8. WebGPU classification (vendored single-file transformer runtime) as an opt-in vendored library.
9. Prioritized Task Scheduling API (`scheduler.postTask`, `scheduler.yield`) for pause responsiveness.
10. `llms.txt` at repository root describing the project for agent harnesses.
11. PyPI Trusted Publishing (OIDC) for the CLI package.
12. Sigstore-signed release bundles.
13. OpenSSF Scorecard target score >= 7.

## Acceptance criteria

- **AC1**: `docs/adr/` contains thirteen files `0001-` .. `0013-` matching the candidate order above, plus `docs/adr/README.md` explaining the numbering and status vocabulary (`proposed`, `accepted`, `rejected`, `superseded`).
- **AC2**: Every ADR contains the four headings `## Context`, `## Decision`, `## Consequences`, `## Go/no-go checklist` (verified by `grep -c`).
- **AC3**: Every ADR's go/no-go checklist includes the three mandatory lines: zero-install feasibility, prerequisite sibling tasks, conformance/verification method.
- **AC4**: No file under `web/`, `cli/`, `mcp/`, or `.github/workflows/` is modified by this track (`git diff --stat <base>..HEAD -- web cli mcp .github/workflows` is empty).
- **AC5**: CI leak-prevention gate passes; ADRs refer to "standard replay tools", "agent harnesses", and "cloud provider" rather than product or vendor names.

## Non-functional constraints

- Each ADR is under 400 words excluding the checklist.
- An ADR that concludes "no-go" is still a complete deliverable.

## External gates

- **G1 (publication)**: no push without user authorization.
- **G5 (external accounts)**: Trusted Publishing, Sigstore, and Scorecard require repository/organisation settings on the hosting platform and package index; ADRs 0011–0013 list the required settings but changing them is a user action.

## Out of scope

- Any implementation of the thirteen candidates; adding vendored libraries; changing the MCP server; release workflow changes (`release_and_packaging_20260905`).
