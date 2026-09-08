"""Token-gated, scoped native GET transport for the local capture console.

Source bytes are returned as inert JSON. No target scripts run on station origin.
Browser cookies are not inherited; an explicit authentication profile is required.
"""
import base64
import json
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

try:
    from .politeness import PolitenessEngine
    from .auth import request_headers, ssl_context, SENSITIVE
except ImportError:
    from politeness import PolitenessEngine
    from auth import request_headers, ssl_context, SENSITIVE

MAX_BODY = 32 * 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class CaptureBridge:
    def __init__(self, log_dir, station_port):
        self.token = secrets.token_urlsafe(32)
        self.log_dir = Path(log_dir)
        self.station_port = station_port
        self.session = None
        self.lock = threading.Lock()

    def configure(self, profile):
        target = profile.get('target', {})
        hosts = target.get('allowed_domains', [])
        if not isinstance(hosts, list) or not 1 <= len(hosts) <= 32:
            raise ValueError('Choose 1 to 32 allowed hosts')
        if any(not isinstance(h, str) or not h or len(h) > 253 or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789.-' for c in h) for h in hosts):
            raise ValueError('Allowed hosts must be lowercase hostnames')
        policy = profile.get('politeness') or {}
        # Validate bounded pacing parameters before constructing the engine.
        bounds = {'min_delay_ms': (1, 60000), 'max_delay_ms': (1, 60000),
                  'max_requests_per_minute': (1, 600), 'burst_limit': (1, 10),
                  'consecutive_error_tripwire': (1, 20), 'cooldown_seconds': (1, 600)}
        for key, (lo, hi) in bounds.items():
            if key in policy and (type(policy[key]) not in (int, float) or not lo <= policy[key] <= hi):
                raise ValueError('Invalid pacing parameter: ' + key)
        policy = {**policy, 'respect_retry_after': True, 'adaptive_ewma_backoff': True}
        authentication = profile.get('authentication') or {}
        if not isinstance(authentication, dict):
            raise ValueError('Authentication must be an object')
        auth_hosts = authentication.get('allowed_domains', [])
        if not isinstance(auth_hosts, list) or any(h not in hosts for h in auth_hosts):
            raise ValueError('Credential scope must be within capture scope')
        with self.lock:
            if self.session and not self.session['stop'].is_set():
                raise ValueError('A native capture is already active; stop it first')
            stop = threading.Event()
            sid = secrets.token_hex(12)
            self.log_dir.mkdir(parents=True, exist_ok=True)
            session = dict(id=sid, hosts=hosts, authentication=authentication, stop=stop,
                           engine=PolitenessEngine(policy, stop_event=stop), lock=threading.Lock(),
                           log=self.log_dir / (sid + '.jsonl'))
            self.session = session
            self.event(session, 'started', hosts=hosts, robots_policy=policy.get('robots_policy', 'respect'))
            return {'id': sid, 'log_file': str(session['log'])}

    @staticmethod
    def event(session, event, **fields):
        with session['log'].open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'timestamp': time.time(), 'event': event, **fields}) + '\n')

    def get_session(self, sid):
        session = self.session
        if not session or session['id'] != sid:
            raise ValueError('Unknown capture session')
        return session

    def close(self, sid):
        session = self.get_session(sid)
        session['stop'].set()
        self.event(session, 'stopped')
        return {'stopped': True}

    def fetch(self, sid, url):
        session = self.get_session(sid)
        if not isinstance(url, str) or len(url) > 8192 or any(ord(c) < 32 for c in url):
            raise ValueError('Invalid URL')
        parsed = urllib.parse.urlsplit(url)
        host = parsed.hostname or ''
        if (parsed.scheme not in ('http', 'https') or parsed.username or parsed.password
                or not any(host == h or host.endswith('.' + h) for h in session['hosts'])
                or (parsed.port or (443 if parsed.scheme == 'https' else 80)) == self.station_port):
            raise ValueError('URL is outside the explicit capture scope')
        with session['lock']:
            if session['stop'].is_set() or session['engine'].acquire_permission(url)['aborted']:
                raise ValueError('Capture stopped')
            started = time.monotonic()
            self.event(session, 'request', url=url)
            try:
                authentication = session['authentication']
                headers = {'User-Agent': 'AegisArchive/1.0', 'Accept-Encoding': 'identity'}
                headers.update(request_headers(authentication, url))
                handlers = [NoRedirect()]
                context = ssl_context(authentication, url=url)
                if context is not None:
                    handlers.append(urllib.request.HTTPSHandler(context=context))
                opener = urllib.request.build_opener(*handlers)
                try:
                    response = opener.open(urllib.request.Request(url, headers=headers), timeout=30)
                except urllib.error.HTTPError as error:
                    response = error  # preserve status and Location; never follow implicitly
                with response:
                    body = response.read(MAX_BODY + 1)
                    if len(body) > MAX_BODY:
                        raise ValueError('Response exceeds native transport 32 MiB limit')
                    status = response.code
                    safe_headers = {k.lower(): v for k, v in response.headers.items()
                                    if k.lower() not in SENSITIVE | {'transfer-encoding'}}
                if safe_headers.get('content-encoding', 'identity').lower() not in ('identity', ''):
                    raise ValueError('Server ignored identity encoding; response not archived')
                elapsed = round((time.monotonic() - started) * 1000)
                if status < 400:
                    session['engine'].record_success(url, elapsed)
                else:
                    session['engine'].record_failure(url, status, safe_headers.get('retry-after'))
                self.event(session, 'response', url=url, status=status, bytes=len(body), elapsed_ms=elapsed)
                return {'status': status, 'headers': safe_headers,
                        'body': base64.b64encode(body).decode('ascii')}
            except Exception as error:
                session['engine'].record_failure(url, 0)
                # Keep credential values and exception objects out of persisted logs.
                self.event(session, 'failure', url=url, error_type=type(error).__name__)
                raise ValueError('Native request failed (' + type(error).__name__ + '); check access, TLS and capture log') from error


def handle(handler):
    """Handle only the capture API; caller retains station Host/path guards."""
    path = handler.path.split('?', 1)[0]
    if not path.startswith('/__station/capture/'):
        return False
    bridge = getattr(handler.server, 'capture_bridge', None)
    if bridge is None:
        handler.send_error(503, 'Native capture unavailable')
        return True
    if handler.headers.get('Sec-Fetch-Site') not in (None, 'same-origin'):
        handler.send_error(403, 'Same-origin UI required')
        return True
    origin = handler.headers.get('Origin')
    if origin and origin != 'http://' + handler.headers.get('Host', ''):
        handler.send_error(403, 'Invalid origin')
        return True
    try:
        if path == '/__station/capture/session' and handler.command == 'GET':
            if handler.headers.get('X-Aegis-UI') != '1':
                handler.send_error(403, 'UI bootstrap header required')
                return True
            result = {'token': bridge.token}
        else:
            if handler.command != 'POST' or not secrets.compare_digest(handler.headers.get('X-Capture-Token', ''), bridge.token):
                handler.send_error(403, 'Capture token required')
                return True
            length = int(handler.headers.get('Content-Length', '0'))
            if not 0 < length <= 65536:
                raise ValueError('Invalid request length')
            payload = json.loads(handler.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError('JSON object required')
            if path == '/__station/capture/start':
                result = bridge.configure(payload['profile'])
            elif path == '/__station/capture/fetch':
                result = bridge.fetch(payload['id'], payload['url'])
            elif path == '/__station/capture/stop':
                result = bridge.close(payload['id'])
            else:
                raise ValueError('Unknown capture endpoint')
        body = json.dumps(result).encode('utf-8')
        handler.send_response(200)
    except (ValueError, KeyError, TypeError, AttributeError):
        body = json.dumps({'error': 'Native request rejected or failed; check capture scope, network access, TLS and local capture log.'}).encode('utf-8')
        handler.send_response(400)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Content-Length', str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)
    return True
