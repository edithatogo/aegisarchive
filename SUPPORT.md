# Support

AegisArchive is maintained on a best-effort basis by volunteers.

## Where to ask

- **Usage questions and how-to**: open a GitHub Discussion if enabled, otherwise an issue using the *Bug report* template with the title prefix `[QUESTION]`.
- **Bugs**: use the *Bug report* issue template. Include your OS, Python version (`python3 --version`), browser and version, the profile used, and the last 20 lines of the console log.
- **Improvement ideas**: use the *Improvement proposal* issue template; it maps to the project backlog in `conductor/backlog.md`.
- **Security vulnerabilities**: do **not** open a public issue. Follow `SECURITY.md`.

## What to include

1. What you expected, what happened, and the smallest set of steps that reproduces it.
2. The exact command or button used and the output of `python3 cli/launch.py --help` if the launcher is involved.
3. Whether the target site is one you are authorised to archive. We do not help circumvent access controls or rate limits.

## Out of support scope

- Archiving sites you are not permitted to crawl.
- Disabling or weakening the politeness engine.
- Running on Python versions older than the one listed in `.github/workflows/ci.yml`.
- Third-party tools bundled by downstream distributions.

Response times are not guaranteed. Pull requests that follow `CONTRIBUTING.md` are the fastest route to a fix.
