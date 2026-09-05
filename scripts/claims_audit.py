#!/usr/bin/env python3
"""
AegisArchive - Claims Audit

Maps user-facing capability claims (README, AGENTS.md) to mechanical checks
against the code. Prints a Markdown table; exits 1 when any claim is not
backed by code, unless --allow-fail is given (scheduled report mode).

Python 3 standard library only.
"""

import argparse
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TEXT_EXT = ('.js', '.py', '.html', '.json', '.md', '.yml', '.yaml', '.txt')


def iter_files(*rel_dirs):
    for rel in rel_dirs:
        base = os.path.join(ROOT, rel)
        if os.path.isfile(base):
            yield base
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in ('.git', '__pycache__', 'node_modules')]
            for name in filenames:
                if name.startswith('._'):
                    continue
                if name.endswith(TEXT_EXT):
                    yield os.path.join(dirpath, name)


def grep(pattern, *rel_dirs):
    """Return list of 'relpath:line' hits for a regex across the given dirs/files."""
    rx = re.compile(pattern)
    hits = []
    for path in iter_files(*rel_dirs):
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
                for n, line in enumerate(fh, 1):
                    if rx.search(line):
                        hits.append(f"{os.path.relpath(path, ROOT)}:{n}")
        except OSError:
            continue
    return hits


def claim_present(pattern, *rel_dirs):
    """A claim is 'made' when the pattern appears in the documentation sources."""
    return bool(grep(pattern, *rel_dirs))


def check_cdx_field_count():
    """Run the Python WARC writer and count CDX fields on header and data rows."""
    sys.path.insert(0, os.path.join(ROOT, 'cli'))
    try:
        import aegis_cli  # noqa: E402
    except Exception as exc:  # pragma: no cover
        return False, f"import failed: {exc}"
    with tempfile.TemporaryDirectory() as tmp:
        warc = os.path.join(tmp, 'audit.warc')
        w = aegis_cli.PythonWarcWriter(warc)
        w.write_response('http://localhost/audit', 200, {'Content-Type': 'text/html'}, b'<html>audit</html>')
        w.close()
        with open(os.path.join(tmp, 'audit.cdx'), 'r', encoding='utf-8') as fh:
            header, row = fh.readline(), fh.readline()
    h = len(header.split()) - 1  # drop leading 'CDX' token
    r = len(row.split())
    return (h == 11 and r == 11), f"header declares {h} fields, data row has {r}"


CLAIMS = [
    # (id, claim text, where claimed, checker) -- checker returns (ok, detail)
    ("opfs", "OPFS streaming is used for large captures",
     lambda: claim_present(r'OPFS', 'README.md', 'AGENTS.md'),
     lambda: (bool(grep(r'new OpfsStreamer', 'web')), 'new OpfsStreamer in web/')),
    ("request_records", "Captures true HTTP request/response payloads",
     lambda: claim_present(r'request/response', 'README.md'),
     lambda: (bool(grep(r'WARC-Type: request', 'web/lib', 'cli')), 'WARC-Type: request emitted by a writer')),
    ("state_persistence", "IndexedDB state persistence / checkpointing",
     lambda: claim_present(r'IndexedDB', 'README.md'),
     lambda: (bool(grep(r'indexedDB|localStorage', 'web')), 'indexedDB or localStorage used in web/')),
    ("cdx11", "Companion CDX-11 indexes",
     lambda: claim_present(r'CDX-11', 'README.md'),
     check_cdx_field_count),
    ("revisit", "SHA-256 deduplication emits warc/revisit records",
     lambda: claim_present(r'warc/revisit', 'README.md'),
     lambda: (bool(grep(r'WARC-Type: revisit', 'web/lib', 'cli')), 'WARC-Type: revisit emitted by a writer')),
    ("mcp_tools", "MCP tools list_profiles, search_archive, validate_profile",
     lambda: claim_present(r'validate_profile', 'README.md'),
     lambda: (all(grep(rf'{t}', 'mcp/server.py') for t in ('list_profiles', 'search_archive', 'validate_profile')),
              'all three tool names present in mcp/server.py')),
    ("retry_after", "Respects Retry-After headers",
     lambda: claim_present(r'Retry-After', 'README.md'),
     lambda: (bool(grep(r'Retry-After|retry-after', 'web/lib/politeness_engine.js')), 'Retry-After parsed in politeness engine')),
]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Audit documentation claims against code.")
    ap.add_argument('--allow-fail', action='store_true', help='exit 0 even when claims are unbacked (report mode)')
    args = ap.parse_args(argv)

    rows = []
    failures = 0
    for cid, text, claimed, checker in CLAIMS:
        is_claimed = claimed()
        try:
            ok, detail = checker()
        except Exception as exc:  # keep the report going
            ok, detail = False, f"checker error: {exc}"
        if not is_claimed:
            status = 'NOT CLAIMED'
        elif ok:
            status = 'OK'
        else:
            status = 'MISMATCH'
            failures += 1
        rows.append((cid, text, status, detail))

    print("| id | claim | status | check |")
    print("| :-- | :-- | :-- | :-- |")
    for cid, text, status, detail in rows:
        print(f"| `{cid}` | {text} | {status} | {detail} |")
    print()
    print(f"{failures} mismatch(es) out of {len(rows)} claims.")
    if failures and not args.allow_fail:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
