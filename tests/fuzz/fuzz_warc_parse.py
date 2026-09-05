#!/usr/bin/env python3
"""Fuzz cli/warc_verify.verify_warc: arbitrary bytes written to a temp .warc must never raise."""
import contextlib
import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "cli"))
import _harness  # noqa: E402

try:
    import atheris
    with atheris.instrument_imports():
        import warc_verify
except ImportError:
    import warc_verify  # noqa: E402

PREFIX = b"WARC/1.1\r\nWARC-Type: response\r\nWARC-Payload-Digest: sha256:00\r\nContent-Length: "


def TestOneInput(data):
    payload = data
    if data and data[0] % 2 == 0:  # half the inputs get a plausible WARC header prefix
        payload = PREFIX + data[1:5] + b"\r\n\r\n" + data[5:]
    fd, path = tempfile.mkstemp(suffix=".warc")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
        with contextlib.redirect_stdout(io.StringIO()):
            result = warc_verify.verify_warc(path)
        assert isinstance(result, bool)
    finally:
        os.unlink(path)


if __name__ == "__main__":
    _harness.run(TestOneInput)
