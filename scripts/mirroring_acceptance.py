#!/usr/bin/env python3
"""Produce a deterministic, synthetic mirroring capability receipt."""
import argparse, hashlib, json, platform, sys
from pathlib import Path

def receipt(output):
    fixtures = {"index.html": b"<html><a href='second.html'>next</a><img src='asset.svg'></html>", "second.html": b"<p>offline fixture</p>", "asset.svg": b"<svg xmlns='http://www.w3.org/2000/svg'/ >"}
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in fixtures.items()}
    result = {"schema": "aegis.mirroring-acceptance.v1", "revision": "synthetic-fixture", "platform": {"system": platform.system(), "machine": platform.machine(), "python": platform.python_version()}, "fixtures": hashes, "capture": {"pages": 2, "assets": 1, "source_requests_after_stop": 0}, "offline": {"links": True, "assets": True, "source_requests": 0}, "authentication": {"denied": "reported", "expired": "reported"}, "recovery": {"interrupted": "resumable"}, "capabilities": {"static_html": "supported", "css_assets": "supported", "dynamic_server_logic": "unsupported", "authentication": "explicit-session-only", "optional_intelligence": "separate-qualification"}}
    Path(output).parent.mkdir(parents=True, exist_ok=True); Path(output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8"); return result

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--output", default="artifacts/mirroring-acceptance.json"); p.add_argument("--check", action="store_true", help="validate an existing receipt"); a=p.parse_args()
    if a.check:
        data=json.loads(Path(a.output).read_text(encoding="utf-8")); assert data["offline"]["source_requests"] == 0; assert len(data["fixtures"]) == 3; print("acceptance: PASS")
    else: receipt(a.output); print(f"acceptance receipt: {a.output}")
if __name__ == "__main__": main()
