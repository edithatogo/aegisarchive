import base64, json, os, time
from urllib.parse import urlparse
SENSITIVE = {'authorization','proxy-authorization','cookie','set-cookie'}
def _load(v):
    if not v: return ''
    if v.startswith('env:'): return os.environ.get(v[4:], '')
    if v.startswith('file:'):
        with open(v[5:], encoding='utf-8') as f: return f.read().strip()
    return v
def request_headers(config, url, now=None):
    config = config or {}
    if not config or config.get('mode') in (None, 'none'): return {}
    if config.get('expires_at') is not None and (time.time() if now is None else now) >= float(config['expires_at']): return {}
    host = (urlparse(url).hostname or '').lower(); domains = [str(d).lower().lstrip('.') for d in config.get('allowed_domains', [])]
    if domains and not any(host == d or host.endswith('.'+d) for d in domains): return {}
    value = _load(config.get('source')); mode = config.get('mode')
    if mode == 'headers_env': return {str(k): str(v) for k,v in json.loads(value).items()} if value else {}
    if mode == 'cookies_env': return {'Cookie': value} if value else {}
    if mode == 'basic_env': return {'Authorization': 'Basic '+base64.b64encode(value.encode()).decode()} if value else {}
    if mode in ('client_certificate','browser_handoff'): return {}
    raise ValueError('unsupported authentication mode')
def redact_headers(headers): return {k: ('[REDACTED]' if k.lower() in SENSITIVE else v) for k,v in headers.items()}
