# 🛡️ AegisArchive

> **An enterprise-grade, zero-install, server-preserving web archiver and ISO 28500 forensic engine for high-fidelity offline replication, digital preservation, and resilient research.**

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Format](https://img.shields.io/badge/Standard-ISO_28500_WARC%2F1.1-emerald.svg)](https://iipc.github.io/warc-specifications/specifications/warc-format/warc-1.1/)
[![Index](https://img.shields.io/badge/Index-CDX--11-purple.svg)](https://archive.org/web/researcher/cdx_legend.php)
[![Zero-Install](https://img.shields.io/badge/Zero--Install-Browser_%26_Python_stdlib-amber.svg)](#quick-start)
[![MCP](https://img.shields.io/badge/AI_Agent-Model_Context_Protocol-cyan.svg)](#model-context-protocol-mcp-server)

---

## ⚡ 1-Minute Quick Start (Non-Technical Friendly)

You do **not** need Docker, Node.js, `npm`, or database installations. AegisArchive runs directly on any computer with Python 3 and a modern web browser.

### 🍎 On macOS
1. Download or clone this repository.
2. Double-click **`START_MAC.command`**.
3. Your web browser will open automatically to the AegisArchive Web Console.

### 🪟 On Windows
1. Download or clone this repository.
2. Double-click **`START_WINDOWS.cmd`** (or right-click `START_WINDOWS.ps1` → *Run with PowerShell*).
3. Your browser will open automatically.

### 🐧 On Linux
```bash
./START_LINUX.sh
```

---

## 🌟 Why AegisArchive?

Legacy scrapers (like HTTrack or Wget) and commercial scraping platforms often cause major headaches:
* **Server Strain & Bans**: They fire parallel bursts with static delays, tripping firewalls (WAFs) or inadvertently overloading institutional web servers.
* **Complex Installations**: They require administrator rights, package managers (`pip`, `npm`), Docker containers, or browser drivers.
* **Corrupted Links**: Saving raw HTML files often breaks relative links, stylesheets, and embedded assets.
* **Heavy RAM Usage**: Browser-based tools frequently crash with *"Out of Memory"* when capturing large PDF collections.

### How AegisArchive Solves This:
* **🛡️ Polite Server Preservation**: Built-in **Token-Bucket rate limiting**, **AWS Decorrelated Full Jitter back-off**, and **EWMA latency tracking** ensure target servers are never overwhelmed. If a server slows down or returns HTTP 429/503, AegisArchive automatically decelerates and respects standard `Retry-After` headers.
* **📦 Standard ISO 28500 WARC/1.1 Containers**: Captures true HTTP request/response payloads with companion **CDX-11 indexes**—the exact format used by the Internet Archive, Library of Congress, and Wayback Machine.
* **♻️ Content-Addressable Deduplication**: Uses cryptographic SHA-256 digests. If an asset (logo, style bundle, recurring PDF) is already captured, it emits an ISO 28500 `warc/revisit` record, reducing archive file size by **40% to 70%**.
* **📂 Built-in Offline Replay Viewer**: Inspect and browse captured archives completely offline without running external servers or uploading sensitive data to third parties.
* **🤖 AI Agent Integration**: Native **Model Context Protocol (MCP)** server allows Claude, Cursor, and Antigravity agents to drive archival tasks programmatically.

---

## 🏛️ System Architecture

```mermaid
graph TD
    subgraph Browser Engine [Zero-Install Client-Side Web Standards]
        UI[Intuitive Monitor & Configuration GUI]
        REPLAY[In-Browser Offline WARC Replay Viewer]
        QUEUE[BFS Priority Queue & Scope Rules]
        POLITE[Server Preservation & Rate Limiter]
        WARC[ISO 28500 WARC/1.1 & CDX-11 Writer]
        IDB[(IndexedDB State Persistence)]
    end

    subgraph Server Preservation Suite
        EWMA[EWMA Latency Dynamic Adaptation]
        BACKOFF[Decorrelated Full Jitter Back-Off]
        CIRCUIT[Circuit Breaker Tripwire]
        RETRY[RFC 9110 Retry-After Parser]
    end

    subgraph Headless & AI Automation
        CLI[Python stdlib Headless CLI]
        MCP[Model Context Protocol MCP Server]
        LAUNCH[Native 1-Click Launchers]
    end

    UI --> QUEUE
    QUEUE --> POLITE
    POLITE --> EWMA
    POLITE --> BACKOFF
    POLITE --> CIRCUIT
    POLITE --> RETRY
    POLITE --> WARC
    POLITE --> IDB
    WARC --> REPLAY
    CLI -.->|Consumes Profiles| QUEUE
    MCP -.->|Agentic Tools| CLI
    LAUNCH --> UI
```

---

## 🎯 Configuration Profiles

AegisArchive is 100% profile-driven. You can choose from bundled presets or create your own in the GUI:

| Profile | Target Scope | Politeness & Anti-DDoS |
| :--- | :--- | :--- |
| **Default Polite** (`profiles/default_polite.json`) | General preservation of public websites. | 25 req/min, 1.2s–3.2s Gaussian jitter, EWMA auto-throttle. |
| **Enterprise Intranet** (`profiles/enterprise_intranet.json`) | Internal portals (Squiz Matrix, SharePoint, Confluence). | 20 req/min, 1.5s–4.0s delay, path blacklist for calendar loops. |
| **Rapid Research** (`profiles/rapid_research.json`) | Authorized staging servers, test mirrors, localhost. | 180 req/min, 4-worker concurrency, uniform jitter. |

---

## 💻 Command Line Interface (CLI)

For headless servers, scheduled cron jobs, or containerized environments:

```bash
# Run headless crawl using a profile
python3 cli/aegis_cli.py --profile profiles/default_polite.json --output-dir ./archive

# Verify cryptographic integrity of any WARC file
python3 cli/warc_verify.py archive/aegis_preservation_20260905.warc
```

---

## 🤖 Model Context Protocol (MCP) Server

AegisArchive includes a native MCP server for AI pairs (Claude Desktop, Cursor, Antigravity CLI).

Add this to your `claude_desktop_config.json` or MCP settings:
```json
{
  "mcpServers": {
    "aegisarchive": {
      "command": "python3",
      "args": ["/path/to/aegisarchive/mcp/server.py"]
    }
  }
}
```

### Available Tools:
* `list_profiles`: Enumerate all available preservation profiles.
* `search_archive`: Search local CDX indexes for captured URLs and MIME types.
* `validate_profile`: Validate a custom profile JSON against the schema.

---

## 📜 Ethical Archival Charter

AegisArchive is designed for legitimate research, digital preservation, and institutional compliance. It embodies ethical principles:
1. **Never Flood Servers**: Strict rate limits and burst caps prevent server distress.
2. **Back Off on Congestion**: Automatically slows down when server response latencies spike.
3. **Respect RFC 9110**: Complies immediately with HTTP 429 (`Too Many Requests`) and `Retry-After` headers.
4. **Transparent Identity**: Sends polite, informative `User-Agent` metadata.

---

## 📄 License

Licensed under the **Apache License, Version 2.0**. See the [LICENSE](LICENSE) and [NOTICE](NOTICE) files for details.
