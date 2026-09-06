# Native implementation and review checkpoint

The track remains **in progress** and is **not archive eligible**. T3 stays `[~]`: Darwin complete-package integrity now verifies after bytecode purge, Linux/Windows native *execution* receipts are still absent. Adapter tests are not native acceptance evidence.

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

Hosted `portable-full-native.yml` runs on pull requests for `ubuntu-latest`, `windows-latest`, and `macos-14`. Missing or unreadable `native-qualification.json` is recorded as `blocked` with `inference_claimed: false` and the job fails. A prior hosted Ubuntu job on this matrix completed provision and qualification with status `passed`; Windows died on ftp.gnu.org before models, and macOS sandbox-exec rejected a `127.0.0.1` filter (host must be `*` or `localhost`). Embeddings and station probes now use `localhost` so Darwin can stay inside the existing provisioner policy. GNU Bash is staged from HTTPS mirrors before provision so Windows does not depend on ftp.gnu.org. T3 and T4 stay incomplete until passing receipts exist on `main`.
