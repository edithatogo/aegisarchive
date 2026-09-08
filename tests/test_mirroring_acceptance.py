import json, tempfile, unittest
from pathlib import Path
from scripts.mirroring_acceptance import receipt

class MirroringAcceptanceTests(unittest.TestCase):
    def test_receipt_is_hash_bound_and_offline(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"receipt.json"; data=receipt(p)
            self.assertEqual(data["schema"], "aegis.mirroring-acceptance.v1")
            self.assertEqual(data["offline"]["source_requests"], 0)
            self.assertEqual(len(data["fixtures"]), 3)
            self.assertTrue(all(len(h)==64 for h in data["fixtures"].values()))
    def test_scope_labels_dynamic_and_auth(self):
        with tempfile.TemporaryDirectory() as d:
            data=receipt(Path(d)/"r.json")
            self.assertEqual(data["capabilities"]["dynamic_server_logic"], "unsupported")
            self.assertEqual(data["capabilities"]["authentication"], "explicit-session-only")

if __name__ == "__main__": unittest.main()
