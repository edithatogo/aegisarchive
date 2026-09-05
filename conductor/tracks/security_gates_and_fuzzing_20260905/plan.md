# Track Plan: Security Gates & Fuzzing

## Status: PLANNED

Implementation contract for every task: touch only the files under **Files**; write exactly the content under **Change**; run the **Verify** command(s) from the repository root and require the stated result; stop when **Done when** holds; never do anything under **Do not**. Tasks are ordered so the repository stays green after each commit and so that `security.yml` (T9) is green on its first run. Commit after each task with the given conventional-commit message. Do not push (gate G1).

Global drift guards (apply to every task):
- Never modify `.github/workflows/ci.yml`, `cli/launch.py`, `cli/verify_bundle.py`, `cli/test_station_hardening.py`, or `conductor/tracks/portable_station_hardening_20260905/**`.
- Never add a runtime import of any third-party package; scanners and `atheris` are dev-only.
- Never write organisation names, hostnames, or vendor names (leak gate). After every task run `python3 scripts/gate.py leak` (from T8 onward) or the grep step copied from `ci.yml`.
- Never create files starting with `._`.
- Every `uses:` in new workflows is a 40-hex SHA with a `# vX.Y.Z` comment, except the documented SLSA/reusable exceptions in sibling tracks.
- Never weaken a threshold or add an exception beyond the five pre-approved ones in `spec.md`.

## Phase 1 — Specification & approval

- [ ] Capture requirements, severity semantics, verified findings and pre-approved exceptions in the track specification (R1–R11). *(evidence: spec.md)*
- [ ] Approval basis: user requested gitleaks/CodeQL/Semgrep/Bandit/fuzzing gates that fail on medium-or-higher findings (2026-09-05). Tracks-only scope; implementation by a later agent.

## Phase 2 — Configuration and code hardening (no new workflow yet)

- [x] **T1 Dev requirements and scanner configuration files** *(R3, R7, R11)* (0274912)

  **Files**: `tests/requirements-dev.txt` (append, or create if missing), create `.gitleaks.toml`, `.github/zizmor.yml`, `.github/codeql/codeql-config.yml`.

  **Change**:

  Append to `tests/requirements-dev.txt` (create the file with the first two lines if it does not exist):

  ```text
  # Development-only tooling. Never imported at runtime (AGENTS.md zero-install invariant).
  coverage>=7.6
  # Security gates (security_gates_and_fuzzing_20260905). Pinned; Renovate updates them.
  bandit==1.9.4
  semgrep==1.176.1
  zizmor==1.30.0
  # atheris publishes Linux wheels for CPython 3.12+ only; CI fuzz job uses Python 3.12.
  atheris==3.1.0; sys_platform == "linux"
  ```

  `.gitleaks.toml` (complete):

  ```toml
  # gitleaks configuration: default rules plus repository allowlist.
  title = "AegisArchive gitleaks config"

  [extend]
  useDefault = true

  [allowlist]
  description = "Synthetic test fixtures are not secrets"
  paths = [
    '''tests/fixtures/.*''',
  ]
  ```

  `.github/zizmor.yml` (complete):

  ```yaml
  # zizmor configuration (read by both .github/workflows/zizmor.yml and security.yml).
  # ci.yml is owned by another active conductor track and still uses tag pins and
  # default permissions; its owner has been asked to fix it (see the security track
  # handoff note). Remove these ignores once ci.yml is SHA-pinned with explicit permissions.
  rules:
    unpinned-uses:
      ignore:
        - ci.yml
    excessive-permissions:
      ignore:
        - ci.yml
  ```

  `.github/codeql/codeql-config.yml` (complete):

  ```yaml
  name: AegisArchive CodeQL configuration
  paths-ignore:
    - web/lib/minisearch.min.js
  ```

  **Verify**: `python3 -c "t=open('tests/requirements-dev.txt').read();assert 'bandit==' in t and 'semgrep==' in t and 'zizmor==' in t and 'atheris==3.1.0; sys_platform == \"linux\"' in t and t.count('coverage>=7.6')==1;print('ok')"` prints `ok`; `python3 -c "t=open('.gitleaks.toml').read();assert 'useDefault = true' in t and 'tests/fixtures/.*' in t;print('ok')"`; `python3 -c "t=open('.github/zizmor.yml').read();assert t.count('- ci.yml')==2;print('ok')"`; `python3 -c "t=open('.github/codeql/codeql-config.yml').read();assert 'web/lib/minisearch.min.js' in t;print('ok')"`.

  **Done when**: all four print `ok`. Commit: `chore: add dev security tooling requirements and scanner configs (T1)`.

  **Do not**: put these packages in `pyproject.toml`; allow-list anything other than `tests/fixtures/.*`; ignore any file other than `ci.yml` in zizmor config.

- [x] **T2 Extract importable MCP dispatch (no behaviour change)** *(R1, AC1)* (063101c)

  **Files**: modify `mcp/server.py` only.

  **Change**: replace the whole `def main():` function (from the line `def main():` up to, but not including, `if __name__ == "__main__":`) with the three functions below. `list_profiles`, `search_cdx`, `handle_tool_call`, imports and the `__main__` block stay untouched. The tool descriptions inside `tools/list` are copied verbatim from the current file.

  ```python
  def handle_request(req):
      """Dispatch one JSON-RPC 2.0 request dict. Returns a response dict, or None for notifications."""
      req_id = req.get("id")
      method = req.get("method")
      params = req.get("params", {})

      if method == "initialize":
          return {
              "jsonrpc": "2.0",
              "id": req_id,
              "result": {
                  "protocolVersion": "2024-11-05",
                  "capabilities": {
                      "tools": {}
                  },
                  "serverInfo": {
                      "name": "aegisarchive-mcp",
                      "version": "1.0.0"
                  }
              }
          }
      if method == "notifications/initialized":
          return None
      if method == "tools/list":
          return {
              "jsonrpc": "2.0",
              "id": req_id,
              "result": {
                  "tools": [
                      {
                          "name": "list_profiles",
                          "description": "List all available AegisArchive preservation profiles.",
                          "inputSchema": {
                              "type": "object",
                              "properties": {}
                          }
                      },
                      {
                          "name": "search_archive",
                          "description": "Search local CDX indexes for captured URLs and MIME types.",
                          "inputSchema": {
                              "type": "object",
                              "properties": {
                                  "query": { "type": "string", "description": "Keyword or URL substring to search for" },
                                  "cdx_path": { "type": "string", "description": "Optional path to .cdx index file" }
                              },
                              "required": ["query"]
                          }
                      },
                      {
                          "name": "validate_profile",
                          "description": "Validate a JSON profile against the AegisArchive schema.",
                          "inputSchema": {
                              "type": "object",
                              "properties": {
                                  "profile_json": { "type": "string", "description": "Raw JSON string of the profile" }
                              },
                              "required": ["profile_json"]
                          }
                      }
                  ]
              }
          }
      if method == "tools/call":
          tool_name = params.get("name")
          tool_args = params.get("arguments", {})
          tool_result = handle_tool_call(tool_name, tool_args)
          return {
              "jsonrpc": "2.0",
              "id": req_id,
              "result": {
                  "content": [
                      {
                          "type": "text",
                          "text": json.dumps(tool_result, indent=2)
                      }
                  ]
              }
          }
      return {
          "jsonrpc": "2.0",
          "id": req_id,
          "error": {
              "code": -32601,
              "message": f"Method not found: {method}"
          }
      }

  def process_line(line):
      """Handle one raw stdin line. Returns the JSON response text to write, or None for notifications."""
      try:
          req = json.loads(line)
          res = handle_request(req)
          if res is None:
              return None
          return json.dumps(res) + "\n"
      except Exception as e:
          err_res = {
              "jsonrpc": "2.0",
              "id": None,
              "error": {
                  "code": -32603,
                  "message": f"Internal error: {str(e)}",
                  "data": traceback.format_exc()
              }
          }
          return json.dumps(err_res) + "\n"

  def main():
      """Stdio JSON-RPC 2.0 loop for Model Context Protocol."""
      while True:
          line = sys.stdin.readline()
          if not line:
              break
          out = process_line(line)
          if out is not None:
              sys.stdout.write(out)
              sys.stdout.flush()

  ```

  **Verify**:
  1. `python3 -m py_compile mcp/server.py`.
  2. `printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' '{"jsonrpc":"2.0","method":"notifications/initialized"}' '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' 'garbage' '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"validate_profile","arguments":{"profile_json":"{}"}}}' '{"jsonrpc":"2.0","id":4,"method":"x"}' | python3 mcp/server.py | python3 -c "import sys,json;rs=[json.loads(l) for l in sys.stdin];assert [r.get('id') for r in rs]==[1,2,None,3,4],rs;assert rs[2]['error']['code']==-32603 and rs[4]['error']['code']==-32601;assert rs[0]['result']['serverInfo']['name']=='aegisarchive-mcp';assert len(rs[1]['result']['tools'])==3;print('ok')"` prints `ok`.
  3. `python3 -c "import sys;sys.path.insert(0,'.');from mcp import server;assert server.handle_request({'method':'notifications/initialized'}) is None;assert server.process_line('nope')[0]=='{';print('ok')"` prints `ok`.
  4. If `tests/test_smoke.py` exists: `python3 -m unittest discover -s tests -t . -p "test_*.py"` passes.

  **Done when**: all pass. Commit: `refactor(mcp): extract handle_request/process_line for testability (T2, AC1)`.

  **Do not**: change any response payload, error code, protocol version, tool description, or the `id: None` on internal errors; add input validation (that would be a behaviour change — the fuzz harness relies on the try/except in `process_line`); reorder or rename existing functions.

- [x] **T3 Harden `verify_warc` and allow-list URL schemes in the CLI** *(R2, AC2; also clears Bandit/Semgrep findings in `aegis_cli.py`)* (494583f)

  **Files**: modify `cli/warc_verify.py` and `cli/aegis_cli.py` only.

  **Change** in `cli/warc_verify.py`, inside `verify_warc`, replace

  ```python
          rec_type = headers.get('warc-type', 'unknown')
          body_len = int(headers.get('content-length', '0'))
          target_uri = headers.get('warc-target-uri', '-')
  ```

  with

  ```python
          rec_type = headers.get('warc-type', 'unknown')
          target_uri = headers.get('warc-target-uri', '-')
          raw_len = headers.get('content-length', '0')
          if not raw_len.isdigit():
              print(f"  [Warning] Malformed Content-Length {raw_len!r} at offset {pos}; stopping scan.")
              corrupt_count += 1
              break
          body_len = int(raw_len)
  ```

  and replace

  ```python
          rec_body_start = header_end + 4
          rec_body_end = rec_body_start + body_len
  ```

  with

  ```python
          rec_body_start = header_end + 4
          rec_body_end = min(rec_body_start + body_len, content_len)
  ```

  **Change** in `cli/aegis_cli.py` (around line 191–194), replace

  ```python
          req = urllib.request.Request(url, headers={'User-Agent': 'AegisArchive/1.0 (Ethical Archival Preservation)'})
          start_t = time.time()
          try:
              with urllib.request.urlopen(req, timeout=15) as resp:
  ```

  with

  ```python
          if urllib.parse.urlparse(url).scheme not in ('http', 'https'):
              print(f"[SKIP] {url} (non-HTTP scheme)")
              continue
          req = urllib.request.Request(url, headers={'User-Agent': 'AegisArchive/1.0 (Ethical Archival Preservation)'})
          start_t = time.time()
          try:
              # Scheme allow-listed above; audit rules cannot see that guard.
              with urllib.request.urlopen(req, timeout=15) as resp:  # nosec B310  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
  ```

  (`urllib.parse` is already imported in `aegis_cli.py`; verify with `rg -n "^import urllib|urllib.parse" cli/aegis_cli.py` and add `import urllib.parse` after the existing `import urllib.request` if absent.)

  **Verify**:
  1. `python3 -m py_compile cli/warc_verify.py cli/aegis_cli.py && python3 cli/warc_verify.py --help >/dev/null && python3 cli/aegis_cli.py --help >/dev/null && echo ok`.
  2. `python3 -c "
  import contextlib,io,os,random,sys,tempfile;sys.path.insert(0,'cli');import warc_verify
  random.seed(1);bad=0
  for i in range(2000):
      b=bytes(random.getrandbits(8) for _ in range(random.randint(0,300)))
      if i%2==0:b=b'WARC/1.1\r\nWARC-Type: response\r\nContent-Length: '+b[:4]+b'\r\n\r\n'+b[4:]
      fd,p=tempfile.mkstemp(suffix='.warc');os.write(fd,b);os.close(fd)
      try:
          with contextlib.redirect_stdout(io.StringIO()):assert isinstance(warc_verify.verify_warc(p),bool)
      except Exception as e:bad+=1
      os.unlink(p)
  assert bad==0,bad;print('ok')"` prints `ok` (the same script on the unpatched file raises `ValueError`/`IndexError`).
  3. A valid minimal WARC still verifies: `python3 -c "
  import contextlib,io,sys,tempfile;sys.path.insert(0,'cli');import warc_verify
  w=b'WARC/1.1\r\nWARC-Type: warcinfo\r\nContent-Length: 2\r\n\r\nok\r\n\r\n'
  f=tempfile.NamedTemporaryFile(suffix='.warc',delete=False);f.write(w);f.close()
  with contextlib.redirect_stdout(io.StringIO()):assert warc_verify.verify_warc(f.name) is True
  print('ok')"`.

  **Done when**: all print `ok`. Commit: `fix: harden WARC verifier against malformed lengths; allow-list URL schemes in CLI (T3, AC2)`.

  **Do not**: change the printed summary format; catch exceptions broadly around the whole loop; touch `cli/launch.py` even though it has the same Bandit finding.

## Phase 3 — Gate scripts and harnesses

- [x] **T4 SARIF medium-or-higher gate script** *(R4, AC3)* (1790b13)

  **Files**: create `scripts/sarif_gate.py`.

  **Change**: complete file content (verified: exits 1 on a 7.5-severity result and on an `error`-level rule, 0 on an empty run):

  ```python
  #!/usr/bin/env python3
  """Fail when a SARIF file contains any medium-or-higher finding.

  Standard library only. A result is medium-or-higher when either:
    * its rule has ``properties.security-severity`` >= 4.0 (CVSS scale), or
    * its effective level is ``error`` (result ``level`` or the rule's
      ``defaultConfiguration.level``).

  Usage: python3 scripts/sarif_gate.py FILE.sarif [FILE2.sarif ...] [--threshold 4.0]
  Exit status: 0 = no gated findings, 1 = gated findings present, 2 = usage/parse error.
  """
  import argparse
  import json
  import sys


  def _rule_index(run):
      rules = {}
      driver = run.get("tool", {}).get("driver", {})
      for rule in driver.get("rules", []) or []:
          if "id" in rule:
              rules[rule["id"]] = rule
      for ext in run.get("tool", {}).get("extensions", []) or []:
          for rule in ext.get("rules", []) or []:
              if "id" in rule:
                  rules.setdefault(rule["id"], rule)
      return rules


  def _severity(rule):
      props = rule.get("properties", {}) or {}
      raw = props.get("security-severity")
      try:
          return float(raw) if raw is not None else None
      except (TypeError, ValueError):
          return None


  def _location(result):
      for loc in result.get("locations", []) or []:
          phys = loc.get("physicalLocation", {})
          uri = phys.get("artifactLocation", {}).get("uri", "?")
          line = phys.get("region", {}).get("startLine", "?")
          return "%s:%s" % (uri, line)
      return "?"


  def gate(paths, threshold):
      failures = []
      for path in paths:
          with open(path, "r", encoding="utf-8") as fh:
              sarif = json.load(fh)
          for run in sarif.get("runs", []) or []:
              rules = _rule_index(run)
              for result in run.get("results", []) or []:
                  rule = rules.get(result.get("ruleId"), {})
                  level = result.get("level") or rule.get("defaultConfiguration", {}).get("level", "warning")
                  sev = _severity(rule)
                  if level == "error" or (sev is not None and sev >= threshold):
                      failures.append("%s: %s (level=%s, security-severity=%s) at %s" % (
                          path, result.get("ruleId"), level, sev, _location(result)))
      return failures


  def main(argv=None):
      parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
      parser.add_argument("sarif", nargs="+", help="SARIF file(s) to gate")
      parser.add_argument("--threshold", type=float, default=4.0,
                          help="minimum security-severity that fails the gate (default 4.0 = medium)")
      args = parser.parse_args(argv)
      try:
          failures = gate(args.sarif, args.threshold)
      except (OSError, ValueError) as exc:
          print("sarif_gate: cannot read SARIF: %s" % exc, file=sys.stderr)
          return 2
      if failures:
          print("sarif_gate: %d medium-or-higher finding(s):" % len(failures))
          for line in failures:
              print("  " + line)
          return 1
      print("sarif_gate: no medium-or-higher findings.")
      return 0


  if __name__ == "__main__":
      sys.exit(main())
  ```

  **Verify**: `printf '%s' '{"version":"2.1.0","runs":[{"tool":{"driver":{"name":"t","rules":[{"id":"r1","properties":{"security-severity":"7.5"}},{"id":"r2","defaultConfiguration":{"level":"note"}},{"id":"r3","defaultConfiguration":{"level":"error"}}]}},"results":[{"ruleId":"r1"},{"ruleId":"r2"},{"ruleId":"r3"}]}]}' > /tmp/s.sarif; python3 scripts/sarif_gate.py /tmp/s.sarif; echo "exit=$?"` prints two findings (`r1`, `r3`) and `exit=1`; `printf '%s' '{"version":"2.1.0","runs":[{"tool":{"driver":{"name":"t","rules":[]}},"results":[]}]}' > /tmp/e.sarif; python3 scripts/sarif_gate.py /tmp/e.sarif; echo "exit=$?"` prints `exit=0`; `python3 scripts/sarif_gate.py /tmp/missing.sarif; echo "exit=$?"` prints `exit=2`.

  **Done when**: the three exit codes are 1, 0, 2. Commit: `feat(ci): add stdlib SARIF medium-or-higher gate (T4, AC3)`.

  **Do not**: import anything outside the standard library; change the default threshold.

- [x] **T5 atheris fuzz harnesses with stdlib smoke fallback** *(R8, AC2)* (3f4b7a1)

  **Files**: create `tests/fuzz/_harness.py`, `tests/fuzz/fuzz_warc_parse.py`, `tests/fuzz/fuzz_cdx_search.py`, `tests/fuzz/fuzz_mcp_rpc.py`. Requires T2 and T3.

  **Change**:

  `tests/fuzz/_harness.py`:

  ```python
  """Shared runner: use atheris when available, otherwise a stdlib random smoke loop.

  Each harness defines ``TestOneInput(data: bytes) -> None`` and calls ``run(TestOneInput)``.
  ``--smoke N`` (or a missing atheris module) runs N random inputs with the stdlib only.
  """
  import os
  import random
  import sys


  def run(test_one_input):
      argv = sys.argv[1:]
      smoke = None
      if "--smoke" in argv:
          idx = argv.index("--smoke")
          smoke = int(argv[idx + 1]) if idx + 1 < len(argv) else 200
      try:
          import atheris  # noqa: F401  (dev-only; tests/requirements-dev.txt)
      except ImportError:
          atheris = None
      if smoke is None and atheris is not None:
          atheris.Setup(sys.argv, test_one_input)
          atheris.Fuzz()
          return
      rng = random.Random(int(os.environ.get("FUZZ_SEED", "1")))
      for _ in range(smoke or 200):
          size = rng.randint(0, 512)
          test_one_input(bytes(rng.getrandbits(8) for _ in range(size)))
      print("%s: smoke OK (%d inputs)" % (os.path.basename(sys.argv[0]), smoke or 200))
  ```

  `tests/fuzz/fuzz_warc_parse.py`:

  ```python
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
  ```

  `tests/fuzz/fuzz_cdx_search.py`:

  ```python
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
  ```

  `tests/fuzz/fuzz_mcp_rpc.py`:

  ```python
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
  ```

  **Verify**: `for f in tests/fuzz/fuzz_*.py; do python3 "$f" --smoke 2000 || exit 1; done; FUZZ_SEED=7 python3 tests/fuzz/fuzz_warc_parse.py --smoke 2000` prints `smoke OK` four times. If Linux with Python 3.12 and `atheris` installed: `python3 tests/fuzz/fuzz_warc_parse.py -max_total_time=20` exits 0.

  **Done when**: verify passes. Commit: `test: add atheris fuzz harnesses with stdlib smoke mode (T5, AC2)`.

  **Do not**: name files `test_*.py` (unittest discovery must not pick them up); import `atheris` at module top without the try/except; catch exceptions inside `TestOneInput` (that hides crashes).

- [x] **T6 JS property tests (no npm)** *(R8, AC7)* (f14beec)

  **Files**: create `tests/js/fuzz_props.test.js`.

  **Change**: complete file content (verified with Node 26: 4 passing tests; `core_crawler.js` needs `PolitenessEngine` and `WarcWriter` as globals when loaded in Node):

  ```javascript
  // Property tests with a tiny deterministic generator (no npm). Run: node --test tests/js/
  'use strict';
  const test = require('node:test');
  const assert = require('node:assert/strict');
  const path = require('node:path');

  const LIB = path.join(__dirname, '..', '..', 'web', 'lib');
  globalThis.PolitenessEngine = require(path.join(LIB, 'politeness_engine.js'));
  globalThis.WarcWriter = require(path.join(LIB, 'warc_writer.js'));
  const CoreCrawler = require(path.join(LIB, 'core_crawler.js'));
  const WarcReader = require(path.join(LIB, 'warc_reader.js'));

  const RUNS = Number(process.env.FUZZ_RUNS || 500);
  let seed = Number(process.env.FUZZ_SEED || 20260905);
  const rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
  const ALPHABET = 'abcXYZ019:/?#[]@!$&()*+,;=%._~ -\\<>"\'\u00e9\u4e2d\n\t';
  const randomString = (max = 48) => {
    const n = Math.floor(rnd() * max);
    let s = '';
    for (let i = 0; i < n; i++) s += ALPHABET[Math.floor(rnd() * ALPHABET.length)];
    return s;
  };
  const randomBytes = (max = 512) => {
    const n = Math.floor(rnd() * max);
    const u = new Uint8Array(n);
    for (let i = 0; i < n; i++) u[i] = Math.floor(rnd() * 256);
    return u;
  };
  const profile = { target: { allowed_domains: ['example.com'], seed_urls: ['https://example.com/'] } };

  test('canonicalizeUrl never throws and returns string or null', () => {
    const crawler = new CoreCrawler(profile, {});
    for (let i = 0; i < RUNS; i++) {
      const out = crawler.canonicalizeUrl(randomString(), rnd() < 0.5 ? 'https://example.com/a/b' : null);
      assert.ok(out === null || typeof out === 'string', `run ${i}: ${typeof out}`);
    }
  });

  test('isUrlInScope never throws and returns boolean', () => {
    const crawler = new CoreCrawler(profile, {});
    for (let i = 0; i < RUNS; i++) {
      const out = crawler.isUrlInScope(rnd() < 0.3 ? 'https://example.com/' + randomString() : randomString());
      assert.equal(typeof out, 'boolean', `run ${i}`);
    }
  });

  test('parseRetryAfter returns null/undefined or a non-negative finite ms value', () => {
    const engine = new PolitenessEngine({});
    for (let i = 0; i < RUNS; i++) {
      const out = engine.parseRetryAfter(randomString(20));
      assert.ok(out == null || (Number.isFinite(out) && out >= 0), `run ${i}: ${out}`);
    }
  });

  test('WarcReader.loadWarcBuffer accepts random bytes without throwing', async () => {
    const header = new TextEncoder().encode('WARC/1.1\r\nWARC-Type: response\r\nContent-Length: ');
    for (let i = 0; i < RUNS; i++) {
      let bytes = randomBytes();
      if (rnd() < 0.5) {
        const len = new TextEncoder().encode(['x', '-5', '999999', '', '1e3'][i % 5] + '\r\n\r\n');
        const merged = new Uint8Array(header.length + len.length + bytes.length);
        merged.set(header); merged.set(len, header.length); merged.set(bytes, header.length + len.length);
        bytes = merged;
      }
      await new WarcReader().loadWarcBuffer(bytes.buffer);
    }
  });
  ```

  **Verify**: `node --test tests/js/` reports `pass 4`, `fail 0`; `FUZZ_RUNS=5000 node --test tests/js/` also passes.

  **Done when**: both pass. Commit: `test: add node property tests for URL, Retry-After and WARC reader (T6, AC7)`.

  **Do not**: add `package.json` or any npm dependency; modify files under `web/`.

- [x] **T7 Bandit baseline for the one parallel-owned finding** *(R6, AC4)* (d36a66b)

  **Files**: create `.bandit-baseline.json`. Requires T1 and T3.

  **Change**: complete content (generated with Bandit 1.9.4 after T3; the only remaining medium+ finding):

  ```json
  {
    "errors": [],
    "generated_at": "2026-09-05T00:00:00Z",
    "metrics": {},
    "results": [
      {
        "code": "169     try:\n170         with urllib.request.urlopen(\n171             f\"http://127.0.0.1:{port}/__station/status\", timeout=timeout\n172         ) as resp:\n173             data = json.loads(resp.read().decode(\"utf-8\"))\n",
        "col_offset": 13,
        "end_col_offset": 9,
        "filename": "cli/launch.py",
        "issue_confidence": "HIGH",
        "issue_cwe": {
          "id": 22,
          "link": "https://cwe.mitre.org/data/definitions/22.html"
        },
        "issue_severity": "MEDIUM",
        "issue_text": "Audit url open for permitted schemes. Allowing use of file:/ or custom schemes is often unexpected.",
        "line_number": 170,
        "line_range": [
          170,
          171,
          172
        ],
        "more_info": "https://bandit.readthedocs.io/en/1.9.4/blacklists/blacklist_calls.html#b310-urllib-urlopen",
        "test_id": "B310",
        "test_name": "blacklist"
      }
    ]
  }
  ```

  If `cli/launch.py` has changed since planning and Bandit still reports a finding that the baseline no longer matches, regenerate with `bandit -r cli mcp -ll -ii -f json -o .bandit-baseline.json` **only if** the regenerated `results` list contains exactly one entry with `filename == "cli/launch.py"` and `test_id == "B310"`; otherwise stop and report.

  **Verify**: in a venv with `tests/requirements-dev.txt` installed: `bandit -q -r cli mcp -ll -ii -b .bandit-baseline.json; echo "exit=$?"` prints `exit=0`; `python3 -c "import json;r=json.load(open('.bandit-baseline.json'))['results'];assert len(r)==1 and r[0]['filename']=='cli/launch.py' and r[0]['test_id']=='B310';print('ok')"` prints `ok`.

  **Done when**: both pass. Commit: `chore(security): baseline the single parallel-owned Bandit finding (T7, AC4)`.

  **Do not**: baseline anything in `cli/aegis_cli.py`, `cli/warc_verify.py`, or `mcp/`; add `skips` to any Bandit config.

- [x] **T8 Local gate runner** *(R10, AC7)* (26c18b8)

  **Files**: create `scripts/gate.py`.

  **Change**: complete file content (verified: `leak` decodes the pattern from `ci.yml`; `static` skips uninstalled tools):

  ```python
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
  ```

  **Verify**: `python3 scripts/gate.py leak` prints `leak gate passed`; `python3 scripts/gate.py` ends with `gate: PASS` (tools not installed are reported as `skip:`); `python3 scripts/gate.py bogus; echo "exit=$?"` prints the usage text and `exit=2`. Negative check: `printf 'x' > /tmp/leakprobe && python3 -c "
  import base64,re;t=open('.github/workflows/ci.yml').read();p=base64.b64decode(re.search(r'echo \"([A-Za-z0-9+/=]{40,})\"',t).group(1)).decode();print(len(p)>50)"` prints `True` (pattern decoded, never printed).

  **Done when**: verify passes. Commit: `feat(dev): add stdlib local gate runner mirroring CI (T8, AC7)`.

  **Do not**: hard-code the forbidden-word list anywhere (read it from `ci.yml`); print the decoded pattern; add third-party imports.

## Phase 4 — Workflows

- [ ] **T9 `security.yml`** *(R3–R8, AC5, AC6, AC8)*

  **Files**: create `.github/workflows/security.yml`. Requires T1–T8.

  **Change**: complete file content (verified clean with actionlint and zizmor 1.30 at medium+):

  ```yaml
  name: Security gates

  # Every job fails when a medium-or-higher finding persists. Thresholds are fixed here;
  # lowering them is a specification change, not an implementation detail.

  on:
    push:
      branches: [main]
    pull_request:
      branches: [main]
    schedule:
      - cron: '41 2 * * 1'
    workflow_dispatch:

  permissions:
    contents: read

  concurrency:
    group: security-${{ github.workflow }}-${{ github.ref }}
    cancel-in-progress: true

  jobs:
    gitleaks:
      name: Secrets scan (gitleaks)
      runs-on: ubuntu-latest
      timeout-minutes: 10
      steps:
        - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
          with:
            fetch-depth: 0
            persist-credentials: false
        - uses: gitleaks/gitleaks-action@ff98106e4c7b2bc287b24eaf42907196329070c7 # v2.3.9
          env:
            GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
            GITLEAKS_CONFIG: .gitleaks.toml
            GITLEAKS_ENABLE_COMMENTS: "false"
            GITLEAKS_ENABLE_UPLOAD_ARTIFACT: "false"
            GITLEAKS_ENABLE_SUMMARY: "true"

    codeql:
      name: CodeQL (${{ matrix.language }})
      runs-on: ubuntu-latest
      timeout-minutes: 30
      permissions:
        contents: read
        actions: read
        security-events: write
      strategy:
        fail-fast: false
        matrix:
          language: [python, javascript-typescript]
      steps:
        - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
          with:
            persist-credentials: false
        - uses: github/codeql-action/init@cdf488f595d80d6e07e03d4674febd5ab45fa938 # v4.37.9
          with:
            languages: ${{ matrix.language }}
            config-file: .github/codeql/codeql-config.yml
        - uses: github/codeql-action/analyze@cdf488f595d80d6e07e03d4674febd5ab45fa938 # v4.37.9
          with:
            upload: never
            output: sarif-results
        - name: Gate on medium-or-higher findings
          run: python3 scripts/sarif_gate.py sarif-results/*.sarif
        - name: Upload SARIF to code scanning (always, for visibility)
          if: always()
          uses: github/codeql-action/upload-sarif@cdf488f595d80d6e07e03d4674febd5ab45fa938 # v4.37.9
          with:
            sarif_file: sarif-results

    semgrep:
      name: Static analysis (Semgrep)
      runs-on: ubuntu-latest
      timeout-minutes: 15
      steps:
        - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
          with:
            persist-credentials: false
        - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
          with:
            python-version: "3.11"
        - run: python -m pip install --quiet -r tests/requirements-dev.txt
        # WARNING == medium, ERROR == high. --error makes any remaining finding fail the job.
        # The single excluded audit rule duplicates Bandit B310 (tracked via .bandit-baseline.json);
        # cli/aegis_cli.py allow-lists http/https before urlopen.
        - run: >
            semgrep scan --error --severity WARNING --severity ERROR
            --config p/default --config p/python --config p/javascript --config p/owasp-top-ten
            --exclude-rule python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
            --exclude web/lib/minisearch.min.js
            cli mcp web scripts tests

    bandit:
      name: Static analysis (Bandit)
      runs-on: ubuntu-latest
      timeout-minutes: 10
      steps:
        - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
          with:
            persist-credentials: false
        - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
          with:
            python-version: "3.11"
        - run: python -m pip install --quiet -r tests/requirements-dev.txt
        # -ll = medium+ severity, -ii = medium+ confidence. Baseline holds one finding in a file
        # owned by another track (see handoff.md); nothing else may be added to it.
        - run: bandit -r cli mcp -ll -ii -b .bandit-baseline.json

    zizmor:
      name: Workflow lint (zizmor)
      runs-on: ubuntu-latest
      timeout-minutes: 10
      steps:
        - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
          with:
            persist-credentials: false
        - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
          with:
            python-version: "3.11"
        - run: python -m pip install --quiet -r tests/requirements-dev.txt
        - run: zizmor --min-severity medium --min-confidence medium --offline .github/workflows

    fuzz:
      name: Fuzz smoke
      runs-on: ubuntu-latest
      timeout-minutes: 20
      steps:
        - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
          with:
            persist-credentials: false
        - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
          with:
            python-version: "3.12"
        - uses: actions/setup-node@820762786026740c76f36085b0efc47a31fe5020 # v7.0.0
          with:
            node-version: "22"
        - run: python -m pip install --quiet -r tests/requirements-dev.txt
        - name: atheris harnesses (60 s each, crash = failure)
          run: |
            set -e
            for harness in tests/fuzz/fuzz_*.py; do
              echo "== $harness"
              python "$harness" -max_total_time=60 -atheris_runs=500000 -rss_limit_mb=2048
            done
        - name: JS property tests (node --test)
          run: FUZZ_RUNS=2000 node --test tests/js/
  ```

  **Verify**:
  1. `python3 -c "
  import re;t=open('.github/workflows/security.yml').read()
  uses=re.findall(r'uses: (\S+)',t);bad=[u for u in uses if not re.search(r'@[0-9a-f]{40}$',u)]
  assert not bad,bad;assert 'upload: never' in t and 'sarif_gate.py' in t and '-ll -ii -b .bandit-baseline.json' in t and '--severity WARNING --severity ERROR' in t and 'python-version: \"3.12\"' in t;print('ok',len(uses),'pinned uses')"` prints `ok 15 pinned uses`.
  2. If installed: `actionlint .github/workflows/security.yml` exits 0; `zizmor --min-severity medium --min-confidence medium --offline .github/workflows` exits 0.
  3. In a venv with `tests/requirements-dev.txt`: the exact `semgrep scan ...` and `bandit ...` commands from the file exit 0 (AC5, AC4).

  **Done when**: checks pass. Commit: `ci: add security gates workflow (gitleaks, CodeQL gate, Semgrep, Bandit, zizmor, fuzz) (T9)`.

  **Do not**: touch `ci.yml`; add `continue-on-error`; change `upload: never`; scan `.github` with Semgrep; use Python 3.11 for the fuzz job (no atheris wheel).

- [ ] **T10 ClusterFuzzLite configuration and PR workflow** *(R9)*

  **Files**: create `.clusterfuzzlite/project.yaml`, `.clusterfuzzlite/Dockerfile`, `.clusterfuzzlite/build.sh`, `.github/workflows/cflite_pr.yml`.

  **Change**:

  `.clusterfuzzlite/project.yaml`:

  ```yaml
  language: python
  ```

  `.clusterfuzzlite/Dockerfile`:

  ```dockerfile
  FROM gcr.io/oss-fuzz-base/base-builder-python
  COPY . $SRC/aegisarchive
  WORKDIR $SRC/aegisarchive
  COPY .clusterfuzzlite/build.sh $SRC/
  ```

  `.clusterfuzzlite/build.sh` (mark executable: `chmod +x`):

  ```bash
  #!/bin/bash -eu
  # Build every tests/fuzz/fuzz_*.py harness into a standalone fuzzer binary.
  # compile_python_fuzzer is provided by the oss-fuzz python base image (pyinstaller wrapper).
  cd "$SRC/aegisarchive"
  for harness in tests/fuzz/fuzz_*.py; do
    compile_python_fuzzer "$harness" \
      --paths=tests/fuzz --paths=cli --paths=. \
      --hidden-import=_harness --hidden-import=warc_verify --hidden-import=mcp.server
  done
  ```

  `.github/workflows/cflite_pr.yml` (verified with actionlint and zizmor):

  ```yaml
  name: ClusterFuzzLite PR fuzzing

  on:
    pull_request:
      branches: [main]
      paths:
        - 'cli/**'
        - 'mcp/**'
        - 'tests/fuzz/**'
        - '.clusterfuzzlite/**'
        - '.github/workflows/cflite_pr.yml'

  permissions:
    contents: read

  concurrency:
    group: cflite-${{ github.workflow }}-${{ github.ref }}
    cancel-in-progress: true

  jobs:
    fuzz-pr:
      name: ClusterFuzzLite (${{ matrix.sanitizer }})
      runs-on: ubuntu-latest
      timeout-minutes: 30
      permissions:
        contents: read
        security-events: write
      strategy:
        fail-fast: false
        matrix:
          sanitizer: [address]
      steps:
        - name: Build fuzzers
          id: build
          uses: google/clusterfuzzlite/actions/build_fuzzers@884713a6c30a92e5e8544c39945cd7cb630abcd1 # v1
          with:
            language: python
            github-token: ${{ secrets.GITHUB_TOKEN }}
            sanitizer: ${{ matrix.sanitizer }}
        - name: Run fuzzers (code-change mode, 300 s)
          uses: google/clusterfuzzlite/actions/run_fuzzers@884713a6c30a92e5e8544c39945cd7cb630abcd1 # v1
          with:
            github-token: ${{ secrets.GITHUB_TOKEN }}
            fuzz-seconds: 300
            mode: code-change
            sanitizer: ${{ matrix.sanitizer }}
            output-sarif: true
  ```

  **Verify**: `bash -n .clusterfuzzlite/build.sh && test -x .clusterfuzzlite/build.sh && echo ok`; `python3 -c "t=open('.clusterfuzzlite/project.yaml').read();assert t.strip()=='language: python';print('ok')"`; `actionlint .github/workflows/cflite_pr.yml` if installed. Optional local build if Docker is available: `docker build -t cflite-aegis -f .clusterfuzzlite/Dockerfile . && docker run --rm -e SANITIZER=address cflite-aegis bash -c 'compile' ` — not required; CFLite runs on the first PR that touches the listed paths.

  **Done when**: verify passes. Commit: `ci: add ClusterFuzzLite PR fuzzing (T10)`.

  **Do not**: add a `checkout` step before `build_fuzzers` (the action clones the PR itself); use `undefined` sanitizer for Python; create `cflite_batch.yml`/`cflite_cron.yml` (needs a storage repository; future work).

## Phase 5 — Handoff and checkpoint

- [ ] **T11 Handoff note to the parallel agent** *(G2)*

  **Files**: create `conductor/tracks/security_gates_and_fuzzing_20260905/handoff.md`.

  **Change**: list, for the owner of `ci.yml`/`cli/launch.py`: (1) `cli/launch.py:170` — add `# nosec B310  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected` on the `urlopen` line (loopback literal URL), after which `.bandit-baseline.json` is deleted and the `--exclude-rule` removed from `security.yml` and `scripts/gate.py`; (2) `ci.yml` — SHA-pin `actions/checkout` (`3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`) and `actions/setup-python` (`5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0`) at all four sites, add top-level `permissions: contents: read`, `concurrency`, `timeout-minutes`; after which the two `ci.yml` ignores in `.github/zizmor.yml` are deleted; (3) `ci.yml` may call `python3 scripts/gate.py leak` instead of the inline grep once both are on `main` (optional).

  **Verify**: file exists; `python3 scripts/gate.py leak` passes.

  **Done when**: committed: `chore(conductor): record security handoff for parallel-owned files (T11)`.

  **Do not**: apply any of the three items yourself.

- [ ] **T12 Checkpoint** *(AC1–AC7, AC9)*

  **Verify** (all must pass): `python3 -m py_compile cli/aegis_cli.py cli/warc_verify.py mcp/server.py scripts/gate.py scripts/sarif_gate.py tests/fuzz/*.py`; `python3 scripts/gate.py` → `gate: PASS`; `python3 cli/test_station_hardening.py` passes; `git diff --stat origin/main -- .github/workflows/ci.yml cli/launch.py cli/verify_bundle.py cli/test_station_hardening.py` prints nothing; `python3 -c "import tomllib;assert tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']==[]"` if `pyproject.toml` exists.

  **Done when**: append a `checkpoint_validated` line to `evidence.jsonl` with the command outputs summarised. Commit: `chore(conductor): record security track checkpoint (T12)`.

## Phase 6 — Completion (after G1 push by the integrator)

- [ ] **F1** Observe the first `security.yml` run on `main`; all seven checks green (AC8). If CodeQL reports medium-or-higher findings, fix the code (never the threshold) in a follow-up task recorded here with its rule ids.
- [ ] **F2** Update `metadata.json` (`status`, `updated_at`), append `track_completed` to `evidence.jsonl`; the integrator updates `conductor/tracks.md` and adds the seven check names to the ruleset (standards track T11).
