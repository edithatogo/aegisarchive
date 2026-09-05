"""Build and verify offline packages from explicitly vetted local assets.

No downloads happen here. Asset checksums must come from an independent trusted
release record; a checksum calculated from an untrusted download is not approval.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import shlex
import stat
import tarfile
import tempfile
import zipfile

APP_PATHS = ('cli', 'web', 'mcp', 'portable', 'profiles', 'presets', 'LICENSE',
             'README.md', 'START_MAC.command', 'START_WINDOWS.cmd', 'START_LINUX.sh')
MAX_EXPANDED_BYTES = 20 * 1024**3


def digest(path):
    value = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def safe_path(name):
    """Reject names unsafe on any supported platform, including NTFS streams."""
    parts = PurePosixPath(name).parts
    if (not name or not parts or '\\' in name or ':' in name or name.startswith('/') or
            any(p in ('..', '.') or p.endswith((' ', '.')) or
                p.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL',
                    *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}
                for p in parts) or any(ord(c) < 32 for c in name)):
        raise ValueError('unsafe package path: ' + repr(name))
    return Path(*parts)


def extract(archive, destination):
    """Extract regular files/directories only, with size and collision limits."""
    destination = Path(destination)
    seen = set()
    total = 0

    def target(name, size, directory=False):
        nonlocal total
        relative = safe_path(name.rstrip('/'))
        key = str(relative).casefold()
        if key in seen:
            raise ValueError('duplicate archive member: ' + name)
        seen.add(key)
        total += size
        if size < 0 or total > MAX_EXPANDED_BYTES:
            raise ValueError('archive exceeds extraction budget')
        result = destination / relative
        result.parent.mkdir(parents=True, exist_ok=True)
        if directory:
            result.mkdir(exist_ok=True)
        return result

    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                mode = member.external_attr >> 16
                if stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
                    raise ValueError('archive special file forbidden')
                out = target(member.filename, member.file_size, member.is_dir())
                if not member.is_dir():
                    with bundle.open(member) as incoming, out.open('xb') as stream:
                        shutil.copyfileobj(incoming, stream)
                    out.chmod(0o755 if mode & 0o111 else 0o644)
    else:
        with tarfile.open(archive) as bundle:
            for member in bundle:
                if not (member.isfile() or member.isdir()):
                    raise ValueError('archive links and special files forbidden')
                out = target(member.name, member.size, member.isdir())
                if member.isfile():
                    with bundle.extractfile(member) as incoming, out.open('xb') as stream:
                        shutil.copyfileobj(incoming, stream)
                    out.chmod(0o755 if member.mode & 0o111 else 0o644)


def files(root):
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('package symlink forbidden: ' + str(path))
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            safe_path(relative)
            if relative == 'manifest.json' or relative.startswith('data/'):
                continue
            result[relative] = {'sha256': digest(path), 'size': path.stat().st_size,
                                'executable': bool(path.stat().st_mode & 0o111)}
    return result


def assemble(source, destination, assets=()):
    """Create a new package atomically; never overwrite existing user data.

    Assets have id, platform, archive, sha256, source_url, license, license_file,
    and entrypoint. The last two paths refer to files inside the archive.
    """
    if Path(destination).is_symlink():
        raise ValueError('destination symlink forbidden')
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination.exists() or destination.is_symlink():
        raise ValueError('destination already exists')
    if source == destination or source in destination.parents:
        raise ValueError('destination must be outside source tree')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.aegis-package-', dir=destination.parent) as temp:
        root = Path(temp) / 'package'
        for name in ('app', 'data', 'runtime', 'licenses'):
            (root / name).mkdir(parents=True)
        for name in APP_PATHS:
            path = source / name
            if not path.exists():
                continue
            # Never dereference a source symlink, even when it targets outside the tree.
            candidates = [path, *path.rglob('*')] if path.is_dir() else [path]
            if any(p.is_symlink() for p in candidates):
                raise ValueError('application source symlink forbidden')
            if path.is_dir():
                shutil.copytree(path, root / 'app' / name,
                                ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            else:
                shutil.copy2(path, root / 'app' / name)
        if not (root / 'app' / 'cli' / 'launch.py').is_file():
            raise ValueError('application source lacks cli/launch.py')
        records = []
        identifiers = set()
        for asset in assets:
            identifier = asset['id']
            if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,79}', identifier) or identifier in identifiers:
                raise ValueError('invalid or repeated asset id')
            identifiers.add(identifier)
            if not re.fullmatch(r'[a-f0-9]{64}', asset['sha256']):
                raise ValueError('asset requires SHA256 pin')
            if not asset['source_url'].startswith('https://') or not asset['license'].strip() or not asset['platform'].strip():
                raise ValueError('asset requires provenance, platform and license')
            if digest(asset['archive']) != asset['sha256']:
                raise ValueError('asset checksum mismatch: ' + identifier)
            target = root / 'runtime' / identifier
            target.mkdir()
            extract(asset['archive'], target)
            license_path = target / safe_path(asset['license_file'])
            entrypoint = target / safe_path(asset['entrypoint'])
            if not license_path.is_file() or not entrypoint.is_file():
                raise ValueError('asset license or entrypoint missing')
            shutil.copyfile(license_path, root / 'licenses' / (identifier + '.txt'))
            records.append({k: asset[k] for k in ('id', 'platform', 'sha256', 'source_url',
                                                'license', 'license_file', 'entrypoint')})
        python_assets = [asset for asset in records if asset['id'] == 'python']
        if python_assets:
            interpreter = 'runtime/python/' + safe_path(python_assets[0]['entrypoint']).as_posix()
            launcher = ('#!/bin/sh\nset -eu\n'
                        'cd "$(dirname "$0")"\n'
                        'bundle_root="$PWD"\n'
                        'cd app\n'
                        'exec "$bundle_root"/' + shlex.quote(interpreter) +
                        ' -I -B cli/launch.py "$@"\n')
            for name in ('START_MAC.command', 'START_LINUX.sh'):
                (root / name).write_text(launcher)
                (root / name).chmod(0o755)
            if python_assets[0]['platform'].startswith('windows'):
                if any(char in interpreter for char in '%!"'):
                    raise ValueError('unsafe Windows interpreter path')
                (root / 'START_WINDOWS.cmd').write_text(
                    '@echo off\r\ncd /d "%~dp0app"\r\n"%~dp0' +
                    interpreter.replace('/', '\\') +
                    '" -I -B cli/launch.py %*\r\n')
        manifest = {'schema_version': 1, 'application': 'AegisArchive',
                    'layout': {'application': 'app', 'writable_data': 'data', 'runtimes': 'runtime'},
                    'assets': records, 'files': files(root)}
        (root / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        verify(root)
        os.rename(root, destination)
    return manifest


def verify(package):
    """Verify all immutable files offline; user data is intentionally mutable.

    This detects corruption relative to a manifest, not authenticity: distribute
    the manifest digest/signature through an independent trusted channel.
    """
    root = Path(package)
    if root.is_symlink() or (root / 'manifest.json').is_symlink():
        raise ValueError('package or manifest symlink forbidden')
    manifest = json.loads((root / 'manifest.json').read_text())
    if manifest.get('schema_version') != 1 or not isinstance(manifest.get('files'), dict):
        raise ValueError('unsupported package manifest')
    for name in ('app', 'data', 'runtime', 'licenses'):
        if not (root / name).is_dir() or (root / name).is_symlink():
            raise ValueError('missing package directory: ' + name)
    actual = files(root)
    if actual != manifest['files']:
        raise ValueError('package integrity mismatch')
    for asset in manifest.get('assets', []):
        identifier = asset['id']
        if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,79}', identifier):
            raise ValueError('invalid asset id')
        for field in ('entrypoint', 'license_file'):
            path = 'runtime/' + identifier + '/' + safe_path(asset[field]).as_posix()
            if path not in actual:
                raise ValueError('missing asset ' + field)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    build = sub.add_parser('build')
    build.add_argument('source')
    build.add_argument('destination')
    build.add_argument('--assets', help='JSON list of vetted local runtime archives')
    check = sub.add_parser('verify')
    check.add_argument('package')
    args = parser.parse_args()
    try:
        if args.command == 'build':
            assets = json.loads(Path(args.assets).read_text()) if args.assets else []
            result = assemble(args.source, args.destination, assets)
        else:
            result = verify(args.package)
    except (ValueError, OSError, KeyError, tarfile.TarError, zipfile.BadZipFile) as error:
        parser.exit(1, str(error) + '\n')
    print(json.dumps({'files': len(result['files']), 'assets': len(result['assets'])}))


if __name__ == '__main__':
    main()
