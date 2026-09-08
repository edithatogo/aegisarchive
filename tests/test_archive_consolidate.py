import tempfile,unittest
from pathlib import Path
from cli.archive_consolidate import consolidate
class ConsolidateTests(unittest.TestCase):
 def test_deduplicates_payloads_and_preserves_history(self):
  with tempfile.TemporaryDirectory() as t:
   m=consolidate([{'url':'https://f/a','body':b'x'},{'url':'https://f/b','body':b'x','revisit':True}],t); self.assertEqual(len(m),2); self.assertEqual(len(list((Path(t)/'payloads').iterdir())),1)
 def test_rejects_invalid_records(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaises(ValueError): consolidate([{'url':'file:///x','body':'secret'}],t)
