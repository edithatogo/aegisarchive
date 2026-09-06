"""Frozen static resource graph and capture acceptance."""
import hashlib
import json
from pathlib import Path
import unittest

FIXTURES = Path(__file__).parent / 'fixtures' / 'mirror'
MANIFEST = json.loads((FIXTURES / 'manifest.json').read_text())

class FixtureContract(unittest.TestCase):
    def test_fixture_hashes_and_paths(self):
        resources = MANIFEST['resources']
        self.assertEqual(len(resources), 9)
        self.assertEqual(len({r['path'] for r in resources}), len(resources))
        for resource in resources:
            self.assertEqual(hashlib.sha256((FIXTURES / resource['file']).read_bytes()).hexdigest(), resource['sha256'])

if __name__ == '__main__':
    unittest.main()
