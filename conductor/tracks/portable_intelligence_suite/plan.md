# Track Plan: Portable Platform Compatibility & Offline Intelligence Suite

## Status: IN PROGRESS

### Objectives
- [ ] Package into a portable application format (app directory, data directory, and package manifest).
- [ ] Bundle a portable minimal Git runtime (~35MB) and a self-contained portable console (~12MB) into `runtime/`.
- [ ] Local LLM engine (`llama.cpp`) with 3-tier GGUF models (Scout 1-3B, General 3.8-8B, Deep 7-14B).
- [ ] Integrate offline voice-to-text (`whisper.cpp`) for interview and meeting transcription.
- [ ] Integrate offline text-to-speech (`piper-tts`) for audio policy briefings.
- [ ] Integrate local vector embeddings (`bge-small-en-v1.5`) alongside BM25 search.
- [ ] Integrate local GraphRAG memory (SQLite/DuckDB) for policy and committee knowledge graphs.

## Implementation tasks

- [x] T1 Assemble a verified portable package.
  - **Files**: `portable/packaging.py`, `portable/PACKAGING.md`, `tests/test_portable_packaging.py`.
  - **Change**: app/data/runtime layout; SHA256-pinned local asset intake, licence/source inventory, traversal-safe extraction and offline verification.
  - **Verify**: `python3 -m unittest tests.test_portable_packaging`.
  - **Done when**: tampering and unsafe extraction tests fail closed and a temporary package verifies.
  - **Do not**: describe synthetic test assets as native runtime bundles.

- [x] T2 Implement optional offline intelligence integration.
  - **Files**: `portable/intelligence.py`, `portable/test_intelligence.py`, optional requirements and documentation under `portable/`.
  - **Change**: subprocess adapters for inference and speech; isolated embeddings; SQLite BM25/vector/graph retrieval.
  - **Verify**: `python3 -m unittest discover -s portable -p 'test_*.py'`.
  - **Done when**: adapter validation and retrieval regression tests pass.
  - **Do not**: add core runtime dependencies or claim mocked adapters establish native compatibility.

- [~] T3 Acquire and verify native runtime/model assets and exercise the complete offline package.
  - **Files**: local package output, asset provenance and validation receipts; `portable/native_platform_probe.py`, `portable/native_qualification.py`, `portable/gguf_embeddings.py`, `.github/workflows/portable-native.yml`, `portable/provision_models.py`, `portable/model-lock.json`, `portable/provision_speech.py`, `portable/provision_native.py`, `.github/workflows/portable-full-native.yml`, packaging and native regression tests and documentation.
  - **Change**: source and checksum each runtime/model, retain licences, execute inference, transcription, synthesis, embedding and graph retrieval; validate target OS launch.
  - **Verify**: real native smoke commands recorded in review.md.
  - **Done when**: all original roadmap objectives have direct execution evidence.
  - **Do not**: archive while native acceptance is incomplete.

## Review fixes

- [~] T4 Close native qualification findings and preserve direct execution evidence.
  - **Files**: `portable/intelligence.py`, `portable/native_qualification.py`, `portable/test_intelligence.py`, `tests/test_portable_packaging.py`, `portable/test_provision_models.py`, native provisioning/workflow files and this track's evidence/review records.
  - **Change**: invalidate graph edges when source text changes, normalize extreme vectors safely, require semantic-only retrieval and functional Git/console checks, verify immutable files after execution, and test relocated bundled launchers.
  - **Verify**: `python3 -m unittest tests.test_portable_packaging portable.test_intelligence`; `python3 scripts/gate.py test`; full native qualification receipts on each target OS.
  - **Done when**: review findings are fixed and all required native receipts pass.
  - **Do not**: replace native execution evidence with adapter test results or archive with an incomplete platform matrix.
