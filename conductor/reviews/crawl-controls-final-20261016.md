# Review Report: Crawl controls, previews and site reports — T4–T7

## Summary

Accepted within the local synthetic/loopback scope: crawl decisions, previews,
reconciled reports and safe graph exports are implemented and verified; historical
integrity exceptions are preserved and excluded from current functional proof.

## Verification Checks

- [x] **Plan Compliance**: Yes — R1–R3 and AC1–AC3 map to retained source/tests in
  the [acceptance manifest](../tracks/crawl_controls_reports_20260906/acceptance.json).
- [x] **Style Compliance**: Pass — standard-library Python, vanilla browser APIs,
  focused changes and no new core dependencies. Protected launcher files unchanged.
- [x] **New Tests**: Yes — pre-body policy, malformed transport, receipt identity,
  preview, graph, stale-load and cold-console readiness regressions.
- [x] **Test Coverage**: Yes within the stated scope; no unexecuted platform run
  is represented as passing.
- [x] **Test Results**: All passed — 58 Python rule/report tests; 18 JS rule tests;
  full gate 301 Python (12 expected optional skips), 18 station, 80 JavaScript;
  25 real-browser tests. Strict Conductor health: zero findings across 35 tracks.
  Compilation, profile checks, CLI help, leak and whitespace checks passed.

## Acceptance and independent challenge

T4 (`cdd4f7b`) integrates rules into CLI/browser/native paths. Known URL exclusions
send no request; metadata-dependent exclusions close before response-body reads.
Conflicting/missing MIME, chunked/ambiguous lengths and malformed transfers retain
honest outcomes. Download-only captures do not traverse. Alias, query and bounded
cyclic-sitemap policies are exercised. Restrictions never expand caller scope.

T5 (`e404606`) supplies network-free previews and reports bound to their input
receipt. Counts and quantities must reconcile; missing/inaccessible resources
remain failures, pending or unsupported, never organisational absence. Actual CLI
receipts with fractional robots timestamps are accepted without rewriting them.
File/URL mode hashes exact UTF-8 source JSON; canonical generated mode is labelled
separately. Neither mode claims independent archive integrity verification.

T4 follow-up (`87c8022`) resolves reproduced cold-console resets by sequencing
trusted local dependencies. A single generated profile bundle remains static.
Exports/methods and bootstrap completion must succeed before controls become
active. Three fresh contexts, missing dependency, HTTP-200 empty dependency and
execution-error cases are verified. No captured source scripts are executed.

T6 (`197f4a7`) classifies recorded edges by explicit recorded scope, validates
endpoints and exports deterministic receipt-bound JSON and inert SVG. Up to
10,000 selected edges remain in JSON; diagrams/text display at most 500 with an
explicit clipping count. Shortened SVG labels retain full URLs in inert titles.
No source scripts, executable links or event attributes are included. Unknown
scope cannot be classified. Failed or superseded loads disable stale exports.

Independent reviewers Tesla and Chandrasekhar accepted their code/security/UI
scopes after findings were fixed. Final requirement/evidence review accepted the
functional scope, conditional only on append-only closeout records and accurate
metadata. Both conditions are implemented during T7. The coordinator also reran
the maintained native-capture browser suite: normal non-CORS capture, robots,
authentication, pause/resume, debug failures, USB failures and session recovery.

## Evidence integrity, not rewritten history

The manifest freezes a 28-event prefix: 18 of 19 artifact references resolve to
retained Git bytes. Every current functional artifact resolves. The inherited
status-only reference `186a30d4-533b-47af-b1f4-b40ec8b32eb6` has an unavailable
`4453f1ae…` fingerprint; retained bytes hash to `62ddd2f0…`. T7 explicitly
quarantines it. Its original event remains unchanged and is not counted as proof.

Original T1/T2 revisions `6bb387c…` and `e0483b0…` are unavailable. Retained
September 8 reconciliation records map them to `580cdb2` and `7149730`; this is
recovered lineage, not new verification of unavailable original bytes. Fresh
current-source tests and versioned artifacts independently support acceptance.
No exception-free historical-ledger claim is made. Later closeout receipts append
to the frozen prefix; they do not invalidate its count/tip.

To recheck the snapshot and all version-verified artifact bytes from the root:

```sh
python3 - <<'PY'
import hashlib, json, pathlib, subprocess
p = pathlib.Path('conductor/tracks/crawl_controls_reports_20260906')
m = json.loads((p / 'acceptance.json').read_text())['evidence_audit']
events = [json.loads(x) for x in (p / 'evidence.jsonl').read_text().splitlines()]
assert len(events) >= m['chain_event_count']
previous = None
for index, event in enumerate(events):
    value = dict(event)
    digest = value.pop('entry_sha256')
    assert value['previous_entry_sha256'] == previous
    assert hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == digest
    previous = digest
    if index + 1 == m['chain_event_count']:
        assert digest == m['chain_tip']
for ref in m['references']:
    if ref['status'] == 'version_verified':
        raw = subprocess.check_output(['git', 'show', ref['resolved_commit'] + ':' + ref['path']])
        assert hashlib.sha256(raw).hexdigest() == ref['sha256']
    else:
        assert ref['event_id'] == '186a30d4-533b-47af-b1f4-b40ec8b32eb6'
print('Chain and retained snapshot bytes verified; historical exception preserved.')
PY
```

## Use and reproduction

Launch the console and choose **Capture reports & rule preview**. Open a saved
`.coverage.json` receipt, inspect the reconciled data, or supply bounded rules and
candidates for a dry preview. Previewing never fetches those candidate URLs.
Select all/internal/external graph edges and export JSON or a scriptless SVG.
The displayed receipt fingerprint identifies the evidence input, not a finding
that the site or archive is complete.

Profiles support `target.crawl_rules` version 1, explicit `domain_aliases`, up to
32 `sitemap_seeds`, and `query_policy`: `strip_tracking` (default), `preserve` or
`drop`. Fragments are always removed. Legacy path-pattern fields accept bounded
literal alternatives such as `/logout|/signin`; migrate other regex syntax to
safe ordered rules rather than assuming its old semantics.

```sh
python3 -m unittest tests.test_crawl_rules
node --test tests/js/crawl_rules.test.js
python3 scripts/gate.py test
python3 scripts/track_health.py --strict
python3 scripts/gate.py leak
```

The browser run used the existing cached Playwright
`1.63.0-alpha-2026-08-31`, Chromium `153.0.8010.12`, macOS arm64 and Python 3.11.6:

```sh
NODE_PATH=/Users/doughnut/.npm/_npx/31e32ef8478fbf80/node_modules node /Users/doughnut/.npm/_npx/31e32ef8478fbf80/node_modules/playwright/cli.js test --config tests/browser/playwright.config.js tests/browser/capture.spec.js tests/browser/crawl_controls.spec.js tests/browser/crawl_startup.spec.js
```

The direct-browser loopback fixture grants network permission only in an
ephemeral test context. No user browser profile/settings were changed. These are
local checks, not new Windows/Linux qualification, hosted approvals, publication
or a complete-site guarantee. No push is authorised. Product definition, stack
and product guidelines require no strategic changes.
