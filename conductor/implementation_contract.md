# Implementation Contract

This is the protocol an implementing agent (human or model, of any size) follows to turn a **planned** Conductor track into merged commits without drift. It is a checklist, not guidance. Every step is mandatory. If a step cannot be completed exactly as written, record `blocked` and move on; never improvise.

Vocabulary: a **track** is a directory under `conductor/tracks/<track_id>/` with `index.md`, `spec.md`, `plan.md`, `metadata.json`, `evidence.jsonl`. A **task** is one `- [ ] T<n>` line in `plan.md` together with its `**Files**`, `**Change**`, `**Verify**`, `**Done when**`, `**Do not**` subsections. An **AC** is an acceptance criterion in `spec.md`.

---

## 0. Invariants that override everything below

1. Runtime is zero-install: Python 3 standard library only under `cli/` and `mcp/`; vanilla ES6+ only under `web/`. Development tooling goes only in `tests/requirements-dev.txt` and CI workflows.
2. Never write words that trip the CI leak-prevention gate (see step 3.4). The gate is authoritative; if it fails, your change is wrong, not the gate.
3. Never push without a `gate_authorized` G1 line in the track's `evidence.jsonl` written on the user's explicit instruction.
4. One task = one commit. Never bundle tasks.
5. You do not edit files owned by another active track (step 2.4).
6. You do not create files whose names start with `._`.

---

## 1. Session start

Run these in order. Stop at the first failure.

```bash
cd "$(git rev-parse --show-toplevel)"
test -z "$(git status --porcelain)" || { echo "STOP: working tree not clean"; exit 1; }
git pull --rebase
```

Read, in this order, without skipping:

1. `conductor/index.md`
2. `conductor/backlog.md` — a Markdown table with the columns `priority` (P0 highest .. P3 lowest), `track_id`, `task` (the `T<n>` id or a short label), `status` (`open`, `in_progress`, `blocked`, `done`), `owner` (agent or person id, or `-`), `blocked_by` (comma-separated `track_id/T<n>` references, or `-`). Rows under the heading `## Proposed` are not yet approved and are not selectable.
3. `AGENTS.md`
4. `conductor/implementation_contract.md` (this file)
5. The `spec.md` and `plan.md` of the track you select in 1.1.

### 1.1 Select exactly one task

```bash
# List candidate tracks in backlog file order (Approved table is already priority-sorted).
# Do not pipe to sort: lexicographic sort would reorder P0 tracks (cli_parity before engine_correctness).
grep -E '^\| *P[0-3] ' conductor/backlog.md
```

Skip heading/separator lines and any row whose `status` is not `open`/`in_progress`. Pick the FIRST remaining row that satisfies all of:

- `status` is `open` (or `in_progress` with `owner` equal to you);
- `blocked_by` is `-` or every referenced task is ticked `- [x]` in its own `plan.md`;
- the referenced track's `metadata.json.status` is `new` (canonical planned state), legacy `planned`, or `in_progress`;
- inside that track's `plan.md`, the task is the FIRST unchecked `- [ ] T<n>` in document order (tasks are ordered; do not skip ahead).

If no row qualifies, stop and report "no selectable task".

### 1.2 Claim the task

```bash
TRACK=<track_id>; TASK=T<n>
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
python3 - "$TRACK" "$TS" <<'EOF'
import json, sys
p = f"conductor/tracks/{sys.argv[1]}/metadata.json"
m = json.load(open(p))
if m["status"] in ("new", "planned"):
    m["status"] = "in_progress"
m["updated_at"] = sys.argv[2]
json.dump(m, open(p, "w"), indent=2); open(p, "a").write("\n")
EOF
printf '{"ts": "%s", "kind": "task_started", "task": "%s", "actor": "<your id>", "summary": "Started %s per implementation contract."}\n' "$TS" "$TASK" "$TASK" >> conductor/tracks/$TRACK/evidence.jsonl
```

Commit the claim on its own so parallel workers can see it:

```bash
git add conductor/tracks/$TRACK/metadata.json conductor/tracks/$TRACK/evidence.jsonl
git commit -m "chore(conductor): start $TASK [$TRACK]"
```

---

## 2. Task execution rules

### 2.1 Read the task block fully before touching anything

Every task has these subsections. If any is missing, the task is malformed: record `blocked` with summary `malformed task: missing <subsection>` and go to the next task.

```markdown
- [ ] T3 Short imperative title. *(AC2, AC5)*
  - **Files**: `path/one.py`, `path/two.js` (new)
  - **Change**: exact description; new files have full contents inline; edits quote the exact existing lines to replace.
  - **Verify**: fenced commands with the expected result stated.
  - **Done when**: observable conditions, each testable by a command above.
  - **Do not**: explicit prohibitions for this task.
```

### 2.2 Touch only the listed files

You may create or modify only the paths in `**Files**`, plus the track's own `plan.md`, `metadata.json`, `evidence.jsonl`. Nothing else, including "obvious" adjacent fixes. If the change genuinely requires another file, the task is wrong: record `blocked` with summary `needs file not in Files: <path>` and propose a backlog row (step 7).

### 2.3 Quoted snippets must match exactly

When `**Change**` quotes existing lines ("replace the following"), check they still exist verbatim:

```bash
grep -nF -- '<first line of quoted snippet>' <file> || echo "SNIPPET MISSING"
```

If the snippet does not match (moved, edited, deleted), STOP. Do not adapt. Append:

```json
{"ts": "...", "kind": "blocked", "task": "T3", "actor": "...", "summary": "Change snippet no longer matches", "context": "<the 5 lines currently at the expected location, plus the quoted snippet>"}
```

then move to the next task (step 1.1).

### 2.4 Ownership of files

Before editing any file, find who owns it:

```bash
rg -l --fixed-strings '<path>' conductor/tracks/*/plan.md
```

Then for each matching track check `metadata.json.status`. If any OTHER track with status `in_progress` lists the path, you do not have ownership: record `blocked` with summary `file owned by <track_id>` and move on. Tracks with status `completed` or `planned` do not block you. Additionally, never edit the files of another track's directory (`conductor/tracks/<other>/...`).

### 2.5 No new dependencies

No `pip install`, no `npm install`, no new imports outside the Python standard library in `cli/` or `mcp/`, no `<script src="https://...">` in `web/`. Vendored browser libraries are only allowed when the task explicitly lists the file under `web/lib/` and a `web/lib/VENDORED.json` entry with its SHA-256.

### 2.6 Attempt budget

You get at most 3 attempts per task (an attempt ends when a `**Verify**` command fails). After the third failure, revert your working changes for that task (`git checkout -- <files>`; delete new files), record `blocked` with the last failing output, and move on.

---

## 3. Verification

### 3.1 Run the task's Verify commands verbatim

Copy them from `plan.md`. Do not edit flags, paths, or expected values. If the actual output differs from the stated expectation, the task is blocked (step 6), not the expectation.

### 3.2 Run the repository baseline

```bash
# Compile every Python file
python3 -m py_compile $(git ls-files '*.py')
# Station hardening tests (always present)
python3 cli/test_station_hardening.py
# Python unit tests, when the directory exists
[ -d tests ] && python3 -m unittest discover -s tests -p 'test_*.py'
# JS tests, when present
[ -d tests/js ] && node --test tests/js
# --help smoke
python3 cli/launch.py --help >/dev/null && python3 cli/aegis_cli.py --help >/dev/null && python3 cli/warc_verify.py --help >/dev/null
```

If `scripts/gate.py` exists (owned by `security_gates_and_fuzzing_20260905`), `python3 scripts/gate.py test` replaces the block above; use it.

### 3.3 Profile schema check

```bash
python3 -c "import json,glob,os
s=json.load(open('profiles/schema.json'))
for p in glob.glob('profiles/*.json'):
    if os.path.basename(p)=='schema.json': continue
    d=json.load(open(p))
    for r in s.get('required',[]): assert r in d,(p,r)
print('profiles ok')"
```

### 3.4 Leak-prevention gate (exactly as CI runs it)

The forbidden pattern is stored base64-encoded in `.github/workflows/ci.yml` so that the words never appear in plain text. Reproduce it without typing the words:

```bash
FORBIDDEN_PATTERN=$(grep -oE '"[A-Za-z0-9+/=]{40,}"' .github/workflows/ci.yml | head -1 | tr -d '"' | base64 -d)
MATCHES=$(grep -rnI -E -i "$FORBIDDEN_PATTERN" --exclude-dir=.git . || true)
[ -z "$MATCHES" ] && echo "leak gate clean" || { echo "$MATCHES"; echo "LEAK GATE FAILED"; }
```

If it fails on your text, rewrite using neutral terms ("agent harnesses", "standard replay tools", "cloud provider", "collaboration platform").

### 3.5 Record the verification

Append one line summarising exact outcomes (test counts, exit codes). Do not paraphrase into "all good".

```json
{"ts": "...", "kind": "task_verified", "task": "T3", "actor": "...", "summary": "Verify: 3/3 commands passed. Baseline: py_compile OK (14 files); test_station_hardening 17/17; unittest 9 ran OK; leak gate clean; profiles ok."}
```

---

## 4. Commit

One task, one commit, containing:

- the task's files;
- `plan.md` with the task's box changed from `- [ ]` to `- [x]` and ` — commit <short-sha>` appended after you know the sha (amend once: `git commit --amend --no-edit` after editing the line, or write `pending` and fix in the next commit; prefer the amend);
- `metadata.json` with `updated_at` set to now;
- `evidence.jsonl` with `task_started`, `task_verified`, `task_completed` lines.

Message format (conventional commits, exactly):

```
<type>(<scope>): <summary> (T<n>, AC<m>[, AC<k>]) [<track_id>]
```

`type` in `feat|fix|chore|docs|refactor|test|ci`. `scope` is the top-level directory touched (`cli`, `web`, `mcp`, `scripts`, `conductor`, `docs`, `github`). Example:

```
feat(scripts): add claims audit that maps README claims to code checks (T1, AC1) [self_improvement_loop_20260905]
```

Never push. Pushing requires a line of kind `gate_authorized` with `"gate": "G1"` in the track's `evidence.jsonl`, written only when the user says so in the current session. If it is present: `git pull --rebase && git push`, then append `{"kind": "pushed", ...}`.

---

## 5. Track completion

When the last `- [ ]` in `plan.md` is ticked:

1. Change the `## Status:` line in `plan.md` to `## Status: COMPLETED (<date> — <one-line summary>)`.
2. Set `metadata.json.status` to `completed`, update `updated_at`.
3. Append ONE lesson to `conductor/lessons.md` following its header format: date, track_id, what surprised you, what the next planner should change. Be specific and generic at the same time: no organisation names, no secrets, no blame.
4. In `conductor/tracks.md`, change the track's `- [ ]` to `- [x]` and its `*Status:*` line to `*Status: Completed*`.
5. Update `index.md` of the track: `Status: completed (<date>)`.
6. Append `{"kind": "track_completed", ...}` to `evidence.jsonl`.
7. Commit: `chore(conductor): complete track '<track_id>'`.

---

## 6. Drift guards

- **3 attempts** per task, then `blocked` (step 2.6).
- **Expectations are frozen.** If a Verify command's expected output differs from reality, you record `blocked` with both values. You never change the expectation, the test, or the assertion to make it pass.
- **Time-box.** A task should take under 90 minutes of wall-clock work. If you exceed it, record `blocked` with summary `time-box exceeded` and what remains.
- **No refactoring beyond the task.** Do not rename, reformat, reorder, or "clean up" lines the task did not ask you to change. Diff size is a review signal; keep it minimal.
- **Unrelated failing tests are not yours to fix.** If a baseline command fails on code the task did not touch, record `blocked` with summary `baseline failure outside task scope: <command>` and add a `## Proposed` backlog row. Do not skip, delete, or mark the test expected-failure.
- **No speculative features.** If you see a "better" design, write a backlog proposal, not code.
- **Re-read before each commit.** Diff your staged changes against `**Files**`; anything extra gets unstaged.

---

## 7. Proposing new work

Append a row under `## Proposed` in `conductor/backlog.md`:

```markdown
| P2 | <track_id or `new`> | <short task label> | open | - | - |
```

Add one sentence below the table under `### Proposal notes` explaining the evidence (file, line, failing command). Never create a new track directory yourself: a track needs a `spec.md` with R/AC/G sections written by a planner and approved by the user. The `.github/ISSUE_TEMPLATE/improvement_proposal.yml` form produces the same columns for external contributors; the integrator moves approved rows above the `## Proposed` heading.

---

## Task template (copy into `plan.md` when planning)

```markdown
- [ ] T<n> <Imperative title>. *(AC<m>)*
  - **Files**: `<path>` (new|edit)
  - **Change**: <For new files: full contents in a fenced block. For edits: quote the exact existing lines under "Replace:" and give the exact new lines under "With:".>
  - **Verify**:
    ```bash
    <command 1>   # expected: <exact expectation>
    <command 2>   # expected: <exact expectation>
    ```
  - **Done when**: <condition 1>; <condition 2>.
  - **Do not**: <prohibition 1>; <prohibition 2>.
```

## Worked mini example

Task in `plan.md`:

```markdown
- [ ] T4 Add `docs/QUICKSTART.md`. *(AC3)*
  - **Files**: `docs/QUICKSTART.md` (new)
  - **Change**: create the file with exactly this content:
    ```markdown
    # Quickstart
    1. Clone the repository.
    2. Double-click the launcher for your OS.
    ```
  - **Verify**:
    ```bash
    test -f docs/QUICKSTART.md && wc -l < docs/QUICKSTART.md   # expected: 3
    ```
  - **Done when**: file exists with 3 lines; leak gate clean.
  - **Do not**: edit README.md.
```

Session:

```bash
git status --porcelain            # (empty)
git pull --rebase
# select T4 (first unchecked, blocked_by "-"), claim it:
#   metadata.json status -> in_progress; evidence task_started; commit "chore(conductor): start T4 [contributor_experience_20260905]"
rg -l --fixed-strings 'docs/QUICKSTART.md' conductor/tracks/*/plan.md
#   -> only contributor_experience_20260905/plan.md: I own it.
mkdir -p docs && printf '# Quickstart\n1. Clone the repository.\n2. Double-click the launcher for your OS.\n' > docs/QUICKSTART.md
test -f docs/QUICKSTART.md && wc -l < docs/QUICKSTART.md   # 3  -> matches expectation
python3 -m py_compile $(git ls-files '*.py') && python3 cli/test_station_hardening.py   # baseline OK
# leak gate (step 3.4) -> clean
# evidence: task_verified "Verify 1/1 OK (3 lines); baseline OK; leak gate clean"
# plan.md: "- [x] T4 ... — commit <sha>"; metadata.json updated_at; evidence task_completed
git add docs/QUICKSTART.md conductor/tracks/contributor_experience_20260905/{plan.md,metadata.json,evidence.jsonl}
git commit -m "docs(docs): add QUICKSTART page (T4, AC3) [contributor_experience_20260905]"
# no G1 line in evidence.jsonl -> do not push. Return to step 1.1.
```

If `docs/QUICKSTART.md` had already existed with different content, the correct action would have been `blocked` ("target file exists with unexpected content") rather than merging or overwriting.

## Post-review evidence compatibility

For metadata with `evidence_schema: "1.0"`, use the installed Conductor evidence-ledger helper to append canonical hash-chained events. The older ts/kind JSON snippets above are historical examples and must not be appended to a canonical ledger. Preserve `evidence.legacy.jsonl` unchanged. Read completed dependency plans in either `conductor/tracks/` or `conductor/archive/`; absence from the active directory alone is not a blocker. A pending gate that is part of acceptance keeps the track in progress even if all local code exists.
