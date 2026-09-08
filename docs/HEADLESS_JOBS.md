# Headless jobs

`cli.jobs.JobStore` provides a dependency-free lifecycle store for capture jobs. Run identities are deterministic for identical specifications, leases prevent overlapping workers, and stale leases can be recovered after expiry. State changes are explicit and terminal states cannot be reused.

Scheduling is opt-in: definitions must set `enabled: true` and are never activated during installation. Notifications are also opt-in and expose only a run identifier, state, event, timestamp and summary hash. Operators supply the platform scheduler invocation; AegisArchive does not register jobs or contact a destination automatically.
