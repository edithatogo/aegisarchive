"""Stage the pinned GNU Bash source using HTTPS mirrors.

Hosted Windows often cannot open ftp.gnu.org. The provisioner fetch skips the
download when this path already has the locked SHA-256. This module only imports
URL and digest pins from provision_native; it does not change that file.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import shutil
import urllib.error
import urllib.request

from portable.provision_native import BASH_SHA, BASH_URL, digest

MIRRORS = (
    'https://ftpmirror.gnu.org/gnu/bash/bash-5.3.tar.gz',
    'https://mirrors.kernel.org/gnu/bash/bash-5.3.tar.gz',
    BASH_URL,
)


def stage(work: Path, opener=None) -> Path:
    target = work / 'downloads' / 'bash.tar.gz'
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and digest(target) == BASH_SHA:
        return target
    open_url = opener or urllib.request.urlopen
    last_error = None
    for url in MIRRORS:
        temporary = target.with_suffix(target.suffix + '.part')
        try:
            request = urllib.request.Request(
                url, headers={'User-Agent': 'AegisArchive-provisioner/1'})
            with open_url(request, timeout=180) as source, temporary.open('wb') as output:
                shutil.copyfileobj(source, output)
            if digest(temporary) != BASH_SHA:
                temporary.unlink(missing_ok=True)
                last_error = ValueError('checksum mismatch: ' + url)
                continue
            temporary.replace(target)
            return target
        except (OSError, urllib.error.URLError, ValueError) as error:
            last_error = error
            temporary.unlink(missing_ok=True)
    raise RuntimeError('pinned Bash source unavailable: ' + str(last_error))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args(argv)
    path = stage(args.work.resolve())
    print({'bash': str(path), 'sha256': BASH_SHA, 'inference_claimed': False})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
