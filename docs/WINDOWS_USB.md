# Windows USB deployment

On this prepared USB, open `aegisarchive/START_WINDOWS.cmd`. Keep the console window open while using the browser console. The application includes `runtime/python/python.exe` (Windows x64). Python installation, administrator rights and package downloads are not required on the target computer. Use CMD launcher if PowerShell scripts are restricted.

Maintainers preparing a fresh USB must run `python3 scripts/prepare_windows_runtime.py` on a setup computer with internet access, or `scripts/prepare_windows_runtime.ps1` on Windows. This verifies the official archive against `portable/windows-python.json`, includes the upstream license, and creates a per-file `runtime-manifest.json`. Copy the entire application folder, including ignored `runtime/`, onto the USB. A Git clone or GitHub source ZIP alone does not contain the runtime. Existing runtimes are never silently overwritten.

The application uses only the embedded standard library and its own source. The isolated import configuration adds the application root; it does not enable system site packages. No preparation script runs at normal launch.

Windows CI prepares the same pinned runtime, removes system Python from PATH, starts the actual CMD launcher, retrieves the console, and captures synthetic pages with the CLI regression suite. It does not establish corporate policy acceptance or successful authenticated intranet capture. Corporate application control can still prohibit USB executables; browser login state is not automatically inherited by native HTTP requests.

Launcher captures stream into `archive/captures/<capture-id>/` on the USB. The application writes `archive.warc`, `archive.cdx` and `receipt.json`, verifies saved bytes, and shows the path when storage completes. No download is needed to retain the archive. Interrupted or failed writes can leave `.partial` files; these are not a successful archive receipt.

Capture diagnostics remain on the USB under `archive/capture-logs/`. The console does not use OPFS or localStorage for new captures; pause state stays in memory, so reloading does not restore that frontier. Keep the console open while capturing. The existing browser may still maintain its own history/cache, and optional manual exports use its chosen download location. Keep the whole application folder and captured data together when moving the USB.

See [requirement acceptance](REQUIREMENTS_ACCEPTANCE.md) for tested behavior and authentication limits. In particular, native capture does not automatically reuse a Chrome login or Windows integrated SSO.

## Windows network route

Launcher capture now evaluates the current Windows user's configured PAC script or automatic proxy discovery for each destination when no proxy environment configuration is present. It uses built-in WinHTTP APIs, without changing Windows settings. Explicit environment settings retain standard Python precedence; static proxy settings continue through Python's platform discovery. Loopback destinations use a direct connection on Windows when there is no environment override.

Automatic discovery failure is reported as `proxy_resolution` rather than silently trying direct access. Only the first supported HTTP proxy returned by PAC is used; SOCKS, credential-bearing PAC proxy values and proxy failover are unsupported. Discovery does not automatically send domain credentials to retrieve a PAC script. DNS and PAC discovery timing depends on Windows; configured API timeouts are not a guaranteed overall deadline. Browser-specific enterprise policy may differ from the current-user Windows settings.

This closes a missing PAC capability. It does not establish that PAC caused an earlier timeout or that the target workstation will now succeed. Native capture still requires explicit supported authentication if the destination needs a session; Windows integrated authentication and automatic browser-session reuse are not provided by this routing change. All routing failures and connection stages are recorded automatically in USB JSON logs. No additional diagnostic command is needed on the target computer.

Implementation references: [Python proxy discovery](https://docs.python.org/3/library/urllib.request.html#urllib.request.getproxies), [Windows current-user settings](https://learn.microsoft.com/en-us/windows/win32/api/winhttp/nf-winhttp-winhttpgetieproxyconfigforcurrentuser), [per-URL proxy resolution](https://learn.microsoft.com/en-us/windows/win32/api/winhttp/nf-winhttp-winhttpgetproxyforurl), and [automatic proxy options](https://learn.microsoft.com/en-us/windows/win32/api/winhttp/ns-winhttp-winhttp_autoproxy_options).
