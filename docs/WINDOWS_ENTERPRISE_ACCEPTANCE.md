# Windows enterprise acceptance

`windows-portable-noadmin.yml` prepares checksum-pinned embedded Python and
executes the real CMD launcher with system Python removed from PATH. It runs
synthetic capture and USB storage regressions. Browser acceptance also uses
the bundled runtime on Windows. Preparation occurs on the setup runner;
normal target-machine launch performs no package installation.

These are hosted integration tests, not execution under a corporate non-admin
identity or in a Windows container. They do not reproduce application-control
policy or automatic integrated SSO. See [requirement acceptance](REQUIREMENTS_ACCEPTANCE.md)
for explicit deployment limits and [USB setup](WINDOWS_USB.md) for preparation.
