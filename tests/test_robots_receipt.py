import unittest
from cli.robots_receipt import decision, fingerprint
class RobotsReceiptTests(unittest.TestCase):
    def test_fingerprint_is_stable(self): self.assertEqual(fingerprint(['User-agent: *','Disallow: /x']), fingerprint(['User-agent: *','Disallow: /x']))
    def test_authorisation_is_explicit(self):
        self.assertIsNone(decision('respect',403,authorization_ref='ref')['authorization_ref'])
        self.assertEqual(decision('ignore_authorised',200,authorization_ref='ref')['authorization_ref'],'ref')
