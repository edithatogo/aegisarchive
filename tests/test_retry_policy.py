import unittest
from cli.retry_policy import classify, select
class RetryPolicyTests(unittest.TestCase):
    def test_categories_never_retry_access_or_missing(self):
        self.assertEqual(classify(403),'access_denied'); self.assertEqual(classify(404),'not_found'); self.assertEqual(select({'a':{'status':403},'b':{'status':503}},['a','b']),['b'])
    def test_selection_is_bounded(self):
        self.assertEqual(select({str(i):{'status':503} for i in range(5)},list(map(str,range(5))),2),['0','1'])
