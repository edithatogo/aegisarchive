import os, time, unittest
from cli.auth import request_headers, redact_headers
class TestAuth(unittest.TestCase):
    def test_optional_scope_and_expiry(self):
        self.assertEqual(request_headers(None, 'https://example.test/'), {})
        os.environ['AEGIS_TEST_AUTH']='{"X-Test":"ok"}'
        c={'mode':'headers_env','source':'env:AEGIS_TEST_AUTH','allowed_domains':['example.test']}
        self.assertEqual(request_headers(c,'https://example.test/a')['X-Test'],'ok')
        self.assertEqual(request_headers(c,'https://other.test/a'),{})
        c['expires_at']=time.time()-1; self.assertEqual(request_headers(c,'https://example.test/a'),{})
    def test_redaction(self): self.assertEqual(redact_headers({'Cookie':'secret','X':'ok'})['Cookie'],'[REDACTED]')
