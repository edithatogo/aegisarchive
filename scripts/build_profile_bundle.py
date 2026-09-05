#!/usr/bin/env python3
"""Generates web/profiles.bundle.js from profiles/*.json (single source of truth for built-in profiles)."""
import argparse
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES_DIR = os.path.join(ROOT, "profiles")
OUT_PATH = os.path.join(ROOT, "web", "profiles.bundle.js")
HEADER = "// GENERATED FILE - do not edit. Source: profiles/*.json. Regenerate: python3 scripts/build_profile_bundle.py\n"


def load_profiles():
    profiles = {}
    for path in sorted(glob.glob(os.path.join(PROFILES_DIR, "*.json"))):
        name = os.path.basename(path)
        if name == "schema.json" or name.startswith("._"):
            continue
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        profiles[data["profile_id"]] = data
    return profiles


def render(profiles):
    body = json.dumps(profiles, indent=2, sort_keys=True, ensure_ascii=False)
    return (
        HEADER
        + ";(function (root) {\n  var PROFILES = " + body + ";\n"
        + "  root.AEGIS_BUNDLED_PROFILES = PROFILES;\n"
        + "  if (typeof module === 'object' && module.exports) { module.exports = PROFILES; }\n"
        + "})(typeof self !== 'undefined' ? self : globalThis);\n"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build web/profiles.bundle.js from profiles/*.json")
    parser.add_argument("--check", action="store_true", help="Exit 1 if the bundle is stale instead of writing it")
    args = parser.parse_args(argv)
    expected = render(load_profiles())
    current = None
    if os.path.isfile(OUT_PATH):
        with open(OUT_PATH, "r", encoding="utf-8") as f:
            current = f.read()
    if args.check:
        if current != expected:
            print("profiles.bundle.js is stale; run: python3 scripts/build_profile_bundle.py")
            return 1
        print("profiles.bundle.js is up to date")
        return 0
    with open(OUT_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(expected)
    print(f"wrote {os.path.relpath(OUT_PATH, ROOT)} ({len(expected)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
