# Retrospective specification: Portable Platform Compatibility & Offline Intelligence Suite

This pack was reconstructed on 2026-09-05 from the existing objective-only plan; it does not assert a historical review.

## Scope and acceptance

- Package into a portable application format (app directory, data directory, and package manifest).
- Bundle a portable minimal Git runtime (~35MB) and a self-contained portable console (~12MB) into `runtime/`.
- Local LLM engine (`llama.cpp`) with 3-tier GGUF models (Scout 1-3B, General 3.8-8B, Deep 7-14B).
- Integrate offline voice-to-text (`whisper.cpp`) for interview and meeting transcription.
- Integrate offline text-to-speech (`piper-tts`) for audio policy briefings.
- Integrate local vector embeddings (`bge-small-en-v1.5`) alongside BM25 search.
- Integrate local GraphRAG memory (SQLite/DuckDB) for policy and committee knowledge graphs.


## Authoritative inputs

- AGENTS.md and conductor/workflow.md.
- Current implementation and named successor tracks, where their reviewed security requirements supersede original designs.

## Validation

Run `python3 scripts/gate.py test`, profile checks and CLI smoke checks. Record source coverage and limitations in review.md before archival.

## External boundary

Local review does not authorize publication. Hosted or native checks not run locally must be identified as such.
