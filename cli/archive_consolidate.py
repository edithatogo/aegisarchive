"""Consolidate synthetic capture segments into content-addressed payloads."""
from __future__ import annotations
import hashlib, json, os, tempfile
from pathlib import Path

def consolidate(records, destination):
    root=Path(destination); root.mkdir(parents=True,exist_ok=True); payloads=root/'payloads'; payloads.mkdir(exist_ok=True); manifest=[]
    for item in records:
        if not isinstance(item,dict) or not isinstance(item.get('url'),str) or not isinstance(item.get('body'),bytes): raise ValueError('invalid capture record')
        digest=hashlib.sha256(item['body']).hexdigest(); target=payloads/digest
        if target.exists() and target.read_bytes()!=item['body']: raise ValueError('conflicting payload')
        if not target.exists():
            fd,tmp=tempfile.mkstemp(dir=payloads)
            try:
                with os.fdopen(fd,'wb') as f: f.write(item['body']); f.flush(); os.fsync(f.fileno())
                os.replace(tmp,target)
            finally:
                if os.path.exists(tmp): os.unlink(tmp)
        manifest.append({'url':item['url'],'status':int(item.get('status',200)),'mime':item.get('mime','application/octet-stream'),'sha256':digest,'bytes':len(item['body']),'revisit':bool(item.get('revisit',False))})
    out=root/'manifest.json'; out.write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n',encoding='utf-8'); return manifest
