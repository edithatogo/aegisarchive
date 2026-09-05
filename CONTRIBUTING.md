# Contributing to AegisArchive

Thank you for your interest in improving AegisArchive!

## Architectural Principles
1. **Zero External Dependencies**: The core browser client and the CLI launcher must operate without third-party package installations (`pip`, `npm`, `Docker`).
2. **Server-Preserving Politeness**: All crawling capabilities must enforce rate limits, exponential backoff, and compliant RFC 9110 / RFC 9309 behavior.
3. **Standards-First**: Output must strictly adhere to ISO 28500:2017 (WARC/1.1) and CDX-11 indexing.
4. **Complete Abstraction**: No private, organizational, or domain-specific identifiers should ever be committed to the engine repository.

## Submitting Changes
1. Fork the repository and create a descriptive feature branch (`git checkout -b feature/my-enhancement`).
2. Verify all Python scripts pass syntax compilation: `python3 -m py_compile cli/*.py mcp/*.py`.
3. Verify JSON profiles validate against `profiles/schema.json`.
4. Ensure the abstraction audit passes: verify zero organizational or departmental identifiers exist in diffs.
5. Submit a Pull Request.
