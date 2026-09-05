# AegisArchive Quickstart

1. Install nothing: you need only Python 3 and a modern browser.
2. Download or clone this repository and unzip it if needed.
3. macOS: double-click `START_MAC.command`. Windows: double-click `START_WINDOWS.cmd`. Linux: run `./START_LINUX.sh`.
4. Your browser opens the Web Console on a loopback address; nothing is exposed to the network.
5. Choose a profile (Default Polite is safe for public sites) and enter one or more seed URLs.
6. Press Start; the politeness engine paces requests and slows down if the server does.
7. Press Stop at any time; the capture so far is preserved.
8. Download the `.warc` and companion `.cdx` files when the run finishes.
9. Open `web/viewer.html` (Viewer link in the console) to browse the archive offline.
10. Headless use: `python3 cli/aegis_cli.py --profile profiles/default_polite.json --output-dir ./archive`; verify with `python3 cli/warc_verify.py <file.warc>`.
