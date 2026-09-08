# Windows enterprise acceptance

`windows-portable-noadmin.yml` exercises the portable acceptance path on a
Windows runner without installing packages, starting services, requiring
Docker, or writing to a system directory. It writes only to the runner's
user-writable temporary directory and validates the hash-bound offline receipt.

This is an enterprise-style no-admin simulation. It does not claim that a
Windows Docker container ran. Windows-container validation requires a Windows
host with Windows container mode and a registered self-hosted runner.
