# Track Plan: PortableApps Compatibility & Offline Intelligence Suite

## Status: ROADMAP PLANNED

### Objectives
- Package into PortableApps.com `.paf.exe` format (`App/`, `Data/`, `AppInfo/appinfo.ini`).
- Bundle MinGit (~35MB) and Cmder Mini (~12MB) into `runtime/`.
- Local LLM engine (`llama.cpp`) with 3-tier GGUF models (Scout 1-3B, General 3.8-8B, Deep 7-14B).
- Integrate offline voice-to-text (`whisper.cpp`) for interview and meeting transcription.
- Integrate offline text-to-speech (`piper-tts`) for audio policy briefings.
- Integrate local vector embeddings (`bge-small-en-v1.5`) alongside BM25 search.
- Integrate local GraphRAG memory (SQLite/DuckDB) for policy and committee knowledge graphs.
