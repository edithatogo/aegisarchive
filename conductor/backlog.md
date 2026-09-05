# Implementation Backlog

Select work using `conductor/implementation_contract.md`. Columns: `priority` (P0 highest), `track_id`, `task` (first implementable checkbox id), `status`, `owner`, `blocked_by`.

`grep -E '^\| *P[0-3] ' conductor/backlog.md | sort` lists selectable rows. Pick the first row with `status` `open` whose `blocked_by` is `-` or already ticked.

`cli/launch.py` is a read-only API from completed track `portable_station_hardening_20260905` (token auth, Host check, no CORS, `--verify`, `--idle-timeout`). Never edit another track's directory. Never edit `.github/workflows/ci.yml`.

Task ids are the first implementable checkbox in each `plan.md` (`T1`, `W1`, `S1`, `C1`, or `T0`). Remaining tasks stay in that plan; do not skip ahead.

## Approved

| priority | track_id | task | status | owner | blocked_by |
| --- | --- | --- | --- | --- | --- |
| P0 | engine_correctness_20260905 | T1 | done | - | - |
| P0 | warc_interop_20260905 | W1 | done | - | - |
| P0 | web_console_security_20260905 | S1 | done | - | - |
| P0 | cli_parity_20260905 | C1 | done | - | - |
| P1 | repo_standards_alignment_20260905 | T1 | done | - | - |
| P1 | security_gates_and_fuzzing_20260905 | T1 | done | - | - |
| P2 | self_improvement_loop_20260905 | T1 | in_progress | - | - |
| P2 | contributor_experience_20260905 | T1 | open | - | security_gates_and_fuzzing_20260905/T1 |
| P2 | release_and_packaging_20260905 | T1 | open | - | - |
| P3 | future_capabilities_20260905 | T0 | open | - | - |

Priority order for humans: engine correctness, WARC interop, web console security, CLI parity, then repository standards, security gates, self-improvement, contributor experience, release/packaging, future ADRs.

`future_capabilities_20260905` WACZ spikes (`T1` onward) wait on `warc_interop_20260905` correctness tasks even though `T0` (ADR index) is unblocked.

`self_improvement_loop_20260905` T5 (AGENTS Improvement Protocol) and lessons seed entries were applied by the integrator; implementers should treat those as already present and not rewrite them.

## G2 companion-program delegations

These items are not implemented in this repository. Status stays `blocked` here. No organisation or hostname names.

| priority | track_id | task | status | owner | blocked_by |
| --- | --- | --- | --- | --- | --- |
| P3 | companion_g2 | same-origin harvest | blocked | companion | G2 |
| P3 | companion_g2 | harvest manifest | blocked | companion | G2 |
| P3 | companion_g2 | text extraction | blocked | companion | G2 |
| P3 | companion_g2 | privacy screen on extracted text | blocked | companion | G2 |

In-browser harvest cannot rely on cross-origin CORS; same-origin harvest belongs in the companion program (G2), not in this engine.

## Proposed

Rows below are not selectable until moved into **Approved**.

| priority | track_id | task | status | owner | blocked_by |
| --- | --- | --- | --- | --- | --- |

### Proposal notes

(none)
