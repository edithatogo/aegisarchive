import sys
import ctypes
import unittest
from unittest.mock import Mock, patch

from cli.windows_proxy import WindowsProxyAPI, proxy_for_scheme, ProxyDiscoveryError, _UserConfig, _ProxyInfo, _Options


class ProxyParsingTests(unittest.TestCase):
    def test_allocated_settings_strings_are_copied_and_freed(self):
        buffers = [ctypes.create_unicode_buffer(value) for value in ('http://pac.example.test/', 'proxy.example.test:80', '<local>')]
        pointers = [ctypes.addressof(buffer) for buffer in buffers]
        api = WindowsProxyAPI.__new__(WindowsProxyAPI); api.dll = Mock(); api.kernel = Mock()
        def configure(pointer):
            config = ctypes.cast(pointer, ctypes.POINTER(_UserConfig)).contents
            config.auto = 1; config.pac, config.proxy, config.bypass = pointers
            return 1
        api.dll.WinHttpGetIEProxyConfigForCurrentUser.side_effect = configure
        result = api.settings()
        self.assertEqual(result['pac_url'], 'http://pac.example.test/')
        self.assertEqual([call.args[0] for call in api.kernel.GlobalFree.call_args_list], pointers)

    def test_resolution_frees_outputs_and_never_enables_auto_logon(self):
        buffer = ctypes.create_unicode_buffer('proxy.example.test:8080')
        api = WindowsProxyAPI.__new__(WindowsProxyAPI); api.dll = Mock(); api.kernel = Mock()
        api.dll.WinHttpOpen.return_value = 123
        def resolve(handle, url, options_pointer, info_pointer):
            options = ctypes.cast(options_pointer, ctypes.POINTER(_Options)).contents
            self.assertEqual(options.auto_logon, 0)
            info = ctypes.cast(info_pointer, ctypes.POINTER(_ProxyInfo)).contents
            info.access = 3; info.proxy = ctypes.addressof(buffer)
            return 1
        api.dll.WinHttpGetProxyForUrl.side_effect = resolve
        self.assertEqual(api.resolve('http://target.example.test/', {'pac_url': 'http://pac.example.test/'}), ('proxy.example.test:8080', 1))
        api.kernel.GlobalFree.assert_called_once_with(ctypes.addressof(buffer))
        api.dll.WinHttpCloseHandle.assert_called_once_with(123)

    def test_discovery_error_closes_handle_without_retrying(self):
        api = WindowsProxyAPI.__new__(WindowsProxyAPI); api.dll = Mock(); api.kernel = Mock()
        api.dll.WinHttpOpen.return_value = 123
        api.dll.WinHttpGetProxyForUrl.return_value = 0
        with patch('cli.windows_proxy.ctypes.get_last_error', return_value=12180, create=True):
            with self.assertRaises(ProxyDiscoveryError) as caught:
                api.resolve('http://target.example.test/', {'auto_detect': True})
        self.assertEqual(caught.exception.winerror, 12180)
        api.dll.WinHttpGetProxyForUrl.assert_called_once()
        api.dll.WinHttpCloseHandle.assert_called_once_with(123)

    def test_scheme_selection_and_multiple_candidates(self):
        self.assertEqual(proxy_for_scheme('http=a.test:80;https=b.test:81', 'https'), ('b.test:81', 1))
        self.assertEqual(proxy_for_scheme('a.test:80; b.test:81', 'http'), ('a.test:80', 2))
        self.assertEqual(proxy_for_scheme('[::1]:8080', 'https'), ('[::1]:8080', 1))

    def test_unsupported_routes_fail_closed(self):
        for value in ('', 'user:secret@a.test:80', 'socks=a.test:80', 'https://a.test:80', 'a.test:bad', 'a.test:80/path', 'a.test:80\n'):
            with self.subTest(value=value), self.assertRaises(ProxyDiscoveryError):
                proxy_for_scheme(value, 'http')

    @unittest.skipUnless(sys.platform == 'win32', 'Windows native bindings')
    def test_current_user_settings_native_api(self):
        settings = WindowsProxyAPI().settings()
        self.assertIs(type(settings['auto_detect']), bool)
        self.assertIsInstance(settings['pac_url'], str)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows PAC evaluator')
    def test_native_pac_direct_and_proxy_per_destination(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading
        class PAC(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Type', 'application/x-ns-proxy-autoconfig')
                self.end_headers()
                self.wfile.write(b'function FindProxyForURL(url, host) { return host == "direct.example.test" ? "DIRECT" : "PROXY 127.0.0.1:9191"; }')
            def log_message(self, *args): pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), PAC)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            api = WindowsProxyAPI()
            settings = {'pac_url': 'http://127.0.0.1:%s/proxy.pac' % server.server_port, 'auto_detect': False}
            self.assertEqual(api.resolve('http://direct.example.test/', settings), (None, 0))
            self.assertEqual(api.resolve('http://proxy.example.test/', settings), ('127.0.0.1:9191', 1))
        finally:
            server.shutdown(); server.server_close(); thread.join()
