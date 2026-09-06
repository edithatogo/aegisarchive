"""Regression coverage for complete speech staging with generated launchers."""
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from portable import provision_speech as speech


class SpeechProvisioningTests(unittest.TestCase):
    def test_generated_wrapper_seeds_runtime_before_loading_voice(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site = root / 'piper-site'
            site.mkdir()
            (site / 'onnxruntime.py').write_text(
                'seed = None\ndef set_seed(value):\n    global seed\n    seed = value\n')
            (site / 'piper.py').write_text(
                'import onnxruntime\nclass PiperVoice:\n'
                '    @staticmethod\n    def load(*args, **kwargs):\n'
                '        assert onnxruntime.seed == 42\n        return PiperVoice()\n'
                '    def synthesize_wav(self, text, output):\n'
                '        output.setparams((1, 2, 16000, 0, "NONE", "PCM"))\n'
                '        output.writeframes(b"\\0" * 32)\n')
            entry = root / 'piper_entry.py'
            entry.write_text(speech.PIPER_ENTRY)
            result = subprocess.run([sys.executable, '-I', '-B', str(entry),
                '--model', 'voice', '--config', 'config', '--seed', '42',
                '--output_file', str(root / 'out.wav')], input='archive',
                text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertGreater((root / 'out.wav').stat().st_size, 44)

    def test_pruned_console_directories_do_not_replace_native_asset_path(self):
        """Exercise all staging steps while replacing network and build processes."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            python = root / "python"
            python.write_bytes(b"bundled interpreter")
            destination = root / "bundle"
            wheel_bytes = b"test pinned wheel"
            wheel_name = "piper_tts-1.8.0-py3-none-any.whl"
            preflights = []

            def download(url, target, expected):
                target = Path(target)
                if "whisper.cpp/tarball" in url:
                    with tarfile.open(target, "w:gz") as archive:
                        content = b"MIT licence"
                        entry = tarfile.TarInfo("source/LICENSE")
                        entry.size = len(content)
                        archive.addfile(entry, io.BytesIO(content))
                else:
                    target.write_bytes(b"pinned fixture")
                return {"url": url, "sha256": speech.digest(target)}

            def run(command, log, **kwargs):
                command = list(map(str, command))
                if "--build" in command:
                    binary = Path(command[command.index("--build") + 1]) / "bin"
                    binary.mkdir(parents=True)
                    (binary / ("whisper-cli.exe" if os.name == "nt" else "whisper-cli")).write_bytes(b"native whisper")
                elif "download" in command:
                    wheels = Path(command[command.index("--dest") + 1])
                    (wheels / wheel_name).write_bytes(wheel_bytes)
                elif "install" in command:
                    site = Path(command[command.index("--target") + 1])
                    (site / "piper").mkdir(parents=True)
                    (site / "piper" / "runtime.dat").write_bytes(b"package data retained")
                    (site / "COPYING").write_text("GPL-3.0", encoding="utf-8")
                    for name in ("bin", "Scripts"):
                        (site / name).mkdir()
                        (site / name / "piper").write_text("#!build-host-python", encoding="utf-8")
                elif "--help" in command:
                    self.assertEqual(command[1:5], ["-X", "utf8", "-I", "-B"])
                    self.assertTrue(Path(command[-2]).is_file())
                    preflights.append(command)

            wheel_pins = {"piper-tts": {"version": "1.8.0", "wheels": {
                wheel_name: hashlib.sha256(wheel_bytes).hexdigest()}}}
            with patch.object(speech, "download", side_effect=download), \
                 patch.object(speech, "run", side_effect=run), \
                 patch.object(speech.subprocess, "check_output", return_value="3.12\n"), \
                 patch.object(speech, "WHEEL_PINS", wheel_pins), \
                 patch.object(speech.platform, "platform", return_value="test native platform"):
                assets = speech.provision(destination, python)

            for key, asset in assets.items():
                path = destination / asset["path"]
                self.assertTrue(path.is_file(), key)
                self.assertEqual(asset["sha256"], speech.digest(path))
            self.assertEqual((destination / assets["whisper"]["path"]).read_bytes(), b"native whisper")
            self.assertEqual(assets["piper"]["interpreter"], "python")
            self.assertFalse((destination / "speech/piper-site/bin").exists())
            self.assertFalse((destination / "speech/piper-site/Scripts").exists())
            self.assertEqual((destination / "speech/piper-site/piper/runtime.dat").read_bytes(), b"package data retained")
            self.assertEqual((destination / "speech/PIPER-COPYING").read_text(), "GPL-3.0")
            report = json.loads((destination / "speech/provenance.json").read_text())
            self.assertEqual(report["omitted_generated_entrypoints"], ["Scripts/piper", "bin/piper"])
            self.assertEqual(len(preflights), 1)


if __name__ == "__main__":
    unittest.main()
