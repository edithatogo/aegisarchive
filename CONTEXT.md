# System Context & Architecture: AegisArchive

## Core Mission
AegisArchive provides an enterprise-grade, zero-install, server-preserving web archiver and ISO 28500 forensic engine for high-fidelity offline replication, digital preservation, and resilient research.

## Component Map
* **`web/`**: Zero-install client-side web application.
  * `index.html`: Main harvesting console, live telemetry dashboard, and profile editor.
  * `viewer.html`: In-browser offline WARC replay viewer.
  * `lib/core_crawler.js`: Multi-tier priority BFS queue, URL canonicalization, and crawler trap detection.
  * `lib/politeness_engine.js`: Token bucket rate limiter, AWS decorrelated full jitter, EWMA latency tracking, and circuit breaker.
  * `lib/warc_writer.js`: ISO 28500 WARC/1.1 and CDX-11 serializer with SHA-256 revisit deduplication.
  * `lib/warc_reader.js`: In-browser WARC parser and link rewriter for replay viewer.
  * `lib/opfs_streamer.js`: Origin Private File System disk streaming engine.
  * `lib/self_reflection.js`: Automated diagnostic health report generator.
* **`profiles/`**: JSON configuration profiles and schema (`schema.json`).
* **`cli/`**: Python 3 stdlib utilities (`launch.py`, `aegis_cli.py`, `warc_verify.py`).
* **`mcp/`**: Model Context Protocol stdio server (`server.py`).
* **`conductor/`**: Track registry and development planning.
