# GitHub Copilot & Cursor Rules for AegisArchive

- Always preserve the zero-install property. Do not import external packages into `cli/` or `web/`.
- All web frontend code must be compatible with vanilla JavaScript (ES6+), HTML5, and CSS3 without bundling steps (`webpack`, `vite`, `npm`).
- Respect ISO 28500:2017 WARC specifications when modifying header formatting or record types.
- Ensure all timing mechanisms follow the polite, server-preserving ethos (decorrelated jitter, rate limiting, EWMA adaptation).
