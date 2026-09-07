import json, os, time, unittest
from unittest.mock import patch
from cli.auth import ssl_context
from cli.auth import browser_handoff, request_headers, redact_headers
class TestAuth(unittest.TestCase):
    def test_optional_scope_and_expiry(self):
        self.assertEqual(request_headers(None, 'https://example.test/'), {})
        os.environ['AEGIS_TEST_AUTH']='{"X-Test":"ok"}'
        c={'mode':'headers_env','source':'env:AEGIS_TEST_AUTH','allowed_domains':['example.test']}
        self.assertEqual(request_headers(c,'https://example.test/a')['X-Test'],'ok')
        self.assertEqual(request_headers(c,'https://other.test/a'),{})
        c['expires_at']=time.time()-1; self.assertEqual(request_headers(c,'https://example.test/a'),{})
    def test_redaction(self): self.assertEqual(redact_headers({'Cookie':'secret','X':'ok'})['Cookie'],'[REDACTED]')

    def test_browser_session_import_is_scoped_and_expiry_aware(self):
        state = {'headers': {'X-Session': 'ok'}, 'cookies': [
            {'name': 'sid', 'value': 'secret', 'domain': '.example.test', 'path': '/'},
            {'name': 'old', 'value': 'gone', 'domain': 'example.test', 'expires': 90},
            {'name': 'other', 'value': 'no', 'domain': 'other.test'},
        ]}
        os.environ['AEGIS_TEST_SESSION'] = json.dumps(state)
        config = {'mode': 'browser_session', 'source': 'env:AEGIS_TEST_SESSION',
                  'allowed_domains': ['example.test']}
        result = request_headers(config, 'https://www.example.test/a', now=100)
        self.assertEqual(result['X-Session'], 'ok')
        self.assertEqual(result['Cookie'], 'sid=secret')
        self.assertEqual(request_headers(config, 'https://other.test/', now=100), {})
    def test_browser_handoff_is_explicit_and_credential_free(self):
        c={'mode':'browser_handoff','allowed_domains':['example.test'],'expires_at':time.time()+60}
        handoff=browser_handoff(c,'https://example.test/login')
        self.assertTrue(handoff['requires_operator_login'])
        self.assertTrue(handoff['supports_sso_mfa'])
        self.assertEqual(handoff['credential_collection'],'none')
        self.assertEqual(request_headers(c,'https://example.test/'),{})
        self.assertIsNone(browser_handoff(c,'https://other.test/'))
        c['expires_at']=time.time()-1
        self.assertIsNone(browser_handoff(c,'https://example.test/'))

    def test_client_certificate_is_optional_and_expiry_is_fail_closed(self):
        self.assertIsNone(ssl_context(None))
        config = {'mode': 'client_certificate', 'certificate_file': 'cert.pem', 'key_file': 'key.pem'}
        with patch('cli.auth.ssl.create_default_context') as create:
            context = create.return_value
            self.assertIs(context, ssl_context(config))
            context.load_cert_chain.assert_called_once_with(certfile='cert.pem', keyfile='key.pem')
        config['expires_at'] = 1
        self.assertIsNone(ssl_context(config, now=2))

    def test_client_certificate_requires_both_files(self):
        with self.assertRaisesRegex(ValueError, 'requires certificate_file'):
            ssl_context({'mode': 'client_certificate'})
