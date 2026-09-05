# Native implementation and review checkpoint

The track remains **in progress** and is **not archive eligible** while Linux/Windows full native receipts are pending. Adapter tests are not native acceptance evidence. T3 added fail-closed inventory/audit/smoke machinery and re-ran Darwin model execution; it does not close the hosted platform matrix.

## T3 session (2026-09-06)

Machinery: `provision_models.py --inventory` / `--audit`, `provision_native.py --inventory` / `--verify-bundle` / `--smoke-bundle`. An empty cache audit exits 1 with `inference_claimed: false`. A missing bundle writes `status: blocked` and `smoke: not_run`.

Acquired this session (HTTPS, SHA-256 pinned): all ten lock-file licence and model-card documents (Scout/General/Deep/transcription/embeddings). Weights were not re-downloaded; they were verified in the existing Darwin assembled runtime.

Verified against `portable/model-lock.json`: all fifteen locked files, including the five weights (8,756,774,347 bytes). Receipt: [t3-model-audit.json](native-evidence/t3-model-audit.json).

Darwin model/runtime smoke (existing internal package, current adapters): Scout, General and Deep each returned `ARCHIVE`; Piper synthesis and Whisper transcription of that audio; BGE-384 hybrid/semantic/graph retrieval; bundled Git 2.55.0; bundled console `ARCHIVE`. Receipt: [t3-model-smoke.json](native-evidence/t3-model-smoke.json). `llama-cli --version` reported build 10819.

Blocked / fail-closed:

- `--verify-bundle` on that Darwin tree failed: 531 extra files versus the manifest, including interpreter bytecode caches. No complete-package integrity pass was recorded. [t3-bundle-verify.json](native-evidence/t3-bundle-verify.json).
- Linux x64 and Windows x64 native runtimes/models were not provisioned or executed on this host. Hosted `portable-full-native.yml` remains the matrix gate.
- Empty cache audit correctly refused to claim models. [t3-empty-cache-audit.json](native-evidence/t3-empty-cache-audit.json).

Inventories: [t3-source-inventory.json](native-evidence/t3-source-inventory.json), [t3-model-inventory.json](native-evidence/t3-model-inventory.json), [t3-licence-fetch.json](native-evidence/t3-licence-fetch.json).

## Prior macOS acceptance (retained)

The internally stored macOS ARM64 package previously recorded 14 asset records and a complete relocated sandbox run. That historical receipt remains at [darwin-full-native.json](native-evidence/darwin-full-native.json). This T3 session did not treat a drifted tree (extra bytecode) as a fresh complete-package pass.

## Provisioning and resource records

`portable/model-lock.json` pins all five model files and their licences/cards by exact source revision, SHA-256 and byte size. Scout is Qwen2.5 1.5B Instruct Q4_K_M, General Qwen3 4B Q4_K_M, and Deep Qwen3 8B Q4_K_M; Whisper tiny.en and BGE small en v1.5 Q8_0 complete the set. Recommended one-model-at-a-time RAM is 4/8/12 GiB for inference tiers at 2,048 tokens; transcription and embeddings each have a 1 GiB planning allowance, and voice 0.5 GiB. These are estimates, not measured peak-RSS guarantees.

Runtime pins remain in the native provisioners. Component licences are retained separately; the repository licence does not replace them.

## Remaining acceptance

T4 still owns review-fix closeout and full native receipts on each target OS. Archive only after those receipts pass. Foundation Python/SQLite/CLI probes are not a substitute for Linux/Windows inference/speech/retrieval.
