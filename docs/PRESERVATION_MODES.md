# Preservation modes

AegisArchive exposes three explicit capability modes:

* `preservation` retains original HTTP responses and does not claim replay.
* `offline_reading` uses only captured bytes for safe navigation and local search.
* `rendered_optional` adds an optional, separately recorded DOM or screenshot derivative.

Original responses remain authoritative in every mode. Rendered output never replaces originals and backend functionality, remote forms, search services, DRM and other application behaviour are reported as unsupported. Offline replay must make no source requests.
