"""Dependency-free deterministic export of captured URL/payload records."""
from __future__ import annotations
import hashlib, json, posixpath, re, zipfile
from pathlib import Path
from urllib.parse import urlparse

def safe_path(url: str) -> str:
    p = urlparse(url)
    if p.scheme not in ('http','https') or not p.netloc: raise ValueError('unsupported URL')
    path = p.path or '/index.html'
    if path.endswith('/'): path += 'index.html'
    name = posixpath.normpath(path).lstrip('/')
    if name == '..' or name.startswith('../') or '\\' in name: raise ValueError('unsafe path')
    if p.query: name += '__q_' + hashlib.sha256(p.query.encode()).hexdigest()[:12]
    return name[:240]

def export_directory(records, destination):
    root = Path(destination); root.mkdir(parents=True, exist_ok=True); manifest=[]
    for url, payload in sorted(records, key=lambda x:x[0]):
        rel=safe_path(url); target=root/rel; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(payload)
        manifest.append({'url':url,'path':rel,'sha256':hashlib.sha256(payload).hexdigest(),'bytes':len(payload)})
    (root/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n',encoding='utf-8'); return manifest

def export_zip(records, destination):
    import tempfile, shutil
    with tempfile.TemporaryDirectory() as t:
        export_directory(records,t)
        with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as z:
            for p in sorted(Path(t).rglob('*')):
                if p.is_file():
                    info=zipfile.ZipInfo(p.relative_to(t).as_posix(),date_time=(1980,1,1,0,0,0)); info.compress_type=zipfile.ZIP_DEFLATED; z.writestr(info,p.read_bytes())
