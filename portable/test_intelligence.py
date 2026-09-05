"""Tests execute real SQLite and subprocesses; no native/model claims."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
from portable.intelligence import LocalTools, Memory, run_tool, _vector


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/"memory.sqlite"
        self.memory = Memory(self.path)

    def tearDown(self):
        self.memory.close()
        self.temp.cleanup()

    def test_hybrid_persistence_and_graph(self):
        self.memory.put("a", "committee water water report", [1, 0])
        self.memory.put("b", "forest assessment", [0, 1])
        self.memory.relate("committee", "published", "report", "a")
        self.assertEqual(self.memory.search("water")[0]["id"], "a")
        self.assertEqual(self.memory.search("", [0, 1])[0]["id"], "b")
        self.assertEqual(self.memory.search("water", [1, 0])[0]["id"], "a")
        self.assertEqual(self.memory.search("absent"), [])
        self.memory.close()
        self.memory = Memory(self.path)
        self.assertEqual(self.memory.neighbors("report")[0]["document"], "a")
        self.memory.put("a", "committee water water report", [0.8, 0.2])
        self.assertEqual(len(self.memory.neighbors("committee")), 1)
        self.memory.put("a", "revised water report", [1, 0])
        self.assertEqual(self.memory.neighbors("committee"), [])

    def test_invalid_vectors_and_source(self):
        self.assertAlmostEqual(sum(x*x for x in _vector([1.7e308, 1.7e308])), 1)
        for bad in ([0, 0], [float("nan")], [float("inf")], [], [True]):
            with self.assertRaises(ValueError):
                self.memory.put("bad", "bad", bad)
        self.memory.put("valid", "text", [1, 0])
        with self.assertRaises(ValueError):
            self.memory.search("", [1])
        with self.assertRaises(ValueError):
            self.memory.put("bad", "text", [1])
        with self.assertRaises(sqlite3.IntegrityError):
            self.memory.relate("a", "b", "c", "missing")


class ToolTests(unittest.TestCase):
    def test_piper_script_uses_verified_python_in_isolated_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            assets = {}
            for name, filename in [('python', 'python'), ('piper', 'piper_entry.py'),
                                   ('piper_model', 'voice'), ('piper_config', 'config')]:
                path = root / filename
                path.write_text(name)
                assets[name] = {'path': filename,
                                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({'assets': assets}))
            target = root / 'output.wav'
            with patch('portable.intelligence.run_tool',
                       side_effect=lambda *a, **k: target.write_bytes(b'0' * 44)) as run:
                LocalTools(manifest).speak('archive', target)
            self.assertEqual(run.call_args.args[0], root / 'python')
            self.assertEqual(run.call_args.args[1][:5], ['-X', 'utf8', '-I', '-B', root / 'piper_entry.py'])

    def test_real_subprocess_literal_argument_and_error(self):
        literal = '$(touch should-not-exist); "quoted"'
        self.assertEqual(run_tool(sys.executable, ["-c", "import sys;print(sys.argv[1],end='')", literal]), literal)
        import subprocess
        with self.assertRaises(subprocess.CalledProcessError):
            run_tool(sys.executable, ["-c", "raise SystemExit(2)"])
        with self.assertRaises(subprocess.TimeoutExpired):
            run_tool(sys.executable, ["-c", "import time;time.sleep(5)"], timeout=0.05)

    def test_package_manifest_integration(self):
        import zipfile
        from portable.packaging import assemble
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root/"source"
            source.mkdir()
            (source/"cli").mkdir()
            (source/"cli/launch.py").write_text("# fixture")
            archive = root/"model.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("model.gguf", b"fixture model")
                output.writestr("LICENSE", "fixture only")
            asset = dict(id="scout", platform="test-only", archive=str(archive),
                         sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                         source_url="https://example.org/fixture", license="fixture-only",
                         license_file="LICENSE", entrypoint="model.gguf")
            bundle = root/"bundle"
            assemble(source, bundle, [asset])
            self.assertEqual(LocalTools(bundle/"manifest.json").asset("scout").read_bytes(), b"fixture model")

    def test_asset_integrity_and_containment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = root/"model.gguf"
            model.write_bytes(b"fixture")
            manifest = root/"manifest.json"
            digest = hashlib.sha256(model.read_bytes()).hexdigest()
            manifest.write_text(json.dumps({"assets": {"scout": {"path": model.name, "sha256": digest}}}))
            tools = LocalTools(manifest)
            self.assertEqual(tools.asset("scout"), model.resolve())
            model.write_bytes(b"tampered")
            with self.assertRaises(ValueError):
                tools.asset("scout")
            tools.config["assets"]["scout"]["path"] = sys.executable
            with self.assertRaises(ValueError):
                tools.asset("scout")


if __name__ == "__main__":
    unittest.main()
