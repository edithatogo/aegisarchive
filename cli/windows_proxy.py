"""Read-only per-user Windows auto-proxy resolution; no browser credentials.

Allocated WinHTTP strings remain raw pointers until copied and GlobalFree'd.
No raw Windows errors, PAC URLs or proxy addresses are diagnostic fields.
"""
import ctypes
import re
import urllib.parse


class ProxyDiscoveryError(OSError):
    def __init__(self, code=0):
        super().__init__('Windows proxy discovery failed or returned an unsupported route')
        self.winerror = code


def proxy_for_scheme(value, scheme):
    """Select the first applicable HTTP proxy; never invent a direct fallback."""
    if not value or any(ord(c) < 32 for c in value):
        raise ProxyDiscoveryError()
    candidates = []
    for item in re.split(r'[; ]+', value.strip()):
        if not item:
            continue
        if '=' in item:
            selector, item = item.split('=', 1)
            if selector not in ('http', 'https'):
                raise ProxyDiscoveryError()
            if selector != scheme:
                continue
        # WinHTTP's https= selector denotes the destination, not TLS-to-proxy.
        if item.startswith('http://'):
            item = item[7:]
        parsed = urllib.parse.urlsplit('http://' + item)
        try:
            port = parsed.port
        except ValueError as error:
            raise ProxyDiscoveryError() from error
        if (not parsed.hostname or parsed.username is not None or parsed.password is not None
                or parsed.path or parsed.query or parsed.fragment or '%' in item
                or any(c.isspace() for c in item) or port == 0):
            raise ProxyDiscoveryError()
        candidates.append(item)
    if not candidates:
        raise ProxyDiscoveryError()
    return candidates[0], len(candidates)


class _UserConfig(ctypes.Structure):
    _fields_ = [('auto', ctypes.c_int32), ('pac', ctypes.c_void_p),
                ('proxy', ctypes.c_void_p), ('bypass', ctypes.c_void_p)]


class _Options(ctypes.Structure):
    _fields_ = [('flags', ctypes.c_uint32), ('detect', ctypes.c_uint32),
                ('url', ctypes.c_wchar_p), ('reserved', ctypes.c_void_p),
                ('reserved_flags', ctypes.c_uint32), ('auto_logon', ctypes.c_int32)]


class _ProxyInfo(ctypes.Structure):
    _fields_ = [('access', ctypes.c_uint32), ('proxy', ctypes.c_void_p),
                ('bypass', ctypes.c_void_p)]


class WindowsProxyAPI:
    def __init__(self):
        # WinDLL uses the system DLL search rules, not the USB working directory.
        self.dll = ctypes.WinDLL('winhttp.dll', use_last_error=True, winmode=0x800)
        self.kernel = ctypes.WinDLL('kernel32.dll', use_last_error=True, winmode=0x800)
        definitions = {
            'WinHttpGetIEProxyConfigForCurrentUser': ([ctypes.POINTER(_UserConfig)], ctypes.c_int32),
            'WinHttpOpen': ([ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32], ctypes.c_void_p),
            'WinHttpSetTimeouts': ([ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int], ctypes.c_int32),
            'WinHttpGetProxyForUrl': ([ctypes.c_void_p, ctypes.c_wchar_p, ctypes.POINTER(_Options), ctypes.POINTER(_ProxyInfo)], ctypes.c_int32),
            'WinHttpCloseHandle': ([ctypes.c_void_p], ctypes.c_int32),
        }
        for name, (args, result) in definitions.items():
            function = getattr(self.dll, name)
            function.argtypes, function.restype = args, result
        self.kernel.GlobalFree.argtypes = [ctypes.c_void_p]
        self.kernel.GlobalFree.restype = ctypes.c_void_p

    def _free(self, *pointers):
        for pointer in pointers:
            if pointer:
                self.kernel.GlobalFree(pointer)

    def settings(self):
        config = _UserConfig()
        try:
            if not self.dll.WinHttpGetIEProxyConfigForCurrentUser(ctypes.byref(config)):
                raise ProxyDiscoveryError(ctypes.get_last_error())
            return {'auto_detect': bool(config.auto),
                    'pac_url': ctypes.wstring_at(config.pac) if config.pac else '',
                    'static_proxy_present': bool(config.proxy),
                    'bypass_present': bool(config.bypass)}
        finally:
            self._free(config.pac, config.proxy, config.bypass)

    def resolve(self, url, settings):
        pac = settings.get('pac_url', '')
        if pac:
            parsed = urllib.parse.urlsplit(pac)
            if (parsed.scheme not in ('http', 'https') or not parsed.hostname
                    or parsed.username is not None or parsed.password is not None
                    or any(ord(c) < 32 for c in pac)):
                raise ProxyDiscoveryError()
        elif not settings.get('auto_detect'):
            raise ProxyDiscoveryError()
        options = _Options(2 if pac else 1, 0 if pac else 3, pac or None, None, 0, 0)
        info = _ProxyInfo()
        handle = self.dll.WinHttpOpen('AegisArchive/1.0', 1, None, None, 0)
        if not handle:
            raise ProxyDiscoveryError(ctypes.get_last_error())
        try:
            if not self.dll.WinHttpSetTimeouts(handle, 10000, 10000, 10000, 10000):
                raise ProxyDiscoveryError(ctypes.get_last_error())
            if not self.dll.WinHttpGetProxyForUrl(handle, url, ctypes.byref(options), ctypes.byref(info)):
                raise ProxyDiscoveryError(ctypes.get_last_error())
            if info.access == 1:  # WINHTTP_ACCESS_TYPE_NO_PROXY
                return None, 0
            if info.access != 3 or not info.proxy or info.bypass:
                # PAC normally returns a destination-specific result without a
                # bypass list. Unsupported results must not silently go direct.
                raise ProxyDiscoveryError()
            return proxy_for_scheme(ctypes.wstring_at(info.proxy), urllib.parse.urlsplit(url).scheme)
        finally:
            self._free(info.proxy, info.bypass)
            self.dll.WinHttpCloseHandle(handle)
