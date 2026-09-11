"""Scoped urllib transport with private route/stage evidence, no global patches."""
import http.client
import ipaddress
import socket
import sys
import time
import urllib.parse
import urllib.request

try:
    from .windows_proxy import WindowsProxyAPI
except ImportError:
    from windows_proxy import WindowsProxyAPI


class NetworkTrace:
    def __init__(self, emit):
        self.emit = emit
        self.stage = 'preflight'
        self.started = time.monotonic()

    def enter(self, stage, **fields):
        self.stage = stage
        self.emit(stage=stage, elapsed_ms=round((time.monotonic() - self.started) * 1000), **fields)

    def connect(self, address, timeout=30, source_address=None, **kwargs):
        self.enter('dns')
        addresses = socket.getaddrinfo(address[0], address[1], 0, socket.SOCK_STREAM)
        self.enter('tcp_connect', address_count=len(addresses))
        last_error = None
        # Bound TCP attempts collectively; DNS uses the operating system resolver.
        deadline = time.monotonic() + timeout
        for family, socktype, proto, _, sockaddr in addresses:
            sock = None
            try:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError()
                sock = socket.socket(family, socktype, proto)
                sock.settimeout(remaining)
                if source_address:
                    sock.bind(source_address)
                sock.connect(sockaddr)
                sock.settimeout(timeout)
                return sock
            except OSError as error:
                last_error = error
                if sock is not None:
                    sock.close()
        if last_error:
            raise last_error
        raise OSError('No usable address')

    def handlers(self, context=None):
        trace = self

        class Connection(http.client.HTTPConnection):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._create_connection = trace.connect

            def connect(self):
                super().connect()
                trace.enter('request_headers')

            def _tunnel(self):
                trace.enter('proxy_tunnel')
                return super()._tunnel()

            def getresponse(self):
                trace.enter('response_headers')
                return super().getresponse()

        class SecureConnection(Connection, http.client.HTTPSConnection):
            def connect(self):
                # Preserve stdlib CONNECT and verified SSL context; the only
                # change is stage boundaries around the TLS handshake.
                http.client.HTTPConnection.connect(self)
                trace.enter('tls')
                hostname = self._tunnel_host or self.host
                self.sock = self._context.wrap_socket(self.sock, server_hostname=hostname)
                trace.enter('request_headers')

        class HTTP(urllib.request.HTTPHandler):
            def http_open(self, req):
                return self.do_open(Connection, req)

        class HTTPS(urllib.request.HTTPSHandler):
            def https_open(self, req):
                return self.do_open(SecureConnection, req, context=self._context)

        return [HTTP(), HTTPS(context=context)]


class _ResolvedProxy(urllib.request.ProxyHandler):
    """A destination-specific PAC result must not be overridden by ambient bypass."""
    def proxy_open(self, req, proxy, scheme):
        req.set_proxy(proxy, 'http')
        return None


def route_handlers(url, trace):
    trace.enter('proxy_resolution')
    parsed = urllib.parse.urlsplit(url)
    environment = urllib.request.getproxies_environment()
    # An explicit environment configuration, including no_proxy, retains normal
    # urllib semantics. Do not silently override an operator's routing choice.
    if sys.platform == 'win32' and not environment:
        host = parsed.hostname or ''
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = host.lower() == 'localhost'
        if loopback:
            trace.enter('proxy_resolution', source='loopback', route='direct')
            return [urllib.request.ProxyHandler({})]
        api = WindowsProxyAPI()
        settings = api.settings()
        trace.enter('proxy_resolution', source='windows_settings',
                    auto_detect=settings['auto_detect'], pac_present=bool(settings['pac_url']),
                    static_proxy_present=bool(settings.get('static_proxy_present')),
                    bypass_present=bool(settings.get('bypass_present')))
        if settings['pac_url'] or settings['auto_detect']:
            proxy, count = api.resolve(url, settings)
            trace.enter('proxy_resolution', source='windows_auto', route='proxy' if proxy else 'direct', proxy_candidates=count)
            return [_ResolvedProxy({parsed.scheme: proxy}) if proxy else urllib.request.ProxyHandler({})]
    proxies = urllib.request.getproxies()
    bypass = urllib.request.proxy_bypass(parsed.netloc)
    trace.enter('proxy_resolution', source='environment' if environment else 'platform',
                route='proxy' if proxies.get(parsed.scheme) and not bypass else 'direct',
                bypass=bool(bypass), proxy_configured=bool(proxies.get(parsed.scheme)))
    return [urllib.request.ProxyHandler(proxies)]
