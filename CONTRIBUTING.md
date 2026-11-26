# Contributing to AegisArchive

Thank you for helping. Follow these steps to run the local checks and prepare a pull request.

## Local setup

1. Clone the repository and change into its directory.
2. Create and activate a repo-local `.venv` from a qualified Python 3.15.2 interpreter. Confirm `python -VV` reports 3.15.2.
3. Run `python scripts/gate.py test` for the test suites and `python scripts/gate.py leak` for the private identifier check.
4. Try the app by double-clicking `START_MAC.command` or `START_WINDOWS.cmd`, or running `./START_LINUX.sh`.

The application runs with the Python 3 standard library and a modern browser. Install the following tools for source development.

## Git hooks and repository checks

Install Gitleaks and actionlint on your PATH, then run the following with the repo-local environment activated.

```sh
python -m pip install pre-commit==4.7.0
pre-commit install
```

Commits check staged whitespace and secrets. Changes to workflow YAML also run actionlint. Run `pre-commit run --all-files` to check all workflows and catch any missing tools. The Gitleaks hook always scans the staged diff.

The [Repository health workflow](.github/workflows/repository-health.yml) runs TruffleHog on Git history patches reachable from the checked-out revision with credential verification disabled. TruffleHog's patch scan can omit changes introduced solely by merge conflict resolution. Logs show the detector, commit, line, path hash, and match counts. The fixture list matches eight reviewed synthetic URI values by commit, path, line, detector, and SHA-256. New matches fail the job. This workflow also runs alint for repository policy and reports the advisory RepoHealth score. The [security policy](SECURITY.md) describes the other scanners and private reporting.

## Picking a task

1. Open `conductor/backlog.md`. Rows are ordered by `priority` (P0 first). Take the first row whose `status` is `open` and whose `blocked_by` is `-`.
2. Open the row's track: `conductor/tracks/<track_id>/spec.md` (why) and `plan.md` (how). Your task is the first unchecked `- [ ] T<n>` in that plan.
3. Each task has **Files**, **Change**, **Verify**, **Done when**, **Do not**. If anything in it is unclear or no longer matches the code, do not guess: comment on the tracking issue or open an "Improvement proposal" issue.
4. New to the project? Filter issues by the `good first issue` label; each one links to a task that fits in an hour.

The full procedure, including what to do when something does not match, is `conductor/implementation_contract.md`. It is short and binding.

## Making the change

- Touch only the files the task lists.
- Keep the runtime zero-install: standard library in `cli/` and `mcp/`, vanilla ES6+ in `web/`. Vendored browser libraries need an entry in `web/lib/VENDORED.json` with a SHA-256.
- Run the task's **Verify** commands, then `python scripts/gate.py test` and `python scripts/gate.py leak` in the active repo-local environment.
- Never commit private hostnames, organisation names, or product/vendor names; the CI leak gate will fail the build and the text has to change, not the gate.
- One task = one commit = one pull request. Commit message: `<type>(<scope>): <summary> (T<n>, AC<m>) [<track_id>]`.

## Pull request checklist

- [ ] The PR implements exactly one task and references it as `T<n>` in the title.
- [ ] `python scripts/gate.py test` and `python scripts/gate.py leak` pass in the repo-local environment. Include the output summary in the PR description.
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
