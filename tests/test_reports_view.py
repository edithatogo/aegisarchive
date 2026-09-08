import unittest
from pathlib import Path

class ReportsViewTests(unittest.TestCase):
    def test_report_view_escapes_cells_and_bounds_graph(self):
        text = Path('web/reports.html').read_text(encoding='utf-8')
        self.assertIn('replace(/[&<>', text)
        self.assertIn('slice(0,10000)', text)
        self.assertIn('counts.captured', text)

if __name__ == '__main__': unittest.main()
