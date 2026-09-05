/**
 * AegisArchive - In-Browser WARC & CDX Replay Engine
 * 
 * Parses ISO 28500 WARC/1.0 and 1.1 records and CDX index files entirely in-browser.
 * Enables zero-dependency offline browsing and verification of captured archives.
 * 
 * Licensed under the Apache License, Version 2.0.
 */
(function (root, factory) {
  if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.WarcReader = factory();
  }
}(typeof self !== 'undefined' ? self : this, function () {

  class WarcReader {
    constructor() {
      this.recordsByUrl = new Map(); // normalizedUrl -> { url, status, headers, bodyBytes, mimeType }
      this.recordsByDigest = new Map(); // WARC-Payload-Digest -> record
      this.recordsById = new Map();
      this.warcInfo = null;
      this.urlList = [];
    }

    /**
     * Parses a CDX index text file.
     */
    parseCdx(cdxText) {
      const lines = cdxText.split('\n');
      const entries = [];
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith('CDX') || trimmed.startsWith(' ')) continue;
        const parts = trimmed.split(/\s+/);
        if (parts.length >= 11) {
          entries.push({
            surt: parts[0],
            timestamp: parts[1],
            url: parts[2],
            mimeType: parts[3],
            status: parseInt(parts[4], 10),
            digest: parts[5],
            length: parseInt(parts[8], 10),
            offset: parseInt(parts[9], 10),
            filename: parts[10]
          });
        }
      }
      return entries;
    }

    /**
     * Parses a raw WARC file ArrayBuffer into memory records.
     */
    async loadWarcBuffer(arrayBuffer) {
      for (const record of this.recordsByUrl.values()) {
        if (record.blobUrl) URL.revokeObjectURL(record.blobUrl);
      }
      this.recordsByUrl.clear();
      this.recordsByDigest.clear();
      this.recordsById.clear();
      this.urlList = [];
      this.warcInfo = null;
      const warnings = [];
      const uint8 = new Uint8Array(arrayBuffer);
      const textDecoder = new TextDecoder('utf-8');
      let offset = 0;
      const totalLen = uint8.length;

      while (offset < totalLen) {
        // Find header boundary (\r\n\r\n)
        const headerEnd = this.findSequence(uint8, [13, 10, 13, 10], offset);
        if (headerEnd === -1) { warnings.push('Incomplete WARC header'); break; }

        const warcHeaderStr = textDecoder.decode(uint8.subarray(offset, headerEnd));
        const warcHeaders = this.parseHeaders(warcHeaderStr);
        const recordType = warcHeaders['warc-type'];
        const targetUri = warcHeaders['warc-target-uri'];
        const rawLength = warcHeaders['content-length'];
        const contentLength = Number(rawLength);
        if (!/^WARC\/1\.[01]\r\n/.test(warcHeaderStr) || !/^\d+$/.test(rawLength || '') ||
            !Number.isSafeInteger(contentLength) || contentLength < 0) {
          warnings.push('Invalid WARC header or record length'); break;
        }

        const contentStart = headerEnd + 4;
        const recordEnd = contentStart + contentLength;
        if (recordEnd > totalLen || !uint8.subarray(recordEnd, recordEnd + 4).every((b, i) => b === [13, 10, 13, 10][i]) || recordEnd + 4 > totalLen) {
          warnings.push('Truncated WARC record or missing terminator'); break;
        }

        if (recordType === 'warcinfo') {
          this.warcInfo = textDecoder.decode(uint8.subarray(contentStart, recordEnd));
        } else if (recordType === 'response' && targetUri) {
          // Parse HTTP response header block
          const httpHeaderEnd = this.findSequence(uint8, [13, 10, 13, 10], contentStart);
          if (httpHeaderEnd !== -1 && httpHeaderEnd < recordEnd) {
            const httpHeaderStr = textDecoder.decode(uint8.subarray(contentStart, httpHeaderEnd));
            const httpHeaders = this.parseHeaders(httpHeaderStr);
            const statusLine = httpHeaderStr.split('\r\n')[0] || '';
            const statusMatch = statusLine.match(/HTTP\/\S+\s+(\d+)/);
            const status = statusMatch ? parseInt(statusMatch[1], 10) : 200;

            const bodyStart = httpHeaderEnd + 4;
            const bodyBytes = uint8.slice(bodyStart, recordEnd);
            const contentType = httpHeaders['content-type'] || 'application/octet-stream';

            const record = {
              url: targetUri,
              status,
              headers: httpHeaders,
              bodyBytes,
              mimeType: contentType.split(';')[0].trim().toLowerCase()
            };

            this.recordsByUrl.set(this.normalizeUrl(targetUri), record);
            record.isRevisit = false;
            this.recordsById.set(warcHeaders['warc-record-id'], record);
            if (warcHeaders['warc-payload-digest']) this.recordsByDigest.set(warcHeaders['warc-payload-digest'], record);
            this.urlList.push(targetUri);
          }
        } else if (recordType === 'revisit' && targetUri) {
          const http = this.parseHttpBlock(uint8, contentStart, recordEnd, textDecoder);
          const refUri = warcHeaders['warc-refers-to-target-uri'];
          const referred = this.recordsById.get(warcHeaders['warc-refers-to'])
            || this.recordsByDigest.get(warcHeaders['warc-payload-digest'])
            || (refUri && this.recordsByUrl.get(this.normalizeUrl(refUri))) || null;
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
        }

        // Advance to next record (skip trailing \r\n\r\n)
        offset = recordEnd;
        while (offset < totalLen && (uint8[offset] === 13 || uint8[offset] === 10)) {
          offset++;
        }
      }

      return {
        totalRecords: this.recordsByUrl.size,
        warcInfo: this.warcInfo,
        urls: this.urlList
        , warnings
      };
    }

    normalizeUrl(urlStr) {
      try {
        const u = new URL(urlStr);
        return `${u.origin}${u.pathname}${u.search}`;
      } catch (e) {
        return urlStr;
      }
    }

    getRecord(url) {
      return this.recordsByUrl.get(this.normalizeUrl(url)) || null;
    }

    findSequence(uint8, seq, startOffset) {
      const len = uint8.length;
      const seqLen = seq.length;
      for (let i = startOffset; i <= len - seqLen; i++) {
        let match = true;
        for (let j = 0; j < seqLen; j++) {
          if (uint8[i + j] !== seq[j]) {
            match = false;
            break;
          }
        }
        if (match) return i;
      }
      return -1;
    }

    parseHeaders(headerStr) {
      const headers = {};
      const lines = headerStr.split('\r\n');
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const colon = line.indexOf(':');
        if (colon !== -1) {
          const key = line.slice(0, colon).trim().toLowerCase();
          const val = line.slice(colon + 1).trim();
          headers[key] = val;
        }
      }
      return headers;
    }

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

    /**
     * Renders a captured HTML page with inlined or rewritten assets.
     */
    renderPage(url) {
      const record = this.getRecord(url);
      if (!record) return null;

      let html = new TextDecoder('utf-8').decode(record.bodyBytes);

      // Never resolve against the live origin (V2); lock the document down with a CSP (V1).
      html = html.replace(/<base\b[^>]*>/gi, '');
      html = this.rewriteRequisites(html, record.url);
      const csp = WarcReader.REPLAY_CSP_META;
      if (/<head[^>]*>/i.test(html)) {
        html = html.replace(/<head[^>]*>/i, m => m + csp);
      } else {
        html = csp + html;
      }

      return html;
    }
  }

  WarcReader.REPLAY_CSP_META = '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src blob: data:; style-src \'unsafe-inline\' blob:;">';

  return WarcReader;
}));
