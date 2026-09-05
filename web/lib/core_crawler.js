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
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.CoreCrawler = factory();
  }
}(typeof self !== 'undefined' ? self : this, function () {

  const TRACKING_PARAMS = new Set([
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'fbclid', 'gclid', 'ref', 'source', 'session_id', 'jsessionid', 'phpsessid',
    '_ga', '_gl', 'msclkid', 'mc_cid', 'mc_eid'
  ]);

  class CoreCrawler {
    constructor(profile = {}, callbacks = {}) {
      this.profile = profile;
      this.callbacks = {
        onLog: callbacks.onLog || (() => {}),
        onProgress: callbacks.onProgress || (() => {}),
        onStatusChange: callbacks.onStatusChange || (() => {}),
        onDocumentFound: callbacks.onDocumentFound || (() => {}),
        onComplete: callbacks.onComplete || (() => {})
      };

      // State
      this.isRunning = false;
      this.isPaused = false;
      this.shouldStop = false;
      this.startTime = null;
      this.endTime = null;

      // Queues & Trackers
      this.queue = [];       // [{ url, tier, depth, parentUrl }]
      this.visited = new Set();
      this.documents = [];   // [{ url, title, mimeType, size, hash, date }]
      this.auditLedger = []; // [{ url, status, mimeType, latency_ms, size_bytes, timestamp }]

      // Submodules
      this.politeness = new PolitenessEngine(profile.politeness || {});
      this.warc = new WarcWriter({
        prefix: profile.archival ? profile.archival.warc_prefix : 'archive',
        operator: profile.archival ? profile.archival.operator : 'AegisArchive Preservationist',
        organization: profile.archival ? profile.archival.organization : 'Public Preservation',
        deduplicate: profile.archival ? profile.archival.deduplicate_payloads : true
      });

      // Config shortcuts
      this.targetConfig = profile.target || {};
      this.allowedDomains = (this.targetConfig.allowed_domains || []).map(d => d.toLowerCase());
      this.assetExtensions = new Set((this.targetConfig.asset_extensions || [
        '.pdf', '.docx', '.xlsx', '.pptx', '.csv', '.zip'
      ]).map(ext => ext.toLowerCase()));
      this.maxDepth = this.targetConfig.max_depth || 5;
      this.maxPages = this.targetConfig.max_pages || 5000;
    }

    /**
     * Canonicalizes URLs, removes fragments, normalizes slashes, scrubs tracking queries.
     */
    canonicalizeUrl(rawUrl, baseUrl = null) {
      try {
        const u = baseUrl ? new URL(rawUrl, baseUrl) : new URL(rawUrl);
        if (u.protocol !== 'http:' && u.protocol !== 'https:') return null;

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

        let normalized = u.toString();
        if (normalized.endsWith('/') && u.pathname !== '/') {
          normalized = normalized.slice(0, -1);
        }
        return normalized;
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
          const canon = this.canonicalizeUrl(raw);
          if (canon && this.isUrlInScope(canon) && !this.visited.has(canon)) {
            this.queue.push({ url: canon, tier, depth: 0, parentUrl: 'root' });
          }
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
      this.startTime = this.startTime || Date.now();

      if (this.queue.length === 0 && this.visited.size === 0) {
        this.seedQueue();
      }

      this.callbacks.onLog(`[AegisArchive] Engine started. Seeded ${this.queue.length} target URLs.`);
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
      }

      this.isRunning = false;
      this.endTime = Date.now();
      this.callbacks.onStatusChange('STOPPED');
      this.callbacks.onLog(`[AegisArchive] Run complete. Crawled ${this.visited.size} pages; archived ${this.documents.length} assets.`);
      this.callbacks.onComplete(this.getFinalResults());
    }

    async processUrl(task) {
      const { url, depth, tier } = task;

      // Acquire permission from Politeness Engine (applies rate limit, EWMA backoff, Retry-After, circuit tripwire)
      const gate = await this.politeness.acquirePermission(url);
      const reqStartTime = performance.now();

      try {
        const resp = await fetch(url, {
          method: 'GET',
          headers: {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8',
            'X-Preservation-Agent': 'AegisArchive/1.0'
          },
          cache: 'default'
        });

        const reqEndTime = performance.now();
        const latencyMs = Math.round(reqEndTime - reqStartTime);

        if (!resp.ok) {
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
          return;
        }

        this.politeness.recordSuccess(url, latencyMs);

        const contentType = resp.headers.get('content-type') || '';
        const isHtml = contentType.includes('text/html');
        const isAsset = this.isAssetUrl(url) || !isHtml;

        const arrayBuffer = await resp.arrayBuffer();
        const uint8 = new Uint8Array(arrayBuffer);

        // Append to WARC / CDX writer (with automatic SHA-256 deduplication revisit records)
        const warcResult = await this.warc.addResponseRecord(url, resp, uint8);

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

        // If HTML and within depth limit, parse links for BFS
        if (isHtml && depth < this.maxDepth) {
          const htmlText = new TextDecoder('utf-8').decode(uint8);
          this.extractLinks(htmlText, url, depth + 1, tier);
        }

      } catch (err) {
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
      }
    }

    extractLinks(html, baseUrl, nextDepth, tier) {
      const linkRegex = /<a\s+(?:[^>]*?\s+)?href=["']([^"']+)["']/gi;
      let match;
      while ((match = linkRegex.exec(html)) !== null) {
        const rawHref = match[1].trim();
        if (!rawHref || rawHref.startsWith('#') || rawHref.startsWith('javascript:') || rawHref.startsWith('mailto:')) {
          continue;
        }

        const canonical = this.canonicalizeUrl(rawHref, baseUrl);
        if (canonical && this.isUrlInScope(canonical) && !this.visited.has(canonical)) {
          // Avoid duplicate entries in pending queue
          if (!this.queue.some(q => q.url === canonical)) {
            this.queue.push({
              url: canonical,
              tier,
              depth: nextDepth,
              parentUrl: baseUrl
            });
          }
        }
      }
    }

    pause() {
      this.isPaused = true;
      this.callbacks.onLog('[AegisArchive] Pause requested. Completing active request before sleeping.');
      this.callbacks.onStatusChange('PAUSED');
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
      this.callbacks.onLog('[AegisArchive] Graceful shutdown requested. Preserving all captured records.');
      this.callbacks.onStatusChange('STOPPING');
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

    getFinalResults() {
      const selfReflection = SelfReflectionEngine.analyze({
        auditLedger: this.auditLedger,
        documents: this.documents,
        visited: Array.from(this.visited),
        queue: this.queue,
        startTime: this.startTime,
        endTime: this.endTime
      }, this.profile);

      return {
        warcBlob: this.warc.getWarcBlob(),
        cdxBlob: this.warc.getCdxBlob(),
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
