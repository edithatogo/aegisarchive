"""Archive relocation must not turn completed dependencies into unknown tracks."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts import track_health


class ArchiveLookupTests(unittest.TestCase):
    def test_archived_dependencies_and_external_delegations(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'tracks').mkdir()
            pack = root / 'archive' / 'done'
            pack.mkdir(parents=True)
            (pack / 'metadata.json').write_text(json.dumps({'status': 'completed'}))
            backlog = root / 'backlog.md'
            backlog.write_text('## Approved\n| P0 | done | T1 | done | - | - |\n## G2 companion-program delegations\n| P3 | companion_g2 | task | blocked | companion | G2 |\n')
            with patch.object(track_health, 'TRACKS', str(root / 'tracks')), patch.object(track_health, 'BACKLOG', str(backlog)):
                self.assertEqual([t['id'] for t in track_health.load_tracks()], ['done'])
                self.assertEqual(track_health.backlog_track_ids(), ['done'])
