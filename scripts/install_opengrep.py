#!/usr/bin/env python3
"""Install the SHA-256-qualified OpenGrep v1.33.1 standalone Linux CLI.

No shell execution, semgrep Python CLI, credentials or runtime dependencies.
The source code is never sent to the installer.
"""
from __future__ import annotations

import hashlib
import os
import platform
import sys
import tempfile
from pathlib import Path
from urllib.request import urlopen

VERSION = "v1.33.1"
URL = "https://github.com/opengrep/opengrep/releases/download/v1.33.1/opengrep_manylinux_x86"
SHA256 = "46e8133cc490f9f50518061590ce2f6be5a08afaeda034471c0ceda4b3899808"
MAX_BYTES = 64 * 1024 * 1024


def install(directory: Path) -> Path:
    """Download and atomically install only the pinned binary; reject other bytes."""
    if platform.system() != "Linux" or platform.machine() not in ("x86_64", "AMD64"):
        raise RuntimeError("The pinned OpenGrep asset supports Linux x86_64 only")
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / "opengrep"
    staging: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, prefix=".opengrep-", delete=False) as output:
            staging = Path(output.name)
            digest = hashlib.sha256()
            size = 0
            with urlopen(URL, timeout=120) as response:  # noqa: S310 - fixed HTTPS host, digest checked
                while block := response.read(1024 * 1024):
                    size += len(block)
                    if size > MAX_BYTES:
                        raise RuntimeError("OpenGrep release exceeds bounded size")
                    digest.update(block)
                    output.write(block)
        if size == 0 or digest.hexdigest() != SHA256:
            raise RuntimeError("OpenGrep release SHA-256 verification failed")
        staging.chmod(0o755)
        os.replace(staging, destination)
        return destination
    finally:
        if staging is not None:
            staging.unlink(missing_ok=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/install_opengrep.py <destination-directory>")
    print(install(Path(sys.argv[1]).resolve()))
