import hashlib, json, tempfile, unittest
from pathlib import Path
from cli.mirror_checkpoint import CheckpointError, MirrorCheckpoint

class MirrorResumeTests(unittest.TestCase):
    def test_atomic_segment_and_verified_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            c = MirrorCheckpoint(d, "p", "a" * 64)
            seg = c.append_segment(0, b"payload")
            c.save([], ["https://fixture.test/"], [seg], cancelled=True)
            self.assertTrue(c.load()["extra"]["cancelled"])
            self.assertEqual(seg["sha256"], hashlib.sha256(b"payload").hexdigest())

    def test_corrupt_or_mismatched_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            c = MirrorCheckpoint(d, "p", "a" * 64)
            seg = c.append_segment(0, b"payload")
            c.save([], [], [seg])
            (Path(d) / "segments" / seg["name"]).write_bytes(b"changed")
            with self.assertRaises(CheckpointError): c.load()
            other = MirrorCheckpoint(d, "other", "a" * 64)
            with self.assertRaises(CheckpointError): other.load()

    def test_segment_symlink_escape_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            c = MirrorCheckpoint(d, "p", "a" * 64)
            outside = Path(d).parent / "outside-segment.bin"
            outside.write_bytes(b"secret")
            link = Path(d) / "segments" / "segment-00000000.bin"
            link.symlink_to(outside)
            c.save([], [], [{"sequence": 0, "name": link.name, "bytes": 6,
                            "sha256": hashlib.sha256(b"secret").hexdigest()}])
            with self.assertRaises(CheckpointError): c.load()

if __name__ == '__main__': unittest.main()
