# Native implementation and review checkpoint

**Completed:** final native qualification and review closeout passed. The dated sections below preserve earlier checkpoint limitations; this final decision supersedes their pending status.

## Issue #11 acquire session (2026-09-06)

Earlier `--acquire` with `--max-bytes 120000000` verified 58 locked artefacts on Darwin and size-skipped Scout/General/Deep GGUF weights. Receipt: [t3-locked-acquire.json](native-evidence/t3-locked-acquire.json).

A later Darwin `--acquire --require-complete` verified **61/61** locked files, including the three GGUF weight files, against `portable/model-lock.json`. Host: Darwin arm64. `runtimes_complete: true`, `models_complete: true`, `complete: true`, `inference_claimed: false`. Weight `fetch_result` values are `cached`: bytes were already present from a prior Darwin package cache and were re-hashed this session; this is not a fresh upstream download and is not native inference. Fail-closed empty-cache audit remains in [t3-empty-cache-audit.json](native-evidence/t3-empty-cache-audit.json). Receipts: [t3-locked-acquire-complete.json](native-evidence/t3-locked-acquire-complete.json), [t3-lock-cache-audit.json](native-evidence/t3-lock-cache-audit.json) (15/15 lock files verified). Linux/Windows native *execution* was not run.

Hosted `portable-native.yml` still uses `--max-bytes 120000000` on `ubuntu-latest` and `windows-latest` for pull requests. That job is checksum acquisition of smaller pins, not full GGUF intake and not OS-matrix execution.

## T3 session (2026-09-06)

Machinery: `provision_models.py --inventory` / `--audit`, `provision_native.py --inventory` / `--verify-bundle` / `--purge-undeclared-bytecode` / `--smoke-bundle`. An empty cache audit exits 1 with `inference_claimed: false`. A missing bundle writes `status: blocked` and `smoke: not_run`. Qualification smoke uses the bundle-owned script and records subprocess/JSON failures instead of crashing. Cache audit rejects dest and ancestor symlinks and hashes with `O_NOFOLLOW`. Speech inventory retains per-wheel SHA-256 pins. Full qualification and smoke set `PYTHONDONTWRITEBYTECODE=1`.

Acquired this session (HTTPS, SHA-256 pinned): all ten lock-file licence and model-card documents. Weights were not re-downloaded; they were verified in the existing Darwin assembled runtime.

Verified against `portable/model-lock.json`: all fifteen locked files, including the five weights (8,756,774,347 bytes). Receipt: [t3-model-audit.json](native-evidence/t3-model-audit.json).

Darwin model/runtime smoke (existing internal package): Scout, General and Deep each returned `ARCHIVE`; Piper synthesis and Whisper transcription; BGE-384 hybrid/semantic/graph; bundled Git 2.55.0; bundled console. Receipt: [t3-model-smoke.json](native-evidence/t3-model-smoke.json).

Darwin `--verify-bundle` first failed on 531 extra interpreter bytecode files. `--purge-undeclared-bytecode` removed those extras only; a later `--verify-bundle` passed (`status: verified`, 9,513 immutable files, `inference_claimed: false`, `smoke: not_run`). Receipt: [t3-bundle-verify.json](native-evidence/t3-bundle-verify.json).

Still blocked for T3 completion:

- Linux x64 and Windows x64 native runtimes/models were not provisioned or executed on this host. Hosted `portable-full-native.yml` remains the matrix gate.
- Empty cache audit correctly refused to claim models. [t3-empty-cache-audit.json](native-evidence/t3-empty-cache-audit.json).

Inventories: [t3-source-inventory.json](native-evidence/t3-source-inventory.json), [t3-model-inventory.json](native-evidence/t3-model-inventory.json), [t3-licence-fetch.json](native-evidence/t3-licence-fetch.json).

## Prior macOS acceptance (retained)

The internally stored macOS ARM64 package previously recorded a complete relocated sandbox run at [darwin-full-native.json](native-evidence/darwin-full-native.json).

## Remaining acceptance

T3 is not complete until Linux and Windows have direct native execution receipts. T4 still owns remaining review-fix closeout on the hosted matrix. Archive only after those receipts pass.

Hosted `portable-full-native.yml` runs on pull requests for `ubuntu-latest`, `windows-latest`, and `macos-14`. Missing or unreadable `native-qualification.json` is recorded as `blocked` with `inference_claimed: false` and the job fails. Merge #22 produced passing hosted receipts on all three matrix OSes (run `34003139520`); artifacts retain `native-qualification.json` with status `passed`. Earlier Windows failures hit ftp.gnu.org before models, and macOS sandbox-exec rejected a `127.0.0.1` filter (host must be `*` or `localhost`). Embeddings and station probes use `localhost` so Darwin stays inside the existing provisioner policy. GNU Bash is staged from HTTPS mirrors before provision so Windows does not depend on ftp.gnu.org; the prefetch entrypoint adds the repository root to `sys.path` so `python portable/prefetch_bash.py` resolves under Actions (previously `ModuleNotFoundError`, masked by `continue-on-error`). T3 and T4 stay `[~]` until review closeout copies those receipts into track evidence on `main`.

## Retained hosted matrix and T3 acceptance (2026-09-06)

See [provenance index](native-evidence/hosted-34003139520/index.json). Windows AMD64, Linux x86_64 and Darwin arm64 each passed 14/14 checks: external network denial, bundled Python, pre/post integrity, three inference tiers, synthesis, transcription, 384-dimensional semantic/hybrid/graph retrieval, functional Git and console, relocated launcher and station. These map directly to all seven objectives. Receipts preserve original bytes; hosted archive digests are reported rather than independently rehashed.

Local verification on integrated main `80864a0`: focused packaging/intelligence 19 tests; portable suite 35 tests; repository gate passed (48 unit tests, station-hardening tests, 36 JavaScript tests); all three CLI help smokes passed. Code review confirmed source-change graph invalidation, safe extreme-vector normalization and the required semantic, functional and post-execution checks.

T4 remains open: PR #24 fixes the Bash-prefetch script import failure masked by continue-on-error. Its run 34004202702 is pending. Historical statements that Linux/Windows receipts are absent are superseded by the retained receipts above. No release is claimed.

## Acceptance checkpoint — run 34005505093

Run [34005505093](https://github.com/edithatogo/aegisarchive/actions/runs/34005505093) passed on Linux x86_64, Windows AMD64 and Darwin arm64. [Retained receipts](native-evidence/hosted-34005505093/index.json) each record 14/14 passing checks. Application and workflow bytes match the tested revision. The Bash-prefetch entrypoint now gates requests and HTTPS redirects through PolitenessEngine, with Retry-After, backoff and cancellation tests. The prior macOS embeddings EPERM failure was preserved in hosted run 34004202702; its root cause was not established. Five local sandboxed embedding runs and this final hosted matrix passed without relaxing the sandbox or assertions.

Review covered graph invalidation, extreme-vector normalization, semantic-only retrieval, real Git/console operations, relocated launchers, post-execution integrity, request pacing and original receipt hashes. Local baseline passed: 48 Python tests, 18 station tests, 36 JavaScript tests; focused tests and claims audit passed. All 18 canonical ledgers validate; four recovered ledgers retain their original bytes without re-attesting historical claims. No release or companion-program authorization is implied.

## Final review and acceptance — 2026-09-06

Run [34008890917](https://github.com/edithatogo/aegisarchive/actions/runs/34008890917) passed on Linux x86_64, Windows AMD64 and Darwin arm64. [Retained receipts](native-evidence/hosted-34008890917/index.json) each record 14/14 passing checks. Application and workflow bytes match the tested revision. The Bash-prefetch entrypoint now gates requests and HTTPS redirects through PolitenessEngine, with Retry-After, backoff and cancellation tests. Earlier macOS failure receipts are retained, including a child-process startup failure; startup diagnostics now preserve its exit code and log tail. Numeric IPv4 loopback now avoids hostname resolution in the sandbox path; failure receipts include exception type and traceback. Twenty native local embedding runs and the real sandbox HTTP regression passed with external egress denied. Qualification speech now uses ONNX Runtime seed 42; three local synthesized files were byte-identical and passed the unchanged transcription assertions. This final native matrix passed without relaxing external-egress restrictions or acceptance assertions; the later traceback identified probe.bind as the denied operation, and the Darwin policy now explicitly permits loopback network-bind. External-egress denial remains required.

Review covered graph invalidation, extreme-vector normalization, semantic-only retrieval, real Git/console operations, relocated launchers, post-execution integrity, request pacing and original receipt hashes. Local baseline passed: 48 Python tests, 18 station tests, 36 JavaScript tests; focused tests and claims audit passed. All 18 canonical ledgers validate; four recovered ledgers retain their original bytes without re-attesting historical claims. No release or companion-program authorization is implied.

## Durable native delivery

The three qualified runtime payloads, complete manifests, restore instructions, source inventories and provisioning/native receipts from run 34008890917 are retained at `/Volumes/DM/aegisarchive-assets/qualified-20260906/34008890917`. The five shared model files and their licences are retained in `/Volumes/DM/aegisarchive-assets/models`. The [verification receipt](native-evidence/hosted-34008890917/durable-verification.json) records complete SHA-256, size and executable-flag verification of every immutable file, plus the shared models. Licences remain inside the verified payloads. This establishes durable restore inputs; Windows/Linux execution evidence comes from hosted native qualification, not local cross-platform execution.
