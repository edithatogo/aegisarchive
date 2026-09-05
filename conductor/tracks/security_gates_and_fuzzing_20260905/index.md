# Track: Security Gates & Fuzzing (`security_gates_and_fuzzing_20260905`)

* [Specification](./spec.md)
* [Plan](./plan.md)
* [Metadata](./metadata.json)
* [Evidence Ledger](./evidence.jsonl)

Type: feature. Status: completed. Created: 2026-09-05.

Adds a new `security.yml` workflow (gitleaks, CodeQL with a medium-or-higher SARIF gate, Semgrep, Bandit, zizmor, atheris fuzz smoke, JS property tests), ClusterFuzzLite PR fuzzing, and a stdlib local gate runner (`scripts/gate.py`). All gates fail when any medium-or-higher finding persists. `ci.yml` is not modified.
