import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestWebConsoleStatic(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "web", "viewer.html"), "r", encoding="utf-8") as f:
            self.viewer = f.read()
        with open(os.path.join(ROOT, "web", "index.html"), "r", encoding="utf-8") as f:
            self.index = f.read()

    def test_viewer_sandbox_hardened(self):
        self.assertIn('sandbox=""', self.viewer)
        self.assertNotIn("allow-same-origin", self.viewer)

    def test_forbidden_raw_interpolations_absent(self):
        forbidden = ["${url}", "${doc.url}", "${file.name}"]
        for term in forbidden:
            self.assertNotIn(term, self.viewer, f"Found forbidden '{term}' in viewer.html")
            self.assertNotIn(term, self.index, f"Found forbidden '{term}' in index.html")

    def test_single_profile_bundle_source(self):
        self.assertIn('src="profiles.bundle.js"', self.index)
        self.assertNotIn("BUILTIN_PROFILES = {", self.index)

    def test_checkpoint_and_launcher_handoff_present(self):
        self.assertIn("aegis.checkpoint.v1", self.index)
        self.assertIn("URLSearchParams(location.search).get('profile')", self.index)

    def test_profiles_bundle_up_to_date(self):
        scripts_dir = os.path.join(ROOT, "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import build_profile_bundle

        exit_code = build_profile_bundle.main(["--check"])
        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
