/**
 * AegisArchive - Core Archival Crawler & Queue Orchestrator
 * 
 * Standards & Capabilities:
 * - Scoped Multi-Tier Priority Queue (Tier 1 -> Tier 2 -> Tier 3)
 * - URL Canonicalization & Parameter Scrubbing (RFC 3986)
 * - Recursive Directory Cycle Detection & Path Depth Limiting
 * - Politeness & Server Preservation Integration
 * - Forensic ISO 28500 Archiving & Live Audit Ledger
 * - Crash-Safe Session Checkpointing (Pause / Stop / Resume)
 * 
 * Licensed under the Apache License, Version 2.0.
 */
(function (root, factory) {
  if (typeof define === 'function' && define.amd) {
    define(['./mirror_resources'], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory(require('./mirror_resources.js'));
  } else {
    root.CoreCrawler = factory(root.MirrorResources);
  }
}(typeof self !== 'undefined' ? self : this, function (MirrorResources) {

  const TRACKING_PARAMS = new Set([
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'fbclid', 'gclid', 'session_id', 'jsessionid', 'phpsessid',
    '_ga', '_gl', 'msclkid', 'mc_cid', 'mc_eid'
  ]);

  const REQUEST_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8',
    'X-Preservation-Agent': 'AegisArchive/1.0'
  };

  class CoreCrawler {
    constructor(profile = {}, callbacks = {}) {
      this.profile = profile;
      this.callbacks = {
        onLog: callbacks.onLog || (() => {}),
        onProgress: callbacks.onProgress || (() => {}),
        onStatusChange: callbacks.onStatusChange || (() => {}),
        onDocumentFound: callbacks.onDocumentFound || (() => {}),
        onCheckpoint: callbacks.onCheckpoint || (() => {}),
        onComplete: callbacks.onComplete || (() => {})
      };

      // State
      this.isRunning = false;
      this.isPaused = false;
      this.shouldStop = false;
      this.startTime = null;
      this.endTime = null;

      // Queues & Trackers
      this.queue = [];       // [{ url, tier, depth, parentUrl, retries }]
      this.visited = new Set();
      this.documents = [];   // [{ url, title, mimeType, size, hash, date }]
      this.discoveryLimitations = [];
      this.resourceOutcomes = new Map();
      this.auditLedger = []; // [{ url, status, mimeType, latency_ms, size_bytes, timestamp }]

      // Submodules
      this.politeness = new PolitenessEngine(profile.politeness || {});
      this.warc = new WarcWriter({
        prefix: profile.archival ? profile.archival.warc_prefix : 'archive',
        operator: profile.archival ? profile.archival.operator : 'AegisArchive Preservationist',
        organization: profile.archival ? profile.archival.organization : 'Public Preservation',
        deduplicate: profile.archival ? profile.archival.deduplicate_payloads : true
      });
      const wantsOpfs = !profile.archival || profile.archival.enable_opfs_streaming !== false;
      this.streamer = (wantsOpfs && typeof OpfsStreamer !== 'undefined') ? new OpfsStreamer(this.warc.filename) : null;
      this.streamerAttached = false;

      // Config shortcuts
      this.targetConfig = profile.target || {};
      this.allowedDomains = (this.targetConfig.allowed_domains || []).map(d => d.toLowerCase());
      this.assetExtensions = new Set((this.targetConfig.asset_extensions || [
        '.pdf', '.docx', '.xlsx', '.pptx', '.csv', '.zip'
      ]).map(ext => ext.toLowerCase()));
      this.maxDepth = this.targetConfig.max_depth ?? 5;
      this.maxPages = this.targetConfig.max_pages ?? 5000;
      this.maxRetries = 3;

      // robots.txt (D8): 'respect' (default) or 'ignore_authorised'
      this.robotsPolicy = (profile.politeness && profile.politeness.robots_policy) || 'respect';
      this.agentToken = 'aegisarchive';
      this.robotsRules = new Map(); // origin -> array of Disallow prefixes
    }

    /**
     * Canonicalizes URLs, removes fragments, normalizes slashes, scrubs tracking queries.
     */
    canonicalizeUrl(rawUrl, baseUrl = null) {
      try {
        const u = baseUrl ? new URL(rawUrl, baseUrl) : new URL(rawUrl);
        if (u.protocol !== 'http:' && u.protocol !== 'https:') return null;
        if (u.username || u.password) return null;

        // Clean tracking parameters
        const searchParams = new URLSearchParams(u.search);
        const keysToRemove = [];
        for (const key of searchParams.keys()) {
          if (TRACKING_PARAMS.has(key.toLowerCase()) || key.toLowerCase().startsWith('utm_')) {
            keysToRemove.push(key);
          }
        }
        for (const k of keysToRemove) searchParams.delete(k);
        searchParams.sort();

        u.search = searchParams.toString();
        u.hash = '';

        // Lowercase hostname and normalize default ports
        u.hostname = u.hostname.toLowerCase();
        if ((u.protocol === 'http:' && u.port === '80') || (u.protocol === 'https:' && u.port === '443')) {
          u.port = '';
        }

        return u.toString(); // trailing slash preserved: /docs/ and /docs may be different resources (D10)
      } catch (e) {
        return null;
      }
    }

    /**
     * Checks if a URL is within allowed domains and passes path filters.
     */
    isUrlInScope(urlStr) {
      try {
        const u = new URL(urlStr);
        const host = u.hostname.toLowerCase();
        const isInDomain = this.allowedDomains.some(d => host === d || host.endsWith('.' + d));
        if (!isInDomain) return false;

        // Blacklist check
        if (this.targetConfig.path_blacklist_regex) {
          const re = new RegExp(this.targetConfig.path_blacklist_regex, 'i');
          if (re.test(u.pathname)) return false;
        }

        // Whitelist check
        if (this.targetConfig.path_whitelist_regex) {
          const re = new RegExp(this.targetConfig.path_whitelist_regex, 'i');
          if (!re.test(u.pathname)) return false;
        }

        // Directory recurrence check (prevent crawler traps)
        const segments = u.pathname.split('/').filter(Boolean);
        const counts = {};
        for (const seg of segments) {
          counts[seg] = (counts[seg] || 0) + 1;
          if (counts[seg] >= 3) return false; // Repeated path loop detected
        }

        return true;
      } catch (e) {
        return false;
      }
    }

    isAssetUrl(urlStr) {
      try {
        const u = new URL(urlStr);
        const extMatch = u.pathname.match(/\.([a-z0-9]+)$/i);
        if (extMatch) {
          return this.assetExtensions.has('.' + extMatch[1].toLowerCase());
        }
        return false;
      } catch (e) {
        return false;
      }
    }

    /**
     * Seeds initial URLs into priority queue.
     */
    seedQueue() {
      const seeds = this.targetConfig.seed_urls || {};
      const addTier = (urls, tier) => {
        for (const raw of urls || []) {
          this.enqueueReference(raw, null, 0, tier);
        }
      };

      addTier(seeds.tier_1_core, 1);
      addTier(seeds.tier_2_breadth, 2);
      addTier(seeds.tier_3_discovery, 3);
    }

    /**
     * Starts the crawl loop.
     */
    async start() {
      if (this.isRunning) return;
      this.isRunning = true;
      this.isPaused = false;
      this.shouldStop = false;
      this.politeness.resetAbort();
      this.startTime = this.startTime || Date.now();

      if (this.queue.length === 0 && this.visited.size === 0) {
        this.seedQueue();
      }

      if (this.streamer && !this.streamerAttached) {
        const onDisk = await this.streamer.init();
        await this.warc.attachStreamer(this.streamer);
        this.streamerAttached = true;
        this.callbacks.onLog(onDisk ? '[Storage] Streaming WARC records to origin-private file storage.' : '[Storage] OPFS unavailable; streaming to memory chunks.');
      }

      this.callbacks.onLog(`[AegisArchive] Engine started. Seeded ${this.queue.length} target URLs.`);
      if (this.robotsPolicy === 'ignore_authorised' && !this.robotsPolicyLogged) {
        this.robotsPolicyLogged = true;
        this.auditLedger.push({ url: 'robots_policy', status: -1, mimeType: 'robots_policy', latency_ms: 0, size_bytes: 0, robots_policy: this.robotsPolicy, timestamp: new Date().toISOString() });
        this.callbacks.onLog('[Robots] Policy ignore_authorised: robots.txt is NOT consulted. Operator asserts authorisation for these targets.');
      }
      this.callbacks.onStatusChange('RUNNING');

      while (this.isRunning && !this.shouldStop && this.queue.length > 0) {
        if (this.isPaused) {
          this.callbacks.onStatusChange('PAUSED');
          await new Promise(r => setTimeout(r, 500));
          continue;
        }

        if (this.visited.size >= this.maxPages) {
          this.callbacks.onLog(`[AegisArchive] Max page ceiling reached (${this.maxPages}). Halting politely.`);
          break;
        }

        // Sort queue by tier (1 before 2 before 3), then breadth (depth ascending)
        this.queue.sort((a, b) => a.tier - b.tier || a.depth - b.depth);
        const task = this.queue.shift();

        if (this.visited.has(task.url)) continue;
        this.visited.add(task.url);

        await this.processUrl(task);
        this.callbacks.onProgress(this.getProgressStats());
        if (this.visited.size % 10 === 0) this.callbacks.onCheckpoint(this.exportCheckpoint());
      }

      this.isRunning = false;
      this.endTime = Date.now();
      this.callbacks.onStatusChange('STOPPED');
      this.callbacks.onCheckpoint(this.queue.length > 0 ? this.exportCheckpoint() : null);
      this.callbacks.onLog(`[AegisArchive] Run complete. Crawled ${this.visited.size} pages; archived ${this.documents.length} assets.`);
      this.callbacks.onComplete(await this.getFinalResults());
    }

    async processUrl(task) {
      const { url, depth, tier } = task; // task.retries is managed by requeueForRetry

      // Acquire permission from Politeness Engine (applies rate limit, EWMA backoff, Retry-After, circuit tripwire)
      if (!(await this.isAllowedByRobots(url))) {
        if (this.shouldStop || this.politeness.abortController?.signal.aborted) {
          this.visited.delete(url);
          this.queue.unshift(task);
          return;
        }
        this.resourceOutcomes.set(url,{url,state:'excluded',reason:'robots_policy'});
        this.auditLedger.push({ url, status: -1, mimeType: 'robots_disallow', latency_ms: 0, size_bytes: 0, timestamp: new Date().toISOString() });
        this.callbacks.onLog(`[Robots] Skipped (Disallow): ${url}`);
        return;
      }
      const gate = await this.politeness.acquirePermission(url);
      if (gate.aborted || this.shouldStop) {
        this.visited.delete(url);
        this.queue.unshift(task);
        return;
      }
      const reqStartTime = performance.now();

      try {
        const resp = await fetch(url, {
          method: 'GET',
          headers: REQUEST_HEADERS,
          cache: 'no-store',
          redirect: 'manual'
        });

        const reqEndTime = performance.now();
        const latencyMs = Math.round(reqEndTime - reqStartTime);

        if (resp.type === 'opaque' || resp.type === 'opaqueredirect' || resp.status === 0) {
          this.discoveryLimitations.push({source:url, reason:'unreadable_response_or_redirect'});
          this.resourceOutcomes.set(url, {url,state:'unsupported',reason:'unreadable_response_or_redirect'});
          return;
        }
        const isRedirect = [301,302,303,307,308].includes(resp.status);
        if (!resp.ok && !isRedirect) {
          this.resourceOutcomes.set(url,{url,state:'failed',reason:'http_error',status:resp.status});
          const retryAfter = resp.headers.get('retry-after');
          this.politeness.recordFailure(url, resp.status, retryAfter);
          this.auditLedger.push({
            url,
            status: resp.status,
            mimeType: resp.headers.get('content-type') || 'error',
            latency_ms: latencyMs,
            size_bytes: 0,
            timestamp: new Date().toISOString()
          });
          this.callbacks.onLog(`[HTTP ${resp.status}] ${url} (${latencyMs} ms)`);
          if (PolitenessEngine.isCountableFailure(resp.status)) this.requeueForRetry(task);
          return;
        }

        this.politeness.recordSuccess(url, latencyMs);

        const contentType = resp.headers.get('content-type') || '';
        const mime = contentType.split(';')[0].trim().toLowerCase();
        const isHtml = ['text/html','application/xhtml+xml'].includes(mime);
        const isAsset = this.isAssetUrl(url) || !isHtml;

        const arrayBuffer = await resp.arrayBuffer();
        const uint8 = new Uint8Array(arrayBuffer);

        // Append to WARC / CDX writer (with automatic SHA-256 deduplication revisit records)
        const warcResult = await this.warc.addResponseRecord(url, resp, uint8, { request: { method: 'GET', headers: REQUEST_HEADERS } });

        this.resourceOutcomes.set(url,{url,state:'captured',reason:null,status:resp.status,sha256:warcResult.digest,bytes:uint8.length});
        this.auditLedger.push({
          url,
          status: resp.status,
          mimeType: contentType.split(';')[0].trim(),
          latency_ms: latencyMs,
          size_bytes: uint8.length,
          digest: warcResult.digest,
          isRevisit: warcResult.isRevisit,
          timestamp: new Date().toISOString()
        });

        if (isAsset) {
          const title = url.split('/').pop() || 'Asset';
          const docEntry = {
            url,
            title,
            mimeType: contentType.split(';')[0].trim(),
            size: uint8.length,
            hash: warcResult.digest,
            date: new Date().toISOString()
          };
          this.documents.push(docEntry);
          this.callbacks.onDocumentFound(docEntry);
        }

        if (isRedirect) {
          const location = resp.headers.get('location');
          if (location) this.enqueueReference(location, url, depth, tier);
          else this.discoveryLimitations.push({source:url,reason:'redirect_without_location'});
        } else if (isHtml || mime === 'text/css') {
          const charset = /charset\s*=\s*["']?([^;\s"']+)/i.exec(contentType)?.[1] || 'utf-8';
          try {
            const text = new TextDecoder(charset, {fatal:true}).decode(uint8);
            const found = MirrorResources.discover(text, contentType, url);
            this.discoveryLimitations.push(...found.unsupported.map(reason => ({source:url,reason})));
            for (const reference of found.resources) this.enqueueReference(reference.url, url, depth + 1, tier);
          } catch (_) {
            this.discoveryLimitations.push({source:url,reason:'unsupported_or_invalid_charset'});
          }
        }

      } catch (err) {
        this.resourceOutcomes.set(url,{url,state:'failed',reason:'network_or_decode_error'});
        const reqEndTime = performance.now();
        const latencyMs = Math.round(reqEndTime - reqStartTime);
        this.politeness.recordFailure(url, 0, null);
        this.auditLedger.push({
          url,
          status: 0,
          mimeType: 'network_error',
          latency_ms: latencyMs,
          size_bytes: 0,
          timestamp: new Date().toISOString()
        });
        this.callbacks.onLog(`[Network Error] ${url}: ${err.message}`);
        this.requeueForRetry(task);
      }
    }

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
        const parts = rule.split('*');
        if (!path.startsWith(parts[0])) return false;
        let offset = parts[0].length;
        for (const part of parts.slice(1)) {
          const found = path.indexOf(part, offset);
          if (found === -1) return false;
          offset = found + part.length;
        }
        return true;
      });
    }

    async isAllowedByRobots(urlStr) {
      if (this.robotsPolicy !== 'respect') return true;
      const origin = new URL(urlStr).origin;
      if (!this.robotsRules.has(origin)) {
        const robotsUrl = origin + '/robots.txt';
        const gate = await this.politeness.acquirePermission(robotsUrl);
        if (gate.aborted || this.shouldStop) return false;
        let status = 0, rules = [];
        const started = performance.now();
        try {
          const resp = await fetch(robotsUrl, { method: 'GET', headers: { 'X-Preservation-Agent': 'AegisArchive/1.0' }, cache: 'no-store', redirect: 'manual' });
          status = resp.status;
          if (resp.ok) rules = this.parseRobotsTxt(await resp.text());
          if (resp.ok) this.politeness.recordSuccess(robotsUrl, performance.now() - started);
          else this.politeness.recordFailure(robotsUrl, status, resp.headers?.get('retry-after'));
        } catch (e) { status = 0; }
        if (status === 0) this.politeness.recordFailure(robotsUrl, 0);
        // An unavailable robots policy must not silently grant access.
        if (status === 0 || status === 429 || status >= 500 || (status >= 300 && status < 400)) rules = ['/'];
        this.robotsRules.set(origin, rules);
        this.auditLedger.push({ url: robotsUrl, status, mimeType: 'robots_txt', latency_ms: 0, size_bytes: 0, robots_policy: this.robotsPolicy, disallow_count: rules.length, timestamp: new Date().toISOString() });
        this.callbacks.onLog(`[Robots] ${robotsUrl} -> HTTP ${status}; ${rules.length} Disallow rule(s) honoured.`);
      }
      return !this.isPathDisallowed(urlStr, this.robotsRules.get(origin));
    }

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
      this.resourceOutcomes.set(task.url,{url:task.url,state:'pending',reason:'retry'});
      this.queue.push({ ...task, retries });
      this.callbacks.onLog(`[Retry ${retries}/${this.maxRetries}] Re-queued ${task.url}`);
      return true;
    }

    /**
     * Collects raw candidate URLs (anchors + page requisites) from HTML (D9).
     * Uses DOMParser in browsers; falls back to a tolerant regex (handles unquoted values).
     */
    collectCandidateUrls(html) {
      return MirrorResources.discover(html, 'text/html', 'http://discovery.invalid/').resources.map(x => x.url);
    }

    enqueueReference(raw, baseUrl, nextDepth, tier) {
      const url = this.canonicalizeUrl(raw, baseUrl);
      if (!url) {
        this.discoveryLimitations.push({source:baseUrl,reason:'unsupported_seed_or_reference'});
        return;
      }
      if (!this.isUrlInScope(url) || nextDepth > this.maxDepth) {
        if (!this.resourceOutcomes.has(url)) this.resourceOutcomes.set(url,{url,state:'excluded',reason:nextDepth > this.maxDepth ? 'depth_limit' : 'scope'});
        return;
      }
      if (!this.resourceOutcomes.has(url)) this.resourceOutcomes.set(url,{url,state:'pending',reason:null});
      if (!this.visited.has(url) && !this.queue.some(q => q.url === url)) this.queue.push({url,tier,depth:nextDepth,parentUrl:baseUrl});
    }

    extractLinks(html, baseUrl, nextDepth, tier) {
      const found = MirrorResources.discover(html, 'text/html', baseUrl);
      this.discoveryLimitations.push(...found.unsupported.map(reason => ({source:baseUrl,reason})));
      for (const reference of found.resources) this.enqueueReference(reference.url, baseUrl, nextDepth, tier);
    }

    pause() {
      this.isPaused = true;
      this.callbacks.onLog('[AegisArchive] Pause requested. Completing active request before sleeping.');
      this.callbacks.onStatusChange('PAUSED');
      this.callbacks.onCheckpoint(this.exportCheckpoint());
    }

    resume() {
      if (this.isPaused) {
        this.isPaused = false;
        this.callbacks.onLog('[AegisArchive] Resuming operations.');
        this.callbacks.onStatusChange('RUNNING');
      }
    }

    stop() {
      this.shouldStop = true;
      this.isPaused = false;
      this.politeness.abort();
      this.callbacks.onLog('[AegisArchive] Graceful shutdown requested. Preserving all captured records.');
      this.callbacks.onStatusChange('STOPPING');
      this.callbacks.onCheckpoint(this.exportCheckpoint());
    }

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
      if (cp.profile_id !== (this.profile.profile_id || null) || !Array.isArray(cp.visited)) return false;
      if (!cp.queue.every(task => task && typeof task.url === 'string' &&
          this.canonicalizeUrl(task.url) === task.url && this.isUrlInScope(task.url) &&
          Number.isInteger(task.depth) && task.depth >= 0 && Number.isInteger(task.tier) && task.tier >= 1)) return false;
      if (!cp.visited.every(url => typeof url === 'string' && this.isUrlInScope(url))) return false;
      this.discoveryLimitations.push({source:null,reason:'frontier_checkpoint_does_not_restore_archive_bytes'});
      this.queue = cp.queue.slice();
      this.visited = new Set(cp.visited || []);
      return true;
    }

    getProgressStats() {
      return {
        visitedCount: this.visited.size,
        queueLength: this.queue.length,
        documentsFound: this.documents.length,
        auditCount: this.auditLedger.length,
        telemetry: this.politeness.getTelemetry()
      };
    }

    async getFinalResults() {
      const selfReflection = SelfReflectionEngine.analyze({
        auditLedger: this.auditLedger,
        documents: this.documents,
        visited: Array.from(this.visited),
        queue: this.queue,
        startTime: this.startTime,
        endTime: this.endTime
      }, this.profile);

      const warcBlob = await this.warc.getWarcBlob();
      const cdxBlob = this.warc.getCdxBlob();
      const hashBlob = async blob => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', await blob.arrayBuffer())), b => b.toString(16).padStart(2,'0')).join('');
      const resources = [...this.resourceOutcomes.values()].sort((a,b) => a.url.localeCompare(b.url));
      const counts = Object.fromEntries(['captured','excluded','failed','pending','unsupported'].map(state => [state,resources.filter(x => x.state === state).length]));
      const coverage = {schema_version:1,extractor_version:MirrorResources.VERSION,scope:'discovered_static_resource_graph',
        complete:resources.length > 0 && counts.captured === resources.length && this.discoveryLimitations.length === 0,
        counts,discovered:resources.length,resources,limitations:this.discoveryLimitations,robots_policy:this.robotsPolicy,
        archives:{warc:{sha256:await hashBlob(warcBlob)},cdx:{sha256:await hashBlob(cdxBlob)}}};
      return {
        coverage,
        warcBlob,
        cdxBlob,
        cdxText: this.warc.getCdxContent(),
        warcStats: this.warc.getStats(),
        documents: this.documents,
        auditLedger: this.auditLedger,
        selfReflection
      };
    }
  }

  return CoreCrawler;
}));
