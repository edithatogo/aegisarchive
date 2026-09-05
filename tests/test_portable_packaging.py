import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
import zipfile

from portable.packaging import assemble, extract, verify


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        (self.source / 'cli').mkdir(parents=True)
        (self.source / 'cli/launch.py').write_text('print("hello")\n')
        self.destination = self.root / 'bundle'

    def asset(self):
        path = self.root / 'runtime.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('bin/tool', 'native fixture')
            archive.writestr('LICENSE', 'Fixture licence')
        return dict(id='fixture', platform='test-only', archive=str(path),
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    source_url='https://example.org/fixture', license='fixture-only',
                    license_file='LICENSE', entrypoint='bin/tool')

    def test_build_verify_and_mutable_data(self):
        manifest = assemble(self.source, self.destination, [self.asset()])
        self.assertEqual(len(manifest['assets']), 1)
        (self.destination / 'data/session.json').write_text('{}')
        self.assertEqual(verify(self.destination), manifest)
        self.assertEqual((self.destination / 'licenses/fixture.txt').read_text(), 'Fixture licence')

    @unittest.skipIf(os.name == 'nt', 'POSIX shell launcher')
    def test_relocated_launcher_uses_explicit_interpreter_and_literal_arguments(self):
        archive = self.root / 'python.tar'
        with tarfile.open(archive, 'w') as output:
            for name, content, mode in (
                ('bin/python', b'#!/bin/sh\nprintf "%s\\n" "$PWD" "$@"\n', 0o755),
                ('LICENSE', b'Fixture licence', 0o644),
            ):
                info = tarfile.TarInfo(name)
                info.size, info.mode = len(content), mode
                output.addfile(info, io.BytesIO(content))
        asset = dict(id='python', platform='test-only', archive=str(archive),
                     sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                     source_url='https://example.org/fixture', license='fixture-only',
                     license_file='LICENSE', entrypoint='bin/python')
        assemble(self.source, self.destination, [asset])
        relocated = self.root / 'relocated bundle with spaces'
        self.destination.rename(relocated)
        literal = '$(touch should-not-exist); "literal"'
        output = subprocess.check_output([str(relocated / 'START_LINUX.sh'), literal],
                                         text=True, env={'PATH': '/usr/bin:/bin'})
        self.assertEqual(output.splitlines(), [str(relocated / 'app'), '-X', 'utf8', '-I', '-B',
                                               'cli/launch.py', literal])
        verify(relocated)

    def test_tamper_and_extra_file_fail(self):
        assemble(self.source, self.destination)
        file = self.destination / 'app/cli/launch.py'
        file.write_text('different')
        with self.assertRaisesRegex(ValueError, 'integrity'):
            verify(self.destination)

    def test_wrong_pin_is_atomic(self):
        asset = self.asset()
        asset['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'checksum'):
            assemble(self.source, self.destination, [asset])
        self.assertFalse(self.destination.exists())

    def test_no_overwrite_or_recursion(self):
        with self.assertRaises(ValueError):
            assemble(self.source, self.source / 'inside')
        self.destination.mkdir()
        (self.destination / 'valuable').write_text('keep')
        with self.assertRaises(ValueError):
            assemble(self.source, self.destination)
        self.assertEqual((self.destination / 'valuable').read_text(), 'keep')

    def test_archive_traversal_and_windows_paths_rejected(self):
        for name in ('../escape', '/absolute', 'C:/drive', 'bin/CON', 'bin/a:stream', 'bin\\escape'):
            with self.subTest(name=name):
                archive = self.root / 'bad.zip'
                with zipfile.ZipFile(archive, 'w') as output:
                    output.writestr(name, 'bad')
                with self.assertRaises(ValueError):
                    extract(archive, self.root / 'extracted')
        self.assertFalse((self.root / 'escape').exists())

    def test_tar_symlink_rejected(self):
        archive = self.root / 'bad.tar'
        with tarfile.open(archive, 'w') as output:
            link = tarfile.TarInfo('link')
            link.type = tarfile.SYMTYPE
            link.linkname = '../../outside'
            output.addfile(link)
        with self.assertRaises(ValueError):
            extract(archive, self.root / 'extracted')

    def test_source_and_manifest_symlink_rejected(self):
        (self.source / 'cli/link').symlink_to(self.root / 'outside')
        with self.assertRaises(ValueError):
            assemble(self.source, self.destination)
        (self.source / 'cli/link').unlink()
        assemble(self.source, self.destination)
        manifest = self.destination / 'manifest.json'
        copy = self.root / 'manifest.json'
        manifest.rename(copy)
        manifest.symlink_to(copy)
        with self.assertRaises(ValueError):
            verify(self.destination)

    def test_missing_licence_rejected(self):
        asset = self.asset()
        asset['license_file'] = 'missing'
        with self.assertRaisesRegex(ValueError, 'license'):
            assemble(self.source, self.destination, [asset])

    def test_case_collisions_rejected(self):
        archive = self.root / 'bad.zip'
        with zipfile.ZipFile(archive, 'w') as output:
            output.writestr('Tool', 'one')
            output.writestr('tool', 'two')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            extract(archive, self.root / 'extracted')


if __name__ == '__main__':
    unittest.main()
