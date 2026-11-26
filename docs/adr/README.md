# Architecture Decision Records

One file per decision: `docs/adr/NNNN-<slug>.md`, four-digit zero-padded, never renumbered. Headings are fixed: `## Context`, `## Decision`, `## Consequences`, `## Go/no-go checklist`.

Status vocabulary (first bullet under the title):

- `proposed` — written, not yet reviewed.
- `accepted` — approved; a follow-up track may be planned from it.
- `rejected` — decided against; keep the file.
- `superseded by NNNN` — replaced by a later ADR.

Rules:

1. An ADR is research output. It never ships code and never changes documentation claims.
2. Implementation happens in a separate Conductor track whose `spec.md` cites the ADR in "Authoritative inputs".
3. Every browser-library candidate states the zero-install delivery shape: standard Web API, Python standard library, or a single vendored file pinned by SHA-256 in `web/lib/VENDORED.json`.
4. Editing an accepted ADR is not allowed; write a new one that supersedes it.

Index: the files in this directory, sorted by number, are the index.

## Roadmap handoff

The four format and replay tracks form the current product roadmap. Each track has a focused first task and its own acceptance checks. The remaining ADRs retain the prerequisites below.

| ADR | Next decision or executable track |
| --- | --- |
| [0001 WACZ](0001-wacz-export.md) | [WACZ export](../../conductor/tracks/wacz_export_20261127/index.md) follows compressed WARC and CDXJ readback. |
| [0002 CDXJ](0002-cdxj-index.md) | [CDXJ index](../../conductor/tracks/cdxj_index_export_20261127/index.md) follows verified compressed spans. |
| [0003 WARC gzip](0003-warc-gz-compression-streams.md) | [Compressed WARC export](../../conductor/tracks/warc_gzip_export_20261127/index.md) starts with the existing finalized WARC. |
| [0004 Worker replay](0004-service-worker-replay.md) | [Isolated replay](../../conductor/tracks/isolated_worker_replay_20261127/index.md) starts with an actual browser scope check. |
| [0005 Scheduling](0005-prioritized-task-scheduling.md) | Use the existing headless job lifecycle. A concrete competing-job ordering requirement would justify a priority slice with a recovery fixture. |
| [0006 MCP](0006-mcp-2025-06-18-upgrade.md) | Identify a client that needs an archive resource and pin its protocol version before defining the first read-only resource. |
| [0007 Skills](0007-agent-skills-folder.md) | Reuse the existing repo-owned diagnostic skill and AGENTS.md. Add another skill when a distinct repeatable task needs one. |
| [0008 llms.txt](0008-llms-txt.md) | Reuse the maintained README and Conductor links. A demonstrated discovery gap can justify a short generated index with a link check. |
| [0009 Text extraction](0009-in-browser-text-extraction.md) | Reuse existing local extraction. Browser extraction needs a corpus and an offline fixture proving that separate runtime is necessary. |
| [0010 WebGPU](0010-webgpu-classification.md) | Requires the browser text corpus and an explicit local classification use case. |
| [0011 Publishing](0011-pypi-trusted-publishing.md) | Requires a qualified package, owner-approved package index enrollment and a published release. |
| [0012 Signing](0012-sigstore-signed-bundles.md) | Requires a real release workflow receipt and a documented independent verification path. |
| [0013 Scorecard](0013-scorecard-target.md) | Use the existing Scorecard workflow. Convert a specific unresolved control into a task when an actual report identifies it. |
