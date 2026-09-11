# Progressive USB debug recording

User authorized a Debug control that progressively saves troubleshooting evidence inside the USB repository without downloading files.

- R1 / AC1: Debug starts a local JSONL journal before capture and displays its path and acknowledged save status.
- R2 / AC2: Capture lifecycle, structured audit records, progress, browser failures and native transport events are appended progressively with durable write acknowledgement.
- R3 / AC3: Token/origin protections, bounded batches and queues, duplicate retry protection and visible storage failure protect recording integrity; logs exclude response bodies and authentication secrets.
- R4 / AC4: Browser regression reads the actual journal before capture finishes and after reload without downloading. Python/JS tests and final-head CI pass before merge.
- G1: User says Proceed under standing delivery authorization.
- G2: Browser or OS termination can lose unacknowledged events; no guarantee of recording a failed disk or events before Debug activation.
