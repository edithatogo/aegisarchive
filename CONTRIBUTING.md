# Contributing to AegisArchive

Thank you for helping. This page gets you from clone to a green local gate in five minutes and tells you exactly what a mergeable change looks like.

## 5-minute setup

1. Clone: `git clone <repository-url> && cd aegisarchive`
2. Run the local gate (tests, compile checks, leak gate): `python3 scripts/gate.py test`
3. Try the app: double-click `START_MAC.command`, `START_WINDOWS.cmd`, or run `./START_LINUX.sh`

That is all. The runtime is Python 3 standard library plus a modern browser; there is nothing to `pip install`, `npm install`, or containerise. Development-only tools (linters, fuzzers) live in `tests/requirements-dev.txt` and are optional.

## Picking a task

1. Open `conductor/backlog.md`. Rows are ordered by `priority` (P0 first). Take the first row whose `status` is `open` and whose `blocked_by` is `-`.
2. Open the row's track: `conductor/tracks/<track_id>/spec.md` (why) and `plan.md` (how). Your task is the first unchecked `- [ ] T<n>` in that plan.
3. Each task has **Files**, **Change**, **Verify**, **Done when**, **Do not**. If anything in it is unclear or no longer matches the code, do not guess: comment on the tracking issue or open an "Improvement proposal" issue.
4. New to the project? Filter issues by the `good first issue` label; each one links to a task that fits in an hour.

The full procedure, including what to do when something does not match, is `conductor/implementation_contract.md`. It is short and binding.

## Making the change

- Touch only the files the task lists.
- Keep the runtime zero-install: standard library in `cli/` and `mcp/`, vanilla ES6+ in `web/`. Vendored browser libraries need an entry in `web/lib/VENDORED.json` with a SHA-256.
- Run the task's **Verify** commands verbatim, then `python3 scripts/gate.py test`.
- Never commit private hostnames, organisation names, or product/vendor names; the CI leak gate will fail the build and the text has to change, not the gate.
- One task = one commit = one pull request. Commit message: `<type>(<scope>): <summary> (T<n>, AC<m>) [<track_id>]`.

## Pull request checklist

- [ ] The PR implements exactly one task and references it as `T<n>` in the title.
- [ ] `python3 scripts/gate.py test` passes locally; output summary pasted in the PR description.
- [ ] Task box ticked in `conductor/tracks/<track_id>/plan.md` and a `task_verified` line appended to that track's `evidence.jsonl`.
- [ ] No new runtime dependencies; no files starting with `._`.
- [ ] No documentation claims about features that are not in this PR (see `scripts/claims_audit.py`).
- [ ] If you noticed unrelated problems, they are listed under `## Proposed` in `conductor/backlog.md`, not fixed in this PR.

## Principles (unchanged)

1. **Zero external dependencies** at runtime.
2. **Server-preserving politeness**: every request goes through the politeness engine; rate limits, backoff, and `Retry-After` are honoured (RFC 9110 / RFC 9309).
3. **Standards first**: ISO 28500:2017 (WARC/1.1) and CDX-11 output.
4. **Complete abstraction**: no private, organisational, or domain-specific identifiers in this repository.

Questions: see `SUPPORT.md`. Security issues: see `SECURITY.md`.
