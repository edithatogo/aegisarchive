"""Fail-closed SARIF regression cases."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from scripts.sarif_gate import main


class SarifReviewTests(unittest.TestCase):
    def test_failed_or_malformed_scan_cannot_pass(self):
        cases = [({}, 2), ({'runs': []}, 2),
                 ({'runs': [{'results': [], 'invocations': [{'executionSuccessful': False}]}]}, 2),
                 ({'runs': [{'results': []}]}, 0),
                 ({'runs': [{'tool': {'driver': {'rules': [{'id': 'a', 'properties': {'security-severity': '7.5'}}]}}, 'results': [{'ruleIndex': 0}]}]}, 1)]
        with tempfile.TemporaryDirectory() as td, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            p = Path(td) / 'scan.sarif'
            for payload, expected in cases:
                p.write_text(json.dumps(payload))
                self.assertEqual(main([str(p)]), expected)
            self.assertEqual(main([str(p), '--threshold', '9']), 2)
