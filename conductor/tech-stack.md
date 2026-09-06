# Technology Stack & Design Decisions

* **Language (Frontend)**: Modern Vanilla JavaScript (ES6+), HTML5, CSS3.
* **Storage & Memory**: Web Streams API, Origin Private File System (OPFS), localStorage frontier checkpoints. IndexedDB byte persistence remains planned.
* **Archival Standards**: ISO 28500:2017 (WARC/1.1), CDX 11-field index.
* **Cryptography**: Web Cryptography API (`crypto.subtle.digest('SHA-256')`) and Python `hashlib`.
* **Language (CLI & Automation)**: Python 3 standard library only (`http.server`, `urllib`, `socket`, `argparse`).
* **AI Interoperability**: Model Context Protocol (JSON-RPC 2.0 stdio).
* **Licensing**: Apache License 2.0.

## Optional portable intelligence

Verified optional packages use pinned llama.cpp/GGUF inference, Whisper transcription, Piper synthesis, 384-dimensional BGE embeddings and SQLite BM25/vector/graph retrieval. Native qualification covers Linux x86_64, Windows AMD64 and Darwin arm64, including relocated bundled Python, Git and console execution under outbound-network restrictions. These optional assets do not add core runtime dependencies; qualification is separate from release.
