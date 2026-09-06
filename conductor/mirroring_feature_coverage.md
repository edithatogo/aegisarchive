# Mirroring roadmap coverage

All entries are planned, not delivered. Core static mirroring remains first.

| Capability | Owning track |
| --- | --- |
| Static resource graph, CSS and coverage receipts | mirror_capture_20260906 |
| Offline links, fragments, history and safe assets | offline_navigation_20260906 |
| Explicit HTTP/session acquisition and expiry | authenticated_acquisition_20260906 |
| Durable resume, revisions and conditional updates | mirror_resume_20260906 |
| Same-revision macOS/Windows acceptance | mirroring_platform_acceptance_20260906 |
| Scan/download rules, sitemap seeds, previews, link maps and reports | crawl_controls_reports_20260906 |
| Document inventory, versions, extraction/OCR, search and changes | document_lifecycle_20260906 |
| Optional JavaScript, lazy loading, login recipes and bounded headless capture | rendered_capture_20260906 |
| JSON jobs, CLI/MCP, scheduling, cancellation and retries | headless_jobs_20260906 |
| Static folder/ZIP, format interoperability and relocation | portable_exports_20260906 |

“Dynamic Document Management” is interpreted as a generic document lifecycle capability, not a named product or an organisation-specific system. Clarifying a different meaning would refine that track rather than invent product parity.

No blanket claim of preserving server-side applications, protected media or every interactive website is made. Retain the archived research ADRs; these new tracks implement selected gaps rather than claiming the research already delivered them.

## Execution granularity

The ten tracks now contain 78 pending tasks. Each slice names owned files, a focused verification command and acceptance criteria; fixture/schema tasks retain honest RED evidence. Core static acceptance remains independent of optional tiers. Browser-test provisioning has one owner, and dependency edges are recorded in both metadata and the backlog.

Shared crawler integration order: capture → crawl controls → authenticated acquisition → resume. Offline navigation can proceed after capture because it owns the reader/viewer rather than crawler files. Optional browser capture consumes completed authentication, controls and navigation tooling.
