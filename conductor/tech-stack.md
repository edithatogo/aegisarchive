# Technology Stack & Design Decisions

* **Language (Frontend)**: Modern Vanilla JavaScript (ES6+), HTML5, CSS3.
* **Storage & Memory**: Web Streams API, Origin Private File System (OPFS), localStorage frontier checkpoints. IndexedDB byte persistence remains planned.
* **Archival Standards**: ISO 28500:2017 (WARC/1.1), CDX 11-field index.
* **Cryptography**: Web Cryptography API (`crypto.subtle.digest('SHA-256')`) and Python `hashlib`.
* **Language (CLI & Automation)**: Python 3 standard library only (`http.server`, `urllib`, `socket`, `argparse`).
* **AI Interoperability**: Model Context Protocol (JSON-RPC 2.0 stdio).
* **Licensing**: Apache License 2.0.
