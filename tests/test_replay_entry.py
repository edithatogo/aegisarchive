import unittest
from pathlib import Path
class ReplayEntryTests(unittest.TestCase):
    def test_entry_is_local_and_network_free(self):
        text=Path('web/replay.html').read_text()
        self.assertIn('viewer.html', text); self.assertIn("connect-src 'none'", text); self.assertIn("form-action 'none'", text)
