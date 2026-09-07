import copy
import unittest

from cli.crawl_rules import validate_rules


class RuleSchemaTests(unittest.TestCase):
    def test_order_and_independent_actions_are_preserved(self):
        config = {'version': 1, 'rules': [
            {'id': 'files', 'match': {'path_prefix': '/files/'},
             'decision': {'download': True, 'traverse': False}},
            {'id': 'rest', 'match': {}, 'decision': {'discover': False}},
        ]}
        original = copy.deepcopy(config)
        self.assertEqual(validate_rules(config), config)
        self.assertEqual(config, original)

    def test_unsafe_or_ambiguous_schema_is_rejected(self):
        invalid = [
            {'version': True, 'rules': []},
            {'version': 1, 'rules': [], 'extra': 1},
            {'version': 1, 'rules': [{'id': 'x', 'match': {'regex': '(a+)+$'}, 'decision': {'download': True}}]},
            {'version': 1, 'rules': [{'id': 'x', 'match': {'max_depth': True}, 'decision': {'download': True}}]},
            {'version': 1, 'rules': [{'id': 'x', 'match': {}, 'decision': {'download': 1}}]},
            {'version': 1, 'rules': [{'id': 'x', 'match': {'host': 'example.test.evil/'}, 'decision': {'download': True}}]},
        ]
        for config in invalid:
            with self.subTest(config=config), self.assertRaises(ValueError):
                validate_rules(config)

    def test_duplicate_ids_and_unbounded_inputs_are_rejected(self):
        rule = {'id': 'x', 'match': {}, 'decision': {'download': True}}
        for rules in ([rule, rule], [dict(rule, id=str(i)) for i in range(101)]):
            with self.assertRaises(ValueError):
                validate_rules({'version': 1, 'rules': rules})
        rule['match'] = {'path_prefix': '/' + 'x' * 2048}
        with self.assertRaises(ValueError):
            validate_rules({'version': 1, 'rules': [rule]})

    def test_numeric_intervals_and_resource_kinds(self):
        rule = {'id': 'asset', 'match': {'kind': 'asset', 'mime': 'image/png',
                'min_bytes': 0, 'max_bytes': 4096, 'max_depth': 4},
                'decision': {'traverse': False}}
        validate_rules({'version': 1, 'rules': [rule]})
        rule['match']['min_bytes'] = 4097
        with self.assertRaises(ValueError):
            validate_rules({'version': 1, 'rules': [rule]})
