#!/usr/bin/env python3
"""Fuzz mcp/server.process_line: any stdin line must yield None or a JSON-RPC response string."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", ".."))
import _harness  # noqa: E402

try:
    import atheris
    with atheris.instrument_imports():
        from mcp import server
except ImportError:
    from mcp import server  # noqa: E402

METHODS = ["initialize", "notifications/initialized", "tools/list", "tools/call", "nope"]
TOOLS = ["list_profiles", "search_archive", "validate_profile", "zzz"]


def TestOneInput(data):
    if data and data[0] % 2 == 0:  # structured half: valid JSON with fuzzed params
        text = data[1:].decode("utf-8", "replace")
        req = {"jsonrpc": "2.0", "id": len(data), "method": METHODS[data[0] % len(METHODS)],
               "params": {"name": TOOLS[len(data) % len(TOOLS)],
                          "arguments": {"query": text, "cdx_path": text[:8], "profile_json": text}}}
        line = json.dumps(req) + "\n"
    else:
        line = data.decode("utf-8", "replace")
    out = server.process_line(line)
    if out is not None:
        assert isinstance(out, str)
        parsed = json.loads(out)
        assert parsed.get("jsonrpc") == "2.0"
        assert "result" in parsed or "error" in parsed


if __name__ == "__main__":
    _harness.run(TestOneInput)
