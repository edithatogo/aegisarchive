"""Safe discovery of archive inputs; filesystem sidecars and symlinks are excluded."""
from pathlib import Path

SUPPORTED_SUFFIXES = ('.warc', '.warc.gz', '.wacz', '.cdx', '.cdxj')

def discover_archive_inputs(root, explicit=()):
    root = Path(root)
    candidates = [Path(p) for p in explicit] if explicit else root.rglob('*')
    result = []
    for path in candidates:
        if path.name.startswith('._') or path.is_symlink() or not path.is_file():
            continue
        if path.suffix.lower() in SUPPORTED_SUFFIXES or path.name.lower().endswith('.warc.gz'):
            result.append(path)
    return sorted(result, key=lambda p: str(p))
