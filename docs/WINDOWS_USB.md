# Windows USB deployment

On this prepared USB, open `aegisarchive/START_WINDOWS.cmd`. Keep the console window open while using the browser console. The application includes `runtime/python/python.exe` (Windows x64). Python installation, administrator rights and package downloads are not required on the target computer. Use CMD launcher if PowerShell scripts are restricted.

Maintainers preparing a fresh USB must run `python3 scripts/prepare_windows_runtime.py` on a setup computer with internet access, or `scripts/prepare_windows_runtime.ps1` on Windows. This verifies the official archive against `portable/windows-python.json`, includes the upstream license, and creates a per-file `runtime-manifest.json`. Copy the entire application folder, including ignored `runtime/`, onto the USB. A Git clone or GitHub source ZIP alone does not contain the runtime. Existing runtimes are never silently overwritten.

The application uses only the embedded standard library and its own source. The isolated import configuration adds the application root; it does not enable system site packages. No preparation script runs at normal launch.

Windows CI prepares the same pinned runtime, removes system Python from PATH, starts the actual CMD launcher, retrieves the console, and captures synthetic pages with the CLI regression suite. It does not establish corporate policy acceptance or successful authenticated intranet capture. Corporate application control can still prohibit USB executables; browser login state is not automatically inherited by native HTTP requests.

Launcher captures stream into `archive/captures/<capture-id>/` on the USB. The application writes `archive.warc`, `archive.cdx` and `receipt.json`, verifies saved bytes, and shows the path when storage completes. No download is needed to retain the archive. Interrupted or failed writes can leave `.partial` files; these are not a successful archive receipt.

Capture diagnostics remain on the USB under `archive/capture-logs/`. The console does not use OPFS or localStorage for new captures; pause state stays in memory, so reloading does not restore that frontier. Keep the console open while capturing. The existing browser may still maintain its own history/cache, and optional manual exports use its chosen download location. Keep the whole application folder and captured data together when moving the USB.

See [requirement acceptance](REQUIREMENTS_ACCEPTANCE.md) for tested behavior and authentication limits. In particular, native capture does not automatically reuse a Chrome login or Windows integrated SSO.
