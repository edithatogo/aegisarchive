# Fast synthetic acceptance and CI feedback

Keep pull-request verification deterministic and independent of private or unavailable sites. Use local reserved-address fixtures to exercise successful capture, redirects, robots decisions, authentication failures, replay and export. Keep large optional runtime qualification as a manually triggered gate.

Acceptance criteria:

- CI browser tests use only local synthetic fixtures and never a production or intranet URL.
- PR checks complete without downloading multi-gigabyte optional assets.
- Full native qualification remains available through an explicit manual workflow.
- Failure output identifies the fixture, request count, and saved-response count.

