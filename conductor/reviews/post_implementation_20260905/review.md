# Post-implementation review — 2026-09-05

Reviewed current source from baseline 748d468 through 2f13d9cffe3333623020ee8204b5cdb6dc7e43d9. The earlier completion labels were evidence to inspect, not acceptance by themselves.

## Findings and disposition

| Track | Disposition | Review result |
| --- | --- | --- |
| core_engine_politeness | Passed | Output pacing now reserves distinct slots; huge Retry-After values remain finite. The crawler remains single-flight. |
| warc_iso28500_engine | Passed | Header hygiene, real SHA-256, revisit linkage and OPFS roundtrips validated through successor-track tests. CLI gzip decoding was corrected before encoding headers are removed. |
| in_browser_replay_viewer | Passed | Case/slash collisions, stale reader state, unbounded lengths and raw unsandboxed tab opening were fixed in successor tracks. Live base-href replay is intentionally superseded by the security specification. |
| cross_platform_hardening | Passed | Linux wrapper used bash despite its POSIX objective; corrected. Root wrappers and station server reviewed. Native Windows double-click execution was not run on this host; hosted multi-OS CLI help smoke is separate evidence. |
| headless_cli_mcp | Passed | The validate_profile tool previously accepted unsafe rates and incomplete profiles; it now checks the bundled schema. RPC parse/envelope/parameter errors and notifications follow their protocol semantics without traceback disclosure. |
| ci_cd_repo_hardening | Passed | Original workflow, matrix, compilation, profile checks, leak gate and governance files reviewed. Existing mutable CI pins/permissions are the explicitly pre-approved security-track handoff; that qualification track stays open. No claim of complete security qualification is made here. |
| engine_correctness_20260905 | Passed | Robots probing consumed the final delay and could allow a page after cancellation; probes now precede a fresh page gate, interrupted tasks remain pending, unavailable robots policies fail closed, and implicit browser redirects are disabled. |
| warc_interop_20260905 | Passed | Reader URL normalization collapsed distinct resources and malformed lengths could loop; verifier accepted empty/truncated containers and raised on malformed CDX numbers. Regressions now cover all those paths, state reset and record-ID/digest revisit resolution. |
| web_console_security_20260905 | Passed | Raw HTML could open outside the sandbox; it is now downloaded. CSP precedes untrusted pre-head markup, refresh metadata is removed, frame src is reset, gzip inputs are decompressed, parser warnings are surfaced, default OPFS filenames are unique, and checkpoints cannot change profile or scope. |
| cli_parity_20260905 | Passed | urllib automatic redirects bypassed the gate and scope. Redirects now re-enter the gated frontier. gzip/deflate bodies are decoded before archival header normalization. Duplicate query order, IPv6, semicolon paths and depth zero are preserved. |
| security_gates_and_fuzzing_20260905 | Blocked | Observed hosted run 33951784808 failed: Python 3.11 could not install atheris 3.1.0; Node 22 did not discover a directory argument. Corrected the dependency marker and test expansion. SARIF now rejects malformed/failed scans and resolves ruleIndex. F1/AC8 reopened; a new successful hosted run remains required. |
| repo_standards_alignment_20260905 | Blocked | README mixed implemented OPFS/request/frontier support with planned features. Corrected the capability table and deprecated concurrency default. Managed workflows match their pinned templates; isolated package entry points pass. T11/AC9 still requires authorized hosted ruleset work; Codecov activation remains separately pending. |

## Validation and limits

Python suites: ['37', '18']; Node tests: 36; 47 focused plan command blocks matched their expected behavior. Gitleaks found no leaks. The local all-gate passed with explicit skips for unavailable Bandit, Semgrep and zizmor. Actionlint passed security.yml. Both managed standards workflows match their pinned source templates. Isolated installation and all three entry points passed. Browser console/viewer smoke captured no warnings/errors.

The 211 Conductor integrity failures were reconciled by restoring canonical indexes, metadata and linked packs, retaining legacy evidence, correcting false completion at acceptance gates, and adding retrospective specifications for objective-only legacy tracks. No historical approval or hosted pass was fabricated.

Review changes intentionally strengthen some historical checks: retries are tested independently of robots availability; CSP is checked both before markup and in head; RPC parse errors use -32700 rather than preserving the historical -32603 bug.

The archive relocation receipt maps former active paths to archived paths; historical ledger artifact locations refer to the pre-move state.

The existing station-hardening archive was retained. Its metadata/index/evidence format was normalized without claiming a new station review.

A stray AppleDouble .idx sidecar was preserved under .git/metadata-artifacts, outside pack discovery; no actual Git pack was removed.

## Final archive result

Ten newly reviewed tracks were archived with one commit per relocation; eleven tracks are now archived in total and seven remain active. Full Conductor validation passes. All eighteen hash chains and every linked artifact hash verify after applying archive relocations. Track-health strict mode reports zero findings.

Security Gates & Fuzzing remains in progress pending a successful corrected hosted run (AC8/F1). Repository Standards Alignment remains in progress pending authorized ruleset work (T11/AC9); Codecov service activation remains a separate gate. No commits were pushed.

Formatting exception: one trailing blank line in the historical WARC evidence ledger was retained to preserve its exact original bytes; the canonical replacement ledger has valid chained events.
