# Track Plan: Self-Improving System Loop

## Status: PLANNED

Implementers follow `conductor/implementation_contract.md`. Tasks are ordered; take the first unchecked one. Every task lists **Files / Change / Verify / Done when / Do not**. Files quoted in full are to be created byte-for-byte as shown.

## Phase 1 — Audit scripts (stdlib only)

- [x] T1 Add the documentation-claims audit script. *(AC1, AC8)* (8964d0a)

**Files**: `scripts/claims_audit.py` (new)

**Change**: create the file with exactly this content:

```python
#!/usr/bin/env python3
"""
AegisArchive - Claims Audit

Maps user-facing capability claims (README, AGENTS.md) to mechanical checks
against the code. Prints a Markdown table; exits 1 when any claim is not
backed by code, unless --allow-fail is given (scheduled report mode).

Python 3 standard library only.
"""

import argparse
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TEXT_EXT = ('.js', '.py', '.html', '.json', '.md', '.yml', '.yaml', '.txt')


def iter_files(*rel_dirs):
    for rel in rel_dirs:
        base = os.path.join(ROOT, rel)
        if os.path.isfile(base):
            yield base
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in ('.git', '__pycache__', 'node_modules')]
            for name in filenames:
                if name.startswith('._'):
                    continue
                if name.endswith(TEXT_EXT):
                    yield os.path.join(dirpath, name)


def grep(pattern, *rel_dirs):
    """Return list of 'relpath:line' hits for a regex across the given dirs/files."""
    rx = re.compile(pattern)
    hits = []
    for path in iter_files(*rel_dirs):
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
                for n, line in enumerate(fh, 1):
                    if rx.search(line):
                        hits.append(f"{os.path.relpath(path, ROOT)}:{n}")
        except OSError:
            continue
    return hits


def claim_present(pattern, *rel_dirs):
    """A claim is 'made' when the pattern appears in the documentation sources."""
    return bool(grep(pattern, *rel_dirs))


def check_cdx_field_count():
    """Run the Python WARC writer and count CDX fields on header and data rows."""
    sys.path.insert(0, os.path.join(ROOT, 'cli'))
    try:
        import aegis_cli  # noqa: E402
    except Exception as exc:  # pragma: no cover
        return False, f"import failed: {exc}"
    with tempfile.TemporaryDirectory() as tmp:
        warc = os.path.join(tmp, 'audit.warc')
        w = aegis_cli.PythonWarcWriter(warc)
        w.write_response('http://localhost/audit', 200, {'Content-Type': 'text/html'}, b'<html>audit</html>')
        w.close()
        with open(os.path.join(tmp, 'audit.cdx'), 'r', encoding='utf-8') as fh:
            header, row = fh.readline(), fh.readline()
    h = len(header.split()) - 1  # drop leading 'CDX' token
    r = len(row.split())
    return (h == 11 and r == 11), f"header declares {h} fields, data row has {r}"


CLAIMS = [
    # (id, claim text, where claimed, checker) -- checker returns (ok, detail)
    ("opfs", "OPFS streaming is used for large captures",
     lambda: claim_present(r'OPFS', 'README.md', 'AGENTS.md'),
     lambda: (bool(grep(r'new OpfsStreamer', 'web')), 'new OpfsStreamer in web/')),
    ("request_records", "Captures true HTTP request/response payloads",
     lambda: claim_present(r'request/response', 'README.md'),
     lambda: (bool(grep(r'WARC-Type: request', 'web/lib', 'cli')), 'WARC-Type: request emitted by a writer')),
    ("state_persistence", "IndexedDB state persistence / checkpointing",
     lambda: claim_present(r'IndexedDB', 'README.md'),
     lambda: (bool(grep(r'indexedDB|localStorage', 'web')), 'indexedDB or localStorage used in web/')),
    ("cdx11", "Companion CDX-11 indexes",
     lambda: claim_present(r'CDX-11', 'README.md'),
     check_cdx_field_count),
    ("revisit", "SHA-256 deduplication emits warc/revisit records",
     lambda: claim_present(r'warc/revisit', 'README.md'),
     lambda: (bool(grep(r'WARC-Type: revisit', 'web/lib', 'cli')), 'WARC-Type: revisit emitted by a writer')),
    ("mcp_tools", "MCP tools list_profiles, search_archive, validate_profile",
     lambda: claim_present(r'validate_profile', 'README.md'),
     lambda: (all(grep(rf'{t}', 'mcp/server.py') for t in ('list_profiles', 'search_archive', 'validate_profile')),
              'all three tool names present in mcp/server.py')),
    ("retry_after", "Respects Retry-After headers",
     lambda: claim_present(r'Retry-After', 'README.md'),
     lambda: (bool(grep(r'Retry-After|retry-after', 'web/lib/politeness_engine.js')), 'Retry-After parsed in politeness engine')),
]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Audit documentation claims against code.")
    ap.add_argument('--allow-fail', action='store_true', help='exit 0 even when claims are unbacked (report mode)')
    args = ap.parse_args(argv)

    rows = []
    failures = 0
    for cid, text, claimed, checker in CLAIMS:
        is_claimed = claimed()
        try:
            ok, detail = checker()
        except Exception as exc:  # keep the report going
            ok, detail = False, f"checker error: {exc}"
        if not is_claimed:
            status = 'NOT CLAIMED'
        elif ok:
            status = 'OK'
        else:
            status = 'MISMATCH'
            failures += 1
        rows.append((cid, text, status, detail))

    print("| id | claim | status | check |")
    print("| :-- | :-- | :-- | :-- |")
    for cid, text, status, detail in rows:
        print(f"| `{cid}` | {text} | {status} | {detail} |")
    print()
    print(f"{failures} mismatch(es) out of {len(rows)} claims.")
    if failures and not args.allow_fail:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
```

**Verify**:

```bash
python3 -m py_compile scripts/claims_audit.py                 # expected: exit 0, no output
python3 scripts/claims_audit.py; echo "exit=$?"               # expected: Markdown table with 7 rows, "4 mismatch(es) out of 7 claims.", exit=1
python3 scripts/claims_audit.py --allow-fail >/dev/null; echo "exit=$?"   # expected: exit=0
```

If the mismatch count differs from 4 because a sibling track has already landed a fix (for example `warc_interop_20260905` adding request records), record the actual count in `evidence.jsonl` `task_verified`; the pass condition is "exit 1 when at least one row is MISMATCH, exit 0 with `--allow-fail`". If all rows are OK, exit must be 0 in both modes.

**Done when**: both exit codes match; the table lists ids `opfs`, `request_records`, `state_persistence`, `cdx11`, `revisit`, `mcp_tools`, `retry_after`; leak gate clean.

**Do not**: import anything outside the standard library; modify README.md or any file under `web/`, `cli/`, `mcp/`; "fix" a claim by weakening its check.

- [x] T2 Add the Conductor track-health script. *(AC2, AC3, AC8)* (b009016)

**Files**: `scripts/track_health.py` (new)

**Change**: create the file with exactly this content:

```python
#!/usr/bin/env python3
"""
AegisArchive - Conductor Track Health

Parses every conductor/tracks/*/ directory (metadata.json, plan.md,
evidence.jsonl) plus conductor/backlog.md and reports:

  - in_progress tracks older than 14 days (by metadata.updated_at)
  - completed tracks that still have unticked plan boxes
  - planned tracks without spec.md
  - tracks with metadata.json but no evidence.jsonl (or an empty one)
  - backlog rows whose track_id has no track directory
  - completed tracks without an entry in conductor/lessons.md
  - legacy tracks (plan.md only, no metadata.json) as informational

Output is Markdown. Exit code is 0 unless --strict is given and at least one
finding exists. Python 3 standard library only.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACKS = os.path.join(ROOT, 'conductor', 'tracks')
BACKLOG = os.path.join(ROOT, 'conductor', 'backlog.md')
LESSONS = os.path.join(ROOT, 'conductor', 'lessons.md')
STALE_DAYS = 14

UNTICKED = re.compile(r'^\s*- \[ \]', re.M)
TICKED = re.compile(r'^\s*- \[x\]', re.M | re.I)
FENCE = re.compile(r'^```.*?^```[ \t]*$', re.M | re.S)


def strip_fences(text):
    """Remove fenced code blocks so quoted file contents are not counted as tasks."""
    return FENCE.sub('', text)


def read(path):
    with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
        return fh.read()


def parse_ts(value):
    try:
        return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def load_tracks():
    tracks = []
    if not os.path.isdir(TRACKS):
        return tracks
    for name in sorted(os.listdir(TRACKS)):
        d = os.path.join(TRACKS, name)
        if not os.path.isdir(d) or name.startswith('.'):
            continue
        t = {'id': name, 'dir': d, 'meta': None, 'plan': '', 'spec': False, 'evidence_lines': 0}
        mp = os.path.join(d, 'metadata.json')
        if os.path.isfile(mp):
            try:
                t['meta'] = json.loads(read(mp))
            except json.JSONDecodeError as exc:
                t['meta_error'] = str(exc)
        pp = os.path.join(d, 'plan.md')
        if os.path.isfile(pp):
            t['plan'] = strip_fences(read(pp))
        t['spec'] = os.path.isfile(os.path.join(d, 'spec.md'))
        ep = os.path.join(d, 'evidence.jsonl')
        if os.path.isfile(ep):
            t['evidence_lines'] = sum(1 for line in read(ep).splitlines() if line.strip())
        tracks.append(t)
    return tracks


def backlog_track_ids():
    ids = []
    if not os.path.isfile(BACKLOG):
        return ids
    for line in read(BACKLOG).splitlines():
        m = re.match(r'^\|\s*P[0-3]\s*\|\s*([^|]+?)\s*\|', line)
        if m:
            ids.append(m.group(1).strip('` '))
    return ids


def lesson_track_ids():
    if not os.path.isfile(LESSONS):
        return set()
    return set(re.findall(r'^## \d{4}-\d{2}-\d{2} — (\S+)', read(LESSONS), re.M))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Report conductor track health as Markdown.")
    ap.add_argument('--strict', action='store_true', help='exit 1 when any finding exists')
    ap.add_argument('--now', default=None, help='override current time (ISO-8601 UTC, for tests)')
    args = ap.parse_args(argv)

    now = parse_ts(args.now) if args.now else datetime.now(timezone.utc)
    tracks = load_tracks()
    lessons = lesson_track_ids()
    findings = []
    info = []

    print("# Conductor track health\n")
    print("| track | type | status | unticked | ticked | evidence lines | spec |")
    print("| :-- | :-- | :-- | --: | --: | --: | :-- |")
    for t in tracks:
        meta = t['meta'] or {}
        status = meta.get('status', 'legacy')
        unt = len(UNTICKED.findall(t['plan']))
        tick = len(TICKED.findall(t['plan']))
        print(f"| `{t['id']}` | {meta.get('type', '-')} | {status} | {unt} | {tick} | {t['evidence_lines']} | {'yes' if t['spec'] else 'no'} |")

        if 'meta_error' in t:
            findings.append(f"`{t['id']}`: metadata.json is not valid JSON ({t['meta_error']})")
            continue
        if t['meta'] is None:
            info.append(f"`{t['id']}`: legacy track (plan.md only; no metadata.json)")
            continue
        if status == 'in_progress':
            upd = parse_ts(meta.get('updated_at'))
            if upd is None:
                findings.append(f"`{t['id']}`: in_progress without a parseable updated_at")
            elif (now - upd).days > STALE_DAYS:
                findings.append(f"`{t['id']}`: in_progress for {(now - upd).days} days (> {STALE_DAYS})")
        if status == 'completed' and unt:
            findings.append(f"`{t['id']}`: completed but {unt} plan box(es) unticked")
        if status == 'completed' and t['id'] not in lessons:
            findings.append(f"`{t['id']}`: completed without an entry in conductor/lessons.md")
        if status == 'planned' and not t['spec']:
            findings.append(f"`{t['id']}`: planned without spec.md")
        if t['evidence_lines'] == 0:
            findings.append(f"`{t['id']}`: missing or empty evidence.jsonl")

    known = {t['id'] for t in tracks}
    for tid in backlog_track_ids():
        if tid not in known and tid != 'new':
            findings.append(f"backlog row references unknown track `{tid}`")

    print("\n## Findings\n")
    if findings:
        for f in findings:
            print(f"- {f}")
    else:
        print("- none")
    if info:
        print("\n## Informational\n")
        for i in info:
            print(f"- {i}")
    print(f"\n{len(findings)} finding(s) across {len(tracks)} track(s).")
    return 1 if (findings and args.strict) else 0


if __name__ == '__main__':
    sys.exit(main())
```

**Verify**:

```bash
python3 -m py_compile scripts/track_health.py                 # expected: exit 0
python3 scripts/track_health.py; echo "exit=$?"               # expected: Markdown table listing every dir under conductor/tracks/, legacy tracks under "## Informational", exit=0
# Strict-mode fixture (AC3): a completed track with an unticked box must produce a finding
TMP=$(mktemp -d) && cp -R conductor "$TMP/" && mkdir -p "$TMP/scripts" && cp scripts/track_health.py "$TMP/scripts/" \
  && printf -- '- [ ] Tx unfinished\n' >> "$TMP/conductor/tracks/portable_station_hardening_20260905/plan.md" \
  && python3 "$TMP/scripts/track_health.py" --strict | grep -c 'completed but 1 plan box'; echo "strict-exit=${PIPESTATUS[0]}"; rm -rf "$TMP"
# expected: 1 and strict-exit=1
```

**Done when**: non-strict run exits 0 on the current repository; strict fixture run exits 1 with the "completed but 1 plan box(es) unticked" finding; leak gate clean.

**Do not**: treat legacy plan-only tracks as findings; read or write anything outside `conductor/`; add third-party parsers.

## Phase 2 — Scheduled loop

- [ ] T3 Add the weekly self-improvement workflow. *(AC4, AC5, AC8)*

**Files**: `.github/workflows/self-improvement.yml` (new)

**Change**: create the file with exactly this content (do not edit `.github/workflows/ci.yml`, which is owned by `portable_station_hardening_20260905`):

```yaml
name: Self-Improvement Loop

on:
  schedule:
    - cron: '17 3 * * 1'   # weekly, Monday 03:17 UTC
  workflow_dispatch: {}

permissions:
  contents: write
  issues: write

concurrency:
  group: self-improvement
  cancel-in-progress: false

jobs:
  audit:
    name: Claims & Track Health Audit
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Baseline tests
        id: baseline
        continue-on-error: true
        run: |
          set -o pipefail
          {
            git ls-files '*.py' | xargs python3 -m py_compile && echo "py_compile: OK"
            python3 cli/test_station_hardening.py 2>&1 | tail -n 3
            if [ -d tests ]; then python3 -m unittest discover -s tests -p 'test_*.py' 2>&1 | tail -n 3; fi
            if [ -d tests/js ]; then node --test tests/js 2>&1 | tail -n 5; fi
          } | tee baseline.txt

      - name: Claims audit (report mode)
        run: python3 scripts/claims_audit.py --allow-fail | tee claims.md

      - name: Track health
        run: python3 scripts/track_health.py | tee health.md

      - name: Assemble report
        run: |
          mkdir -p audits/latest
          {
            echo "# Self-improvement report"
            echo
            echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ) from commit ${GITHUB_SHA::7}."
            echo
            echo "## Baseline tests"
            echo
            echo '```'
            cat baseline.txt
            echo '```'
            echo
            echo "## Claims audit"
            echo
            cat claims.md
            echo
            cat health.md
            echo
            echo "## How to act on this"
            echo
            echo "Each MISMATCH or finding should become a row under \`## Proposed\` in \`conductor/backlog.md\`, then a task in the owning track. Follow \`conductor/implementation_contract.md\`."
          } > audits/latest/self-improvement.md
          echo "REPORT_PATH=audits/latest/self-improvement.md" >> "$GITHUB_ENV"

      - name: Commit report
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add audits/latest/self-improvement.md
          if git diff --cached --quiet; then
            echo "Report unchanged; nothing to commit."
            exit 0
          fi
          git commit -m "chore(audits): weekly self-improvement report [skip ci]"
          git pull --rebase origin "${GITHUB_REF_NAME}"
          git push origin "HEAD:${GITHUB_REF_NAME}"

      - name: Upsert self-improvement issue
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          gh label create self-improvement --description "Automated weekly audit findings" --color 0E8A16 --force
          TITLE="Self-improvement report (automated)"
          {
            echo "Automated weekly audit. Full report: [\`audits/latest/self-improvement.md\`](https://github.com/${GITHUB_REPOSITORY}/blob/${GITHUB_REF_NAME}/audits/latest/self-improvement.md)"
            echo
            cat claims.md
            echo
            cat health.md
            echo
            echo "_Last run: $(date -u +%Y-%m-%dT%H:%M:%SZ) · workflow run [#${GITHUB_RUN_NUMBER}](https://github.com/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID})_"
          } > issue_body.md
          EXISTING=$(gh issue list --label self-improvement --state open --json number --jq '.[0].number // empty')
          if [ -n "$EXISTING" ]; then
            gh issue edit "$EXISTING" --title "$TITLE" --body-file issue_body.md
            echo "Updated issue #$EXISTING"
          else
            gh issue create --title "$TITLE" --label self-improvement --body-file issue_body.md
          fi
```

**Verify**:

```bash
python3 - <<'EOF'
import re
t = open('.github/workflows/self-improvement.yml').read()
for key in ('schedule:', 'workflow_dispatch:', 'permissions:', 'issues: write', 'contents: write', 'claims_audit.py --allow-fail', 'track_health.py', 'audits/latest/self-improvement.md', '[skip ci]', 'gh issue list --label self-improvement --state open'):
    assert key in t, key
print('workflow keys ok')
EOF
# expected: "workflow keys ok"
command -v actionlint >/dev/null && actionlint .github/workflows/self-improvement.yml && echo "actionlint ok"   # expected when actionlint installed: "actionlint ok"
```

After merge (integrator, not the implementer): trigger `workflow_dispatch` once; expected: a commit `chore(audits): weekly self-improvement report [skip ci]` on the default branch containing `audits/latest/self-improvement.md`, and exactly one open issue labelled `self-improvement`. Trigger a second time; expected: the same issue is edited, `gh issue list --label self-improvement --state open --json number --jq length` prints `1`.

**Done when**: key check passes; actionlint clean if available; the two post-merge expectations are recorded in `evidence.jsonl` by whoever runs them.

**Do not**: add third-party actions beyond `actions/checkout` and `actions/setup-python`; give the job more permissions than `contents: write` and `issues: write`; run fuzzers or Scorecard here (owned by other tracks).

- [ ] T4 Add the improvement-proposal issue form. *(AC6, AC8)*

**Files**: `.github/ISSUE_TEMPLATE/improvement_proposal.yml` (new)

**Change**: create the file with exactly this content:

```yaml
name: Improvement proposal
description: Propose a backlog item. Fields map 1:1 to the columns of conductor/backlog.md.
title: "[PROPOSAL] "
labels: ["proposal"]
body:
  - type: markdown
    attributes:
      value: |
        Proposals are appended under `## Proposed` in `conductor/backlog.md` by a maintainer. Read `conductor/implementation_contract.md` section 7 first. Do not include private hostnames, organisation names, or credentials.
  - type: dropdown
    id: priority
    attributes:
      label: priority
      description: P0 is highest.
      options:
        - P0
        - P1
        - P2
        - P3
      default: 2
    validations:
      required: true
  - type: input
    id: track_id
    attributes:
      label: track_id
      description: Existing track directory name under conductor/tracks/, or `new` if no track fits.
      placeholder: warc_interop_20260905
    validations:
      required: true
  - type: textarea
    id: task
    attributes:
      label: task
      description: One short imperative sentence, plus the evidence (file, line, failing command output) that motivates it.
    validations:
      required: true
  - type: dropdown
    id: status
    attributes:
      label: status
      options:
        - open
      default: 0
    validations:
      required: true
  - type: input
    id: owner
    attributes:
      label: owner
      description: GitHub handle of who intends to implement it, or `-`.
      placeholder: "-"
    validations:
      required: true
  - type: input
    id: blocked_by
    attributes:
      label: blocked_by
      description: Comma-separated `track_id/T<n>` references that must land first, or `-`.
      placeholder: "-"
    validations:
      required: true
```

**Verify**:

```bash
python3 - <<'EOF'
import re
t = open('.github/ISSUE_TEMPLATE/improvement_proposal.yml').read()
ids = re.findall(r'^\s+id: (\w+)$', t, re.M)
assert ids == ['priority', 'track_id', 'task', 'status', 'owner', 'blocked_by'], ids
print('issue form ids ok')
EOF
# expected: "issue form ids ok"
```

**Done when**: ids match the backlog columns in order; leak gate clean.

**Do not**: edit `bug_report.md` or `feature_request.md`; add fields that have no backlog column.

## Phase 3 — Governance wiring

- [ ] T5 Add the "Improvement Protocol" section to `AGENTS.md` (additive). *(AC7, AC8)*

**Files**: `AGENTS.md` (edit, append only)

**Change**: `AGENTS.md` currently ends with this block (quote must match exactly; if it does not, record `blocked`):

```markdown
## 🤖 Model Context Protocol (MCP) Maintenance

* When adding new tools to `mcp/server.py`:
  * Ensure inputs and outputs conform to standard JSON-RPC 2.0.
  * Update tool definitions in `tools/list` handler.
```

Append after the last line of the file (keep one blank line before the new `---`):

```markdown

---

## 🔁 Improvement Protocol

Autonomous agents implementing planned work follow `conductor/implementation_contract.md` exactly. In short:

1. Start from a clean tree; read `conductor/index.md`, `conductor/backlog.md`, this file, then the chosen track's `spec.md` and `plan.md`.
2. Take the first unchecked task of the highest-priority unblocked track; touch only the files that task lists; never edit files owned by another active track.
3. Run the task's Verify commands verbatim, then the repository baseline (or `python3 scripts/gate.py test` when present); record results in the track's `evidence.jsonl`.
4. One task = one commit; never push without a `gate_authorized` G1 entry from the user.
5. On track completion append one entry to `conductor/lessons.md`.
6. New ideas go to `## Proposed` in `conductor/backlog.md`, never straight into code.

The weekly `self-improvement` workflow audits documentation claims (`scripts/claims_audit.py`) and track hygiene (`scripts/track_health.py`) and reports to `audits/latest/self-improvement.md`.
```

**Verify**:

```bash
git diff --stat -- AGENTS.md                                    # expected: only insertions, 0 deletions
grep -c '^## 🔁 Improvement Protocol' AGENTS.md                  # expected: 1
grep -c 'conductor/implementation_contract.md' AGENTS.md         # expected: >= 1
grep -c 'conductor/lessons.md' AGENTS.md                         # expected: >= 1
grep -c 'conductor/backlog.md' AGENTS.md                         # expected: >= 1
```

**Done when**: all counts satisfied; `git diff` shows zero deleted lines; leak gate clean.

**Do not**: reorder, reword, or reformat existing sections; add vendor or product names.

- [ ] T6 Add maintenance rules to `conductor/lessons.md`. *(AC2, AC8)*

**Files**: `conductor/lessons.md` (edit, insert only)

**Change**: the file currently contains the line:

```markdown
Keep entries generic: no organisation names, hostnames, credentials, or personal blame. Reference commits by short SHA when useful. The weekly self-improvement report (`audits/latest/self-improvement.md`) lists tracks completed without a lesson, so an entry here is part of "done".
```

Insert immediately after that line (one blank line on each side):

```markdown
Maintenance rules:

1. Append only; entries are never edited or removed. Corrections are new entries beginning "Supersedes <date> — <track_id>:".
2. The heading must be exactly `## <YYYY-MM-DD> — <track_id>` so `scripts/track_health.py` can match completed tracks to lessons; use `repo` as the id only for repository-wide observations not tied to a track.
3. One entry per completed track is mandatory (implementation contract step 5). `scripts/track_health.py` reports completed tracks without an entry as a finding.
4. Planners read this file before writing a new `spec.md` and cite the entry they are acting on in the spec's "Authoritative inputs".
5. Entries are short: two bullets, under 120 words. Link evidence by path or short SHA instead of pasting logs.
```

**Verify**:

```bash
grep -c '^Maintenance rules:' conductor/lessons.md              # expected: 1
grep -c '^## 2026-09-05 — ' conductor/lessons.md                # expected: 3 (the seed entries are untouched)
python3 scripts/track_health.py | grep -c 'completed without an entry'   # expected: 0
```

**Done when**: counts match; the three seed entries are byte-identical to before (`git diff conductor/lessons.md` shows only the inserted block).

**Do not**: edit or reorder the seed entries; change the heading format.

## Phase 4 — Completion

- [ ] T7 Final validation and completion per implementation contract step 5. *(AC1–AC8)*

**Files**: `conductor/tracks/self_improvement_loop_20260905/plan.md`, `metadata.json`, `evidence.jsonl`, `index.md`; `conductor/lessons.md` (one appended entry); `conductor/tracks.md` (this track's entry only)

**Change**: run the full baseline and leak gate; set status `completed`; append the track's lesson; update the registry entry.

**Verify**:

```bash
git ls-files '*.py' | xargs python3 -m py_compile && echo compile-ok       # expected: compile-ok
python3 cli/test_station_hardening.py 2>&1 | tail -n 1                      # expected: OK
python3 scripts/track_health.py | tail -n 1                                 # expected: "0 finding(s) across N track(s)." once this track is completed
FORBIDDEN_PATTERN=$(grep -oE '"[A-Za-z0-9+/=]{40,}"' .github/workflows/ci.yml | head -1 | tr -d '"' | base64 -d); grep -rnI -E -i "$FORBIDDEN_PATTERN" --exclude-dir=.git . || echo "leak gate clean"   # expected: leak gate clean
```

**Done when**: all boxes above are ticked; `metadata.json.status` is `completed`; `conductor/lessons.md` has an entry with id `self_improvement_loop_20260905`.

**Do not**: push (G1).
