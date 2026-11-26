# Workflow and dependency reconciliation

- **R1** Reconcile the actionable dependency and security PRs with the existing required checks. Keep earlier mirroring receipts bound to their original dependency version.
- **R2** Deliver the audit report and release preview through native Actions artifacts. Keep release publication behind its published-release event.
- **R3** Bring supported CI and the embedded Windows runtime to Python 3.15.2. Record the incompatible fuzz, privacy and optional native dependencies with their existing gate behavior.
- **AC1** Exact-head protected CI and both mirroring platforms qualify the candidate. OpenGrep executes with the existing targets and blocking severity floor. The verifier rejects mismatched lockfile evidence.
- **AC2** Manual qualification saves a readable audit and a checksum-verified release preview on an authorized revision.
- **AC3** Record full native qualification and each old PR disposition. PR #91 requires positive policy, image and scanner/agent results from its upstream profile before adoption.

[PR #84](https://github.com/edithatogo/aegisarchive/pull/84) · [PR #85](https://github.com/edithatogo/aegisarchive/pull/85) · [PR #91](https://github.com/edithatogo/aegisarchive/pull/91) · [PR #92](https://github.com/edithatogo/aegisarchive/pull/92) · [PR #93](https://github.com/edithatogo/aegisarchive/pull/93)
