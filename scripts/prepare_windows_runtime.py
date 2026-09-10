"""Prepare a USB runtime on a maintainer computer; never download at launch."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def prepare(archive, destination, lock):
    if hashlib.sha256(Path(archive).read_bytes()).hexdigest() != lock['sha256']:
        raise ValueError('Windows Python archive checksum mismatch')
    if destination.exists():
        raise FileExistsError('Runtime already exists; verify it before replacing it')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temp:
        stage = Path(temp) / 'python'
        stage.mkdir()
        with zipfile.ZipFile(archive) as source:
            for entry in source.infolist():
                if '/' in entry.filename or '\\' in entry.filename or ':' in entry.filename or entry.filename in ('.', '..'):
                    raise ValueError('Unexpected archive member')
                (stage / entry.filename).write_bytes(source.read(entry))
        if not (stage / 'python.exe').is_file():
            raise ValueError('Missing Python executable')
        paths = list(stage.glob('python*._pth'))
        if len(paths) != 1:
            raise ValueError('Missing isolated import configuration')
        paths[0].write_text(paths[0].read_text() + '\n..\\..\n', encoding='utf-8')
        # macOS may create AppleDouble companions on exFAT; they are not runtime files.
        manifest = dict(lock, files={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in stage.iterdir() if not p.name.startswith('._')})
        (stage / 'runtime-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        stage.rename(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path)
    args = parser.parse_args()
    lock = json.loads((ROOT / 'portable/windows-python.json').read_text())
    with tempfile.TemporaryDirectory() as temp:
        archive = args.archive or Path(temp) / 'python.zip'
        if args.archive is None:
            with urllib.request.urlopen(lock['url'], timeout=60) as response, archive.open('wb') as output:
                shutil.copyfileobj(response, output)
        prepare(archive, ROOT / 'runtime/python', lock)
    print('Prepared runtime/python/python.exe (Windows x64); no target installation required.')


if __name__ == '__main__':
    main()
