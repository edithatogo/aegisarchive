# Agent-panel review and merge policy

Repository changes are reviewed by a panel of independent agents before merge. Each panel member records findings, risks, and one of three outcomes: approve, approve with fixes, or hold. The panel coordinator consolidates the outcomes into a short decision packet with options, trade-offs, and a recommendation for the repository owner.

The repository owner remains the accountable approver for the recommended option. GitHub Actions, local validation, and Conductor integrity checks remain mandatory technical gates. A panel decision does not claim that a hosted GitHub review approval exists and must not be represented as one.

Panel records belong in the relevant PR discussion or `conductor/reviews/` evidence ledger. Merge automation may proceed only after the owner approves the recorded recommendation and all required technical checks pass.

## Standing owner approval

The owner approved routine delivery without repeated approval requests on 2026-09-09 (PR #79 approval). Within already-authorized scope, merge after review findings are resolved and required final-head checks pass. Ask again only for material new scope or an unresolved decision beyond existing authorization. This does not waive technical gates or authorize private-data publication.
