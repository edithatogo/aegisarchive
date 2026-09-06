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
from portable.gguf_embeddings import GGUFEmbedder, LOOPBACK_HOST


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
        semantic = self.memory.search("", [0, 1])
        self.assertEqual(semantic[0]["id"], "b")
        self.assertAlmostEqual(semantic[0]["score"], 1 / 61)
        hybrid = self.memory.search("water", [1, 0])
        self.assertEqual(hybrid[0]["id"], "a")
        self.assertAlmostEqual(hybrid[0]["score"], 2 / 61)
        self.assertEqual(self.memory.search("absent"), [])
        self.memory.close()
        self.memory = Memory(self.path)
        self.assertEqual(self.memory.neighbors("report")[0]["document"], "a")
        self.memory.put("a", "committee water water report", [0.8, 0.2])
        self.assertEqual(len(self.memory.neighbors("committee")), 1)
        self.memory.put("a", "revised water report", [1, 0])
        self.assertEqual(self.memory.neighbors("committee"), [])

    def test_invalid_vectors_and_source(self):
        self.assertAlmostEqual(sum(x * x for x in _vector([1.7e308, 1.7e308])), 1)
        self.assertAlmostEqual(sum(x * x for x in _vector([1e-320, 1e-320])), 1)
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


class QualificationContractTests(unittest.TestCase):
    def test_native_qualification_requires_semantic_git_console_and_post_integrity(self):
        source = Path(__file__).with_name("native_qualification.py").read_text(encoding="utf-8")
        self.assertIn("memory.search('',", source)
        self.assertIn("record('git', git_check)", source)
        self.assertIn("record('console', console_check)", source)
        self.assertIn("record('integrity_after'", source)
        self.assertIn("git('init')", source)
        self.assertIn("git('fsck', '--full')", source)
        self.assertIn("git('show', 'HEAD:evidence.txt')", source)
        self.assertIn("printf \"%s\" \"$1\"", source)
        self.assertIn("LOOPBACK_HOST", source)


class EmbedderLoopbackTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'darwin', 'Darwin sandbox integration')
    def test_numeric_http_loopback_works_while_external_egress_is_denied(self):
        import subprocess
        import textwrap
        policy = ('(version 1)(allow default)(deny network*)'
                  '(allow network-inbound (local ip "localhost:*"))'
                  '(allow network-outbound (remote ip "localhost:*"))')
        script = textwrap.dedent("""\
            import errno, http.server, socket, threading
            from portable.gguf_embeddings import GGUFEmbedder, LOOPBACK_HOST
            class Handler(http.server.BaseHTTPRequestHandler):
                def do_GET(self):
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'{"status":"ok"}')
                def log_message(self, *args):
                    pass
            server = http.server.HTTPServer((LOOPBACK_HOST, 0), Handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            client = GGUFEmbedder.__new__(GGUFEmbedder)
            client.port = server.server_port
            try:
                for _ in range(20):
                    assert client._request('GET', '/health') == {'status': 'ok'}
                with socket.socket() as probe:
                    probe.settimeout(1)
                    try:
                        probe.connect(('1.1.1.1', 443))
                    except OSError as error:
                        assert error.errno in (errno.EPERM, errno.EACCES, errno.ENETUNREACH)
                    else:
                        raise AssertionError('External egress was permitted')
            finally:
                server.shutdown()
                server.server_close()
            """)
        result = subprocess.run(['/usr/bin/sandbox-exec', '-p', policy,
                                 sys.executable, '-B', '-c', script],
                                cwd=Path(__file__).resolve().parents[1],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_embedder_binds_numeric_loopback(self):
        self.assertEqual(LOOPBACK_HOST, "127.0.0.1")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("llama_server", "bge"):
                (root / name).write_text(name)
            manifest = root / "manifest.json"
            assets = {name: {"path": name, "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest()}
                      for name in ("llama_server", "bge")}
            manifest.write_text(json.dumps({"assets": assets}))
            with patch("portable.gguf_embeddings.subprocess.Popen") as popen:
                popen.return_value.poll.return_value = 1
                with self.assertRaises(RuntimeError):
                    GGUFEmbedder(manifest, startup_timeout=5)
                command = popen.call_args[0][0]
                self.assertEqual(command[command.index("--host") + 1], "127.0.0.1")
                self.assertNotIn("localhost", command)


if __name__ == "__main__":
    unittest.main()
