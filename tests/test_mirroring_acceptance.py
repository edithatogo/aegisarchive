"""Synthetic validation fixtures do not establish platform qualification."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import mirroring_acceptance as acceptance


class MirroringAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.hooks = self.root / 'empty-fixture-hooks'
        self.hooks.mkdir()
        (self.root / 'scripts').mkdir()
        (self.root / 'scripts/implementation.py').write_text('implementation = 1\n')
        fixture = self.root / 'tests/browser/fixtures/mirroring-site.json'
        fixture.parent.mkdir(parents=True)
        fixture.write_text(json.dumps({'/index.html': {'mime': 'text/html', 'body': 'fixture'}}))
        self.git('init', '-q')
        self.git('add', '.')
        self.git('-c', 'user.name=Contract Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture')
        self.patcher = patch.object(acceptance, 'ROOT', self.root)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.output = self.root / 'artifacts/receipt.json'
        self.output.parent.mkdir()

    def git(self, *args):
        return subprocess.check_output(
            ['git', '-C', str(self.root), '-c', 'commit.gpgsign=false',
             '-c', 'core.hooksPath=' + str(self.hooks), *args],
            stderr=subprocess.DEVNULL)

    def observations(self):
        source = acceptance.snapshot()
        data = {'schema': 'aegis.mirroring-observations.v2',
                'source_before': source, 'source_after': source,
                'runtime': acceptance.runtime(), 'artifacts': {}}
        data['runtime']['browser'] = {'name': 'chromium', 'version': '149.0.0.0', 'playwright_version': '1.63.0'}
        for group, fields in acceptance.MEASUREMENTS.items():
            data[group] = {key: (True if kind == 'bool' else minimum)
                           for key, (kind, minimum) in fields.items()}
        data['recovery']['mode'] = 'durable_reload_resume'
        for kind in ('warc', 'cdx'):
            path = self.output.parent / ('capture.' + kind)
            path.write_bytes(b'unit validation fixture, not a real archive')
            data['artifacts'][kind] = acceptance.file_binding(path, self.output.parent)
        path = self.output.parent / 'observations.json'
        path.write_text(json.dumps(data))
        return path, data

    def test_default_pending_and_check_nonzero(self):
        result = acceptance.receipt(self.output)
        self.assertEqual(result['schema'], 'aegis.mirroring-acceptance.v2')
        self.assertEqual(result['qualification_status'], 'pending')
        self.assertEqual(len(result['fixture_hashes']), 1)
        self.assertFalse(acceptance.check(self.output))

    def test_git_batch_input_is_file_backed_to_avoid_bidirectional_pipe_deadlock(self):
        import os
        import stat
        original = subprocess.run
        seen = []
        def run(command, **kwargs):
            if 'cat-file' in command:
                self.assertNotIn('input', kwargs)
                self.assertTrue(stat.S_ISREG(os.fstat(kwargs['stdin'].fileno()).st_mode))
                seen.append(True)
            return original(command, **kwargs)
        revision = self.git('rev-parse','HEAD').decode().strip()
        with patch.object(acceptance.subprocess,'run',side_effect=run):
            source, blobs = acceptance.committed_source(revision)
        self.assertEqual(seen,[True])
        self.assertTrue(source['worktree_clean'])
        self.assertEqual(blobs['scripts/implementation.py'],b'implementation = 1\n')

    def test_complete_bound_observations_validate(self):
        path, _ = self.observations()
        self.assertEqual(acceptance.receipt(self.output, path)['qualification_status'], 'passed')
        self.assertTrue(acceptance.check(self.output))

    def test_supported_numeric_runtime_required(self):
        valid = {'python': '3.9.0', 'browser': {'name': 'chromium',
                 'version': '149.0.0.0', 'playwright_version': '1.63.0'}}
        self.assertEqual(acceptance.runtime_status(valid), 'passed')
        for key, values in {
                'python': ('3.8.20', '3', '3.9', 'unknown', 'fake', '3.11.0rc1', ''),
                'name': ('firefox', 'webkit', 'unknown', 'fake', ''),
                'version': ('unknown', 'fake', '', '149.beta'),
                'playwright_version': ('1.62.0', 'unknown', 'fake', '', '1.63.1')}.items():
            target = valid if key == 'python' else valid['browser']
            original = target[key]
            for value in values:
                target[key] = value
                self.assertEqual(acceptance.runtime_status(valid), 'failed', (key, value))
            target[key] = None
            self.assertEqual(acceptance.runtime_status(valid), 'pending')
            target[key] = True
            with self.assertRaises(ValueError):
                acceptance.runtime_status(valid)
            target[key] = original

    def test_unknown_browser_cannot_be_promoted_by_status_flip(self):
        path, data = self.observations()
        data['runtime']['browser']['version'] = 'unknown'
        path.write_text(json.dumps(data))
        result = acceptance.receipt(self.output, path)
        self.assertEqual(result['qualification_status'], 'failed')
        result['qualification_status'] = 'passed'
        result['receipt_sha256'] = acceptance.receipt_hash(result)
        self.output.write_text(json.dumps(result))
        self.assertFalse(acceptance.check(self.output))

    def test_evidence_size_limits(self):
        path, _ = self.observations()
        with patch.object(acceptance, 'MAX_JSON_BYTES', 16):
            with self.assertRaises(ValueError):
                acceptance.load(path)
            with self.assertRaises(ValueError):
                acceptance.receipt(self.output, path)
        with patch.object(acceptance, 'MAX_ARTIFACT_BYTES', 16):
            with self.assertRaises(ValueError):
                acceptance.file_binding(path.parent / 'capture.warc', path.parent)
        acceptance.receipt(self.output, path)
        with patch.object(acceptance, 'MAX_JSON_BYTES', 16):
            self.assertFalse(acceptance.check(self.output))
        with patch.object(acceptance, 'MAX_ARTIFACT_BYTES', 16):
            self.assertFalse(acceptance.check(self.output))

    def test_invalid_encoding_and_deep_json_check_fail_closed(self):
        for content in (b'\xff', b'{"nested":' + b'[' * 2000 + b'0' + b']' * 2000 + b'}'):
            self.output.write_bytes(content)
            self.assertFalse(acceptance.check(self.output))
            self.assertEqual(acceptance.main(['--check', '--output', str(self.output)]), 1)
        path, _ = self.observations()
        acceptance.receipt(self.output, path)
        with patch.object(acceptance, 'git', side_effect=subprocess.CalledProcessError(128, 'git')):
            self.assertFalse(acceptance.check(self.output))

    def test_null_missing_and_manual_status_flip(self):
        for missing in (True, False):
            path, data = self.observations()
            if missing:
                del data['offline']['css_verified']
            else:
                data['offline']['css_verified'] = None
            path.write_text(json.dumps(data))
            result = acceptance.receipt(self.output, path)
            self.assertEqual(result['qualification_status'], 'pending')
            result['qualification_status'] = 'passed'
            result['receipt_sha256'] = acceptance.receipt_hash(result)
            self.output.write_text(json.dumps(result))
            self.assertFalse(acceptance.check(self.output))

    def test_failed_measurements(self):
        for group, key, value in [('offline', 'source_requests', 1), ('capture', 'responses', 0),
                                  ('launcher', 'ordinary', False)]:
            path, data = self.observations()
            data[group][key] = value
            path.write_text(json.dumps(data))
            self.assertEqual(acceptance.receipt(self.output, path)['qualification_status'], 'failed')
            self.assertFalse(acceptance.check(self.output))

    def test_malformed_counts_rejected(self):
        for value in (True, '4', 4.0, [], {}):
            path, data = self.observations()
            data['offline']['navigation_visits'] = value
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                acceptance.receipt(self.output, path)

    def test_every_mandatory_measurement_is_typed_and_required(self):
        data = {group: {key: True if kind == 'bool' else minimum
                        for key, (kind, minimum) in fields.items()}
                for group, fields in acceptance.MEASUREMENTS.items()}
        data['recovery']['mode'] = 'durable_reload_resume'
        self.assertEqual(acceptance.measured_status(data), 'passed')
        for group, fields in acceptance.MEASUREMENTS.items():
            for key, (kind, _) in fields.items():
                original = data[group].pop(key)
                self.assertEqual(acceptance.measured_status(data), 'pending')
                data[group][key] = None
                self.assertEqual(acceptance.measured_status(data), 'pending')
                data[group][key] = 1 if kind == 'bool' else True
                with self.assertRaises(ValueError):
                    acceptance.measured_status(data)
                data[group][key] = original

    def test_dirty_or_unbound_provenance(self):
        path, data = self.observations()
        data['source_before']['revision'] = '0' * 40
        path.write_text(json.dumps(data))
        self.assertEqual(acceptance.receipt(self.output, path)['qualification_status'], 'failed')
        path, _ = self.observations()
        (self.root / 'scripts/implementation.py').write_text('changed')
        self.assertEqual(acceptance.receipt(self.output, path)['qualification_status'], 'failed')

    def hidden_mutation(self, flag):
        path, _ = self.observations()
        acceptance.receipt(self.output, path)
        self.git('update-index', flag, 'scripts/implementation.py')
        (self.root / 'scripts/implementation.py').write_text('hidden executable mutation')
        self.assertFalse(acceptance.snapshot()['worktree_clean'])
        self.assertEqual(acceptance.build(self.output, path)['qualification_status'], 'failed')
        self.assertTrue(acceptance.check(self.output))

    def test_assume_unchanged_cannot_hide_source_mutation(self):
        self.hidden_mutation('--assume-unchanged')

    def test_skip_worktree_cannot_hide_source_mutation(self):
        self.hidden_mutation('--skip-worktree')

    def test_source_crlf_conversion_is_the_only_allowed_byte_difference(self):
        file = self.root / 'scripts/implementation.py'
        original = file.read_bytes()
        self.git('update-index', '--assume-unchanged', 'scripts/implementation.py')
        file.write_bytes(original.replace(b'\n', b'\r\n'))
        self.assertTrue(acceptance.snapshot()['worktree_clean'])
        file.write_bytes(original.replace(b'\n', b'\r\n') + b'changed')
        self.assertFalse(acceptance.snapshot()['worktree_clean'])

    def test_file_tamper(self):
        for target in ('artifacts/capture.warc', 'artifacts/capture.cdx', 'artifacts/observations.json'):
            with self.subTest(target=target):
                path, _ = self.observations()
                acceptance.receipt(self.output, path)
                file = self.root / target
                original = file.read_bytes()
                file.write_bytes(original + b' ')
                self.assertFalse(acceptance.check(self.output))
                file.write_bytes(original)

    def test_source_tamper_blocks_creation_but_retained_commit_still_verifies(self):
        for target in ('scripts/implementation.py', 'tests/browser/fixtures/mirroring-site.json'):
            path, _ = self.observations()
            acceptance.receipt(self.output, path)
            file = self.root / target
            original = file.read_bytes()
            file.write_bytes(original + b' ')
            self.assertTrue(acceptance.check(self.output))
            self.assertEqual(acceptance.build(self.output, path)['qualification_status'], 'failed')
            file.write_bytes(original)

    def test_recorded_implementation_and_fixture_tamper(self):
        for key in ('implementation_sha256', 'revision', 'fixture_sha256', 'fixture_hashes'):
            path, _ = self.observations()
            data = acceptance.receipt(self.output, path)
            if key in ('implementation_sha256', 'revision'):
                data['provenance'][key] = '0' * (40 if key == 'revision' else 64)
            elif key == 'fixture_sha256':
                data[key] = '0' * 64
            else:
                data[key]['/index.html'] = '0' * 64
            data['receipt_sha256'] = acceptance.receipt_hash(data)
            self.output.write_text(json.dumps(data))
            self.assertFalse(acceptance.check(self.output))

    def test_later_commit_and_other_host_do_not_invalidate_receipt(self):
        path, _ = self.observations()
        acceptance.receipt(self.output, path)
        (self.root / 'scripts/implementation.py').write_text('later implementation')
        self.git('add', 'scripts/implementation.py')
        self.git('-c', 'user.name=Contract Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'later')
        with patch.object(acceptance.platform, 'system', return_value='DifferentHost'):
            self.assertTrue(acceptance.check(self.output))

    def test_fixture_line_ending_identity(self):
        file = self.root / 'tests/browser/fixtures/mirroring-site.json'
        file.write_text(json.dumps({'/index.html': {'mime': 'text/html', 'body': 'fixture'}}, indent=2) + '\n')
        before = acceptance.fixture_hashes()
        file.write_bytes(file.read_bytes().replace(b'\n', b'\r\n'))
        self.assertEqual(acceptance.fixture_hashes(), before)

    def test_legacy_and_unbound_receipts(self):
        self.output.write_text(json.dumps({'schema': 'aegis.mirroring-acceptance.v1', 'offline': {'source_requests': 0}}))
        self.assertFalse(acceptance.check(self.output))
        result = acceptance.receipt(self.output)
        result['qualification_status'] = 'passed'
        result['receipt_sha256'] = acceptance.receipt_hash(result)
        self.output.write_text(json.dumps(result))
        self.assertFalse(acceptance.check(self.output))

    def test_traversal_symlink_and_binding_tamper(self):
        for name in ('../escape.warc', '/absolute.warc', 'C:\\escape.warc', 'link.warc'):
            path, data = self.observations()
            link = self.output.parent / 'link.warc'
            if not link.exists():
                link.symlink_to(self.output.parent / 'capture.warc')
            data['artifacts']['warc']['path'] = name
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                acceptance.receipt(self.output, path)

    def test_missing_git_never_passes(self):
        with patch.object(acceptance, 'ROOT', self.output.parent):
            self.assertFalse(acceptance.snapshot()['worktree_clean'])

    def test_durable_reload_required(self):
        for mode, recovered, expected in [
                (None, None, 'pending'), ('same_session_pause_resume', True, 'failed'),
                ('durable_reload_resume', False, 'failed'),
                ('durable_reload_resume', None, 'pending')]:
            path, data = self.observations()
            data['recovery'].update(mode=mode, reload_recovered=recovered)
            path.write_text(json.dumps(data))
            self.assertEqual(acceptance.receipt(self.output, path)['qualification_status'], expected)
            self.assertFalse(acceptance.check(self.output))

    def test_cli_check_pending_and_failed_exit_nonzero(self):
        acceptance.receipt(self.output)
        self.assertEqual(acceptance.main(['--check', '--output', str(self.output)]), 1)
        path, data = self.observations()
        data['offline']['source_requests'] = 1
        path.write_text(json.dumps(data))
        acceptance.receipt(self.output, path)
        self.assertEqual(acceptance.main(['--check', '--output', str(self.output)]), 1)

    def test_compare_requires_exact_platform_pair_and_matching_source(self):
        path, _ = self.observations()
        acceptance.receipt(self.output, path)
        windows = self.output.parent / 'windows.json'
        win_observations = self.output.parent / 'windows-observations.json'
        data = acceptance.load(path)
        data['runtime'].update(system='Windows', machine='AMD64')
        win_observations.write_text(json.dumps(data))
        with patch.object(acceptance.platform, 'system', return_value='Windows'), \
                patch.object(acceptance.platform, 'machine', return_value='AMD64'):
            acceptance.receipt(windows, win_observations)
        # The source and runtime are validation fixtures, not execution proof.
        mac = acceptance.load(path)
        mac['runtime'].update(system='Darwin', machine='arm64')
        path.write_text(json.dumps(mac))
        with patch.object(acceptance.platform, 'system', return_value='Darwin'), \
                patch.object(acceptance.platform, 'machine', return_value='arm64'):
            acceptance.receipt(self.output, path)
        self.assertTrue(acceptance.compare([self.output, windows]))
        self.assertFalse(acceptance.compare([self.output, self.output]))
        result = acceptance.load(windows)
        result['provenance']['revision'] = '0' * 40
        result['receipt_sha256'] = acceptance.receipt_hash(result)
        windows.write_text(json.dumps(result))
        self.assertFalse(acceptance.compare([self.output, windows]))


if __name__ == '__main__':
    unittest.main()
