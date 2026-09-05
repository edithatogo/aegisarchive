import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "cli"))
import aegis_cli  # noqa: E402


class TestCliParity(unittest.TestCase):
    def test_tracking_params_mirror(self):
        js_path = os.path.join(ROOT, "web", "lib", "core_crawler.js")
        with open(js_path, "r", encoding="utf-8") as f:
            content = f.read()

        match = re.search(r"TRACKING_PARAMS\s*=\s*new\s+Set\(\[([^\]]+)\]\)", content)
        self.assertIsNotNone(match, "Could not locate TRACKING_PARAMS in core_crawler.js")

        js_params = set(re.findall(r"['\"]([^'\"]+)['\"]", match.group(1)))
        self.assertEqual(aegis_cli.TRACKING_PARAMS, js_params)

    def test_canonicalize_url_parity_vectors(self):
        vectors = [
            ("https://Example.org/docs/?ref=nav&utm_x=1&b=2", None, "https://example.org/docs/?b=2&ref=nav"),
            ("https://example.org:443/a#frag", None, "https://example.org/a"),
            ("../x?q=1", "http://h.test/a/b/", "http://h.test/a/x?q=1"),
            ("mailto:a@b.test", None, None),
            ("http://127.0.0.1:8123/c?utm_source=x&id=2", None, "http://127.0.0.1:8123/c?id=2"),
            ("https://example.org/dir/", None, "https://example.org/dir/"),
        ]
        for raw, base, expected in vectors:
            actual = aegis_cli.canonicalize_url(raw, base)
            self.assertEqual(actual, expected, f"Failed for raw={raw}, base={base}")

    def test_in_scope_parity(self):
        self.assertTrue(aegis_cli.in_scope("http://h.test/x", ["h.test"]))
        self.assertTrue(aegis_cli.in_scope("http://sub.h.test/x", ["h.test"]))
        self.assertFalse(aegis_cli.in_scope("http://evil-h.test/x", ["h.test"]))
        self.assertFalse(aegis_cli.in_scope("http://other.org/x", ["h.test"]))


if __name__ == "__main__":
    unittest.main()
