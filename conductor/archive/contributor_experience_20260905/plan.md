# Track Plan: Contributor Experience

## Status: COMPLETED (2026-09-05 — contributor guidance, quickstart, support policy, and eight issue seeds delivered)

Implementers follow `conductor/implementation_contract.md`. Tasks are ordered. T1 depends on `scripts/gate.py` existing (`security_gates_and_fuzzing_20260905`); if it does not exist, record `blocked` and continue with T2/T3, which have no dependency.

## Phase 1 — Documents

- [x] T1 Rewrite `CONTRIBUTING.md` around the five-minute setup and the implementation contract. *(AC1, AC2, AC6)*

**Files**: `CONTRIBUTING.md` (edit: full replacement of the two sections below)

**Change**: `CONTRIBUTING.md` currently contains exactly these two sections after the title line (if the quoted text no longer matches, record `blocked`):

```markdown
## Architectural Principles
1. **Zero External Dependencies**: The core browser client and the CLI launcher must operate without third-party package installations (`pip`, `npm`, `Docker`).
2. **Server-Preserving Politeness**: All crawling capabilities must enforce rate limits, exponential backoff, and compliant RFC 9110 / RFC 9309 behavior.
3. **Standards-First**: Output must strictly adhere to ISO 28500:2017 (WARC/1.1) and CDX-11 indexing.
4. **Complete Abstraction**: No private, organizational, or domain-specific identifiers should ever be committed to the engine repository.

## Submitting Changes
1. Fork the repository and create a descriptive feature branch (`git checkout -b feature/my-enhancement`).
2. Verify all Python scripts pass syntax compilation: `python3 -m py_compile cli/*.py mcp/*.py`.
3. Verify JSON profiles validate against `profiles/schema.json`.
4. Ensure the abstraction audit passes: verify zero organizational or departmental identifiers exist in diffs.
5. Submit a Pull Request.
```

Replace the whole file with:

```markdown
# Contributing to AegisArchive

Thank you for helping. This page gets you from clone to a green local gate in five minutes and tells you exactly what a mergeable change looks like.

## 5-minute setup

1. Clone: `git clone <repository-url> && cd aegisarchive`
2. Run the local gate (tests, compile checks, leak gate): `python3 scripts/gate.py test`
3. Try the app: double-click `START_MAC.command`, `START_WINDOWS.cmd`, or run `./START_LINUX.sh`

That is all. The runtime is Python 3 standard library plus a modern browser; there is nothing to `pip install`, `npm install`, or containerise. Development-only tools (linters, fuzzers) live in `tests/requirements-dev.txt` and are optional.

## Picking a task

1. Open `conductor/backlog.md`. Rows are ordered by `priority` (P0 first). Take the first row whose `status` is `open` and whose `blocked_by` is `-`.
2. Open the row's track: `conductor/tracks/<track_id>/spec.md` (why) and `plan.md` (how). Your task is the first unchecked `- [x] T<n>` in that plan.
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

- [x] The PR implements exactly one task and references it as `T<n>` in the title.
- [x] `python3 scripts/gate.py test` passes locally; output summary pasted in the PR description.
- [x] Task box ticked in `conductor/tracks/<track_id>/plan.md` and a `task_verified` line appended to that track's `evidence.jsonl`.
- [x] No new runtime dependencies; no files starting with `._`.
- [x] No documentation claims about features that are not in this PR (see `scripts/claims_audit.py`).
- [x] If you noticed unrelated problems, they are listed under `## Proposed` in `conductor/backlog.md`, not fixed in this PR.

## Principles (unchanged)

1. **Zero external dependencies** at runtime.
2. **Server-preserving politeness**: every request goes through the politeness engine; rate limits, backoff, and `Retry-After` are honoured (RFC 9110 / RFC 9309).
3. **Standards first**: ISO 28500:2017 (WARC/1.1) and CDX-11 output.
4. **Complete abstraction**: no private, organisational, or domain-specific identifiers in this repository.

Questions: see `SUPPORT.md`. Security issues: see `SECURITY.md`.
```

**Verify**:

```bash
grep -n '^## ' CONTRIBUTING.md
# expected order: "## 5-minute setup", "## Picking a task", "## Making the change", "## Pull request checklist", "## Principles (unchanged)"
grep -c 'conductor/implementation_contract.md' CONTRIBUTING.md   # expected: >= 1
grep -c 'conductor/backlog.md' CONTRIBUTING.md                   # expected: >= 1
awk '/^## Picking a task/{exit} /`(pip|npm|docker) /{found=1} END{exit found}' CONTRIBUTING.md && echo "no package managers before Picking a task"   # expected: printed
test -f scripts/gate.py && echo "gate present"                    # expected: gate present (else record blocked on security_gates_and_fuzzing_20260905)
```

**Done when**: heading order matches; both links present; `scripts/gate.py` exists; leak gate clean.

**Do not**: mention `.devcontainer`, `pyproject.toml`, or release tooling (other tracks may add a line later); edit `README.md`; add vendor or product names.

- [x] T2 Add `docs/QUICKSTART.md` (ten lines). *(AC3, AC6)*

**Files**: `docs/QUICKSTART.md` (new; create the `docs/` directory)

**Change**: create the file with exactly this content:

```markdown
# AegisArchive Quickstart

1. Install nothing: you need only Python 3 and a modern browser.
2. Download or clone this repository and unzip it if needed.
3. macOS: double-click `START_MAC.command`. Windows: double-click `START_WINDOWS.cmd`. Linux: run `./START_LINUX.sh`.
4. Your browser opens the Web Console on a loopback address; nothing is exposed to the network.
5. Choose a profile (Default Polite is safe for public sites) and enter one or more seed URLs.
6. Press Start; the politeness engine paces requests and slows down if the server does.
7. Press Stop at any time; the capture so far is preserved.
8. Download the `.warc` and companion `.cdx` files when the run finishes.
9. Open `web/viewer.html` (Viewer link in the console) to browse the archive offline.
10. Headless use: `python3 cli/aegis_cli.py --profile profiles/default_polite.json --output-dir ./archive`; verify with `python3 cli/warc_verify.py <file.warc>`.
```

**Verify**:

```bash
grep -cE '^[0-9]+\. ' docs/QUICKSTART.md          # expected: 10
grep -E '^10\. ' docs/QUICKSTART.md | wc -l        # expected: 1
```

**Done when**: exactly ten numbered single-line steps; leak gate clean.

**Do not**: add screenshots, badges, or content duplicated from README beyond the launcher names; describe features that do not exist (check `scripts/claims_audit.py` output).

- [x] T3 Add `SUPPORT.md`. *(AC4, AC6)*

**Files**: `SUPPORT.md` (new)

**Change**: create the file with exactly this content:

```markdown
# Support

AegisArchive is maintained on a best-effort basis by volunteers.

## Where to ask

- **Usage questions and how-to**: open a GitHub Discussion if enabled, otherwise an issue using the *Bug report* template with the title prefix `[QUESTION]`.
- **Bugs**: use the *Bug report* issue template. Include your OS, Python version (`python3 --version`), browser and version, the profile used, and the last 20 lines of the console log.
- **Improvement ideas**: use the *Improvement proposal* issue template; it maps to the project backlog in `conductor/backlog.md`.
- **Security vulnerabilities**: do **not** open a public issue. Follow `SECURITY.md`.

## What to include

1. What you expected, what happened, and the smallest set of steps that reproduces it.
2. The exact command or button used and the output of `python3 cli/launch.py --help` if the launcher is involved.
3. Whether the target site is one you are authorised to archive. We do not help circumvent access controls or rate limits.

## Out of support scope

- Archiving sites you are not permitted to crawl.
- Disabling or weakening the politeness engine.
- Running on Python versions older than the one listed in `.github/workflows/ci.yml`.
- Third-party tools bundled by downstream distributions.

Response times are not guaranteed. Pull requests that follow `CONTRIBUTING.md` are the fastest route to a fix.
```

**Verify**:

```bash
grep -c 'SECURITY.md' SUPPORT.md            # expected: >= 1
grep -c 'Improvement proposal' SUPPORT.md   # expected: >= 1
test -f SECURITY.md && echo "security policy present"   # expected: printed
```

**Done when**: file exists with the three sections; links resolve to existing files; leak gate clean.

**Do not**: promise response times; add contact e-mail addresses or external chat links.

## Phase 2 — Entry-level work

- [x] T4 Create and label eight `good first issue` items, each linked to a concrete track task. *(AC5)*

**Files**: none in the repository (remote GitHub issues only); this track's `evidence.jsonl`.

**Change**: confirm `gh auth status` succeeds. Ensure the label exists:

```bash
gh label create "good first issue" --description "Small, well-bounded task with an exact plan" --color 7057ff --force
```

Then create one issue per row below. Before creating each, open the referenced track `plan.md` and confirm the task id still exists; if a task id has moved, use the current id for the same change and record it in `evidence.jsonl`. If the sibling track has not been registered yet, record `blocked` for that row only and create the other issues.

| # | title | track / task pointer | body summary |
| :-- | :-- | :-- | :-- |
| 1 | Emit the CDX `S` (record length) field | `warc_interop_20260905` — the task adding the `S` field to `web/lib/warc_writer.js` and `cli/aegis_cli.py` | Header ` CDX N b a m s k r M S V g` declares 11 fields; both writers emit 10. Add the compressed/record length as field 9. Verify: `python3 scripts/claims_audit.py` row `cdx11` becomes OK. |
| 2 | Escape URL, MIME, and status in the viewer URL list | `web_console_security_20260905` — the task escaping `innerHTML` interpolation in `web/viewer.html` (`renderUrlList`, around line 239) | Crawled data is interpolated into `li.innerHTML`. Reuse an `escapeHtml` helper like the one in `web/index.html`. Verify: a record whose URL contains `<img onerror>` renders as text. |
| 3 | Remove the unimplemented `decorrelated` enum value or implement it | `engine_correctness_20260905` — the task reconciling `profiles/schema.json` (`decorrelated`, line 92) with `web/lib/politeness_engine.js` | The schema accepts a jitter mode the engine does not branch on. Follow the track's decision (implement or drop). Verify: schema validation in CI still passes. |
| 4 | Case-insensitive HTTP header lookup in the CLI | `cli_parity_20260905` — the task fixing `headers.get('Content-Type')` in `cli/aegis_cli.py` | Servers may send `Content-type`; the CLI then misses HTML and crawls one page. Use a case-insensitive lookup. Verify: the track's fixture server with lower-case headers yields more than one page. |
| 5 | Add `WARC-Refers-To` to revisit records | `warc_interop_20260905` — the task adding `WARC-Refers-To: <record-id>` in both writers | Revisit records carry `WARC-Refers-To-Target-URI`/`-Date` but not the original record id. Store the id in the payload map and emit it. Verify: `python3 cli/warc_verify.py` on a run with duplicates shows the header. |
| 6 | Support `--cdx` offset checking in the verifier | `warc_interop_20260905` — the task extending `cli/warc_verify.py` to check CDX offsets (`V`) against record positions | `--cdx` is accepted but offsets are not cross-checked. Verify: a CDX with a wrong offset makes the verifier exit non-zero. |
| 7 | Read `?profile=` in the Web Console | `web_console_security_20260905` — the task making `web/index.html` honour the `?profile=` query the launcher sets (`cli/launch.py` line 233) | The launcher appends `?profile=<path>` but the console ignores it. Read `URLSearchParams` and preselect/load the profile. Verify: launching with `--profile` preselects it. |
| 8 | Stop stripping the `ref` query parameter | `engine_correctness_20260905` — the task revising the tracking-parameter list in `web/lib/core_crawler.js` (line 26) | `ref` is a legitimate routing parameter on many sites; stripping it changes page identity. Remove it from the strip list (keep `fbclid`, `gclid`, session ids). Verify: `canonicalizeUrl('https://example.com/a?ref=b')` keeps `ref`. |

Issue body template (fill `<...>` from the row; keep the two links):

```markdown
**Good first issue** — small, bounded, with an exact plan.

Track: `conductor/tracks/<track_id>/plan.md` — task `T<n>`.
Spec: `conductor/tracks/<track_id>/spec.md`.

**What**: <body summary>

**How**: follow `conductor/implementation_contract.md`. Touch only the files listed in the task. Run the task's Verify commands, then `python3 scripts/gate.py test`.

**Done when**: the task's *Done when* conditions hold and the PR title is `<type>(<scope>): <summary> (T<n>, AC<m>) [<track_id>]`.
```

Create each with:

```bash
gh issue create --title "<title>" --label "good first issue" --body-file /tmp/gfi_<n>.md
```

**Verify**:

```bash
gh issue list --label "good first issue" --state open --json number --jq length          # expected: 8
gh issue list --label "good first issue" --state open --json body --jq '.[].body' | grep -c 'conductor/tracks/'   # expected: 8
```

**Done when**: eight open issues; each body has the plan link and a `T<n>`; issue numbers recorded in `evidence.jsonl` as `task_completed` context.

**Do not**: implement any of the eight changes here; create issues for tasks whose track is not yet registered (record `blocked` instead); modify sibling track files.

## Phase 3 — Completion

- [x] T5 Final validation and completion per implementation contract step 5. *(AC1–AC6)*

**Files**: this track's `plan.md`, `metadata.json`, `evidence.jsonl`, `index.md`; `conductor/lessons.md` (one appended entry); `conductor/tracks.md` (this track's entry only)

**Change**: run the baseline and leak gate; set status `completed`; append the track's lesson; update the registry entry.

**Verify**:

```bash
python3 scripts/gate.py test 2>&1 | tail -n 3                    # expected: all checks pass (or the baseline block from the contract if gate.py is absent)
FORBIDDEN_PATTERN=$(grep -oE '"[A-Za-z0-9+/=]{40,}"' .github/workflows/ci.yml | head -1 | tr -d '"' | base64 -d); grep -rnI -E -i "$FORBIDDEN_PATTERN" --exclude-dir=.git . || echo "leak gate clean"   # expected: leak gate clean
python3 scripts/track_health.py | tail -n 1                       # expected: 0 finding(s)
```

**Done when**: all boxes ticked; `metadata.json.status` is `completed`; lesson appended.

**Do not**: push (G1).
