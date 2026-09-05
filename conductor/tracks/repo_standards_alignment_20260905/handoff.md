# Repository Standards Alignment Handoff Notes

## 1. Action SHA Pins in ci.yml (For Parallel Agent)
The repository-standards control plane requires immutable SHA pins with version comments for GitHub Actions steps.
Currently, `.github/workflows/ci.yml` (owned by the parallel CI/CD track) uses mutable major tags (`actions/checkout@v4` and `actions/setup-python@v5`).
Recommended replacements when modifying `ci.yml`:
- `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`
- `actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0`

Per track invariants, `.github/workflows/ci.yml` was not modified in this track.

## 2. Standards Registry Registration (For Integrator)
Once the repository is pushed and the standards CI workflow has completed its initial runs, register this repository in the external standards registry:
- Repository: `edithatogo/repository-standards`
- Target file: `registry/repositories.json`
- Configuration: archetype `python`, supply-chain profile `published`, sole developer model.

## 3. Remote Rulesets and Topics (Gate G1)
Task T11 (branch protection ruleset requiring passing checks and zero human approvals, along with the `solo-maintainer` topic) is gated on Gate G1 (user authorization after live remote push and green CI runs).
