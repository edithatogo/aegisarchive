# Repository health and contributor safeguards

- **AC1** An installed pre-commit hook rejects a staged synthetic secret and a malformed workflow. Supported commits pass with qualified developer tools.
- **AC2** GitHub Actions scans Git history patches from a full checkout with TruffleHog and rejects new detections or scanner errors. Saved job output excludes raw values and file paths. alint validates community files and RepoHealth reports an advisory score.
- **AC3** Community documents and the issue chooser link to support and private reporting. GitHub's community profile and private reporting settings remain valid. Existing Presidio, Gitleaks, OpenGrep and Scorecard workflows keep their coverage.
