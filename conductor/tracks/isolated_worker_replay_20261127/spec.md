# Isolated service-worker replay

[ADR 0004](../../../docs/adr/0004-service-worker-replay.md) · [Service Workers specification](https://w3c.github.io/ServiceWorker/)

- **R1** Offer opt-in, script-free archive replay from a dedicated loopback origin and worker scope. Only a selected archive’s recorded responses may enter that scope.
- **R2** Keep acquisition, capture controls and saved settings on the existing station origin. Reuse the replay reader and existing resource sanitization.
- **AC1** The worker cannot intercept station requests. Archived content, missing resources and attempted remote fetches make no network access beyond the replay origin.
- **AC2** A browser without a viable worker context can still use the existing viewer. Stop replay clears the registration and archive data. A subsequent session uses an isolated origin even after an unclean close.
- **Boundary** No remote hosting or executing arbitrary captured scripts in the initial slice. Release requires hosted browser isolation evidence.
