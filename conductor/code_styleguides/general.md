# Code style

Derived from the existing implementation rather than an external platform guide.

- Python: standard-library imports, four-space indentation, argparse CLIs, explicit errors, unittest regression cases.
- Browser: vanilla JavaScript with existing UMD exports, async Web APIs, node:test regression cases; no bundler.
- Keep changes focused on reproduced defects. Explain compatibility changes and preserve public APIs where possible.
