import tempfile, unittest
from pathlib import Path
from cli.archive_inputs import discover_archive_inputs

class ArchiveInputTests(unittest.TestCase):
    def test_sidecars_and_symlinks_are_excluded(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'good.warc').write_bytes(b''); (root/'._good.warc').write_bytes(b'')
            (root/'notes.txt').write_text('x')
            try: (root/'link.warc').symlink_to(root/'good.warc')
            except OSError: pass
            self.assertEqual([p.name for p in discover_archive_inputs(root)], ['good.warc'])
    def test_explicit_sidecar_is_still_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'._bad.warc'; p.write_bytes(b'')
            self.assertEqual(discover_archive_inputs(d, [p]), [])
