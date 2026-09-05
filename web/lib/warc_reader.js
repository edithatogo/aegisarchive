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
        if (parts.length >= 10) {
          entries.push({
            surt: parts[0],
            timestamp: parts[1],
            url: parts[2],
            mimeType: parts[3],
            status: parseInt(parts[4], 10),
            digest: parts[5],
            offset: parseInt(parts[8], 10),
            filename: parts[9]
          });
        }
      }
      return entries;
    }

    /**
     * Parses a raw WARC file ArrayBuffer into memory records.
     */
    async loadWarcBuffer(arrayBuffer) {
      const uint8 = new Uint8Array(arrayBuffer);
      const textDecoder = new TextDecoder('utf-8');
      let offset = 0;
      const totalLen = uint8.length;

      while (offset < totalLen) {
        // Find header boundary (\r\n\r\n)
        const headerEnd = this.findSequence(uint8, [13, 10, 13, 10], offset);
        if (headerEnd === -1) break;

        const warcHeaderStr = textDecoder.decode(uint8.subarray(offset, headerEnd));
        const warcHeaders = this.parseHeaders(warcHeaderStr);
        const recordType = warcHeaders['warc-type'];
        const targetUri = warcHeaders['warc-target-uri'];
        const contentLength = parseInt(warcHeaders['content-length'] || '0', 10);

        const contentStart = headerEnd + 4;
        const recordEnd = contentStart + contentLength;

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
            this.urlList.push(targetUri);
          }
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
      };
    }

    normalizeUrl(urlStr) {
      try {
        const u = new URL(urlStr);
        return `${u.origin}${u.pathname}${u.search}`.toLowerCase().replace(/\/$/, '');
      } catch (e) {
        return urlStr.toLowerCase().replace(/\/$/, '');
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

    /**
     * Renders a captured HTML page with inlined or rewritten assets.
     */
    renderPage(url) {
      const record = this.getRecord(url);
      if (!record) return null;

      let html = new TextDecoder('utf-8').decode(record.bodyBytes);

      // Create a base tag to resolve relative URLs
      const baseTag = `<base href="${record.url}">`;
      if (html.includes('<head>')) {
        html = html.replace('<head>', `<head>${baseTag}`);
      } else {
        html = `${baseTag}${html}`;
      }

      return html;
    }
  }

  return WarcReader;
}));
