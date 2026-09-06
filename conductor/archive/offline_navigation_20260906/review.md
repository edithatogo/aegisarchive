# Offline navigation acceptance review

Review passed for the archive-local navigation contract. The implementation canonicalizes archived URLs, preserves query identity, removes fragments for lookup, reports missing records, rewrites captured CSS resources to blob URLs, keeps anchors inert, binds navigation messages to the replay frame and nonce, and exposes browser history controls. Captured scripts remain inside a sandboxed frame and cannot use the parent navigation contract without the nonce and source binding.

The focused Node suite passes 4/4. The Playwright suite passes 1/1 using the pinned package and the installed Chrome executable. The full repository gate passes: 52 Python tests, 18 station tests and 45 JavaScript tests. Full Conductor validation, profiles and leak checks pass.

The browser fixture is synthetic and loopback-only. It verifies that disconnected replay has no unintended external requests. A future track must provide richer archive fixtures and test service-worker/offline traversal; this track does not claim rendered application emulation, authenticated replay or universal HTML/CSS conformance.
