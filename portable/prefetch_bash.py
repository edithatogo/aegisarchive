"""Stage the pinned GNU Bash source using HTTPS mirrors.

Hosted Windows often cannot open ftp.gnu.org. The provisioner fetch skips the
download when this path already has the locked SHA-256. This module only imports
URL and digest pins from provision_native; it does not change that file.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import shutil
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urljoin, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from portable.provision_native import BASH_SHA, BASH_URL, digest
from cli.politeness import PolitenessEngine

MIRRORS = (
    'https://ftpmirror.gnu.org/gnu/bash/bash-5.3.tar.gz',
    'https://mirrors.kernel.org/gnu/bash/bash-5.3.tar.gz',
    BASH_URL,
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def polite_open(url, open_url, engine):
    # Handle redirects explicitly so every destination acquires permission.
    for _ in range(10):
        if urlparse(url).scheme != 'https':
            raise ValueError('Bash source must use HTTPS')
        if engine.acquire_permission(url)['aborted']:
            raise InterruptedError('Bash source acquisition interrupted')
        started = time.monotonic()
        try:
            response = open_url(urllib.request.Request(
                url, headers={'User-Agent': 'AegisArchive-provisioner/1'}), timeout=180)
        except urllib.error.HTTPError as error:
            try:
                if error.code in (301, 302, 303, 307, 308):
                    location = error.headers.get('Location')
                    if not location:
                        raise ValueError('Redirect is missing Location') from error
                    url = urljoin(url, location)
                    continue
                engine.record_failure(url, error.code, error.headers.get('Retry-After'))
                raise
            finally:
                error.close()
        except (OSError, urllib.error.URLError):
            engine.record_failure(url, 0)
            raise
        engine.record_success(url, (time.monotonic() - started) * 1000)
        return response
    raise ValueError('Too many Bash source redirects')


def stage(work: Path, opener=None, engine=None) -> Path:
    target = work / 'downloads' / 'bash.tar.gz'
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and digest(target) == BASH_SHA:
        return target
    open_url = opener or urllib.request.build_opener(NoRedirect()).open
    engine = engine or PolitenessEngine()
    last_error = None
    for url in MIRRORS:
        temporary = target.with_suffix(target.suffix + '.part')
        try:
            with polite_open(url, open_url, engine) as source, temporary.open('wb') as output:
                shutil.copyfileobj(source, output)
            if digest(temporary) != BASH_SHA:
                temporary.unlink(missing_ok=True)
                last_error = ValueError('checksum mismatch: ' + url)
                continue
            temporary.replace(target)
            return target
        except InterruptedError:
            temporary.unlink(missing_ok=True)
            raise
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
