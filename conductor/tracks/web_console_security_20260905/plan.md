# Track Plan: Web Console Security & Persistence Claims

## Status: PLANNED

Conventions: paths relative to the repository root; line numbers refer to commit `3f00f46` (re-locate by the quoted snippet if they shifted); Verify commands run from the repository root with Node >= 18 and Python >= 3.9; complete a task only when every "Done when" item holds. Edit only the files listed under **Files**. Never create `._*` files. No new dependencies, no npm, no bundler. Do not commit or push unless the operator explicitly asks. Test fixtures live under `/tmp` or in memory.

Node bootstrap for crawler-level checks (UMD libraries expect globals):

```
node -e "global.PolitenessEngine=require('./web/lib/politeness_engine.js');global.WarcWriter=require('./web/lib/warc_writer.js');global.OpfsStreamer=require('./web/lib/opfs_streamer.js');global.SelfReflectionEngine=require('./web/lib/self_reflection.js');const C=require('./web/lib/core_crawler.js'); /* body */"
```

## Phase 1 — Specification & approval

- [ ] Capture reproduced defects V1–V7 and requirements R1–R8 in `spec.md` (traces to AC1–AC8).
- [ ] Approval basis: user requested Conductor planning artifacts for the 2026-09-05 review; implementation waits for the integrator to register the track.

## Phase 2 — Replay viewer hardening

- [x] **S1 Sandbox without flags + CSP meta, drop `<base>`** *(AC1)*

  **Files**: `web/viewer.html`, `web/lib/warc_reader.js`.

  **Change** (`viewer.html`): line 166
  ```html
            <iframe id="replayFrame" class="view-frame" sandbox="allow-same-origin allow-scripts"></iframe>
  ```
  ->
  ```html
            <iframe id="replayFrame" class="view-frame" sandbox=""></iframe>
  ```
  **Change** (`warc_reader.js`):
  1. Replace lines 171–177 inside `renderPage`:
     ```js
           // Create a base tag to resolve relative URLs
           const baseTag = `<base href="${record.url}">`;
           if (html.includes('<head>')) {
             html = html.replace('<head>', `<head>${baseTag}`);
           } else {
             html = `${baseTag}${html}`;
           }
     ```
     with:
     ```js
           // Never resolve against the live origin (V2); lock the document down with a CSP (V1).
           html = html.replace(/<base\b[^>]*>/gi, '');
           const csp = WarcReader.REPLAY_CSP_META;
           if (/<head[^>]*>/i.test(html)) {
             html = html.replace(/<head[^>]*>/i, m => m + csp);
           } else {
             html = csp + html;
           }
     ```
  2. Before `return WarcReader;` (line 183) add:
     ```js
       WarcReader.REPLAY_CSP_META = '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src blob: data:; style-src \'unsafe-inline\' blob:;">';
     ```

  **Verify**:
  ```
  grep -c 'sandbox=""' web/viewer.html; grep -c 'allow-same-origin' web/viewer.html
  ```
  Expected: `1` then `0`.
  ```
  node -e "const W=require('./web/lib/warc_writer.js');const R=require('./web/lib/warc_reader.js');(async()=>{const w=new W({filename:'t.warc'});const h=()=>({status:200,statusText:'OK',headers:new Headers({'content-type':'text/html'})});await w.addResponseRecord('http://h.test/',h(),new TextEncoder().encode('<html><head><base href=\"http://live.test/\"><title>t</title></head><body>x</body></html>'));const r=new R();await r.loadWarcBuffer(await (await w.getWarcBlob()).arrayBuffer());const out=r.renderPage('http://h.test/');console.log(/<base/i.test(out),out.indexOf(R.REPLAY_CSP_META)===out.indexOf('<head>')+6,out.includes(\"default-src 'none'\"))})()"
  ```
  Expected: `false true true`.

  **Done when**: both outputs match; `viewer.html` still loads a WARC and shows HTML text (scripts inside archived pages no longer run — expected).

  **Do not**: add `allow-scripts` back; do not use `frame.src` with a `blob:` HTML document as a workaround; do not modify `loadWarcBuffer`.

- [x] **S2 Rewrite requisites to `blob:` URLs** *(AC2)*

  **Files**: `web/lib/warc_reader.js` only. Requires S1.

  **Change**:
  1. Add two methods before `renderPage` (line 165):
     ```js
         /** Returns (and caches) a blob: URL for an archived record. */
         blobUrlFor(record) {
           if (!record.blobUrl) {
             record.blobUrl = URL.createObjectURL(new Blob([record.bodyBytes], { type: record.mimeType || 'application/octet-stream' }));
           }
           return record.blobUrl;
         }

         /**
          * Rewrites src/href/srcset so replay only reaches archived requisites (V2).
          * Anchors become inert (#) and keep the original target in data-archived-href.
          */
         rewriteRequisites(html, pageUrl) {
           const attrSafe = s => String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
           const resolve = raw => { try { return new URL(raw, pageUrl).href; } catch (e) { return null; } };
           html = html.replace(/\ssrcset\s*=\s*("[^"]*"|'[^']*')/gi, ' data-archived-srcset=$1');
           const re = /<(a|link|area|img|script|iframe|source|video|audio)\b([^>]*?)\s(href|src)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))/gi;
           return html.replace(re, (m, tag, before, attr, v1, v2, v3) => {
             const raw = v1 !== undefined ? v1 : (v2 !== undefined ? v2 : (v3 || ''));
             const abs = resolve(raw) || raw;
             if (/^(a|area)$/i.test(tag)) {
               return `<${tag}${before} data-archived-href="${attrSafe(abs)}" ${attr}="#"`;
             }
             const rec = this.getRecord(abs);
             const target = rec ? this.blobUrlFor(rec) : 'data:,';
             return `<${tag}${before} data-archived-${attr}="${attrSafe(abs)}" ${attr}="${target}"`;
           });
         }
     ```
  2. In `renderPage`, immediately after the `html = html.replace(/<base\b[^>]*>/gi, '');` line added in S1, insert `      html = this.rewriteRequisites(html, record.url);`.

  **Verify**:
  ```
  node -e "const W=require('./web/lib/warc_writer.js');const R=require('./web/lib/warc_reader.js');(async()=>{const w=new W({filename:'t.warc'});const h=(ct)=>({status:200,statusText:'OK',headers:new Headers({'content-type':ct})});const enc=s=>new TextEncoder().encode(s);await w.addResponseRecord('http://h.test/',h('text/html'),enc('<html><head><link rel=\"stylesheet\" href=\"/s.css\"></head><body><img src=\"i.png\" srcset=\"i.png 1x\"><img src=\"/missing.png\"><a href=\"/p2\">p2</a><script src=\"/j.js\"></script></body></html>'));await w.addResponseRecord('http://h.test/s.css',h('text/css'),enc('body{color:red}'));await w.addResponseRecord('http://h.test/i.png',h('image/png'),new Uint8Array([137,80,78,71]));const r=new R();await r.loadWarcBuffer(await (await w.getWarcBlob()).arrayBuffer());const out=r.renderPage('http://h.test/');const n=(re)=>(out.match(re)||[]).length;console.log(n(/href=\"blob:/g),n(/src=\"blob:/g),n(/src=\"data:,\"/g),out.includes('data-archived-href=\"http://h.test/p2\" href=\"#\"'),/\ssrcset=/.test(out),/<base/i.test(out))})()"
  ```
  Expected: `1 1 2 true false false`.

  **Done when**: output matches; S1 Verify still passes.

  **Do not**: rewrite `url()` inside CSS text (out of scope); do not fetch anything; do not revoke blob URLs inside `renderPage` (they are cached per record for the session).

## Phase 3 — Output encoding

- [x] **S3 Escape crawled strings in `index.html` and `viewer.html`** *(AC3)*

  **Files**: `web/index.html`, `web/viewer.html`.

  **Change** (`index.html`):
  1. Replace lines 534–536:
     ```js
         function escapeHtml(str) {
           return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
         }
     ```
     with:
     ```js
         function escapeHtml(str) {
           return String(str == null ? '' : str)
             .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
             .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
         }
     ```
  2. Replace lines 514–519 in `addDocumentRow`:
     ```js
           tr.innerHTML = `
             <td><a href="${doc.url}" target="_blank" title="${doc.url}">${doc.title || doc.url}</a></td>
             <td><span class="badge">${doc.mimeType || 'unknown'}</span></td>
             <td>${sizeKb} KB</td>
             <td><code style="font-family: var(--font-mono); font-size: 0.75rem;">${shortHash}</code></td>
           `;
     ```
     with:
     ```js
           const safeHref = /^https?:\/\//i.test(doc.url || '') ? doc.url : '#';
           tr.innerHTML = `
             <td><a href="${escapeHtml(safeHref)}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(doc.url)}">${escapeHtml(doc.title || doc.url)}</a></td>
             <td><span class="badge">${escapeHtml(doc.mimeType || 'unknown')}</span></td>
             <td>${sizeKb} KB</td>
             <td><code style="font-family: var(--font-mono); font-size: 0.75rem;">${escapeHtml(shortHash)}</code></td>
           `;
     ```
  **Change** (`viewer.html`):
  3. Add after `let activeUrl = null;` (line 175) the same `escapeHtml` function as in step 1.
  4. Line 191: `` <p style="color: var(--text-primary); margin-top: 16px;">Parsing ISO 28500 records from ${file.name}...</p> `` -> `` ...from ${escapeHtml(file.name)}...</p> ``.
  5. Lines 239–246:
     ```js
             li.innerHTML = `
               <span class="url-link" title="${url}">${url}</span>
               <div class="url-meta">
                 <span class="badge">${status}</span>
                 <span>${mime}</span>
                 <span>${sizeKb} KB</span>
               </div>
             `;
     ```
     ->
     ```js
             li.innerHTML = `
               <span class="url-link" title="${escapeHtml(url)}">${escapeHtml(url)}</span>
               <div class="url-meta">
                 <span class="badge">${escapeHtml(status)}</span>
                 <span>${escapeHtml(mime)}</span>
                 <span>${sizeKb} KB</span>
               </div>
             `;
     ```

  **Verify**:
  ```
  for f in web/index.html web/viewer.html; do node -e "const fs=require('fs');const src=fs.readFileSync('$f','utf8');const m=src.match(/function escapeHtml\(str\) \{[\s\S]*?\n    \}/);eval(m[0]);console.log(escapeHtml('<a href=\"x\">')+escapeHtml(String.fromCharCode(39)), escapeHtml(null)==='')"; done
  ```
  Expected (twice): `&lt;a href=&quot;x&quot;&gt;&#39; true`.
  ```
  grep -c '\${url}' web/viewer.html; grep -c '\${doc.url}' web/index.html; grep -c '\${file.name}' web/viewer.html; grep -c 'rel="noopener noreferrer"' web/index.html
  ```
  Expected: `0`, `0`, `0`, `1`.

  **Done when**: all outputs match; the log line at `index.html` line 529 still uses `escapeHtml(msg)` (unchanged).

  **Do not**: switch these two templates to `textContent`-only DOM construction (larger diff; escaping is sufficient here); do not touch `web/status.html` (other track).

## Phase 4 — Single profile source

- [x] **S4 Generate `web/profiles.bundle.js` from `profiles/*.json`** *(AC4)*

  **Files** (create): `scripts/build_profile_bundle.py`, `web/profiles.bundle.js` (generated). **Modify**: `web/index.html`. Do not edit `profiles/*.json`.

  **Change**:
  1. Create `scripts/build_profile_bundle.py`:
     ```python
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
     ```
  2. Run `python3 scripts/build_profile_bundle.py` to create `web/profiles.bundle.js`.
  3. `index.html`: after line 8 (`<script src="lib/minisearch.min.js"></script>`) add `  <script src="profiles.bundle.js"></script>`.
  4. `index.html` lines 38–40 (the three static `<option>` elements for `default_polite`, `enterprise_intranet`, `rapid_research`): delete them; keep only `<option value="custom">Load Custom Profile JSON...</option>`.
  5. `index.html` lines 241–332 (`const BUILTIN_PROFILES = { ... };`): replace the whole literal with:
     ```js
         // Built-in profiles come from the generated bundle (single source of truth: profiles/*.json) (V4).
         const BUILTIN_PROFILES = (typeof AEGIS_BUNDLED_PROFILES !== 'undefined') ? AEGIS_BUNDLED_PROFILES : {};
     ```
  6. `index.html` lines 334–337 (`function init() { ... }`) ->
     ```js
         function init() {
           const select = document.getElementById('profileSelect');
           const customOpt = select.querySelector('option[value="custom"]');
           for (const [id, p] of Object.entries(BUILTIN_PROFILES)) {
             const opt = document.createElement('option');
             opt.value = id;
             opt.textContent = p.profile_name || id;
             select.insertBefore(opt, customOpt);
           }
           activeProfile = BUILTIN_PROFILES.default_polite || Object.values(BUILTIN_PROFILES)[0] || null;
           if (activeProfile) select.value = activeProfile.profile_id;
           updateProfileDisplay();
         }
     ```

  **Verify**:
  ```
  python3 scripts/build_profile_bundle.py && python3 scripts/build_profile_bundle.py --check; echo "exit=$?"
  ```
  Expected: `wrote web/profiles.bundle.js (<n> bytes)`, `profiles.bundle.js is up to date`, `exit=0`.
  ```
  node -e "const b=require('./web/profiles.bundle.js');console.log(Object.keys(b).sort().join(','),b.default_polite.target.allowed_domains[0],typeof b.rapid_research.politeness.min_delay_ms)"
  ```
  Expected: `default_polite,enterprise_intranet,rapid_research example.org number`.
  ```
  grep -c 'BUILTIN_PROFILES = {' web/index.html; grep -c 'src="profiles.bundle.js"' web/index.html; grep -c 'option value="enterprise_intranet"' web/index.html
  ```
  Expected: `0`, `1`, `0`.

  **Done when**: all outputs match; opening `web/index.html` via `python3 cli/launch.py --no-browser` and loading the page lists three profiles in the selector (manual check acceptable).

  **Do not**: read `profiles/*.json` at runtime via `fetch` (the launcher serves `web/` only); do not hand-edit `web/profiles.bundle.js`; do not add a `package.json` script.

## Phase 5 — Persistence claims

- [x] **S5 Wire `OpfsStreamer` into `WarcWriter`** *(AC5)*

  **Files**: `web/lib/warc_writer.js`, `web/lib/core_crawler.js`. Apply after `warc_interop_20260905` W1–W6 if that track is in progress (its request record adds one more `this.records.push` site).

  **Change** (`warc_writer.js`):
  1. Constructor, after `this.records = [];` (line 73) add `      this.recordCount = 0;` and `      this.streamer = null; // OpfsStreamer once attached (V5)`.
  2. In `addWarcInfoRecord`, after `this.records.push(fullRecord);` (line 121) add `      this.recordCount += 1;` (this record is written synchronously from the constructor and is flushed by `attachStreamer`).
  3. Add methods after `addWarcInfoRecord`:
     ```js
         /** Appends finished record bytes to memory or, once attached, to the streamer. */
         async appendRecord(bytes) {
           this.recordCount += 1;
           this.currentOffset += bytes.length;
           if (this.streamer) await this.streamer.writeChunk(bytes);
           else this.records.push(bytes);
         }

         /** Attaches an initialised OpfsStreamer and flushes records already held in memory. */
         async attachStreamer(streamer) {
           for (const rec of this.records) await streamer.writeChunk(rec);
           this.records = [];
           this.streamer = streamer;
         }
     ```
  4. Replace every remaining pair `this.records.push(X); this.currentOffset += X.length;` with `await this.appendRecord(X);` — in `addResponseRecord` (lines 211–212, `recordBytes`) and, if present from W6, in `addRequestRecord` (`rec`; make that method `async` and `await` its call site).
  5. Replace `getWarcBlob()` (lines 231–233) with:
     ```js
         async getWarcBlob() {
           if (this.streamer) {
             await this.streamer.close();
             return this.streamer.getBlob('application/warc');
           }
           return new Blob(this.records, { type: 'application/warc' });
         }
     ```
  6. In `getStats()`, `recordCount: this.records.length,` -> `recordCount: this.recordCount,`.

  **Change** (`core_crawler.js`):
  7. After the `this.warc = new WarcWriter({...});` statement (ends line 61) add:
     ```js
           const wantsOpfs = !profile.archival || profile.archival.enable_opfs_streaming !== false;
           this.streamer = (wantsOpfs && typeof OpfsStreamer !== 'undefined') ? new OpfsStreamer(this.warc.filename) : null;
           this.streamerAttached = false;
     ```
  8. In `start()`, after the `if (this.queue.length === 0 && this.visited.size === 0) { this.seedQueue(); }` block (lines 189–191) add:
     ```js
           if (this.streamer && !this.streamerAttached) {
             const onDisk = await this.streamer.init();
             await this.warc.attachStreamer(this.streamer);
             this.streamerAttached = true;
             this.callbacks.onLog(onDisk ? '[Storage] Streaming WARC records to origin-private file storage.' : '[Storage] OPFS unavailable; streaming to memory chunks.');
           }
     ```
  9. `getFinalResults()` (line 375) -> `async getFinalResults()`, and `warcBlob: this.warc.getWarcBlob(),` -> `warcBlob: await this.warc.getWarcBlob(),`.
  10. In `start()`, `this.callbacks.onComplete(this.getFinalResults());` (line 223) -> `this.callbacks.onComplete(await this.getFinalResults());`.

  **Verify**:
  ```
  node -e "global.PolitenessEngine=require('./web/lib/politeness_engine.js');global.WarcWriter=require('./web/lib/warc_writer.js');global.OpfsStreamer=require('./web/lib/opfs_streamer.js');global.SelfReflectionEngine=require('./web/lib/self_reflection.js');const C=require('./web/lib/core_crawler.js');const c=new C({target:{allowed_domains:['h.test'],seed_urls:{tier_1_core:['http://h.test/']}},politeness:{min_delay_ms:1,max_delay_ms:2}});global.fetch=async()=>({ok:true,status:200,statusText:'OK',headers:new Headers({'content-type':'text/html'}),text:async()=>'',arrayBuffer:async()=>new TextEncoder().encode('<p>hi</p>').buffer});c.callbacks.onComplete=(r)=>{console.log(c.streamerAttached,r.warcBlob.size===c.warc.currentOffset,c.warc.records.length,r.warcStats.recordCount>=2)};c.start()"
  ```
  Expected: `true true 0 true`.
  ```
  node -e "const W=require('./web/lib/warc_writer.js');const w=new W({filename:'t.warc'});w.getWarcBlob().then(b=>console.log(b.size===w.currentOffset,w.getStats().recordCount))"
  ```
  Expected: `true 1`.

  **Done when**: both outputs match; every Verify of `warc_interop_20260905` that calls `getWarcBlob()` uses `await` (they already do).

  **Do not**: change `OpfsStreamer` itself; do not call `exportToUserDirectory`; do not keep a second copy of records in memory when a streamer is attached.

- [x] **S6 Checkpoint/resume of the frontier** *(AC6)*

  **Files**: `web/lib/core_crawler.js`, `web/index.html`.

  **Change** (`core_crawler.js`):
  1. In the callbacks object (lines 33–39) add `        onCheckpoint: callbacks.onCheckpoint || (() => {}),` after `onDocumentFound`.
  2. Add methods before `getProgressStats()` (line 365):
     ```js
         /** Serialisable frontier for crash-safe resume (V6). Records already written are not included. */
         exportCheckpoint() {
           return {
             version: 1,
             profile_id: this.profile.profile_id || null,
             savedAt: new Date().toISOString(),
             queue: this.queue,
             visited: Array.from(this.visited)
           };
         }

         importCheckpoint(cp) {
           if (!cp || cp.version !== 1 || !Array.isArray(cp.queue)) return false;
           this.queue = cp.queue.slice();
           this.visited = new Set(cp.visited || []);
           return true;
         }
     ```
  3. In the `start()` loop, after `this.callbacks.onProgress(this.getProgressStats());` (line 216) add:
     ```js
             if (this.visited.size % 10 === 0) this.callbacks.onCheckpoint(this.exportCheckpoint());
     ```
  4. In `start()`, after `this.callbacks.onStatusChange('STOPPED');` (line 221) add `      this.callbacks.onCheckpoint(this.queue.length > 0 ? this.exportCheckpoint() : null);` (a finished run clears the checkpoint; a stopped run keeps it).
  5. In `pause()` and `stop()`, add `      this.callbacks.onCheckpoint(this.exportCheckpoint());` as the last statement of each.

  **Change** (`index.html`):
  6. After the profile bar `</div>` (line 49) insert:
     ```html
         <div id="resumeBanner" class="controls-bar" style="display:none; gap: 12px; align-items: center;">
           <span id="resumeBannerText"></span>
           <button class="btn btn-emerald" onclick="resumeFromCheckpoint()">▶️ Resume</button>
           <button class="btn btn-secondary" onclick="discardCheckpoint()">Discard</button>
         </div>
     ```
  7. After `let currentReportMd = "";` (line 239) add `    let pendingCheckpoint = null;` and `    const CHECKPOINT_KEY = 'aegis.checkpoint.v1';`.
  8. Add functions after `init()`:
     ```js
         function saveCheckpoint(cp) {
           try {
             if (cp === null) localStorage.removeItem(CHECKPOINT_KEY);
             else localStorage.setItem(CHECKPOINT_KEY, JSON.stringify(cp));
           } catch (e) { log(`[Checkpoint] Not saved: ${e.message}`); }
         }
         function loadCheckpoint() {
           try { const raw = localStorage.getItem(CHECKPOINT_KEY); return raw ? JSON.parse(raw) : null; } catch (e) { return null; }
         }
         function showResumeBanner(cp) {
           document.getElementById('resumeBannerText').textContent =
             `Unfinished session for profile '${cp.profile_id}': ${cp.visited.length} visited, ${cp.queue.length} queued (saved ${cp.savedAt}). Resume restores the frontier only; records captured before the reload must have been exported.`;
           document.getElementById('resumeBanner').style.display = 'flex';
         }
         function resumeFromCheckpoint() {
           pendingCheckpoint = loadCheckpoint();
           document.getElementById('resumeBanner').style.display = 'none';
           if (pendingCheckpoint && BUILTIN_PROFILES[pendingCheckpoint.profile_id]) {
             activeProfile = BUILTIN_PROFILES[pendingCheckpoint.profile_id];
             document.getElementById('profileSelect').value = pendingCheckpoint.profile_id;
             updateProfileDisplay();
           }
           startHarvest();
         }
         function discardCheckpoint() {
           saveCheckpoint(null);
           document.getElementById('resumeBanner').style.display = 'none';
         }
     ```
  9. In `init()` (as rewritten by S4) add before `updateProfileDisplay();`: `      const cp = loadCheckpoint(); if (cp && Array.isArray(cp.queue) && cp.queue.length > 0) showResumeBanner(cp);`.
  10. In `startHarvest()` add `        onCheckpoint: (cp) => saveCheckpoint(cp),` to the callbacks object, and after the `crawler = new CoreCrawler(...)` statement add:
      ```js
            if (pendingCheckpoint) {
              if (crawler.importCheckpoint(pendingCheckpoint)) log(`[Checkpoint] Resumed ${pendingCheckpoint.visited.length} visited / ${pendingCheckpoint.queue.length} queued URLs.`);
              pendingCheckpoint = null;
            }
      ```

  **Verify**:
  ```
  node -e "global.PolitenessEngine=require('./web/lib/politeness_engine.js');global.WarcWriter=require('./web/lib/warc_writer.js');global.SelfReflectionEngine=require('./web/lib/self_reflection.js');const C=require('./web/lib/core_crawler.js');const c=new C({profile_id:'p1',target:{allowed_domains:['h.test']}},{onCheckpoint:(cp)=>console.log('cp',cp===null?null:cp.queue.length)});c.queue.push({url:'http://h.test/a',tier:1,depth:0,parentUrl:'root'});c.visited.add('http://h.test/b');const cp=JSON.parse(JSON.stringify(c.exportCheckpoint()));const d=new C({profile_id:'p1',target:{allowed_domains:['h.test']}});console.log(d.importCheckpoint(cp),d.queue.length,d.visited.has('http://h.test/b'),cp.profile_id,d.importCheckpoint({version:2}));c.stop()"
  ```
  Expected: `true 1 true p1 false` then `cp 1`.
  ```
  grep -c 'aegis.checkpoint.v1' web/index.html; grep -c 'id="resumeBanner"' web/index.html; grep -c 'onCheckpoint' web/index.html
  ```
  Expected: `1`, `1`, `1`.

  **Done when**: outputs match; a manual reload mid-crawl shows the banner and Resume continues from the saved queue.

  **Do not**: persist WARC bytes or the audit ledger in `localStorage`; do not use IndexedDB in this task; do not auto-resume without the operator clicking Resume.

- [x] **S7 Read `?profile=` from the URL** *(AC7)*

  **Files**: `web/index.html` only. Requires S4 (bundle) for id lookup.

  **Change**:
  1. Add after `discardCheckpoint()` (S6):
     ```js
         // Launcher hand-off (V7): ?profile=<bundled id | path ending in <id>.json | same-origin URL>
         async function applyProfileParam(raw) {
           const select = document.getElementById('profileSelect');
           const idFromPath = (raw.split(/[\\/]/).pop() || '').replace(/\.json$/i, '');
           const byId = BUILTIN_PROFILES[raw] || BUILTIN_PROFILES[idFromPath];
           if (byId) {
             activeProfile = byId; select.value = byId.profile_id; updateProfileDisplay();
             log(`[Profile] Selected '${byId.profile_name}' from ?profile=.`);
             return;
           }
           let u = null;
           try { u = new URL(raw, location.href); } catch (e) {}
           if (!u || u.origin !== location.origin || !/^https?:$/.test(u.protocol)) {
             log(`[Profile] Ignored ?profile= value (not a bundled id or same-origin URL).`);
             return;
           }
           try {
             const resp = await fetch(u.href, { cache: 'no-store' });
             if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
             const parsed = await resp.json();
             if (!parsed.target || !parsed.target.allowed_domains) throw new Error("missing 'target.allowed_domains'");
             activeProfile = parsed; select.value = 'custom'; updateProfileDisplay();
             log(`[Profile] Loaded profile from ${u.pathname}: ${parsed.profile_name || 'Custom'}`);
           } catch (err) {
             log(`[Profile] Could not load ?profile= target: ${err.message}`);
           }
         }
     ```
  2. In `init()`, as the last statement: `      const profileParam = new URLSearchParams(location.search).get('profile'); if (profileParam) applyProfileParam(profileParam);`.

  **Verify**:
  ```
  grep -c "URLSearchParams(location.search).get('profile')" web/index.html; grep -c "u.origin !== location.origin" web/index.html; grep -c "cache: 'no-store'" web/index.html
  ```
  Expected: `1`, `1`, `1`.
  ```
  node -e 'const raw="/abs/path/profiles/default_polite.json";console.log((raw.split(/[\\/]/).pop()||"").replace(/\.json$/i,""))'
  ```
  Expected: `default_polite`.

  **Done when**: outputs match; `python3 cli/launch.py --no-browser --profile profiles/default_polite.json` prints a console URL that, when opened, logs `[Profile] Selected 'Default Server-Preserving Preservation' from ?profile=.` (manual check acceptable).

  **Do not**: fetch cross-origin; do not read filesystem paths; do not modify `cli/launch.py` (G4 — recommend to the integrator that the launcher pass the profile id).

## Phase 6 — Tests

- [ ] **S8 Tests to add (stdlib only)** *(AC8; regression for AC1–AC7)*

  **Files** (create): `tests/js/warc_reader_render.test.js`, `tests/js/warc_writer_streamer.test.js`, `tests/js/core_crawler_checkpoint.test.js`, `tests/test_web_console_static.py`. Run `mkdir -p tests/js` first if absent (other tracks may already have created it; never delete their files).

  **Change**:
  - `tests/js/warc_reader_render.test.js` — S1 and S2 Verify scenarios as `node:test` cases (CSP position, no `<base`, blob/data rewriting counts, inert anchors).
  - `tests/js/warc_writer_streamer.test.js` — S5 Verify scenarios: streamer attach/flush, `records.length === 0` after attach, `getWarcBlob()` size equals `currentOffset`, crawler end-to-end with stubbed `global.fetch`.
  - `tests/js/core_crawler_checkpoint.test.js` — S6 Verify scenario plus: `onCheckpoint(null)` is emitted when the queue drains (stub `fetch` returning a page with no links).
  - `tests/test_web_console_static.py` — `unittest` static assertions on `web/viewer.html` and `web/index.html`: `sandbox=""` present, `allow-same-origin` absent, forbidden raw interpolations absent (`${url}`, `${doc.url}`, `${file.name}`), `profiles.bundle.js` script tag present and `BUILTIN_PROFILES = {` absent, `aegis.checkpoint.v1` present, `URLSearchParams(location.search).get('profile')` present; and `build_profile_bundle.main(['--check']) == 0` (import via `sys.path.insert(0, <repo>/scripts)`).

  **Verify**:
  ```
  node --test tests/js/ && python3 -m unittest discover -s tests -p 'test_*.py' -v
  ```
  Expected: `# fail 0`; `OK`.

  **Done when**: both commands exit 0 on a clean checkout; tests do not write inside the repository and make no network calls.

  **Do not**: add `package.json`; do not edit `.github/workflows/ci.yml` (G3); do not edit other tracks' test files.

## Phase 7 — Completion

- [ ] **F1** Final validation: all Verify commands of S1–S8; `python3 -m py_compile scripts/build_profile_bundle.py cli/*.py mcp/server.py`; leak-prevention gate clean; append `checkpoint_validated` to `evidence.jsonl`.
- [ ] **F2** Update `metadata.json` (`status`, `updated_at`); hand registry update (G2), CI wiring (G3) and the launcher recommendation (G4) to the integrator.
