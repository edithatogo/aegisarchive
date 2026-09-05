#!/usr/bin/env python3
"""Local mirror of the CI gates. Standard library only.

Subcommands (default: all):
  leak    mirror of the leak-prevention gate in .github/workflows/ci.yml
  test    python unittest discovery (tests/) + station tests + node --test tests/js
  static  bandit / semgrep / gitleaks / zizmor when installed (skipped otherwise)
  fuzz    fuzz harness smoke runs (tests/fuzz/*.py without atheris)
  all     leak, test, static, fuzz in that order

Exit status 0 only when every executed check passed. Skipped tools are reported.
"""
import base64
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".tmp", "dist", "build"}


def _run(cmd, **kw):
    print("$ " + " ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=ROOT, **kw)


def leak_pattern():
    """Decode the forbidden-identifier regex from ci.yml (single source of truth)."""
    ci = os.path.join(ROOT, ".github", "workflows", "ci.yml")
    with open(ci, "r", encoding="utf-8") as fh:
        text = fh.read()
    match = re.search(r'echo "([A-Za-z0-9+/=]{40,})"', text)
    if not match:
        raise SystemExit("gate: leak pattern not found in ci.yml")
    return base64.b64decode(match.group(1)).decode("utf-8")


def check_leak():
    pattern = re.compile(leak_pattern())
    hits = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            path = os.path.join(dirpath, name)
            try:
                with open(path, "rb") as fh:
                    raw = fh.read()
            except OSError:
                continue
            if b"\0" in raw:
                continue
            for lineno, line in enumerate(raw.decode("utf-8", "replace").splitlines(), 1):
                if pattern.search(line):
                    hits.append("%s:%d" % (os.path.relpath(path, ROOT), lineno))
    if hits:
        print("leak gate FAILED:\n  " + "\n  ".join(hits))
        return 1
    print("leak gate passed (%s)" % "pattern from ci.yml")
    return 0


def check_test():
    rc = 0
    if os.path.isdir(os.path.join(ROOT, "tests")):
        rc |= _run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-p", "test_*.py"])
    station = os.path.join(ROOT, "cli", "test_station_hardening.py")
    if os.path.isfile(station):
        rc |= _run([sys.executable, station])
    if os.path.isdir(os.path.join(ROOT, "tests", "js")) and shutil.which("node"):
        rc |= _run(["node", "--test", "tests/js/"])
    return rc


def check_static():
    rc = 0
    tools = [
        ("bandit", ["bandit", "-q", "-r", "cli", "mcp", "-ll", "-ii", "-b", ".bandit-baseline.json"]),
        ("semgrep", ["semgrep", "scan", "--quiet", "--error", "--severity", "WARNING", "--severity", "ERROR",
                     "--config", "p/default", "--config", "p/python", "--config", "p/javascript",
                     "--config", "p/owasp-top-ten",
                     "--exclude-rule", "python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected",
                     "--exclude", "web/lib/minisearch.min.js", "cli", "mcp", "web", "scripts", "tests"]),
        ("gitleaks", ["gitleaks", "detect", "--redact", "--no-banner", "--source", ".", "--config", ".gitleaks.toml"]),
        ("zizmor", ["zizmor", "--min-severity", "medium", "--min-confidence", "medium", "--offline", ".github/workflows"]),
    ]
    for name, cmd in tools:
        if shutil.which(name):
            rc |= _run(cmd)
        else:
            print("skip: %s not installed" % name)
    return rc


def check_fuzz():
    rc = 0
    fuzz_dir = os.path.join(ROOT, "tests", "fuzz")
    if not os.path.isdir(fuzz_dir):
        print("skip: tests/fuzz missing")
        return 0
    for name in sorted(os.listdir(fuzz_dir)):
        if name.startswith("fuzz_") and name.endswith(".py"):
            rc |= _run([sys.executable, os.path.join("tests", "fuzz", name), "--smoke", "200"])
    return rc


CHECKS = {"leak": check_leak, "test": check_test, "static": check_static, "fuzz": check_fuzz}


def main(argv):
    which = argv[1] if len(argv) > 1 else "all"
    names = list(CHECKS) if which == "all" else [which]
    if which not in CHECKS and which != "all":
        print(__doc__)
        return 2
    rc = 0
    for name in names:
        print("== %s ==" % name)
        rc |= CHECKS[name]()
    print("gate: %s" % ("PASS" if rc == 0 else "FAIL"))
    return 1 if rc else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
