"""Provision pinned Python and probe relocated CLI execution on a native OS.

This is a platform foundation probe, not evidence of model/speech execution.
Downloads occur before OS-enforced egress denial. No release is published.
"""
from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

RELEASE = "20260901"
VERSION = "3.12.14"
ASSETS = {
    ("Darwin", "arm64"): ("aarch64-apple-darwin", "3ee3ee547cedfeb7c2b16b2b7156039f7b470bb8f857e226fd3d2eb11db83c76"),
    ("Darwin", "x86_64"): ("x86_64-apple-darwin", "2e31b23f3f1319f707d0e620b48847a0046577541d357276821f9f1b5492e0ba"),
    ("Linux", "x86_64"): ("x86_64-unknown-linux-gnu", "936c246dfdbbfa7cb22dd01814a21f582a892689fae96b06071a5e433baffa22"),
    ("Linux", "aarch64"): ("aarch64-unknown-linux-gnu", "b61b856c3e1a4fc65b8f6e6b0495ef975dd0924f90c59f3ea61b38a079173b84"),
    ("Windows", "AMD64"): ("x86_64-pc-windows-msvc", "e90c1b6419da3bd812dd73bb3de40287a21abf153438147639ec5e20375ea93f"),
}


def child(report: Path) -> None:
    """Run only with bundled Python inside an OS network restriction."""
    root = Path(__file__).resolve().parents[1]
    python_root = root.parent / "python"
    executable = Path(sys.executable).resolve()
    if not executable.is_relative_to(python_root.resolve()):
        raise RuntimeError("Probe did not use relocated bundled Python")
    try:
        with socket.create_connection(("1.1.1.1", 443), timeout=3):
            raise RuntimeError("External network connection unexpectedly succeeded")
    except OSError as exc:
        if exc.errno not in (errno.EPERM, errno.EACCES, errno.ENETUNREACH):
            raise RuntimeError("No proven OS network denial: " + str(exc)) from exc
        network_error = {"type": type(exc).__name__, "errno": exc.errno, "message": str(exc)}
    db = sqlite3.connect(":memory:")
    db.execute("CREATE VIRTUAL TABLE docs USING fts5(body)")
    db.execute("INSERT INTO docs VALUES ('offline archive retrieval')")
    assert db.execute("SELECT body FROM docs WHERE docs MATCH 'archive'").fetchone()
    commands = []
    for script in ("cli/launch.py", "cli/aegis_cli.py", "cli/warc_verify.py"):
        result = subprocess.run([str(executable), "-I", "-B", str(root / script), "--help"],
                                capture_output=True, text=True, timeout=60, check=True)
        commands.append({"script": script, "returncode": result.returncode, "stdout": result.stdout})
    report.write_text(json.dumps({"scope": "standalone Python, SQLite FTS5 and CLI help only; not full intelligence suite",
                                 "platform": platform.platform(), "executable": str(executable),
                                 "version": sys.version, "python_prefix": sys.prefix,
                                 "path": os.environ.get("PATH"), "external_egress_denied": network_error,
                                 "sqlite": sqlite3.sqlite_version, "commands": commands}, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("platform-probe.json"))
    parser.add_argument("--child", action="store_true")
    args = parser.parse_args()
    if args.child:
        child(args.output)
        return
    target, expected = ASSETS[(platform.system(), platform.machine())]
    url = f"https://github.com/astral-sh/python-build-standalone/releases/download/{RELEASE}/cpython-{VERSION}%2B{RELEASE}-{target}-install_only.tar.gz"
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="aegis native probe ") as workspace:
        work = Path(workspace).resolve()
        archive = work / "python.tar.gz"
        with urllib.request.urlopen(url, timeout=120) as response, archive.open("wb") as destination:
            shutil.copyfileobj(response, destination)
        actual = hashlib.sha256(archive.read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError("Standalone Python archive checksum mismatch")
        original = work / "original"
        original.mkdir()
        with tarfile.open(archive) as bundle:
            bundle.extractall(original, filter="data")
        relocated = work / "relocated package with spaces"
        original.rename(relocated)
        app = relocated / "app"
        app.mkdir()
        repo = Path(__file__).resolve().parents[1]
        for name in ("cli", "mcp", "portable", "profiles"):
            shutil.copytree(repo / name, app / name, ignore=shutil.ignore_patterns("__pycache__", "._*"))
        executable = (relocated / "python" / ("python.exe" if os.name == "nt" else "bin/python3")).resolve(strict=True)
        report = relocated / "probe.json"
        command = [str(executable), "-I", "-B", str(app / "portable/native_platform_probe.py"), "--child", "--output", str(report)]
        environment = dict(os.environ)
        for key in tuple(environment):
            if key.startswith("PYTHON"):
                environment.pop(key)
        environment["PATH"] = str(work / "no-host-programs")
        if platform.system() == "Darwin":
            restriction = "sandbox-exec deny network*"
            subprocess.run(["/usr/bin/sandbox-exec", "-p", "(version 1)(allow default)(deny network*)", *command], env=environment, check=True, timeout=300)
        elif platform.system() == "Linux":
            restriction = "unshare network namespace"
            subprocess.run(["/usr/bin/sudo", "/usr/bin/unshare", "--net", "--", "/usr/bin/env", "PATH=" + environment["PATH"], *command], env=environment, check=True, timeout=300)
        else:
            restriction = "Windows Firewall outbound block for bundled python.exe"
            # Firewall rejects DOS short-name paths (for example RUNNER~1).
            # resolve(strict=True) above expands the executable to its long path.
            # Establish that this exact interpreter can connect before blocking it.
            subprocess.run([str(executable), "-I", "-B", "-c",
                            "import socket; socket.create_connection(('1.1.1.1',443),timeout=10).close()"],
                           env=environment, check=True, timeout=30)
            # Script is passed as data via an environment variable; no shell interpolation.
            script = work / "restrict.ps1"
            script.write_text("$ErrorActionPreference = 'Stop'\n"
                              "$rule = 'AegisProbe-' + [guid]::NewGuid().ToString()\n"
                              "$cmd = ConvertFrom-Json $env:AEGIS_PROBE_COMMAND\n"
                              "Write-Output ('Firewall target: ' + $cmd[0])\n"
                              "if (!(Test-Path -LiteralPath $cmd[0] -PathType Leaf)) { throw 'Python executable missing' }\n"
                              "if (Get-NetFirewallProfile | Where-Object { $_.Enabled -ne 'True' }) { throw 'Firewall profile disabled' }\n"
                              "try {\n"
                              "  New-NetFirewallRule -DisplayName $rule -Direction Outbound -Program $cmd[0] -Action Block -Enabled True -Profile Any | Out-Null\n"
                              "  $installed = Get-NetFirewallRule -DisplayName $rule -PolicyStore ActiveStore\n"
                              "  if ($installed.Action -ne 'Block' -or $installed.Enabled -ne 'True') { throw 'Firewall rule not active' }\n"
                              "  & $cmd[0] $cmd[1..($cmd.Length-1)]\n"
                              "  if ($LASTEXITCODE -ne 0) { throw 'Bundled probe failed' }\n"
                              "} finally { Remove-NetFirewallRule -DisplayName $rule -ErrorAction SilentlyContinue }\n")
            environment["AEGIS_PROBE_COMMAND"] = json.dumps(command)
            powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
            subprocess.run([str(powershell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)], env=environment, check=True, timeout=300)
        evidence = json.loads(report.read_text())
        evidence.update({"source": url, "source_sha256": actual, "restriction": restriction,
                         "relocated_from": str(original), "relocated_to": str(relocated)})
        output.write_text(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps({"passed": True, "output": str(output), "target": target}))


if __name__ == "__main__":
    main()
