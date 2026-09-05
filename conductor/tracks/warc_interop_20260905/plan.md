# Track Plan: WARC/CDX Interoperability & Integrity

## Status: COMPLETED (implementation; post-review disposition in review.md)

Conventions: paths relative to the repository root; line numbers refer to commit `3f00f46` (re-locate by the quoted snippet if they shifted); Verify commands run from the repository root with Node >= 18 and Python >= 3.9; complete a task only when every "Done when" item holds. Edit only the files listed under **Files**. Never create `._*` files. No new dependencies. Do not commit or push unless the operator explicitly asks. Temporary fixtures go under `/tmp`, never inside the repository.

## Phase 1 — Specification & approval

- [x] Capture reproduced defects Da–Dg and requirements R1–R8 in `spec.md` (traces to AC1–AC8). *(Reconciled in post-implementation review; source specification and registration verified.)*
- [x] Approval basis: user requested Conductor planning artifacts for the 2026-09-05 review; implementation waits for the integrator to register the track. *(Reconciled in post-implementation review; source specification and registration verified.)*

## Phase 2 — Writers

- [x] **W1 Strip hop-by-hop/encoding headers, rewrite Content-Length** *(AC1)*

  **Files**: `web/lib/warc_writer.js`, `cli/aegis_cli.py`.

  **Change** (`warc_writer.js`), replace lines 143–153:
  ```js
        // Reconstruct HTTP response header block
        let httpHeaderBlock = `HTTP/1.1 ${status} ${statusText}\r\n`;
        if (response.headers && typeof response.headers.forEach === 'function') {
          response.headers.forEach((val, key) => {
            httpHeaderBlock += `${key}: ${val}\r\n`;
          });
        } else {
          httpHeaderBlock += `Content-Type: ${contentType}\r\n`;
          httpHeaderBlock += `Content-Length: ${payloadUint8Array.length}\r\n`;
        }
        httpHeaderBlock += `\r\n`;
  ```
  with:
  ```js
        // Reconstruct HTTP response header block. The stored body is the *decoded* payload, so
        // encoding/framing headers from the wire must not be copied (Da).
        const OMIT_HEADERS = new Set(['content-encoding', 'transfer-encoding', 'content-length']);
        let httpHeaderBlock = `HTTP/1.1 ${status} ${statusText}\r\n`;
        if (response.headers && typeof response.headers.forEach === 'function') {
          response.headers.forEach((val, key) => {
            if (!OMIT_HEADERS.has(String(key).toLowerCase())) httpHeaderBlock += `${key}: ${val}\r\n`;
          });
        } else {
          httpHeaderBlock += `Content-Type: ${contentType}\r\n`;
        }
        httpHeaderBlock += `Content-Length: ${payloadUint8Array.length}\r\n`;
        httpHeaderBlock += `\r\n`;
  ```
  **Change** (`cli/aegis_cli.py`), replace lines 91–94:
  ```python
          http_header_lines = [f"HTTP/1.1 {status} Response"]
          for k, v in headers_dict.items():
              http_header_lines.append(f"{k}: {v}")
          http_headers_block = ("\r\n".join(http_header_lines) + "\r\n\r\n").encode('utf-8')
  ```
  with:
  ```python
          omit = {"content-encoding", "transfer-encoding", "content-length"}
          http_header_lines = [f"HTTP/1.1 {status} Response"]
          for k, v in headers_dict.items():
              if k.lower() not in omit:
                  http_header_lines.append(f"{k}: {v}")
          http_header_lines.append(f"Content-Length: {len(body_bytes)}")
          http_headers_block = ("\r\n".join(http_header_lines) + "\r\n\r\n").encode('utf-8')
  ```

  **Verify**:
  ```
  node -e "const W=require('./web/lib/warc_writer.js');const w=new W({filename:'t.warc'});const h=new Headers({'content-type':'text/html','content-encoding':'gzip','transfer-encoding':'chunked','content-length':'999'});w.addResponseRecord('http://h.test/',{status:200,statusText:'OK',headers:h},new TextEncoder().encode('hello')).then(()=>{const s=new TextDecoder().decode(w.records[1]);const http=s.split('\r\n\r\n')[1]+'\r\n';console.log(/content-encoding/i.test(http),/transfer-encoding/i.test(http),/Content-Length: 5\r\n/.test(http),/999/.test(http))})"
  ```
  Expected: `false false true false`.
  ```
  python3 -c "
  import sys,tempfile,os;sys.path.insert(0,'cli');import aegis_cli as a
  d=tempfile.mkdtemp();p=os.path.join(d,'t.warc');w=a.PythonWarcWriter(p)
  w.write_response('http://h.test/',200,{'Content-Type':'text/html','Content-Encoding':'gzip','Transfer-Encoding':'chunked','Content-Length':'999'},b'hello');w.close()
  b=open(p,'rb').read();i=b.index(b'WARC-Type: response');h=b[i:].split(b'\r\n\r\n')[1]+b'\r\n'
  print(b'Content-Encoding' in h, b'Transfer-Encoding' in h, b'Content-Length: 5\r\n' in h, b'999' in h)"
  ```
  Expected: `False False True False`.

  **Done when**: both Verify outputs match; `python3 -m py_compile cli/aegis_cli.py` exits 0.

  **Do not**: change WARC-level `Content-Length` computation (it already uses the stored bytes); do not lowercase or re-case header names; do not touch `warc_reader.js`.

- [x] **W2 CDX record length field `S`** *(AC2)*

  **Files**: `web/lib/warc_writer.js`, `cli/aegis_cli.py`, `web/lib/warc_reader.js`, `mcp/server.py`.

  **Change**:
  1. `warc_writer.js` line 219:
     ```js
           const cdxLine = `${surt} ${cdxDate} ${url} ${cleanMime} ${status} ${payloadDigest} ${redirect} ${robotFlags} ${recordOffset} ${this.filename}`;
     ```
     ->
     ```js
           const cdxLine = `${surt} ${cdxDate} ${url} ${cleanMime} ${status} ${payloadDigest} ${redirect} ${robotFlags} ${recordBytes.length} ${recordOffset} ${this.filename}`;
     ```
  2. `cli/aegis_cli.py` line 135:
     ```python
          cdx_line = f"{surt} {cdx_date} {url} {mime} {status} {digest} - - {rec_offset} {os.path.basename(self.filepath)}\n"
     ```
     ->
     ```python
          cdx_line = f"{surt} {cdx_date} {url} {mime} {status} {digest} - - {len(full_block)} {rec_offset} {os.path.basename(self.filepath)}\n"
     ```
  3. `warc_reader.js` lines 36–46: change `if (parts.length >= 10) {` to `if (parts.length >= 11) {` and replace
     ```js
                 offset: parseInt(parts[8], 10),
                 filename: parts[9]
     ```
     with
     ```js
                 length: parseInt(parts[8], 10),
                 offset: parseInt(parts[9], 10),
                 filename: parts[10]
     ```
  4. `mcp/server.py` lines 48–59: change `if len(parts) >= 10:` to `if len(parts) >= 11:` and replace
     ```python
                          "offset": parts[8],
                          "filename": parts[9]
     ```
     with
     ```python
                          "length": parts[8],
                          "offset": parts[9],
                          "filename": parts[10]
     ```

  **Verify**:
  ```
  node -e "const W=require('./web/lib/warc_writer.js');const w=new W({filename:'t.warc'});w.addResponseRecord('http://h.test/',{status:200,statusText:'OK',headers:new Headers({'content-type':'text/html'})},new TextEncoder().encode('hello')).then(()=>{const parts=w.getCdxContent().trim().split('\n')[1].split(/\s+/);console.log(parts.length,Number(parts[8])===w.records[1].length,Number(parts[9])===w.records[0].length,parts[10])})"
  ```
  Expected: `11 true true t.warc`.
  ```
  node -e "const R=require('./web/lib/warc_reader.js');const e=new R().parseCdx(' CDX N b a m s k r M S V g\ntest,h)/ 20260905000000 http://h.test/ text/html 200 abc - - 455 513 t.warc\n');console.log(e.length,e[0].length,e[0].offset,e[0].filename)"
  ```
  Expected: `1 455 513 t.warc`.
  ```
  python3 -c "
  import sys,tempfile,os;sys.path.insert(0,'cli');import aegis_cli as a
  d=tempfile.mkdtemp();p=os.path.join(d,'t.warc');w=a.PythonWarcWriter(p)
  w.write_response('http://h.test/',200,{'content-type':'text/html'},b'hello');w.close()
  b=open(p,'rb').read();parts=open(p.replace('.warc','.cdx')).read().strip().split('\n')[1].split()
  print(len(parts), int(parts[9])+int(parts[8])==len(b) and b.startswith(b'WARC/1.1',int(parts[9])), parts[10])"
  ```
  Expected: `11 True t.warc`.
  ```
  python3 -c "
  import sys,tempfile,os;sys.path.insert(0,'mcp');import server
  d=tempfile.mkdtemp();p=os.path.join(d,'t.cdx');open(p,'w').write(' CDX N b a m s k r M S V g\ntest,h)/ 20260905000000 http://h.test/ text/html 200 abc - - 455 513 t.warc\n')
  m=server.search_cdx('h.test',p)['matches'][0];print(m['length'],m['offset'],m['filename'])"
  ```
  Expected: `455 513 t.warc`.

  **Done when**: all four Verify outputs match; `python3 -m py_compile cli/aegis_cli.py mcp/server.py` exits 0; the existing CI "MCP Server Smoke Test" still passes.

  **Do not**: change the CDX header string; do not reorder other fields; do not add SURT changes.

- [x] **W3 Fail closed when WebCrypto is missing** *(AC3)*

  **Files**: `web/lib/warc_writer.js` only.

  **Change**:
  1. Replace lines 59–65 (the FNV fallback inside `sha256Hex`):
     ```js
         // Fallback: fast FNV-1a pseudo-digest if WebCrypto is absent (rare in modern browsers)
         let h1 = 0x811c9dc5;
         for (let i = 0; i < uint8Array.length; i++) {
           h1 ^= uint8Array[i];
           h1 = Math.imul(h1, 0x01000193);
         }
         return (h1 >>> 0).toString(16).padStart(64, '0');
     ```
     with:
     ```js
         // No silent downgrade: a non-SHA-256 value labelled "sha256:" is a false integrity claim (Dc).
         throw new Error('WebCrypto SHA-256 is unavailable; refusing to write an unverifiable digest');
     ```
  2. Before `return WarcWriter;` (line 254) add `  WarcWriter.sha256Hex = sha256Hex;`.

  **Verify**:
  ```
  node -e "Object.defineProperty(globalThis,'crypto',{value:{},configurable:true});const W=require('./web/lib/warc_writer.js');W.sha256Hex(new Uint8Array([1])).then(()=>console.log('NO THROW'),e=>console.log(e.message))"
  ```
  Expected: `WebCrypto SHA-256 is unavailable; refusing to write an unverifiable digest`.
  ```
  node -e "const W=require('./web/lib/warc_writer.js');W.sha256Hex(new TextEncoder().encode('hello')).then(h=>console.log(h))"
  ```
  Expected: `2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824`.

  **Done when**: both outputs match. (The crawler surfaces the rejection through its existing `catch` as a `[Network Error]` log line; no crawler change is required.)

  **Do not**: add a JS SHA-256 implementation; do not change `generateUUID`'s fallback.

- [x] **W4 `WARC-Refers-To` on revisit records** *(AC4)*

  **Files**: `web/lib/warc_writer.js`, `cli/aegis_cli.py`.

  **Change** (`warc_writer.js`): in the revisit header array (lines 162–174) insert after `` `WARC-Record-ID: ${recordId}`, `` the line `` `WARC-Refers-To: ${existing.recordId}`, `` (`existing.recordId` is already stored at line 208).

  **Change** (`cli/aegis_cli.py`):
  1. Line 127 `self.payload_map[digest] = {"url": url, "date": warc_date}` -> `self.payload_map[digest] = {"url": url, "date": warc_date, "record_id": rec_id}`.
  2. In the revisit header f-string (lines 100–112) insert after the `WARC-Record-ID` line: `f"WARC-Refers-To: {orig['record_id']}\r\n"`.

  **Verify**:
  ```
  node -e "const W=require('./web/lib/warc_writer.js');const w=new W({filename:'t.warc'});const p=new TextEncoder().encode('x'.repeat(600));const h=()=>({status:200,statusText:'OK',headers:new Headers({'content-type':'text/plain'})});w.addResponseRecord('http://h.test/a',h(),p).then(r1=>w.addResponseRecord('http://h.test/b',h(),p).then(r2=>{const s=new TextDecoder().decode(w.records[2]);console.log(r2.isRevisit,s.includes('WARC-Refers-To: '+r1.recordId))}))"
  ```
  Expected: `true true`.
  ```
  python3 -c "
  import sys,tempfile,os,re;sys.path.insert(0,'cli');import aegis_cli as a
  d=tempfile.mkdtemp();p=os.path.join(d,'t.warc');w=a.PythonWarcWriter(p)
  w.write_response('http://h.test/a',200,{'content-type':'text/plain'},b'x'*600);r=w.write_response('http://h.test/b',200,{'content-type':'text/plain'},b'x'*600);w.close()
  b=open(p,'rb').read();i=b.index(b'WARC-Type: revisit');m=re.search(rb'WARC-Refers-To: (<urn:uuid:[0-9a-f-]+>)',b[i:])
  print(r['is_revisit'], m is not None and (b'WARC-Record-ID: '+m.group(1)) in b[:i])"
  ```
  Expected: `True True`.

  **Done when**: both outputs match; W1/W2 Verify still pass.

  **Do not**: change the revisit `WARC-Profile` URI; do not alter the 512-byte revisit threshold.

## Phase 3 — Reader

- [x] **W5 Resolve revisit records in `WarcReader`** *(AC5)*

  **Files**: `web/lib/warc_reader.js` only. Requires W4 (for `WARC-Refers-To`, used only as a comment reference; resolution uses `WARC-Refers-To-Target-URI` and digest).

  **Change**:
  1. Constructor (lines 20–24): add `      this.recordsByDigest = new Map(); // WARC-Payload-Digest -> record` after `this.recordsByUrl`.
  2. Add a helper method after `parseHeaders` (line 160):
     ```js
         /** Parses the HTTP header block at contentStart; returns { status, headers, bodyStart } or null. */
         parseHttpBlock(uint8, contentStart, recordEnd, textDecoder) {
           const httpHeaderEnd = this.findSequence(uint8, [13, 10, 13, 10], contentStart);
           if (httpHeaderEnd === -1 || httpHeaderEnd > recordEnd) return null;
           const httpHeaderStr = textDecoder.decode(uint8.subarray(contentStart, httpHeaderEnd));
           const statusMatch = (httpHeaderStr.split('\r\n')[0] || '').match(/HTTP\/\S+\s+(\d+)/);
           return {
             status: statusMatch ? parseInt(statusMatch[1], 10) : 200,
             headers: this.parseHeaders(httpHeaderStr),
             bodyStart: httpHeaderEnd + 4
           };
         }
     ```
  3. In `loadWarcBuffer`, inside the `response` branch after `this.recordsByUrl.set(...)` (line 99) add:
     ```js
                 record.isRevisit = false;
                 if (warcHeaders['warc-payload-digest']) this.recordsByDigest.set(warcHeaders['warc-payload-digest'], record);
     ```
  4. After the `response` branch's closing `}` (line 102) add a new branch:
     ```js
             } else if (recordType === 'revisit' && targetUri) {
               const http = this.parseHttpBlock(uint8, contentStart, recordEnd, textDecoder);
               const refUri = warcHeaders['warc-refers-to-target-uri'];
               const referred = (refUri && this.recordsByUrl.get(this.normalizeUrl(refUri)))
                 || this.recordsByDigest.get(warcHeaders['warc-payload-digest']) || null;
               const headers = http ? http.headers : {};
               const contentType = headers['content-type'] || (referred ? referred.mimeType : 'application/octet-stream');
               this.recordsByUrl.set(this.normalizeUrl(targetUri), {
                 url: targetUri,
                 status: http ? http.status : 200,
                 headers,
                 bodyBytes: referred ? referred.bodyBytes : new Uint8Array(0),
                 mimeType: contentType.split(';')[0].trim().toLowerCase(),
                 isRevisit: true,
                 refersTo: referred ? referred.url : (refUri || null),
                 unresolved: !referred
               });
               this.urlList.push(targetUri);
     ```
     (the existing `response` branch may keep its inline parsing; using `parseHttpBlock` there is optional and not required by this task.)

  **Verify**:
  ```
  node -e "const W=require('./web/lib/warc_writer.js');const R=require('./web/lib/warc_reader.js');const w=new W({filename:'t.warc'});const p=new TextEncoder().encode('x'.repeat(600));const h=()=>({status:200,statusText:'OK',headers:new Headers({'content-type':'text/plain'})});(async()=>{await w.addResponseRecord('http://h.test/a',h(),p);await w.addResponseRecord('http://h.test/b',h(),p);const r=new R();const res=await r.loadWarcBuffer(await (await w.getWarcBlob()).arrayBuffer());const b=r.getRecord('http://h.test/b');console.log(res.totalRecords,b.isRevisit,b.bodyBytes.length,b.refersTo,b.mimeType,r.getRecord('http://h.test/a').isRevisit)})()"
  ```
  Expected: `2 true 600 http://h.test/a text/plain false`.

  **Done when**: output matches; `parseCdx` Verify from W2 still passes.

  **Do not**: change `normalizeUrl`; do not modify `renderPage` (owned by `web_console_security_20260905`).

## Phase 4 — Verifier and request records

- [x] **W6 Request records with `WARC-Concurrent-To`** *(AC7)*

  **Files**: `web/lib/warc_writer.js`, `web/lib/core_crawler.js`, `cli/aegis_cli.py`. Requires W2 (offset semantics) and W4.

  **Change** (`warc_writer.js`):
  1. Add a method before `addResponseRecord` (line 125):
     ```js
         /** Writes a synthesised WARC request record (Dg); returns its record id. */
         addRequestRecord(url, request, concurrentToId, warcDate) {
           const recordId = `<urn:uuid:${generateUUID()}>`;
           const u = new URL(url);
           let block = `${(request.method || 'GET').toUpperCase()} ${u.pathname}${u.search} HTTP/1.1\r\nHost: ${u.host}\r\n`;
           for (const [k, v] of Object.entries(request.headers || {})) block += `${k}: ${v}\r\n`;
           block += '\r\n';
           const bodyBytes = new TextEncoder().encode(block);
           const headerBytes = new TextEncoder().encode([
             'WARC/1.1', 'WARC-Type: request', `WARC-Target-URI: ${url}`, `WARC-Date: ${warcDate}`,
             `WARC-Record-ID: ${recordId}`, `WARC-Concurrent-To: ${concurrentToId}`,
             'Content-Type: application/http; msgtype=request', `Content-Length: ${bodyBytes.length}`
           ].join('\r\n') + '\r\n\r\n');
           const trailing = new TextEncoder().encode('\r\n\r\n');
           const rec = new Uint8Array(headerBytes.length + bodyBytes.length + trailing.length);
           rec.set(headerBytes, 0); rec.set(bodyBytes, headerBytes.length); rec.set(trailing, headerBytes.length + bodyBytes.length);
           this.records.push(rec);
           this.currentOffset += rec.length;
           return recordId;
         }
     ```
  2. In `addResponseRecord`, after `const cdxDate = formatCdxDate(dateObj);` (line 129) add:
     ```js
           const requestRecordId = options.request ? this.addRequestRecord(url, options.request, recordId, warcDate) : null;
           const concurrentLine = requestRecordId ? [`WARC-Concurrent-To: ${requestRecordId}`] : [];
     ```
     (this must run before `const recordOffset = this.currentOffset;` so the CDX offset points at the response record).
  3. In both WARC header arrays (revisit, lines 162–174, and response, lines 186–195) insert `...concurrentLine,` immediately after the `` `WARC-Record-ID: ${recordId}`, `` element.

  **Change** (`core_crawler.js`):
  4. Above `class CoreCrawler` add:
     ```js
       const REQUEST_HEADERS = {
         'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8',
         'X-Preservation-Agent': 'AegisArchive/1.0'
       };
     ```
  5. Replace the `headers: { ... }` object literal in the `fetch` call (lines 236–239) with `headers: REQUEST_HEADERS,`.
  6. Line 271 `const warcResult = await this.warc.addResponseRecord(url, resp, uint8);` -> `const warcResult = await this.warc.addResponseRecord(url, resp, uint8, { request: { method: 'GET', headers: REQUEST_HEADERS } });`.

  **Change** (`cli/aegis_cli.py`):
  7. Signature line 82 `def write_response(self, url, status, headers_dict, body_bytes):` -> `def write_response(self, url, status, headers_dict, body_bytes, request_headers=None):`.
  8. After `cdx_date = format_cdx_date(now)` (line 86) add:
     ```python
             req_id = self._write_request(url, request_headers, rec_id, warc_date) if request_headers is not None else None
             concurrent = f"WARC-Concurrent-To: {req_id}\r\n" if req_id else ""
     ```
     and insert `f"{concurrent}"` as a new line after each `f"WARC-Record-ID: {rec_id}\r\n"` in the revisit and response header f-strings.
  9. Add a method before `write_response`:
     ```python
         def _write_request(self, url, request_headers, concurrent_to, warc_date):
             rec_id = f"<urn:uuid:{uuid.uuid4()}>"
             u = urllib.parse.urlparse(url)
             path = (u.path or "/") + (f"?{u.query}" if u.query else "")
             lines = [f"GET {path} HTTP/1.1", f"Host: {u.netloc}"] + [f"{k}: {v}" for k, v in request_headers.items()]
             body = ("\r\n".join(lines) + "\r\n\r\n").encode("utf-8")
             headers = (
                 f"WARC/1.1\r\nWARC-Type: request\r\nWARC-Target-URI: {url}\r\nWARC-Date: {warc_date}\r\n"
                 f"WARC-Record-ID: {rec_id}\r\nWARC-Concurrent-To: {concurrent_to}\r\n"
                 f"Content-Type: application/http; msgtype=request\r\nContent-Length: {len(body)}\r\n\r\n"
             ).encode("utf-8")
             block = headers + body + b"\r\n\r\n"
             self.file.write(block)
             self.current_offset += len(block)
             return rec_id
     ```
  10. Line 199 `writer.write_response(url, status, headers, body)` -> `writer.write_response(url, status, headers, body, request_headers=dict(req.header_items()))`.

  **Verify**:
  ```
  node -e "const W=require('./web/lib/warc_writer.js');const w=new W({filename:'t.warc'});w.addResponseRecord('http://h.test/p?q=1',{status:200,statusText:'OK',headers:new Headers({'content-type':'text/html'})},new TextEncoder().encode('hello'),{request:{method:'GET',headers:{'Accept':'text/html'}}}).then(()=>{const all=Buffer.concat(w.records.map(r=>Buffer.from(r))).toString('latin1');const req=Buffer.from(w.records[1]).toString('latin1');console.log(w.records.length,(all.match(/WARC-Type: request/g)||[]).length,(all.match(/WARC-Concurrent-To: /g)||[]).length,req.includes('GET /p?q=1 HTTP/1.1\r\nHost: h.test\r\nAccept: text/html\r\n\r\n'),Number(w.getCdxContent().trim().split('\n')[1].split(/\s+/)[9])===w.records[0].length+w.records[1].length,w.getCdxContent().trim().split('\n').length)})"
  ```
  Expected: `3 1 2 true true 2`.
  ```
  python3 -c "
  import sys,tempfile,os;sys.path.insert(0,'cli');import aegis_cli as a
  d=tempfile.mkdtemp();p=os.path.join(d,'t.warc');w=a.PythonWarcWriter(p)
  w.write_response('http://h.test/p?q=1',200,{'content-type':'text/html'},b'hello',request_headers={'User-agent':'AegisArchive/1.0'});w.close()
  b=open(p,'rb').read();parts=open(p.replace('.warc','.cdx')).read().strip().split('\n')[1].split()
  print(b.count(b'WARC-Type: request'),b.count(b'WARC-Concurrent-To: '),b.startswith(b'WARC/1.1\r\nWARC-Type: response',int(parts[9])),b'GET /p?q=1 HTTP/1.1\r\nHost: h.test\r\nUser-agent: AegisArchive/1.0\r\n\r\n' in b)"
  ```
  Expected: `1 2 True True`.

  **Done when**: both outputs match; W1–W5 Verify still pass (their record indices assume no `options.request`, which they do not pass); `python3 -m py_compile cli/aegis_cli.py` exits 0.

  **Do not**: write CDX lines for request records; do not record cookies or authorization headers (none are sent by either client; keep it that way); do not change the response `WARC-Record-ID`.

- [x] **W7a Verifier: `.warc.gz` input, record spans, request count** *(AC6, part 1)*

  **Files**: `cli/warc_verify.py` only.

  **Change**:
  1. Add `import gzip` after `import hashlib` (line 11).
  2. Add before `def verify_warc` (line 14):
     ```python
     def read_container(path):
         """Reads a .warc or (multi-member) .warc.gz container fully into memory."""
         opener = gzip.open if path.endswith('.gz') else open
         with opener(path, 'rb') as f:
             return f.read()
     ```
  3. Replace lines 30–31 (`with open(warc_path, 'rb') as f:` / `content = f.read()`) with `    content = read_container(warc_path)`.
  4. After `revisit_count = 0` (line 26) add `    request_count = 0` and `    record_spans = []  # (offset, length, target_uri)`.
  5. Immediately after `while pos < content_len:` (line 36) add `        rec_start = pos`.
  6. After `elif rec_type == 'revisit': revisit_count += 1` (lines 63–64) add:
     ```python
             elif rec_type == 'request':
                 request_count += 1
     ```
  7. After the trailing-CRLF skip loop (lines 84–85) add `        record_spans.append((rec_start, pos - rec_start, target_uri))`.
  8. After the `- revisit (deduped):` print (line 91) add `    print(f"    - request:             {request_count}")`.
  9. Change the signature to `def verify_warc(warc_path, cdx_path=None, _spans_out=None):` and, just before the `print(f"  Total Container Size: ...")`, add `    if _spans_out is not None: _spans_out.extend(record_spans)` (W7b will use `record_spans` directly; this hook lets tests inspect spans).

  **Verify**:
  ```
  python3 -c "
  import sys,os,gzip,shutil;sys.path.insert(0,'cli');import aegis_cli as a
  os.makedirs('/tmp/aa_verify',exist_ok=True);w=a.PythonWarcWriter('/tmp/aa_verify/t.warc')
  w.write_response('http://h.test/a',200,{'content-type':'text/html'},b'<p>a</p>');w.write_response('http://h.test/b',200,{'content-type':'text/plain'},b'b'*600);w.write_response('http://h.test/c',200,{'content-type':'text/plain'},b'b'*600);w.close()
  with open('/tmp/aa_verify/t.warc','rb') as f, gzip.open('/tmp/aa_verify/t.warc.gz','wb') as g: shutil.copyfileobj(f,g)
  print('fixture ok')" && python3 cli/warc_verify.py /tmp/aa_verify/t.warc.gz; echo "exit=$?"
  ```
  Expected: `fixture ok`, then a report containing `Total WARC Records:      4`, `- response:            2`, `- revisit (deduped):   1`, `- request:             0`, `Integrity Status:        PASSED`, and `exit=0`.
  ```
  python3 -c "
  import sys;sys.path.insert(0,'cli');import warc_verify as v;s=[];v.verify_warc('/tmp/aa_verify/t.warc',None,s);c=open('/tmp/aa_verify/t.warc','rb').read();print(len(s),s[0][0]==0,all(c.startswith(b'WARC/1.1',o) for o,_,_ in s),sum(l for _,l,_ in s)==len(c))"
  ```
  Expected: the report, then `4 True True True`.

  **Done when**: both outputs match; `python3 cli/warc_verify.py --help` exits 0.

  **Do not**: decompress to disk; do not change the digest check; do not implement CDX checking yet (W7b).

- [x] **W7b Verifier: implement `--cdx`** *(AC6, part 2)*

  **Files**: `cli/warc_verify.py` only. Requires W7a and W2 (11-field CDX).

  **Change**:
  1. Add before `def verify_warc`:
     ```python
     def verify_cdx(cdx_path, content, record_spans, compressed):
         """Each CDX line must have 11 fields; for plain .warc, (offset, length) must match a record boundary."""
         spans = {(off, ln) for off, ln, _ in record_spans}
         checked = bad = 0
         with open(cdx_path, 'r', encoding='utf-8', errors='replace') as f:
             for lineno, line in enumerate(f, 1):
                 if not line.strip() or line.startswith(' CDX'):
                     continue
                 parts = line.split()
                 if len(parts) != 11:
                     print(f"  [Warning] CDX line {lineno}: expected 11 fields, found {len(parts)}")
                     bad += 1
                     continue
                 checked += 1
                 if compressed:
                     continue  # offsets are only checkable against the uncompressed stream
                 length, offset = int(parts[8]), int(parts[9])
                 if not content.startswith(b"WARC/1.1", offset) or (offset, length) not in spans:
                     print(f"  [Warning] CDX line {lineno}: offset {offset} / length {length} is not a record boundary ({parts[2]})")
                     bad += 1
         suffix = " (offsets not checked: compressed container)" if compressed else ""
         print(f"  CDX entries verified:    {checked - bad}/{checked}{suffix}")
         return bad
     ```
  2. In `verify_warc`, immediately before the `print(f"  Integrity Status: ...")` line add:
     ```python
         if cdx_path:
             if os.path.isfile(cdx_path):
                 corrupt_count += verify_cdx(cdx_path, content, record_spans, warc_path.endswith('.gz'))
             else:
                 print(f"  [Warning] CDX file not found: {cdx_path}")
                 corrupt_count += 1
     ```

  **Verify** (uses the W7a fixture in `/tmp/aa_verify`):
  ```
  python3 cli/warc_verify.py /tmp/aa_verify/t.warc --cdx /tmp/aa_verify/t.cdx > /tmp/aa_verify/out1.txt; echo "exit=$?"; grep -E "CDX entries|Integrity" /tmp/aa_verify/out1.txt
  ```
  Expected: `exit=0`, `  CDX entries verified:    3/3`, `  Integrity Status:        PASSED`.
  ```
  python3 -c "
  ls=open('/tmp/aa_verify/t.cdx').read().split('\n');p=ls[-2].split();p[9]='1';ls[-2]=' '.join(p);open('/tmp/aa_verify/bad.cdx','w').write('\n'.join(ls))" && python3 cli/warc_verify.py /tmp/aa_verify/t.warc --cdx /tmp/aa_verify/bad.cdx > /tmp/aa_verify/out2.txt; echo "exit=$?"; grep -E "CDX entries|Integrity" /tmp/aa_verify/out2.txt
  ```
  Expected: `exit=1`, `  CDX entries verified:    2/3`, `  Integrity Status:        WARNINGS FOUND`.
  ```
  python3 cli/warc_verify.py /tmp/aa_verify/t.warc.gz --cdx /tmp/aa_verify/t.cdx > /tmp/aa_verify/out3.txt; echo "exit=$?"; grep "CDX entries" /tmp/aa_verify/out3.txt
  ```
  Expected: `exit=0`, `  CDX entries verified:    3/3 (offsets not checked: compressed container)`.

  **Done when**: all three outputs match; `--help` text for `--cdx` updated to `"Companion .cdx index: verify 11 fields and record offsets/lengths"`.

  **Do not**: parse CDXJ; do not require `--cdx`; do not change exit-code semantics (0 = clean, 1 = warnings).

## Phase 5 — Tests

- [x] **W8 Tests to add (stdlib only)** *(AC8; regression for AC1–AC7)*

  **Files** (create): `tests/js/warc_writer.test.js`, `tests/js/warc_reader.test.js`, `tests/test_warc_python.py`. Run `mkdir -p tests/js` first if the directory is absent (other tracks may already have created it; never delete their files).

  **Change**:
  - `tests/js/warc_writer.test.js` — `node:test` + `node:assert/strict`; cases: header hygiene (W1 Verify), CDX-11 positions (W2), `sha256Hex` rejects when `crypto.subtle` is missing (run in a child process via `child_process.execFileSync(process.execPath, ['-e', ...])` so the global override does not leak) and returns the known digest of `hello`, `WARC-Refers-To` (W4), request record layout and CDX offset (W6).
  - `tests/js/warc_reader.test.js` — `parseCdx` positions (W2) and revisit resolution end-to-end via `WarcWriter` -> `Blob.arrayBuffer()` -> `WarcReader` (W5).
  - `tests/test_warc_python.py` — `unittest.TestCase` using `tempfile.TemporaryDirectory()`: `PythonWarcWriter` header hygiene, 11-field CDX with boundary check, `WARC-Refers-To`, request record; `warc_verify.verify_warc` passes on the fixture with `--cdx`, fails on a tampered offset, and reads a `.warc.gz` copy; `mcp/server.search_cdx` returns `length/offset/filename` from positions 8/9/10. Import the modules via `sys.path.insert(0, 'cli')` / `'mcp'` relative to `os.path.dirname(__file__)`.

  **Verify**:
  ```
  node --test tests/js/ && python3 -m unittest discover -s tests -p 'test_*.py' -v
  ```
  Expected: `# fail 0` from node; `OK` from unittest.

  **Done when**: both commands exit 0 on a clean checkout; no network access; no files written inside the repository by tests.

  **Do not**: add `package.json` or any runner; do not edit `.github/workflows/ci.yml` (G3); do not edit other tracks' test files.

## Phase 6 — Completion

- [x] **F1** Final validation: all Verify commands of W1–W8; `python3 -m py_compile cli/*.py mcp/server.py`; leak-prevention gate clean; append `checkpoint_validated` to `evidence.jsonl`.
- [x] **F2** Update `metadata.json` (`status`, `updated_at`); hand registry update (G2) to the integrator; notify `cli_parity_20260905` that W2/W6 are available.

## Review Fixes

- [x] Rev-1 Preserve replay URL identity and fail closed on malformed containers. — review evidence d219c79
  - **Files**: `web/lib/warc_reader.js`, `cli/warc_verify.py`, `tests/js/warc_reader.test.js`, `tests/test_warc_review.py`.
  - **Change**: retain path/query case and trailing slashes, reset reader state on load, prefer record-ID/digest revisit linkage, bound record lengths, reject empty/truncated/invalid gzip containers, and report malformed CDX spans without an exception.
  - **Verify**: `node --test tests/js/warc_reader.test.js`; `python3 -m unittest tests.test_warc_review`; `python3 scripts/gate.py test`.
  - **Done when**: regression cases and repository baseline pass.
  - **Do not**: reinterpret compressed CDX offsets as uncompressed offsets.
