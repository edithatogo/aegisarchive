import unittest
from cli.capture_report import summarize
class ReportTests(unittest.TestCase):
 def test_reconciles_states_without_counting_exclusions(self):
  r=summarize([{'state':'saved'},{'state':'failed'},{'state':'excluded'},{'state':'pending'}]); self.assertEqual((r['attempted'],r['saved'],r['excluded']),(2,1,1)); self.assertEqual(r['coverage']['status'],'partial')
 def test_unknown_integrity_fails_closed(self): self.assertEqual(summarize([],integrity='bogus')['integrity'],'unknown')
