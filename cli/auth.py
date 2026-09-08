import base64, json, os, ssl, time
import urllib.request
from urllib.parse import urlparse
def _in_scope(config, url):
    host = (urlparse(url).hostname or '').lower()
    return any(host == d.lower().lstrip('.') or host.endswith('.' + d.lower().lstrip('.')) for d in config.get('allowed_domains', []))

SENSITIVE = {'authorization','proxy-authorization','cookie','set-cookie'}
def _load(v):
    if not v: return ''
    if v.startswith('env:'): return os.environ.get(v[4:], '')
    if v.startswith('file:'):
        with open(v[5:], encoding='utf-8') as f: return f.read().strip()
    return v

def _browser_session(config):
    """Load a Playwright-compatible storage-state JSON without retaining it."""
    value = _load(config.get('source'))
    if not value:
        return {}, []
    try:
        state = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError('browser session source must be JSON') from exc
    headers = {str(k): str(v) for k, v in (state.get('headers') or {}).items()}
    cookies = state.get('cookies') or []
    if not isinstance(cookies, list):
        raise ValueError('browser session cookies must be a list')
    return headers, cookies

def _session_cookie_header(cookies, url, now):
    parsed = urlparse(url)
    host = (parsed.hostname or '').lower()
    path = parsed.path or '/'
    selected = []
    for cookie in cookies:
        if not isinstance(cookie, dict) or not cookie.get('name'):
            continue
        domain = str(cookie.get('domain', '')).lower().lstrip('.')
        if not domain or (host != domain and (not str(cookie.get('domain', '')).startswith('.') or not host.endswith('.' + domain))):
            continue
        cookie_path = str(cookie.get('path') or '/')
        if cookie.get('secure') and parsed.scheme != 'https':
            continue
        if path != cookie_path and not path.startswith(cookie_path if cookie_path.endswith('/') else cookie_path + '/'):
            continue
        expires = cookie.get('expires', cookie.get('expires_at'))
        if expires not in (None, -1, 0):
            try:
                if now >= float(expires):
                    continue
            except (TypeError, ValueError):
                continue
        selected.append(f"{cookie['name']}={cookie.get('value', '')}")
    return '; '.join(selected)
def request_headers(config, url, now=None):
    config = config or {}
    if not config or config.get('mode') in (None, 'none'): return {}
    if config.get('expires_at') is not None and (time.time() if now is None else now) >= float(config['expires_at']): return {}
    host = (urlparse(url).hostname or '').lower(); domains = [str(d).lower().lstrip('.') for d in config.get('allowed_domains', [])]
    if not _in_scope(config, url): return {}
    value = _load(config.get('source')); mode = config.get('mode')
    if mode == 'headers_env': return {str(k): str(v) for k,v in json.loads(value).items()} if value else {}
    if mode == 'cookies_env': return {'Cookie': value} if value else {}
    if mode == 'basic_env': return {'Authorization': 'Basic '+base64.b64encode(value.encode()).decode()} if value else {}
    if mode == 'browser_session':
        session_headers, cookies = _browser_session(config)
        result = dict(session_headers)
        cookie = _session_cookie_header(cookies, url, time.time() if now is None else now)
        if cookie:
            result['Cookie'] = cookie
        return result
    if mode in ('client_certificate','browser_handoff'): return {}
    raise ValueError('unsupported authentication mode')

def browser_handoff(config, url, now=None):
    """Return a safe browser hand-off request, without touching credentials.

    The operator authenticates in an existing browser (including SSO/MFA), then
    explicitly exports session state through a separate mechanism. AegisArchive
    never automates the login, reads passwords, or converts the hand-off into
    request headers. This function only validates scope/expiry and returns
    display-safe instructions for a UI or external browser adapter.
    """
    config = config or {}
    if config.get('mode') != 'browser_handoff':
        return None
    now = time.time() if now is None else now
    if config.get('expires_at') is not None and now >= float(config['expires_at']):
        return None
    host = (urlparse(url).hostname or '').lower()
    domains = [str(d).lower().lstrip('.') for d in config.get('allowed_domains', [])]
    if not _in_scope(config, url):
        return None
    return {
        'url': url,
        'allowed_domains': domains,
        'expires_at': config.get('expires_at'),
        'requires_operator_login': True,
        'supports_sso_mfa': True,
        'credential_collection': 'none',
        'session_import_required': True,
    }
def redact_headers(headers): return {k: ('[REDACTED]' if k.lower() in SENSITIVE else v) for k,v in headers.items()}

def ssl_context(config, now=None, url=None):
    """Build an optional mutual-TLS context from profile file paths."""
    config = config or {}
    if config.get('mode') != 'client_certificate':
        return None
    if config.get('expires_at') is not None and (time.time() if now is None else now) >= float(config['expires_at']):
        return None
    if url is not None and not _in_scope(config, url):
        return None
    certfile = config.get('certificate_file')
    keyfile = config.get('key_file')
    if not certfile or not keyfile:
        raise ValueError('client_certificate requires certificate_file and key_file')
    cafile = config.get('ca_file')
    context = ssl.create_default_context(cafile=cafile or None)
    context.load_cert_chain(certfile=certfile, keyfile=keyfile)
    return context

def opener_for_auth(config):
    context = ssl_context(config)
    if context is None:
        return urllib.request.build_opener()
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=context))
