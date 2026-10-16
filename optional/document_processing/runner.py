"""Bounded parent transport for separately provisioned parsers."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

MAX_BYTES = 33554432
MAX_OUTPUT = 4194304
TIMEOUT = 20
MIMES = {"application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}


def result(status, reason, text="", locators=None, extractor="optional-1", coverage=None):
    return dict(status=status, reason=reason, text=text, locators=locators or [],
                output_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(), extractor=extractor,
                coverage=coverage if coverage is not None else {"scope": "unassessed"})


def valid_coverage(coverage):
    if not isinstance(coverage, dict):
        return False
    fields = {
        "unassessed": set(),
        "text_layer": {"total_pages", "visited_pages", "pages_with_text", "missing_text_pages"},
        "body_paragraphs": {"total_paragraphs", "visited_paragraphs", "nonempty_paragraphs", "omissions"},
        "stored_cells": {"total_sheets", "visited_sheets", "visited_cells", "nonempty_cells", "omissions"},
    }
    scope = coverage.get("scope")
    if not isinstance(scope, str) or scope not in fields or set(coverage) != fields[scope] | {"scope"}:
        return False
    for key, value in coverage.items():
        if key == "scope":
            continue
        if key == "omissions":
            if not isinstance(value, dict) or any(not isinstance(k, str) or type(v) is not int or v < 0 for k, v in value.items()):
                return False
        elif key == "missing_text_pages":
            if (not isinstance(value, list) or any(type(v) is not int or v < 1 for v in value)
                    or len(set(value)) != len(value)):
                return False
        elif value is not None or key not in {"total_pages", "total_paragraphs", "total_sheets"}:
            if type(value) is not int or value < 0:
                return False
    if scope == "text_layer":
        total, visited = coverage["total_pages"], coverage["visited_pages"]
        return (coverage["pages_with_text"] + len(coverage["missing_text_pages"]) == visited
                and (total is None or visited <= total)
                and all(page <= visited for page in coverage["missing_text_pages"]))
    if scope == "body_paragraphs":
        return (coverage["nonempty_paragraphs"] <= coverage["visited_paragraphs"]
                and (coverage["total_paragraphs"] is None or coverage["visited_paragraphs"] <= coverage["total_paragraphs"]))
    if scope == "stored_cells":
        return (coverage["nonempty_cells"] <= coverage["visited_cells"]
                and (coverage["total_sheets"] is None or coverage["visited_sheets"] <= coverage["total_sheets"]))
    return True


def extract(content: bytes, mime: str, limit: int = MAX_BYTES, *, optional_python=None) -> dict:
    """Extract with sys.executable unless an interpreter is explicitly supplied.

    limit bounds input bytes (hard ceiling 32 MiB); output JSON is capped at 4 MiB.
    All offsets are Python Unicode character offsets into returned text.
    """
    if not isinstance(content, bytes) or type(limit) is not int or limit < 1:
        return result("failed", "invalid_input")
    if len(content) > min(limit, MAX_BYTES):
        return result("failed", "size_limit")
    if mime not in MIMES:
        return result("unsupported", "unsupported_mime")
    try:
        with tempfile.TemporaryDirectory(prefix="aegis-document-") as folder:
            source = Path(folder) / "source"
            source.write_bytes(content)
            command = [os.fspath(optional_python) if optional_python is not None else sys.executable,
                       "-I", str(Path(__file__).with_name("worker.py")), str(source), mime]
            # No inherited Python configuration, credentials, or document-derived arguments.
            env = {k: os.environ[k] for k in ("SYSTEMROOT", "WINDIR") if k in os.environ}
            with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  stdin=subprocess.DEVNULL, cwd=folder, env=env) as process:
                output = bytearray()
                overflow = threading.Event()

                def drain():
                    while True:
                        chunk = process.stdout.read(65536)
                        if not chunk:
                            break
                        if len(output) + len(chunk) > MAX_OUTPUT:
                            overflow.set()
                            process.kill()
                            break
                        output.extend(chunk)

                reader = threading.Thread(target=drain, daemon=True)
                reader.start()
                try:
                    process.wait(timeout=TIMEOUT)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    reader.join(timeout=1)
                    return result("failed", "process_timeout")
                reader.join(timeout=1)
                if reader.is_alive() or overflow.is_set():
                    return result("failed", "output_limit")
                if process.returncode:
                    return result("failed", "worker_failed")
            try:
                value = json.loads(output)
            except (ValueError, UnicodeError, RecursionError):
                return result("failed", "worker_protocol")
            if (not isinstance(value, dict) or set(value) != set(result("", "")) or
                    not isinstance(value["status"], str) or
                    value["status"] not in {"complete", "partial", "failed", "encrypted", "unsupported"} or
                    not isinstance(value["text"], str) or not isinstance(value["locators"], list) or
                    not isinstance(value["extractor"], str) or not isinstance(value["reason"], str) or
                    not valid_coverage(value["coverage"]) or
                    value["output_hash"] != hashlib.sha256(value["text"].encode()).hexdigest()):
                return result("failed", "worker_protocol")
            expected_scope = ("text_layer" if mime == "application/pdf" else
                              "body_paragraphs" if "wordprocessingml" in mime else "stored_cells")
            if value["coverage"]["scope"] not in {"unassessed", expected_scope}:
                return result("failed", "worker_protocol")
            for locator in value["locators"]:
                keys = ({"page", "start", "end"} if mime == "application/pdf" else
                        {"paragraph", "start", "end"} if "wordprocessingml" in mime else
                        {"sheet", "cell", "start", "end"})
                if (not isinstance(locator, dict) or type(locator.get("start")) is not int or
                        type(locator.get("end")) is not int or
                        set(locator) != keys or
                        any(type(locator[k]) is not int or locator[k] < 1 for k in keys & {"page", "paragraph"}) or
                        any(not isinstance(locator[k], str) for k in keys & {"sheet", "cell"}) or
                        not 0 <= locator["start"] < locator["end"] <= len(value["text"])):
                    return result("failed", "worker_protocol")
            return value
    except (OSError, ValueError, TypeError):
        return result("unsupported", "worker_unavailable")
