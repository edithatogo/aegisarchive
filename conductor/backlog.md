# Implementation Backlog

Select work using `conductor/implementation_contract.md`. Columns: `priority` (P0 highest), `track_id`, `task` (first implementable checkbox id), `status`, `owner`, `blocked_by`.

`grep -E '^\| *P[0-3] ' conductor/backlog.md` lists candidate rows in file order. Pick the first row with `status` `open` or `in_progress` whose `blocked_by` is `-` or already ticked.

`cli/launch.py` is a read-only API from completed track `portable_station_hardening_20260905` (token auth, Host check, no CORS, `--verify`, `--idle-timeout`). Never edit another track's directory. Never edit `.github/workflows/ci.yml`.

Task ids are the first implementable checkbox in each `plan.md` (`T1`, `W1`, `S1`, `C1`, or `T0`). Remaining tasks stay in that plan; do not skip ahead.

Archived tracks in `conductor/tracks.md` are `done` here. Hosted G1 work already recorded as satisfied on those packs is not a selectable blocker. Deployment-specific acquisition and acceptance belong outside this repository.

## Approved

| priority | track_id | task | status | owner | blocked_by |
| --- | --- | --- | --- | --- | --- |
| P0 | portable_intelligence_suite | T3 | done | - | - |
| P0 | portable_intelligence_suite | T4 | done | - | portable_intelligence_suite/T3 |
| P0 | engine_correctness_20260905 | T1 | done | - | - |
| P0 | warc_interop_20260905 | W1 | done | - | - |
| P0 | web_console_security_20260905 | S1 | done | - | - |
| P0 | cli_parity_20260905 | C1 | done | - | - |
| P0 | core_engine_politeness | T1 | done | - | - |
| P0 | warc_iso28500_engine | T1 | done | - | - |
| P0 | in_browser_replay_viewer | T1 | done | - | - |
| P0 | cross_platform_hardening | T1 | done | - | - |
| P0 | headless_cli_mcp | T1 | done | - | - |
| P0 | ci_cd_repo_hardening | T1 | done | - | - |
| P0 | portable_station_hardening_20260905 | T1 | done | - | - |
| P1 | repo_standards_alignment_20260905 | T11 | done | - | - |
| P1 | security_gates_and_fuzzing_20260905 | F1 | done | - | - |
| P2 | self_improvement_loop_20260905 | T1 | done | - | - |
| P2 | contributor_experience_20260905 | T1 | done | - | - |
| P2 | release_and_packaging_20260905 | T1 | done | - | - |
| P3 | future_capabilities_20260905 | T0 | done | - | - |

All approved repository tasks are complete. Deployment-specific work is not an AegisArchive completion gate.

## Scope boundary

AegisArchive is a general-purpose archival engine. Target selection, authentication, organisation-specific source registers, downstream document analysis and deployment acceptance belong in the consuming project. They must not appear as blocked engine tasks or carry client identities, internal hostnames or target lists into this repository.

Issues #13–#16 are retained only as closed scope records. Their former deployment work is outside this repository. Historical generic coordination receipts do not create a current engine dependency.

## Proposed

Rows below are not selectable until moved into **Approved**.

| priority | track_id | task | status | owner | blocked_by |
| --- | --- | --- | --- | --- | --- |

### Proposal notes

(none)
