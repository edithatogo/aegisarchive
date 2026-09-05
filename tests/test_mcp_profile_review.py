import copy
import json
from pathlib import Path
import unittest
from mcp.server import handle_tool_call


class ProfileReviewTests(unittest.TestCase):
    def test_schema_validation_rejects_unsafe_and_incomplete_profiles(self):
        base = json.loads(Path('profiles/default_polite.json').read_text())
        self.assertTrue(handle_tool_call('validate_profile', {'profile_json': json.dumps(base)})['valid'])
        for field, value in [('max_requests_per_minute', 999999), ('min_delay_ms', True), ('robots_policy', 'anything')]:
            data = copy.deepcopy(base)
            data['politeness'][field] = value
            self.assertFalse(handle_tool_call('validate_profile', {'profile_json': json.dumps(data)})['valid'])
        self.assertFalse(handle_tool_call('validate_profile', {'profile_json': json.dumps({'profile_id': 'x', 'target': {'allowed_domains': ['h.test']}})})['valid'])
