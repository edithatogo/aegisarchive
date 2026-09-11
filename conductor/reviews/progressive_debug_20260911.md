# Progressive Debug recording review

Independent reviewer initially requested fixes for permanent disk-error handling: the UI promised retry recovery despite a latched failure, reload hid the warning, and native stop acknowledgement depended on logging. All were corrected with Python and JavaScript regressions. Re-review approved; no further blocking findings.

Coordinator recommendation: deliver progressive structured USB journaling after final-head CI and automated review pass, under standing owner approval. The alternative of end-only downloads does not meet the requested workflow. Full raw browser/error dumps were rejected because they can include authentication material and response content.

The implementation flushes and syncs each append before acknowledging it, preserves a batch across ambiguous retries, enforces token/origin checks, bounds pending events and stops retrying permanent storage failures. Disk failures remain visible and require restart after storage is repaired. Already acknowledged bytes remain subject to storage-device guarantees; pending browser events can be lost on termination.

Verification: focused Python and JavaScript suites, existing baseline, and real Chrome browser tests read the journal during capture and after reload with no download. Hosted multi-platform execution remains the final merge gate.

Hosted-review follow-up: directory opens now reject symlink substitution and use anchored POSIX directory descriptors; Windows validates directory/file identity before writing. Two symlink regressions and actual USB smoke pass. The CodeQL URL assertion now compares the precise URL property. Failed Debug activation blocks capture until successful retry. Independent re-review approved these changes; Windows fallback awaits hosted execution.

Late automated interaction review: concurrent Debug activation is serialized to one client, and transient failure/recovery maintains the correct Resume control. Independent re-review approved both fixes. Queue overflow now leaves a counted gap marker in the journal after delivery recovers and a persistent UI gap count.
