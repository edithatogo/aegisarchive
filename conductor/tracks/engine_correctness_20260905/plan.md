# Track Plan: Politeness Engine & Crawler Correctness

## Status: COMPLETED (2026-09-05 — Politeness Engine & Crawler Correctness)

Conventions for every task below: paths are relative to the repository root; line numbers refer to the files as of commit `3f00f46` (re-locate by the quoted snippet if lines have shifted); "Verify" commands run from the repository root with Node >= 18 and Python >= 3.9; a task is complete only when every "Done when" item is true. Never edit files outside the task's **Files** list. Never create files whose names start with `._`. Never add dependencies (no `npm install`, no `pip install`). Do not commit or push unless the operator explicitly asks.

Node bootstrap used by several Verify commands (the libraries are UMD; `core_crawler.js` expects the other engines as globals):

```
node -e "global.PolitenessEngine=require('./web/lib/politeness_engine.js');global.WarcWriter=require('./web/lib/warc_writer.js');global.SelfReflectionEngine=require('./web/lib/self_reflection.js');const C=require('./web/lib/core_crawler.js'); /* ...test body... */"
```

## Phase 1 — Specification & approval

- [ ] Capture reproduced defects D1–D10 and requirements R1–R11 in `spec.md` (traces to AC1–AC11).
- [ ] Approval basis: user requested Conductor planning artifacts for the 2026-09-05 review findings; implementation waits for the integrator to register the track.

## Phase 2 — Politeness engine (`web/lib/politeness_engine.js`)

- [x] **T1 EWMA baseline warm-up** *(AC1)*

  **Files**: `web/lib/politeness_engine.js` only. Do not touch `web/lib/core_crawler.js`.

  **Change**:
  1. In the constructor, after line 50 (`this.baselineLatencyMs = null;`) add:
     ```js
           this.warmupSize = 10;            // samples used for the median baseline
           this.warmupSamples = [];
           this.baselineDriftAlpha = 0.02;  // slow drift after warm-up
     ```
  2. Replace lines 132–138 (the `// Update EWMA` block):
     ```js
           // Update EWMA
           if (this.ewmaLatencyMs === null) {
             this.ewmaLatencyMs = latencyMs;
             this.baselineLatencyMs = latencyMs;
           } else {
             this.ewmaLatencyMs = Math.round(this.ewmaAlpha * latencyMs + (1 - this.ewmaAlpha) * this.ewmaLatencyMs);
           }
     ```
     with:
     ```js
           // Update EWMA
           if (this.ewmaLatencyMs === null) {
             this.ewmaLatencyMs = latencyMs;
           } else {
             this.ewmaLatencyMs = Math.round(this.ewmaAlpha * latencyMs + (1 - this.ewmaAlpha) * this.ewmaLatencyMs);
           }

           // Baseline: median of the first warmupSize samples, then slow drift (D1)
           if (this.warmupSamples.length < this.warmupSize) {
             this.warmupSamples.push(latencyMs);
             if (this.warmupSamples.length === this.warmupSize) {
               const sorted = this.warmupSamples.slice().sort((a, b) => a - b);
               this.baselineLatencyMs = sorted[Math.floor(sorted.length / 2)];
             }
           } else {
             this.baselineLatencyMs = Math.round(
               (1 - this.baselineDriftAlpha) * this.baselineLatencyMs + this.baselineDriftAlpha * latencyMs
             );
           }
     ```
  The strain check at line 221 (`if (this.adaptiveEwma && this.ewmaLatencyMs && this.baselineLatencyMs)`) is unchanged: it is skipped while `baselineLatencyMs` is `null`.

  **Verify**:
  ```
  node -e "const P=require('./web/lib/politeness_engine.js');const e=new P({});e.recordSuccess('u',5);console.log(e.baselineLatencyMs);for(let i=0;i<9;i++)e.recordSuccess('u',300);console.log(e.baselineLatencyMs,e.warmupSamples.length);e.recordSuccess('u',1000);console.log(e.baselineLatencyMs)"
  ```
  Expected output (three lines): `null`, `300 10`, `314`.

  **Done when**: the Verify output matches exactly; `node -e "require('./web/lib/politeness_engine.js')"` exits 0; no other method changed.

  **Do not**: change `ewmaAlpha`, the strain threshold (`1.35`) or `getTelemetry()` keys; do not read warm-up size from the profile (no schema change in this task).

- [x] **T2 Count only 0/429/5xx as failures** *(AC2)*

  **Files**: `web/lib/politeness_engine.js` only.

  **Change**:
  1. Inside `class PolitenessEngine`, immediately before `recordFailure(url, status, retryAfterHeader = null) {` (line 150) add:
     ```js
         /**
          * Only network errors (0), 429 and 5xx indicate server strain (D2).
          */
         static isCountableFailure(status) {
           const s = Number(status);
           return s === 0 || s === 429 || (s >= 500 && s <= 599);
         }
     ```
  2. Replace the first line of the method body, line 151 `      this.consecutiveErrors++;`, with:
     ```js
           if (!PolitenessEngine.isCountableFailure(status)) {
             return false; // informational 4xx: ledger only, no circuit change
           }
           this.consecutiveErrors++;
     ```
  3. Make the method end with `return true;` by adding that line after the closing `}` of the `if/else` at line 170 (before the method's closing brace at line 171).

  **Verify**:
  ```
  node -e "const P=require('./web/lib/politeness_engine.js');const e=new P({});for(let i=0;i<3;i++)e.recordFailure('http://h.test/',404);console.log(e.circuitState,e.consecutiveErrors);for(let i=0;i<3;i++)e.recordFailure('http://h.test/',503);console.log(e.circuitState,P.isCountableFailure(0),P.isCountableFailure(403))"
  ```
  Expected: `NOMINAL 0` then `TRIPPED true false`.

  **Done when**: Verify matches; `recordFailure` returns a boolean; `core_crawler.js` untouched.

  **Do not**: rename `recordFailure`; do not alter `consecutiveErrorTripwire` semantics; do not change the crawler's ledger writes (they must keep recording 4xx).

- [x] **T3 Re-queue with retry budget on countable failures** *(AC3)*

  **Files**: `web/lib/core_crawler.js` only. Requires T2.

  **Change**:
  1. Line 49 comment `this.queue = [];       // [{ url, tier, depth, parentUrl }]` -> `this.queue = [];       // [{ url, tier, depth, parentUrl, retries }]`.
  2. After line 70 (`this.maxPages = ...`) add `      this.maxRetries = 3;`.
  3. In `processUrl`, change the destructuring on line 227 from `const { url, depth, tier } = task;` to `const { url, depth, tier } = task; // task.retries is managed by requeueForRetry`.
  4. In the `if (!resp.ok) {` block, after the `this.callbacks.onLog(\`[HTTP ${resp.status}] ...\`);` line (257) and before `return;` insert:
     ```js
               if (PolitenessEngine.isCountableFailure(resp.status)) this.requeueForRetry(task);
     ```
  5. In the `catch (err)` block, after the `this.callbacks.onLog(\`[Network Error] ...\`);` line (316) insert `        this.requeueForRetry(task);`.
  6. Add a new method directly after `processUrl` (before `extractLinks`):
     ```js
         /**
          * Puts a task back on the queue after a countable failure (D3). Back-off is applied by
          * acquirePermission() because the engine is now THROTTLED/TRIPPED.
          */
         requeueForRetry(task) {
           const retries = (task.retries || 0) + 1;
           if (retries > this.maxRetries) {
             this.callbacks.onLog(`[Retry] Abandoning ${task.url} after ${this.maxRetries} retries.`);
             return false;
           }
           this.visited.delete(task.url);
           this.queue.push({ ...task, retries });
           this.callbacks.onLog(`[Retry ${retries}/${this.maxRetries}] Re-queued ${task.url}`);
           return true;
         }
     ```

  **Verify**:
  ```
  node -e "global.PolitenessEngine=require('./web/lib/politeness_engine.js');global.WarcWriter=require('./web/lib/warc_writer.js');global.SelfReflectionEngine=require('./web/lib/self_reflection.js');const C=require('./web/lib/core_crawler.js');const c=new C({target:{allowed_domains:['h.test']},politeness:{min_delay_ms:1,max_delay_ms:2}});global.fetch=async()=>({ok:false,status:503,headers:new Headers()});(async()=>{const t={url:'http://h.test/a',tier:1,depth:0,parentUrl:'root'};c.visited.add(t.url);await c.processUrl(t);console.log(c.queue.length,c.queue[0].retries,c.visited.has(t.url));console.log(c.requeueForRetry({url:'http://h.test/b',retries:3}),c.queue.length)})()"
  ```
  Expected: `1 1 false` then `false 1`.

  **Done when**: Verify matches; a `404` does **not** re-queue (add `status:404` to the stub and confirm `c.queue.length` prints `0`).

  **Do not**: change the queue sort; do not add a separate retry queue; do not modify `politeness_engine.js`.

- [x] **T4 Abortable waits, Retry-After cap, `stop()` aborts** *(AC4)*

  **Files**: `web/lib/politeness_engine.js`, `web/lib/core_crawler.js`.

  **Change** (`politeness_engine.js`):
  1. In the constructor after `this.domainCooldowns = new Map();` (line 57) add:
     ```js
           this.abortController = (typeof AbortController !== 'undefined') ? new AbortController() : null;
     ```
  2. Add three methods before `parseRetryAfter` (line 67):
     ```js
         /** Interruptible sleep; resolves true when the delay elapsed, false when aborted (D4). */
         sleep(ms) {
           const signal = this.abortController ? this.abortController.signal : null;
           return new Promise(resolve => {
             if (signal && signal.aborted) return resolve(false);
             const onAbort = () => { clearTimeout(timer); resolve(false); };
             const timer = setTimeout(() => {
               if (signal) signal.removeEventListener('abort', onAbort);
               resolve(true);
             }, ms);
             if (signal) signal.addEventListener('abort', onAbort, { once: true });
           });
         }

         abort() { if (this.abortController) this.abortController.abort(); }

         resetAbort() {
           if (typeof AbortController !== 'undefined') this.abortController = new AbortController();
         }
     ```
  3. In `recordFailure`, replace lines 155–159:
     ```js
           if (retryMs) {
             try {
               const domain = new URL(url).hostname;
               this.domainCooldowns.set(domain, Date.now() + retryMs);
             } catch (e) {}
           }
     ```
     with:
     ```js
           if (retryMs) {
             const capMs = this.cooldownSeconds * 10 * 1000; // never honour absurd Retry-After (D4)
             try {
               const domain = new URL(url).hostname;
               this.domainCooldowns.set(domain, Date.now() + Math.min(retryMs, capMs));
             } catch (e) {}
           }
     ```
  4. In `acquirePermission`, replace each of the four waits:
     - line 189 `await new Promise(resolve => setTimeout(resolve, waitRemaining));`
     - line 202 `await new Promise(resolve => setTimeout(resolve, sleepMs));`
     - line 212 `await new Promise(resolve => setTimeout(resolve, waitMs));`
     - line 238 `await new Promise(resolve => setTimeout(resolve, calculatedDelay));`
     with (same variable name in each):
     ```js
           if (!(await this.sleep(<var>))) return { delayMs: 0, state: this.circuitState, aborted: true };
     ```
     and change the final `return { delayMs: calculatedDelay, state: this.circuitState };` to `return { delayMs: calculatedDelay, state: this.circuitState, aborted: false };`.

  **Change** (`core_crawler.js`):
  5. In `start()`, after `this.shouldStop = false;` (line 186) add `      this.politeness.resetAbort();`.
  6. In `processUrl`, after `const gate = await this.politeness.acquirePermission(url);` (line 230) add `      if (gate.aborted) return;`.
  7. In `stop()`, after `this.isPaused = false;` (line 360) add `      this.politeness.abort();`.

  **Verify**:
  ```
  node -e "const P=require('./web/lib/politeness_engine.js');const e=new P({cooldown_seconds:60});e.recordFailure('http://h.test/',429,'999999');const t0=Date.now();setTimeout(()=>e.abort(),50);e.acquirePermission('http://h.test/').then(g=>console.log(g.aborted,Date.now()-t0<1000,e.domainCooldowns.get('h.test')-Date.now()<=600000));"
  ```
  Expected: `true true true` (printed within about 50 ms; the process exits promptly because the timer was cleared).
  ```
  node -e "const P=require('./web/lib/politeness_engine.js');const e=new P({min_delay_ms:1,max_delay_ms:2});e.acquirePermission('http://h.test/').then(g=>console.log(g.aborted,g.delayMs>=1))"
  ```
  Expected: `false true`.

  **Done when**: both Verify outputs match; `grep -c "setTimeout(resolve" web/lib/politeness_engine.js` prints `0`; `core_crawler.js` still passes the T3 Verify.

  **Do not**: throw on abort (return the `aborted` flag instead); do not change the `getTelemetry()` shape; do not touch `index.html`.

- [x] **T5 Fetch from origin (`cache: 'no-store'`)** *(AC5)*

  **Files**: `web/lib/core_crawler.js` only.

  **Change**: line 240 `          cache: 'default'` -> `          cache: 'no-store'`.

  **Verify**:
  ```
  grep -c "cache: 'no-store'" web/lib/core_crawler.js; grep -c "cache: 'default'" web/lib/core_crawler.js
  ```
  Expected: `1` then `0`.

  **Done when**: Verify matches and `node -e "require('./web/lib/core_crawler.js')"` (with the globals bootstrap) exits 0.

  **Do not**: add other fetch options or headers.

## Phase 3 — Profile schema (`profiles/schema.json`)

- [x] **T6 Bounds, `additionalProperties`, honest enum, deprecated `concurrency`, `robots_policy`** *(AC6, AC7)*

  **Files**: `profiles/schema.json`, `profiles/rapid_research.json` (one value). Do not touch other profiles or `web/index.html`.

  **Change** (`profiles/schema.json`):
  1. `target.max_depth` (lines 62–65): add `"minimum": 0, "maximum": 50`. `target.max_pages` (66–69): add `"minimum": 1, "maximum": 100000`.
  2. Politeness properties (lines 79–123), add keys:
     - `min_delay_ms`: `"minimum": 250, "maximum": 60000`
     - `max_delay_ms`: `"minimum": 250, "maximum": 120000`
     - `jitter_distribution.enum`: remove `"decorrelated"` (result: `["gaussian", "uniform"]`)
     - `max_requests_per_minute`: `"minimum": 1, "maximum": 300`
     - `concurrency`: keep type/default, add `"maximum": 1, "deprecated": true, "description": "Deprecated and ignored: the engine is single-flight by design."`
     - `burst_limit`: `"minimum": 1, "maximum": 20`
     - `consecutive_error_tripwire`: `"minimum": 1, "maximum": 20`
     - `cooldown_seconds`: `"minimum": 5, "maximum": 3600`
     - new property after `cooldown_seconds`:
       ```json
       "robots_policy": {
         "type": "string",
         "enum": ["respect", "ignore_authorised"],
         "default": "respect",
         "description": "respect: fetch /robots.txt once per origin and honour Disallow; ignore_authorised: skip robots.txt only for targets you are explicitly authorised to archive (decision is written to the audit ledger)."
       }
       ```
  3. After the top-level `"required": [...]` array (lines 181–186) add `"additionalProperties": false`.

  **Change** (`profiles/rapid_research.json`): line 33 `"min_delay_ms": 200,` -> `"min_delay_ms": 250,`.

  **Verify**:
  ```
  python3 -c "
  import json,glob
  s=json.load(open('profiles/schema.json'));pol=s['properties']['politeness']['properties']
  assert s['additionalProperties'] is False
  assert pol['jitter_distribution']['enum']==['gaussian','uniform']
  assert pol['concurrency'].get('deprecated') is True
  assert pol['robots_policy']['enum']==['respect','ignore_authorised'] and pol['robots_policy']['default']=='respect'
  assert pol['min_delay_ms']['minimum']==250 and pol['max_requests_per_minute']['maximum']==300 and pol['burst_limit']['maximum']==20
  for f in sorted(glob.glob('profiles/*.json')):
      if f.endswith('schema.json'): continue
      d=json.load(open(f))
      assert set(d)<=set(s['properties']),(f,set(d)-set(s['properties']))
      for k,v in d['politeness'].items():
          p=pol[k]
          if 'minimum' in p: assert v>=p['minimum'],(f,k,v)
          if 'maximum' in p: assert v<=p['maximum'],(f,k,v)
          if 'enum' in p: assert v in p['enum'],(f,k,v)
  print('schema OK')"
  ```
  Expected: `schema OK`. Note: `rapid_research.json` currently has `"concurrency": 4`, which violates the new `maximum: 1`; therefore also change line 37 of `profiles/rapid_research.json` from `"concurrency": 4,` to `"concurrency": 1,` (the engine ignores it either way).

  **Done when**: Verify prints `schema OK`; the existing CI step "Profile Schema Validation" still passes (`python3 -c "import json;json.load(open('profiles/schema.json'))"` exits 0).

  **Do not**: remove `concurrency` (existing profiles reference it); do not add `additionalProperties:false` to nested objects; do not edit `web/index.html` `BUILTIN_PROFILES` (owned by `web_console_security_20260905`).

## Phase 4 — Crawler (`web/lib/core_crawler.js`)

- [x] **T7 Canonicalization fidelity** *(AC10)*

  **Files**: `web/lib/core_crawler.js` only.

  **Change**:
  1. Lines 24–28: remove `'ref', 'source',` from `TRACKING_PARAMS` so the set reads:
     ```js
       const TRACKING_PARAMS = new Set([
         'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
         'fbclid', 'gclid', 'session_id', 'jsessionid', 'phpsessid',
         '_ga', '_gl', 'msclkid', 'mc_cid', 'mc_eid'
       ]);
     ```
  2. Replace lines 101–105:
     ```js
             let normalized = u.toString();
             if (normalized.endsWith('/') && u.pathname !== '/') {
               normalized = normalized.slice(0, -1);
             }
             return normalized;
     ```
     with `        return u.toString(); // trailing slash preserved: /docs/ and /docs may be different resources (D10)`.

  **Verify**:
  ```
  node -e "global.PolitenessEngine=require('./web/lib/politeness_engine.js');global.WarcWriter=require('./web/lib/warc_writer.js');global.SelfReflectionEngine=require('./web/lib/self_reflection.js');const C=require('./web/lib/core_crawler.js');const c=new C({target:{allowed_domains:['example.org']}});console.log(c.canonicalizeUrl('https://Example.org/docs/?ref=nav&utm_x=1&b=2'));console.log(c.canonicalizeUrl('https://example.org:443/a#frag'))"
  ```
  Expected: `https://example.org/docs/?b=2&ref=nav` then `https://example.org/a`.

  **Done when**: Verify matches.

  **Do not**: change `isUrlInScope` or `isAssetUrl`; do not touch `warc_reader.js` `normalizeUrl` (viewer lookup is tolerant of the slash by design).

- [x] **T8 Requisite extraction (DOMParser with regex fallback)** *(AC9)*

  **Files**: `web/lib/core_crawler.js` only. Requires T7 (expected URLs below assume the trailing slash is kept).

  **Change**:
  1. Add a method before `extractLinks` (line 320):
     ```js
         /**
          * Collects raw candidate URLs (anchors + page requisites) from HTML (D9).
          * Uses DOMParser in browsers; falls back to a tolerant regex (handles unquoted values).
          */
         collectCandidateUrls(html) {
           const out = [];
           const pushSrcset = (value) => {
             for (const part of String(value || '').split(',')) {
               const candidate = part.trim().split(/\s+/)[0];
               if (candidate) out.push(candidate);
             }
           };
           if (typeof DOMParser !== 'undefined') {
             const doc = new DOMParser().parseFromString(html, 'text/html');
             doc.querySelectorAll('a[href], link[href], area[href]').forEach(el => out.push(el.getAttribute('href')));
             doc.querySelectorAll('img[src], script[src], iframe[src], source[src], video[src], audio[src]')
               .forEach(el => out.push(el.getAttribute('src')));
             doc.querySelectorAll('img[srcset], source[srcset]').forEach(el => pushSrcset(el.getAttribute('srcset')));
             return out;
           }
           const attrRegex = /<(?:a|link|area|img|script|iframe|source|video|audio)\b[^>]*?\s(?:href|src)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))/gi;
           let m;
           while ((m = attrRegex.exec(html)) !== null) out.push(m[1] || m[2] || m[3]);
           const srcsetRegex = /\ssrcset\s*=\s*(?:"([^"]*)"|'([^']*)')/gi;
           while ((m = srcsetRegex.exec(html)) !== null) pushSrcset(m[1] || m[2]);
           return out;
         }
     ```
  2. Replace the head of `extractLinks` (lines 321–327):
     ```js
           const linkRegex = /<a\s+(?:[^>]*?\s+)?href=["']([^"']+)["']/gi;
           let match;
           while ((match = linkRegex.exec(html)) !== null) {
             const rawHref = match[1].trim();
             if (!rawHref || rawHref.startsWith('#') || rawHref.startsWith('javascript:') || rawHref.startsWith('mailto:')) {
               continue;
             }
     ```
     with:
     ```js
           for (const candidate of this.collectCandidateUrls(html)) {
             const rawHref = String(candidate || '').trim();
             if (!rawHref || /^(#|javascript:|mailto:|tel:|data:|blob:)/i.test(rawHref)) {
               continue;
             }
     ```
     The remainder of the loop body (canonicalize, scope check, de-duplicate, push with `tier` and `nextDepth`) is unchanged; requisites therefore keep the parent's tier and get `depth + 1`.

  **Verify**:
  ```
  node -e "global.PolitenessEngine=require('./web/lib/politeness_engine.js');global.WarcWriter=require('./web/lib/warc_writer.js');global.SelfReflectionEngine=require('./web/lib/self_reflection.js');const C=require('./web/lib/core_crawler.js');const c=new C({target:{allowed_domains:['h.test']}});c.extractLinks('<a href=/p1>x</a><link rel=stylesheet href=\"/s.css\"><img src=\"/i.png\" srcset=\"/i2.png 2x, /i3.png 3x\"><script src=/j.js></script><iframe src=\"/f.html\"></iframe><a href=\"mailto:a@b.test\">m</a><a href=\"#top\">t</a>','http://h.test/',1,2);console.log(c.queue.map(q=>q.url).sort().join(' '));console.log(c.queue.every(q=>q.tier===2&&q.depth===1))"
  ```
  Expected: `http://h.test/f.html http://h.test/i.png http://h.test/i2.png http://h.test/i3.png http://h.test/j.js http://h.test/p1 http://h.test/s.css` then `true`.

  **Done when**: Verify matches (7 URLs, in that order).

  **Do not**: introduce a separate "requisite tier"; do not count requisites differently toward `max_pages`; do not fetch anything in `extractLinks`.

- [x] **T9 robots.txt policy** *(AC8)*

  **Files**: `web/lib/core_crawler.js` only (schema property added in T6). Requires T4 (uses `gate.aborted`) and T5.

  **Change**:
  1. In the constructor after `this.maxRetries = 3;` (added in T3) add:
     ```js
           // robots.txt (D8): 'respect' (default) or 'ignore_authorised'
           this.robotsPolicy = (profile.politeness && profile.politeness.robots_policy) || 'respect';
           this.agentToken = 'aegisarchive';
           this.robotsRules = new Map(); // origin -> array of Disallow prefixes
     ```
  2. In `start()`, directly after the `this.callbacks.onLog(\`[AegisArchive] Engine started. ...\`);` line (193) add:
     ```js
           if (this.robotsPolicy === 'ignore_authorised' && !this.robotsPolicyLogged) {
             this.robotsPolicyLogged = true;
             this.auditLedger.push({ url: 'robots_policy', status: -1, mimeType: 'robots_policy', latency_ms: 0, size_bytes: 0, robots_policy: this.robotsPolicy, timestamp: new Date().toISOString() });
             this.callbacks.onLog('[Robots] Policy ignore_authorised: robots.txt is NOT consulted. Operator asserts authorisation for these targets.');
           }
     ```
  3. In `processUrl`, after the `if (gate.aborted) return;` line (added in T4) insert:
     ```js
           if (!(await this.isAllowedByRobots(url))) {
             this.auditLedger.push({ url, status: -1, mimeType: 'robots_disallow', latency_ms: 0, size_bytes: 0, timestamp: new Date().toISOString() });
             this.callbacks.onLog(`[Robots] Skipped (Disallow): ${url}`);
             return;
           }
     ```
     (placing the check after `acquirePermission` keeps every network request, including robots.txt, behind the politeness gate).
  4. Add three methods before `requeueForRetry`:
     ```js
         parseRobotsTxt(text) {
           const star = [], agent = [];
           let current = null, agentSeen = false;
           for (const rawLine of String(text).split(/\r?\n/)) {
             const line = rawLine.split('#')[0].trim();
             const idx = line.indexOf(':');
             if (idx === -1) continue;
             const field = line.slice(0, idx).trim().toLowerCase();
             const value = line.slice(idx + 1).trim();
             if (field === 'user-agent') {
               const ua = value.toLowerCase();
               if (ua === '*') current = star;
               else if (ua.includes(this.agentToken)) { current = agent; agentSeen = true; }
               else current = null;
             } else if (field === 'disallow' && current && value) {
               current.push(value);
             }
           }
           return agentSeen ? agent : star;
         }

         isPathDisallowed(urlStr, rules) {
           const u = new URL(urlStr);
           const path = u.pathname + u.search;
           return rules.some(rule => {
             const pattern = rule.split('*').map(s => s.replace(/[.+?^${}()|[\]\\]/g, '\\$&')).join('.*');
             return new RegExp('^' + pattern).test(path);
           });
         }

         async isAllowedByRobots(urlStr) {
           if (this.robotsPolicy !== 'respect') return true;
           const origin = new URL(urlStr).origin;
           if (!this.robotsRules.has(origin)) {
             this.robotsRules.set(origin, []); // reserve first: a failed fetch is never retried
             const robotsUrl = origin + '/robots.txt';
             const gate = await this.politeness.acquirePermission(robotsUrl);
             if (gate.aborted) return true;
             let status = 0, rules = [];
             try {
               const resp = await fetch(robotsUrl, { method: 'GET', headers: { 'X-Preservation-Agent': 'AegisArchive/1.0' }, cache: 'no-store' });
               status = resp.status;
               if (resp.ok) rules = this.parseRobotsTxt(await resp.text());
             } catch (e) { status = 0; }
             this.robotsRules.set(origin, rules);
             this.auditLedger.push({ url: robotsUrl, status, mimeType: 'robots_txt', latency_ms: 0, size_bytes: 0, robots_policy: this.robotsPolicy, disallow_count: rules.length, timestamp: new Date().toISOString() });
             this.callbacks.onLog(`[Robots] ${robotsUrl} -> HTTP ${status}; ${rules.length} Disallow rule(s) honoured.`);
           }
           return !this.isPathDisallowed(urlStr, this.robotsRules.get(origin));
         }
     ```

  **Verify**:
  ```
  node -e "global.PolitenessEngine=require('./web/lib/politeness_engine.js');global.WarcWriter=require('./web/lib/warc_writer.js');global.SelfReflectionEngine=require('./web/lib/self_reflection.js');const C=require('./web/lib/core_crawler.js');const c=new C({target:{allowed_domains:['h.test']},politeness:{min_delay_ms:1,max_delay_ms:2}});const calls=[];global.fetch=async(u)=>{calls.push(u);return {ok:true,status:200,text:async()=>'User-agent: *\nDisallow: /private/\nDisallow: /tmp*\n'}};(async()=>{console.log(await c.isAllowedByRobots('http://h.test/public/a'),await c.isAllowedByRobots('http://h.test/private/x'),await c.isAllowedByRobots('http://h.test/tmpfile'),calls.length,c.auditLedger[0].mimeType,c.auditLedger[0].disallow_count);const d=new C({target:{allowed_domains:['h.test']},politeness:{min_delay_ms:1,max_delay_ms:2,robots_policy:'ignore_authorised'}});console.log(await d.isAllowedByRobots('http://h.test/private/x'),calls.length)})()"
  ```
  Expected: `true false false 1 robots_txt 2` then `true 1`.

  **Done when**: Verify matches; T3/T4/T8 Verify commands still pass.

  **Do not**: fetch robots.txt outside the politeness gate; do not implement `Allow`/`Crawl-delay` (out of scope); do not change the CLI.

## Phase 5 — Tests

- [x] **T10 Tests to add (stdlib only)** *(AC11; regression coverage for AC1–AC10)*

  **Files** (create): `tests/js/politeness_engine.test.js`, `tests/js/core_crawler.test.js`, `tests/test_profile_schema.py`. Create the directories with `mkdir -p tests/js` if absent (other tracks may already have created them; never delete their files).

  **Change**:
  - `tests/js/politeness_engine.test.js` — `const test = require('node:test'); const assert = require('node:assert/strict'); const P = require('../../web/lib/politeness_engine.js');` with tests: (a) warm-up median/drift per T1 Verify values; (b) 404 x3 stays NOMINAL, 503 x3 trips; (c) Retry-After cap `<= cooldown_seconds*10*1000`; (d) `abort()` resolves `acquirePermission` with `aborted === true` in under 1 s; (e) `sleep(1)` resolves `true`.
  - `tests/js/core_crawler.test.js` — set the three globals as in the bootstrap, then tests: (a) `canonicalizeUrl` per T7 Verify; (b) `extractLinks` fixture per T8 Verify yields the 7 URLs; (c) `requeueForRetry` behaviour per T3 Verify with a stubbed `global.fetch`; (d) robots fixture per T9 Verify; (e) `grep`-style assertion that `fs.readFileSync('web/lib/core_crawler.js','utf8').includes("cache: 'no-store'")`.
  - `tests/test_profile_schema.py` — `unittest.TestCase` reproducing the T6 Verify checks (bounds, enum, deprecated flag, `additionalProperties`, every bundled profile within bounds).

  **Verify**:
  ```
  node --test tests/js/ && python3 -m unittest discover -s tests -p 'test_*.py' -v
  ```
  Expected: node reports `# fail 0`; unittest ends with `OK`.

  **Done when**: both commands exit 0 on a clean checkout; tests use only `node:test`, `node:assert`, `fs`, `unittest`, `json`, `glob`.

  **Do not**: add `package.json`, `requirements*.txt` or any test runner; do not edit `.github/workflows/ci.yml` (gate G3, integrator); do not perform network access in tests (stub `global.fetch`).

## Phase 6 — Completion

- [x] **F1** Final validation: all Verify commands of T1–T10; `python3 -m py_compile cli/*.py mcp/server.py`; leak-prevention gate (`grep -rnI -E` pattern from `.github/workflows/ci.yml`) clean. Append a `checkpoint_validated` line to `evidence.jsonl`.
- [x] **F2** Update `metadata.json` (`status`, `updated_at`) and hand the registry update (G2) to the integrator.

## Review Fixes

- [ ] Rev-1 Preserve cancellation and gate every outbound request after robots checks.
  - **Files**: `web/lib/core_crawler.js`, `tests/js/core_crawler.test.js`.
  - **Change**: perform robots checks before the page permission gate; prevent implicit redirects; retain interrupted tasks for resumption; account for robots failures in backoff.
  - **Verify**: `node --test tests/js/core_crawler.test.js`; `python3 scripts/gate.py test`.
  - **Done when**: cancellation sends no subsequent page request and robots/page gate ordering is covered by regression tests.
  - **Do not**: weaken timing or retry thresholds.
