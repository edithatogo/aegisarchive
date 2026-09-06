# Native implementation and review checkpoint

The track remains **in progress** and is **not archive eligible**. T3 stays `[~]`: Darwin complete-package integrity now verifies after bytecode purge, Linux/Windows native *execution* receipts are still absent. Adapter tests are not native acceptance evidence.

## Issue #11 acquire session (2026-09-06)

`--acquire` downloaded and SHA-256-verified 58 locked artefacts on a Darwin host, including Python and llama.cpp archives for Darwin, Linux, and Windows, Git/Bash sources, PortableGit, speech sources, Piper voice, selected wheels, lock-file licences, and sub-120MB models. Scout/General/Deep GGUF weights were skipped by `--max-bytes 120000000`. Receipt: [t3-locked-acquire.json](native-evidence/t3-locked-acquire.json) (`runtimes_complete: true`, `models_complete: false`, `inference_claimed: false`). This is checksum acquisition, not inference.

Hosted `portable-native.yml` now runs the same acquire job on `ubuntu-latest` and `windows-latest` for pull requests.

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

Hosted `portable-full-native.yml` now runs on pull requests for `ubuntu-latest`, `windows-latest`, and `macos-14`, fail-closed on `native-qualification.json` status. Darwin loopback embeddings allow `127.0.0.1` as well as `localhost`.
