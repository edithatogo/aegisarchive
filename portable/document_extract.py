"""Bounded, dependency-free text derivation."""
import hashlib, html, re
MAX_BYTES=32*1024*1024
def extract(content, mime='text/plain', limit=MAX_BYTES):
    if len(content)>limit: return {'status':'failed','reason':'size_limit','text':'','locators':[]}
    if mime in ('text/plain','text/markdown','application/json','text/csv') or mime.startswith('text/'):
        text=content.decode('utf-8','replace'); status='partial' if '\ufffd' in text else 'complete'
    elif mime=='text/html':
        text=re.sub(r'<[^>]+>',' ',html.unescape(content.decode('utf-8','replace'))); text=' '.join(text.split()); status='complete'
    else: return {'status':'unsupported','reason':'no_builtin_extractor','text':'','locators':[]}
    lines=text.splitlines() or ['']; loc=[{'paragraph':i+1,'start':sum(len(x)+1 for x in lines[:i]),'end':sum(len(x)+1 for x in lines[:i+1])} for i in range(len(lines))]
    return {'status':status,'text':text,'locators':loc,'output_hash':hashlib.sha256(text.encode()).hexdigest(),'extractor':'builtin-1'}
