"""Offline migration contracts: scanner provenance, fail-closed results and rule parity."""
from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import gate, install_opengrep

ROOT = Path(__file__).resolve().parents[1]


class OpenGrepMigrationTests(unittest.TestCase):
    def test_corrupted_upstream_binary_is_rejected_without_installing(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(install_opengrep.platform, "system", return_value="Linux"), \
                 patch.object(install_opengrep.platform, "machine", return_value="x86_64"), \
                 patch.object(install_opengrep, "urlopen", return_value=io.BytesIO(b"untrusted bytes")):
                with self.assertRaisesRegex(RuntimeError, "SHA-256"):
                    install_opengrep.install(Path(directory))
            self.assertFalse((Path(directory) / "opengrep").exists())

    def test_local_gate_requires_opengrep_even_if_others_unavailable(self):
        with patch.object(gate.shutil, "which", return_value=None):
            self.assertEqual(gate.check_static(), 1)

    def test_local_gate_preserves_broad_rule_config_and_error_semantics(self):
        calls = []
        with patch.object(gate.shutil, "which", side_effect=lambda name: "/bin/" + name), \
             patch.object(gate, "_run", side_effect=lambda argv: calls.append(argv) or 0):
            self.assertEqual(gate.check_static(), 0)
        scanner = next(command for command in calls if command[0] == "opengrep")
        for token in ("scan", "--strict", "--error", "p/default", "p/python", "p/javascript", "p/owasp-top-ten"):
            self.assertIn(token, scanner)
        self.assertIn("python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected", scanner)
        self.assertNotIn("semgrep", [command[0] for command in calls])

    def test_hosted_gate_installs_pinned_binary_and_preserves_rule_selection(self):
        workflow = (ROOT / ".github/workflows/security.yml").read_text(encoding="utf-8")
        self.assertIn("  opengrep:", workflow)
        self.assertIn("name: Static analysis (Semgrep)", workflow)
        self.assertIn("install_opengrep.py", workflow)
        self.assertIn("--strict --error", workflow)
        for rule in ("p/default", "p/python", "p/javascript", "p/owasp-top-ten"):
            self.assertIn("--config " + rule, workflow)
        self.assertIn("test \"$observed\" -eq 1", workflow)
        self.assertNotIn("semgrep scan --error", workflow)
        self.assertNotIn("semgrep==", (ROOT / "tests/requirements-dev.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
