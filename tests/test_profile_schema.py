import glob
import json
import os
import unittest


class TestProfileSchema(unittest.TestCase):
    def setUp(self):
        self.schema_path = "profiles/schema.json"
        with open(self.schema_path, "r", encoding="utf-8") as f:
            self.schema = json.load(f)

    def test_schema_properties(self):
        self.assertFalse(self.schema.get("additionalProperties", True))
        pol = self.schema["properties"]["politeness"]["properties"]
        self.assertEqual(pol["jitter_distribution"]["enum"], ["gaussian", "uniform"])
        self.assertTrue(pol["concurrency"].get("deprecated", False))
        self.assertEqual(pol["robots_policy"]["enum"], ["respect", "ignore_authorised"])
        self.assertEqual(pol["robots_policy"]["default"], "respect")
        self.assertEqual(pol["min_delay_ms"]["minimum"], 250)
        self.assertEqual(pol["max_requests_per_minute"]["maximum"], 300)
        self.assertEqual(pol["burst_limit"]["maximum"], 20)

    def test_bundled_profiles_conform_to_schema(self):
        pol = self.schema["properties"]["politeness"]["properties"]
        for path in sorted(glob.glob("profiles/*.json")):
            if path.endswith("schema.json"):
                continue
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertTrue(
                set(data).issubset(set(self.schema["properties"])),
                f"{path} has unexpected keys: {set(data) - set(self.schema['properties'])}"
            )
            for k, v in data.get("politeness", {}).items():
                p = pol.get(k)
                if not p:
                    continue
                if "minimum" in p:
                    self.assertGreaterEqual(v, p["minimum"], f"{path} {k}={v} < {p['minimum']}")
                if "maximum" in p:
                    self.assertLessEqual(v, p["maximum"], f"{path} {k}={v} > {p['maximum']}")
                if "enum" in p:
                    self.assertIn(v, p["enum"], f"{path} {k}={v} not in {p['enum']}")


if __name__ == "__main__":
    unittest.main()
