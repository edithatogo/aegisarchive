# Implementation plan

Use the repository-local Python 3.15 environment and the existing hosted browser test setup. Each task owns its listed files and the track record. Run the focused verification first and the existing repository baseline before publication. Keep archive and browser checks scoped to synthetic fixtures.

- [ ] T1 Write and verify one WACZ package.
  - **Files**: `cli/export_mirror.py`, `tests/test_wacz_export.py`.
  - **Change**: Use the existing standard-library ZIP path, the generated archive and index, pages/pages.jsonl, datapackage.json and its digest. Validate the exact saved package before publication.
  - **Verify**: `.venv/bin/python -m unittest tests.test_wacz_export.WaczPackageTest`. Expected exit code 0.
  - **Done when**: Round-trip manifests and member hashes, and reject ambiguous names, missing references, unsafe paths and altered bytes.
  - **Do not**: Change standard ZIP export or combine multiple captures in one command.

- [ ] T2 Qualify independent validation and offline replay.
  - **Files**: `tests/test_wacz_export.py`, `tests/browser/capture.spec.js`, `package.json`, `package-lock.json`, `tests/requirements-wacz-validation.txt`, `.github/workflows/browser-capture.yml`, `docs/PORTABLE_EXPORTS.md`, `README.md`.
  - **Change**: Pin the test-only py-wacz v0.6.0 validator for WACZ 1.1.1 and a test-only replay reader in their dependency locks. Qualify the validator on Python 3.15 and add its invocation to the existing hosted Linux browser job. Save validation receipts for the published fixture, then update the supported-format claim.
  - **Verify**: `.venv/bin/python -m unittest tests.test_wacz_export && AEGIS_TEST_PYTHON="$PWD/.venv/bin/python" npm run test:capture -- --grep "WACZ replay"`. Expected exit code 0.
  - **Done when**: A reference validator and replay reader accept the package, resolve one HTML page and one subresource without contacting the archived site, and reject an altered fixture.
  - **Do not**: Change standard ZIP export or combine multiple captures in one command.
