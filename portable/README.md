# Optional offline intelligence

This isolated module leaves the browser archiver and standard-library CLI unchanged.
It requires explicitly provisioned local assets; no invocation downloads models.

The package builder in `packaging.py` produces a compatible `manifest.json`; use
asset IDs shown below and the tool/model file as each archive entrypoint. The
adapter resolves those records under `runtime/<id>/` and verifies their file hashes.
Alternatively create a standalone JSON manifest next to the asset directories:

```json
{
  "assets": {
    "llama": {"path": "runtime/llama-cli", "sha256": "<64 lowercase hex characters>"},
    "scout": {"path": "models/scout.gguf", "sha256": "<64 lowercase hex characters>"},
    "general": {"path": "models/general.gguf", "sha256": "<64 lowercase hex characters>"},
    "deep": {"path": "models/deep.gguf", "sha256": "<64 lowercase hex characters>"},
    "whisper": {"path": "runtime/whisper-cli", "sha256": "<64 lowercase hex characters>"},
    "whisper_model": {"path": "models/whisper.bin", "sha256": "<64 lowercase hex characters>"},
    "piper": {"path": "runtime/piper", "sha256": "<64 lowercase hex characters>"},
    "piper_model": {"path": "models/voice.onnx", "sha256": "<64 lowercase hex characters>"},
    "piper_config": {"path": "models/voice.onnx.json", "sha256": "<64 lowercase hex characters>"}
  }
}
```

Replace placeholders with hashes of the actual files, obtained independently from
trusted distribution metadata when available. Executables and shared libraries
must match the target OS/architecture. Keep native runtime dependencies alongside
the binaries according to their upstream portable distributions. Retain each
runtime/model licence and provenance. Select GGUF model tiers matching the roadmap:
Scout 1–3B, General 3.8–8B, Deep 7–14B, sized for the target machine's memory.
Do not copy a host executable alone and describe it as a portable runtime.

From the repository root:

```sh
python3 portable/intelligence.py /path/to/manifest.json generate 'Summarize this text' --tier scout
python3 portable/intelligence.py /path/to/manifest.json transcribe /path/to/input.wav
python3 portable/intelligence.py /path/to/manifest.json speak 'Offline briefing' /path/to/new-output.wav
python3 -m unittest portable.test_intelligence
```

The adapters verify asset hashes before execution, use no shell, enforce a timeout,
and propagate native failures. Audio output refuses existing paths. Native tools
are trusted programs; the adapter is not an OS network sandbox. For strict air-gap
validation, disable networking at the OS and exercise each operation with provisioned
assets. Unit tests cover adapter plumbing, not native model quality or portability.

The native bundle uses `GGUFEmbedder` with `llama_server` and the pinned BGE GGUF
asset `bge`; no sentence-transformers installation is required. The managed server
binds only to loopback and is stopped on context-manager exit. Strict offline
qualification permits loopback IPC while denying external traffic.

```python
from portable.gguf_embeddings import GGUFEmbedder
from portable.intelligence import Memory
with GGUFEmbedder('/path/to/manifest.json') as encoder:
    memory = Memory('/path/to/data/memory.sqlite')
    try:
        memory.put('doc-1', 'A committee published a water report.',
                   encoder.encode('A committee published a water report.'))
        memory.relate('committee', 'published', 'water report', 'doc-1')
        print(memory.search('water report', encoder.encode('water report', query=True)))
        print(memory.neighbors('committee'))
    finally:
        memory.close()
```

The alternative `BGEEmbedder` adapter remains available for separately provisioned
sentence-transformers environments; it loads local files with remote code disabled.

Provision the locked model set with `python3 portable/provision_models.py --output
/path/to/models`. Subsequent `--offline` runs verify the cache without downloading.
`model-lock.json` records exact revisions, source URLs, SHA-256 values, licences,
model cards, sizes and estimated RAM. Online acquisition is separate from offline
execution. Native runtime and voice provisioning use the same pinned-input approach.

The selected tiers are Qwen2.5 1.5B Instruct Q4_K_M (Scout), Qwen3 4B Q4_K_M
(General), and Qwen3 8B Q4_K_M (Deep). Their model files occupy approximately
1.12, 2.50 and 5.03 GB; recommended memory budgets are 4, 8 and 12 GiB respectively
at the adapter's 2,048-token context. The portable baseline selects CPU execution
explicitly with two CPU threads and deterministic sampling, so inference does not
require a GPU. Repacking and flash attention are disabled for a reproducible
baseline across the qualified hosts. These are planning estimates, not peak-memory
measurements. The five model files total 8.76 GB before voice and native runtimes.
Piper uses the LJSpeech medium English voice; its runtime includes native ONNX and
phonemization dependencies. The selected macOS wheels require macOS 14 or later.

SQLite preserves document text, normalized embeddings, and graph edges with foreign
keys to source documents. Replacing source text invalidates its graph edges; callers
must re-establish relationships against the revised text. Search combines BM25 and cosine-ranked vectors using
reciprocal rank fusion. Without embeddings it performs BM25 search. This small
local store scans documents in memory; large collections need a separately measured
indexing design. It does not infer facts or graph edges: callers must supply sourced
relationships and may pass retrieved text/edges to the local LLM as context.

Acceptance remains incomplete until actual licensed runtimes and all three model
tiers, speech assets, and the BGE model are bundled and native operations are tested
on each supported platform. The source adapters alone do not satisfy that gate.
