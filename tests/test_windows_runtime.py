"""Bundled runtime integrity and real Windows double-click launcher regression."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prepare_runtime', ROOT / 'scripts/prepare_windows_runtime.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RuntimePreparationTests(unittest.TestCase):
    def test_checksum_failure_leaves_no_runtime(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / 'test.zip'
            archive.write_bytes(b'corrupt')
            destination = Path(temp) / 'runtime'
            with self.assertRaisesRegex(ValueError, 'checksum'):
                module.prepare(archive, destination, {'sha256': '0' * 64})
            self.assertFalse(destination.exists())

    def test_isolated_configuration_and_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / 'test.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('python.exe', b'MZfixture')
                z.writestr('python314._pth', 'python314.zip\n.\n')
            destination = Path(temp) / 'runtime'
            module.prepare(archive, destination, {'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()})
            self.assertIn('..\\..', (destination / 'python314._pth').read_text())
            manifest = json.loads((destination / 'runtime-manifest.json').read_text())
            for name, digest in manifest['files'].items():
                self.assertEqual(hashlib.sha256((destination / name).read_bytes()).hexdigest(), digest)
            with self.assertRaises(FileExistsError):
                module.prepare(archive, destination, manifest)


@unittest.skipUnless(os.name == 'nt' and (ROOT / 'runtime/python/python.exe').exists(), 'Requires bundled Windows runtime')
class BundledLauncherTests(unittest.TestCase):
    def test_cmd_starts_real_console_without_system_python(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        env = dict(os.environ, PATH=os.path.join(os.environ['SystemRoot'], 'System32'))
        with tempfile.TemporaryFile() as log:
            process = subprocess.Popen([os.environ['COMSPEC'], '/d', '/c', str(ROOT / 'START_WINDOWS.cmd'),
                                        '--no-browser', '--port', str(port)], cwd=ROOT, env=env,
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
            try:
                for _ in range(100):
                    try:
                        with urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=1) as response:
                            self.assertEqual(response.status, 200)
                            self.assertIn(b'AegisArchive', response.read())
                        break
                    except OSError:
                        if process.poll() is not None:
                            self.fail('Launcher exited before serving the console')
                        time.sleep(.1)
                else:
                    self.fail('Console did not start within deadline')
            finally:
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
                process.wait(timeout=10)
                log.seek(0)
                output = log.read().decode('utf-8', errors='replace')
                print(output)
                self.assertIn('Using bundled portable Python', output)


if __name__ == '__main__':
    unittest.main()
