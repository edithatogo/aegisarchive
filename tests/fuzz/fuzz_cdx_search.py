#!/usr/bin/env python3
"""Fuzz mcp/server.search_cdx: arbitrary CDX file bytes and queries must never raise."""
import os
import sys
import tempfile

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


def TestOneInput(data):
    query = data[:4].decode("utf-8", "replace")
    fd, path = tempfile.mkstemp(suffix=".cdx")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data[4:])
        result = server.search_cdx(query, path)
        assert isinstance(result, dict)
        assert "matches" in result or "error" in result
    finally:
        os.unlink(path)


if __name__ == "__main__":
    _harness.run(TestOneInput)
