# Development Workflow

1. **Zero-Install Mandate**: Any dependency added must be vendored or part of standard runtime.
2. **Polite Timing Guarantee**: All crawler network requests must pass through `PolitenessEngine`.
3. **Verification Protocol**: Test scripts with `--help`, run WARC verifier, and check browser console.
