# Implementation plan

Chat 01a1a4fa-a107-7502-8670-7abc4e934613 owns replay on the standard Git worktree
`/Users/doughnut/Documents/Codex/2026-11-04/if-y/work/aegis-isolated-replay`
and branch `codex/aegis-isolated-replay-20261127`. Scope covers source and
synthetic verification.

Use the repository-local Python 3.15 environment and the existing hosted browser test setup. Each task owns its listed files and the track record. Run the focused verification first and the existing repository baseline before publication. Keep archive and browser checks scoped to synthetic fixtures.

- [x] T1 Qualify a separate loopback origin with the existing reader.
  - **Files**: `cli/replay_serve.py`, `web/replay/index.html`, `web/replay/app.js`, `web/replay/worker.js`, `web/lib/warc_reader.js`, `tests/browser/isolated_worker_replay.spec.js`, `package.json`.
  - **Change**: Bind the opt-in server to loopback on a separate origin using the standard library. Validate the Host header and restrict content, connections and worker scope to replay. Serve only the selected replay files with the existing viewer sanitization and a restricted worker scope.
  - **Verify**: `AEGIS_TEST_PYTHON="$PWD/.venv/bin/python" npm run test:capture -- --grep "worker replay isolation"`. Expected exit code 0.
  - **Done when**: A real browser leaves the station page uncontrolled and sends zero requests to a reachable second loopback origin while replaying the fixture. Out-of-scope requests fail closed.
  - **Do not**: Give the worker control of the capture origin or execute active code from archived content.

- [x] T2 Verify offline navigation and the fallback viewer.
  - **Files**: `cli/replay_serve.py`, `web/replay/app.js`, `web/replay/worker.js`, `tests/browser/isolated_worker_replay.spec.js`, `docs/CAPTURE_ACCEPTANCE.md`, `README.md`.
  - **Change**: Reuse already captured assets and links. Display a local missing-resource message and keep the existing viewer entry point for unsupported contexts. Provide an explicit Stop replay action that unregisters the worker and discards captured data. Isolate a later session even after an unclean close.
  - **Verify**: `AEGIS_TEST_PYTHON="$PWD/.venv/bin/python" npm run test:capture -- --grep "worker replay"`. Expected exit code 0.
  - **Done when**: Replay the synthetic fixture with external network disabled, confirm scope, explicit Stop, and a fresh replay session after an unclean shutdown with stale worker state, and test both the opt-in route and the existing viewer. The existing hosted browser workflow runs these tests.
  - **Do not**: Give the worker control of the capture origin or execute active code from archived content.

The exact replay source on `88b9517` passed the [hosted capture matrix](https://github.com/edithatogo/aegisarchive/actions/runs/45901021043). It verified archived HTML and styles, zero requests to the reachable fixture origin, a local missing resource, the station's separate worker state, restart isolation, multi-tab cleanup and the fallback viewer.
