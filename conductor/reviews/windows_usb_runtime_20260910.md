# Windows USB runtime review

Independent runtime reviewer: approve with fixes, subject to Windows Actions passing. Embedded import configuration, checksum validation, staging and refusal to overwrite were accepted. Requested README preparation instructions and PowerShell argument/guidance parity are applied.

Options: retain installed-Python acceptance (rejected; misses the reported failure), or provision pinned embedded Python and execute the real launcher plus synthetic capture tests (recommended and implemented under standing owner approval).

CI proves bundled runtime execution with system Python removed from PATH. Console launch and CLI capture are separate tests. This is not a non-admin identity test, a browser UI capture test, or corporate-workstation acceptance. No private data is used.
