# Track Plan: Future Capabilities (Research-First)

## Status: COMPLETED

Research-first: each candidate needs a spike task producing a decision note under `docs/adr/` before any implementation is planned. Implementers follow `conductor/implementation_contract.md`. Tasks T1–T13 are independent of each other after T0 and may be taken in any order, but T0 must be done first.

## Shared ADR template (used by T1–T13)

Every ADR file is created from this template. Replace `<...>` placeholders; keep every heading verbatim. The `## Go/no-go checklist` must contain the three mandatory lines marked *(mandatory)* plus the item-specific lines given in each task.

```markdown
# ADR <NNNN>: <Title>

- Status: proposed
- Date: <YYYY-MM-DD>
- Track: future_capabilities_20260905 / T<n>
- Deciders: <names or "maintainers">

## Context

<What the capability is, why it matters for AegisArchive, and what the current code does instead. 3–8 sentences. Cite files and lines.>

## Decision

<One of: "Go — plan a new track `<proposed_track_id>`", "No-go — <reason>", "Defer until <sibling track/task> lands". State the chosen delivery shape: standard Web API / Python stdlib only, or vendored single file (name, version, size, licence, SHA-256 plan), or not feasible under zero-install.>

## Consequences

<Positive, negative, and neutral consequences. Include maintenance burden, bundle size delta, security surface, and what documentation may claim once implemented (nothing before).>

## Go/no-go checklist

- [x] Zero-install feasibility confirmed: <Web API / stdlib / vendored single file with SHA-256 in web/lib/VENDORED.json / infeasible> *(mandatory)*
- [x] Prerequisite sibling tasks listed with track_id/T<n>: <...> *(mandatory)*
- [x] Verification method named (conformance tool, fixture, or test) that will prove the capability works: <...> *(mandatory)*
<item-specific lines>
```

Shared **Verify** for every ADR task (substitute the file name):

```bash
F=docs/adr/<NNNN>-<slug>.md
test -f "$F" && echo "exists"                                          # expected: exists
grep -c -E '^## (Context|Decision|Consequences)$' "$F"                  # expected: 3
grep -c '^## Go/no-go checklist$' "$F"                                  # expected: 1
grep -c '(mandatory)' "$F"                                             # expected: 3
wc -w < "$F"                                                           # expected: <= 700 (400 words body + checklist)
```

Shared **Do not** for every ADR task: do not modify anything under `web/`, `cli/`, `mcp/`, `.github/workflows/`; do not add vendored files; do not use product or vendor names (write "standard replay tools", "agent harnesses", "cloud provider"); do not describe the capability in README or AGENTS.md.

## Phase 0 — ADR scaffold

- [x] T0 Create `docs/adr/README.md` with numbering and status rules. *(AC1)*

**Files**: `docs/adr/README.md` (new; create directories)

**Change**: create the file with exactly this content:

```markdown
# Architecture Decision Records

One file per decision: `docs/adr/NNNN-<slug>.md`, four-digit zero-padded, never renumbered. Headings are fixed: `## Context`, `## Decision`, `## Consequences`, `## Go/no-go checklist`.

Status vocabulary (first bullet under the title):

- `proposed` — written, not yet reviewed.
- `accepted` — approved; a follow-up track may be planned from it.
- `rejected` — decided against; keep the file.
- `superseded by NNNN` — replaced by a later ADR.

Rules:

1. An ADR is research output. It never ships code and never changes documentation claims.
2. Implementation happens in a separate Conductor track whose `spec.md` cites the ADR in "Authoritative inputs".
3. Every browser-library candidate states the zero-install delivery shape: standard Web API, Python standard library, or a single vendored file pinned by SHA-256 in `web/lib/VENDORED.json`.
4. Editing an accepted ADR is not allowed; write a new one that supersedes it.

Index: the files in this directory, sorted by number, are the index.
```

**Verify**:

```bash
test -f docs/adr/README.md && grep -c '^- `' docs/adr/README.md    # expected: 4
```

**Done when**: file exists with the four status bullets; leak gate clean.

**Do not**: create any `NNNN-*.md` file in this task.

## Phase 1 — Archive format spikes (prerequisite: `warc_interop_20260905` correctness tasks)

- [x] T1 Spike: WACZ export. *(AC1, AC2, AC3)*

**Files**: `docs/adr/0001-wacz-export.md` (new)

**Change**: create from the shared template. Context must cover: WACZ = zip containing `archive/*.warc(.gz)`, `indexes/index.cdx(j)`, `pages/pages.jsonl`, `datapackage.json` (+ optional `datapackage-digest.json`); zip can be built in-browser with `CompressionStream('deflate-raw')` plus a hand-written local-file/central-directory writer (no library); the goal is opening the output directly in standard replay tools. Item-specific checklist lines:

```markdown
- [x] `datapackage.json` fields and `pages.jsonl` schema listed with source spec version
- [x] Zip writer strategy decided: streaming (OPFS-backed) vs in-memory, with size ceiling
- [x] Depends on CDXJ (ADR 0002) and on `warc_interop_20260905` payload-length/encoding fixes
- [x] Conformance: output opens in at least one standard replay tool and validates with its checker
```

**Verify**: shared Verify with `F=docs/adr/0001-wacz-export.md`.

**Done when**: shared Verify passes; the four item-specific lines are present.

**Do not**: shared Do not.

- [x] T2 Spike: CDXJ index alongside CDX-11. *(AC1, AC2, AC3)*

**Files**: `docs/adr/0002-cdxj-index.md` (new)

**Change**: shared template. Context: CDXJ lines are `<surt> <timestamp> <json>` with keys `url`, `mime`, `status`, `digest`, `length`, `offset`, `filename`; compare against the current CDX-11 header/row mismatch (see `conductor/lessons.md`); decide whether both indexes are emitted or CDXJ replaces CDX-11 in the UI download. Item-specific checklist lines:

```markdown
- [x] SURT canonicalisation differences between current `toSURT` and CDXJ expectations documented
- [x] Digest encoding decided (hex vs base32) and its effect on `warc_verify.py`
- [x] Depends on `warc_interop_20260905` CDX `S` field task
```

**Verify**: shared Verify with `F=docs/adr/0002-cdxj-index.md`. **Done when**: shared Verify passes; three item-specific lines present. **Do not**: shared Do not.

- [x] T3 Spike: `.warc.gz` via Compression Streams API. *(AC1, AC2, AC3)*

**Files**: `docs/adr/0003-warc-gz-compression-streams.md` (new)

**Change**: shared template. Context: per-record gzip members (each WARC record its own gzip stream) so offsets remain seekable; `CompressionStream('gzip')` availability in current browsers; effect on CDX offsets (`V` field) and on `cli/warc_verify.py` (Python `gzip` module, stdlib); memory profile for large captures. Item-specific checklist lines:

```markdown
- [x] Member-per-record layout confirmed against WARC/1.1 Annex on compression
- [x] Verifier strategy for multi-member gzip in Python stdlib described
- [x] Depends on `warc_interop_20260905` `.warc.gz` verifier task
```

**Verify**: shared Verify with `F=docs/adr/0003-warc-gz-compression-streams.md`. **Done when**: shared Verify passes; three item-specific lines present. **Do not**: shared Do not.

## Phase 2 — Replay and responsiveness spikes (prerequisite: `web_console_security_20260905` sandbox tasks)

- [x] T4 Spike: service-worker based replay. *(AC1, AC2, AC3)*

**Files**: `docs/adr/0004-service-worker-replay.md` (new)

**Change**: shared template. Context: current viewer injects `<base href>` pointing at the live origin, which leaks requests and breaks offline fidelity; a service worker can intercept fetches under a replay scope and serve bytes from the loaded WARC; constraints: service workers need a secure context (loopback `http://127.0.0.1` qualifies, `file://` does not), scope rules, and interplay with the iframe sandbox decided in `web_console_security_20260905`. Item-specific checklist lines:

```markdown
- [x] Fallback for `file://` opening documented (blob rewriting vs unsupported)
- [x] URL rewriting rules for HTML/CSS/JS inside the worker enumerated
- [x] Depends on `web_console_security_20260905` iframe sandbox and CSP tasks
```

**Verify**: shared Verify with `F=docs/adr/0004-service-worker-replay.md`. **Done when**: shared Verify passes; three item-specific lines present. **Do not**: shared Do not.

- [x] T5 Spike: Prioritized Task Scheduling API for pause responsiveness. *(AC1, AC2, AC3)*

**Files**: `docs/adr/0005-prioritized-task-scheduling.md` (new)

**Change**: shared template. Context: pause/stop in the console currently waits for in-flight timers; `scheduler.postTask` with priorities and `scheduler.yield()` allow the crawl loop to yield to UI input; browser support matrix and a `setTimeout` fallback must be stated; interaction with the politeness engine's timing guarantees. Item-specific checklist lines:

```markdown
- [x] Feature detection and fallback path specified (no behaviour change where unsupported)
- [x] Proof that politeness delays are never shortened by rescheduling
```

**Verify**: shared Verify with `F=docs/adr/0005-prioritized-task-scheduling.md`. **Done when**: shared Verify passes; two item-specific lines present. **Do not**: shared Do not.

## Phase 3 — Agent integration spikes

- [x] T6 Spike: MCP protocol upgrade to `2025-06-18`. *(AC1, AC2, AC3)*

**Files**: `docs/adr/0006-mcp-2025-06-18-upgrade.md` (new)

**Change**: shared template. Context: `mcp/server.py` advertises `protocolVersion` `2024-11-05` (line 111) with three tools; the newer revision adds `resources` (expose profiles and CDX indexes as `file://`-style resources), tool `annotations` (`readOnlyHint`, `destructiveHint`, `idempotentHint`), `outputSchema` with `structuredContent`, and version negotiation during `initialize`; all achievable in stdlib JSON-RPC over stdio. Item-specific checklist lines:

```markdown
- [x] Version negotiation behaviour for older clients decided (downgrade vs reject)
- [x] Resource URIs and MIME types for profiles and CDX listed
- [x] Every tool's annotations and outputSchema drafted
- [x] Depends on `cli_parity_20260905` shared test fixture for a smoke test
```

**Verify**: shared Verify with `F=docs/adr/0006-mcp-2025-06-18-upgrade.md`. **Done when**: shared Verify passes; four item-specific lines present. **Do not**: shared Do not; do not edit `mcp/server.py`.

- [x] T7 Spike: agent `skills/` folder with `SKILL.md`. *(AC1, AC2, AC3)*

**Files**: `docs/adr/0007-agent-skills-folder.md` (new)

**Change**: shared template. Context: agent harnesses discover task-specific instructions from a `skills/<name>/SKILL.md` file with front-matter (`name`, `description`) and a body; candidate skills: "archive a site politely", "verify a WARC", "pick a Conductor task"; must not duplicate `AGENTS.md` or `conductor/implementation_contract.md`, only point to them; the leak gate forbids vendor names so skills are written harness-neutral. Item-specific checklist lines:

```markdown
- [x] Skill list with one-line purpose each and the file each points to
- [x] Confirmed that no skill restates content owned by AGENTS.md or the implementation contract
```

**Verify**: shared Verify with `F=docs/adr/0007-agent-skills-folder.md`. **Done when**: shared Verify passes; two item-specific lines present. **Do not**: shared Do not; do not create `skills/`.

- [x] T8 Spike: `llms.txt` at repository root. *(AC1, AC2, AC3)*

**Files**: `docs/adr/0008-llms-txt.md` (new)

**Change**: shared template. Context: `llms.txt` is a plain-Markdown file giving agent harnesses a curated map of the project (title, summary, key links to README, AGENTS.md, contract, MCP config); must stay in sync with real capabilities (add a `scripts/claims_audit.py` row); no vendor-specific symlinked duplicates because of the leak gate. Item-specific checklist lines:

```markdown
- [x] Section list and link targets enumerated
- [x] Claims-audit row defined so `llms.txt` cannot advertise unimplemented features
```

**Verify**: shared Verify with `F=docs/adr/0008-llms-txt.md`. **Done when**: shared Verify passes; two item-specific lines present. **Do not**: shared Do not; do not create `llms.txt`.

## Phase 4 — Opt-in vendored intelligence spikes (zero-install rule: single vendored files, SHA-256 pinned in `web/lib/VENDORED.json`)

- [x] T9 Spike: in-browser text extraction with a vendored single-file PDF renderer. *(AC1, AC2, AC3)*

**Files**: `docs/adr/0009-in-browser-text-extraction.md` (new)

**Change**: shared template. Context: extracting text from captured PDFs/HTML enables local search (`minisearch.min.js` is already vendored as precedent); the PDF renderer ships as a main file plus a worker file, so "single file" needs a decision (bundle worker inline via `blob:` or accept two pinned files); licence (Apache-2.0) and size (~2–3 MB) must be recorded; opt-in toggle in the console, never loaded by default. Item-specific checklist lines:

```markdown
- [x] Worker delivery decided (inline blob vs second pinned file) and size ceiling
- [x] `web/lib/VENDORED.json` manifest schema drafted (file, version, sha256, source, license)
- [x] Verification: `cli/verify_bundle.py`-style SHA-256 check extended to VENDORED.json (task proposed to `security_gates_and_fuzzing_20260905`)
```

**Verify**: shared Verify with `F=docs/adr/0009-in-browser-text-extraction.md`. **Done when**: shared Verify passes; three item-specific lines present. **Do not**: shared Do not; do not add files to `web/lib/`.

- [x] T10 Spike: WebGPU classification with a vendored single-file transformer runtime. *(AC1, AC2, AC3)*

**Files**: `docs/adr/0010-webgpu-classification.md` (new)

**Change**: shared template. Context: on-device classification (language, document type, sensitivity flags) of captured text with a browser transformer runtime using WebGPU, falling back to WebAssembly; model weights are tens to hundreds of MB and must be fetched on explicit user action from a user-chosen source, cached in OPFS, and hashed; the runtime file itself is vendored and pinned; the politeness engine does not govern model downloads, so a separate consent step is needed. Item-specific checklist lines:

```markdown
- [x] Model acquisition and consent flow described (no automatic downloads)
- [x] WebGPU availability detection and WebAssembly fallback stated
- [x] Storage/eviction plan for cached weights in OPFS
- [x] Depends on ADR 0009 (text extraction) being accepted
```

**Verify**: shared Verify with `F=docs/adr/0010-webgpu-classification.md`. **Done when**: shared Verify passes; four item-specific lines present. **Do not**: shared Do not; do not add model files or runtime files.

## Phase 5 — Supply-chain spikes (prerequisite: `release_and_packaging_20260905` release workflow)

- [x] T11 Spike: PyPI Trusted Publishing for the CLI package. *(AC1, AC2, AC3)*

**Files**: `docs/adr/0011-pypi-trusted-publishing.md` (new)

**Change**: shared template. Context: `release_and_packaging_20260905` introduces `pyproject.toml` with zero runtime dependencies; Trusted Publishing uses OIDC from the CI workflow to the package index with no long-lived tokens; requires a pending publisher configured on the index (user action, gate G5) and an `environment: pypi` job with `id-token: write`. Item-specific checklist lines:

```markdown
- [x] Index-side settings the user must apply listed step by step (G5)
- [x] Package name availability and versioning scheme (CalVer per CHANGELOG) confirmed
- [x] Depends on `release_and_packaging_20260905` release workflow and pyproject tasks
```

**Verify**: shared Verify with `F=docs/adr/0011-pypi-trusted-publishing.md`. **Done when**: shared Verify passes; three item-specific lines present. **Do not**: shared Do not; do not edit release workflows.

- [x] T12 Spike: Sigstore-signed release bundles. *(AC1, AC2, AC3)*

**Files**: `docs/adr/0012-sigstore-signed-bundles.md` (new)

**Change**: shared template. Context: the release zip and `SHA256SUMS` can be keyless-signed in CI (`id-token: write`) producing `.sigstore` bundles; verification by end users requires a client, which conflicts with zero-install for the runtime but not for the release process; relation to SLSA provenance in the release track; what `cli/verify_bundle.py` can check with stdlib only (hashes, not signatures). Item-specific checklist lines:

```markdown
- [x] Which artefacts are signed and where bundles are attached
- [x] User verification instructions that do not require installing tooling to *run* the app
- [x] Depends on `release_and_packaging_20260905` SHA256SUMS/provenance tasks
```

**Verify**: shared Verify with `F=docs/adr/0012-sigstore-signed-bundles.md`. **Done when**: shared Verify passes; three item-specific lines present. **Do not**: shared Do not.

- [x] T13 Spike: OpenSSF Scorecard target >= 7. *(AC1, AC2, AC3)*

**Files**: `docs/adr/0013-scorecard-target.md` (new)

**Change**: shared template. Context: `repo_standards_alignment_20260905` adds the Scorecard workflow; this ADR records the current score once available, lists each check below full marks (branch protection, pinned dependencies by SHA, token permissions, fuzzing, SAST, signed releases) and maps each to the sibling track that closes it; sets the target and the review cadence via the weekly self-improvement report. Item-specific checklist lines:

```markdown
- [x] Baseline score and per-check results recorded from the first workflow run
- [x] Each failing check mapped to an owning track/task or marked accepted risk
- [x] Depends on `repo_standards_alignment_20260905` Scorecard workflow task
```

**Verify**: shared Verify with `F=docs/adr/0013-scorecard-target.md`. **Done when**: shared Verify passes; three item-specific lines present. **Do not**: shared Do not.

## Phase 6 — Completion

- [x] T14 Final validation and completion per implementation contract step 5. *(AC1–AC5)*

**Files**: this track's `plan.md`, `metadata.json`, `evidence.jsonl`, `index.md`; `conductor/lessons.md` (one appended entry); `conductor/tracks.md` (this track's entry only)

**Change**: verify the ADR set is complete; set status `completed`; append a lesson; update the registry entry. Accepted ADRs become proposals in `conductor/backlog.md` under `## Proposed` with `track_id` `new`.

**Verify**:

```bash
ls docs/adr/ | grep -cE '^00(0[1-9]|1[0-3])-.*\.md$'                    # expected: 13
for f in docs/adr/00*.md; do grep -c -E '^## (Context|Decision|Consequences|Go/no-go checklist)$' "$f"; done | sort -u   # expected: 4
git diff --stat "$(git merge-base HEAD origin/main)"..HEAD -- web cli mcp .github/workflows | wc -l   # expected: 0
FORBIDDEN_PATTERN=$(grep -oE '"[A-Za-z0-9+/=]{40,}"' .github/workflows/ci.yml | head -1 | tr -d '"' | base64 -d); grep -rnI -E -i "$FORBIDDEN_PATTERN" --exclude-dir=.git . || echo "leak gate clean"   # expected: leak gate clean
```

**Done when**: 13 ADRs plus README present; all headings verified; no runtime files touched; lesson appended; registry updated.

**Do not**: push (G1); create implementation tracks inside this task (they need their own spec, approved by the user).
