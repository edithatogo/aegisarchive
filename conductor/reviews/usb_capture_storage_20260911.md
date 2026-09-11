# USB capture storage review

First independent reviewer: hold for WARC filename consistency. Passing the fixed USB filename into the WARC constructor resolved the finding; the browser regression checks the serialized header. Token checks, bounded writes, offsets, readback verification and failure handling were otherwise accepted.

Second independent reviewer: approve for integration, with no blocking findings. Independently ran six USB archive tests. Confirmed no new runtime dependencies, embedded Windows browser CI, and explicit authentication/host-browser limitations.

Recommended option: persist launcher archives to the application's USB directory and stop on storage failure. Retaining OPFS and default downloads was rejected because it violates the user's storage requirement. Routine delivery is covered by standing owner authorization, subject to final-head checks.

Acceptance boundary: hosted fixtures do not prove corporate application-control compatibility, integrated SSO, or completeness of the real intranet. See `docs/REQUIREMENTS_ACCEPTANCE.md`.
