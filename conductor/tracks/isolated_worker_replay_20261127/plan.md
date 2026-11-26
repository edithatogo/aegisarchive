# Implementation plan

Use the repository-local Python 3.15 environment and the existing hosted browser test setup. Each task owns its listed files and the track record. Run the focused verification first and the existing repository baseline before publication. Keep archive and browser checks scoped to synthetic fixtures.

- [ ] T1 Qualify a separate loopback origin with the existing reader.
  - **Files**: `cli/replay_serve.py`, `web/replay/index.html`, `web/replay/worker.js`, `tests/browser/capture.spec.js`.
  - **Change**: Bind the opt-in server to loopback on a separate origin using the standard library. Validate the Host header and restrict content, connections and worker scope to replay. Serve only the selected replay files with the existing viewer sanitization and a restricted worker scope.
  - **Verify**: `AEGIS_TEST_PYTHON="$PWD/.venv/bin/python" npm run test:capture -- --grep "worker replay isolation"`. Expected exit code 0.
  - **Done when**: A real browser leaves the station page uncontrolled and sends zero requests to a reachable second loopback origin while replaying the fixture. Out-of-scope requests fail closed.
  - **Do not**: Give the worker control of the capture origin or execute active code from archived content.

- [ ] T2 Verify offline navigation and the fallback viewer.
  - **Files**: `cli/replay_serve.py`, `web/replay/index.html`, `web/replay/worker.js`, `tests/browser/capture.spec.js`, `docs/CAPTURE_ACCEPTANCE.md`.
  - **Change**: Reuse already captured assets and links. Display a local missing-resource message and keep the existing viewer entry point for unsupported contexts. Provide an explicit Stop replay action that unregisters the worker and discards captured data. Isolate a later session even after an unclean close.
  - **Verify**: `AEGIS_TEST_PYTHON="$PWD/.venv/bin/python" npm run test:capture -- --grep "worker replay"`. Expected exit code 0.
  - **Done when**: Replay the synthetic fixture with external network disabled, confirm scope, explicit Stop, and a fresh replay session after an unclean shutdown with stale worker state, and test both the opt-in route and the existing viewer. The existing hosted browser workflow runs these tests.
  - **Do not**: Give the worker control of the capture origin or execute active code from archived content.
