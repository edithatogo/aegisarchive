/**
 * AegisArchive - ISO 28500 WARC/1.1 Archival Writer & CDX-11 Indexer
 * 
 * Standards Compliance:
 * - ISO 28500:2017 (Information and documentation — WARC file format)
 * - CDX 11-Field Index Specification
 * - RFC 3986 (SURT URL canonicalization)
 * - SHA-256 Content-Addressable Deduplication (WARC Revisit Records)
 * 
 * Licensed under the Apache License, Version 2.0.
 */
(function (root, factory) {
  if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.WarcWriter = factory();
  }
}(typeof self !== 'undefined' ? self : this, function () {

  function generateUUID() {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      return crypto.randomUUID();
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }

  function formatWarcDate(date = new Date()) {
    return date.toISOString().replace(/\.\d{3}Z$/, 'Z');
  }

  function formatCdxDate(date = new Date()) {
    const pad = n => String(n).padStart(2, '0');
    return `${date.getUTCFullYear()}${pad(date.getUTCMonth() + 1)}${pad(date.getUTCDate())}${pad(date.getUTCHours())}${pad(date.getUTCMinutes())}${pad(date.getUTCSeconds())}`;
  }

  function toSURT(urlStr) {
    try {
      const u = new URL(urlStr);
      const hostParts = u.hostname.split('.').reverse();
      const port = u.port ? `:${u.port}` : '';
      return `${hostParts.join(',')}${port})${u.pathname}${u.search}`;
    } catch (e) {
      return urlStr;
    }
  }

  async function sha256Hex(uint8Array) {
    if (typeof crypto !== 'undefined' && crypto.subtle && crypto.subtle.digest) {
      const hashBuffer = await crypto.subtle.digest('SHA-256', uint8Array);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    }
    // No silent downgrade: a non-SHA-256 value labelled "sha256:" is a false integrity claim (Dc).
    throw new Error('WebCrypto SHA-256 is unavailable; refusing to write an unverifiable digest');
  }

  class WarcWriter {
    constructor(options = {}) {
      const dateStr = new Date().toISOString().slice(0, 10);
      const prefix = options.prefix || 'aegis_archive';
      this.filename = options.filename || `${prefix}_${dateStr}.warc`;
      this.records = [];
      this.recordCount = 0;
      this.streamer = null; // OpfsStreamer once attached (V5)
      this.cdxLines = [];
      this.currentOffset = 0;
      this.deduplicate = options.deduplicate !== false;
      this.payloadMap = new Map(); // sha256 -> { recordId, url, date }

      // Standard ISO 28500 warcinfo record
      this.addWarcInfoRecord({
        operator: options.operator || 'AegisArchive Preservationist',
        organization: options.organization || 'Public Digital Preservation',
        software: options.software || 'AegisArchive v1.0 (ISO 28500:2017)',
        userAgent: options.userAgent || (typeof navigator !== 'undefined' ? navigator.userAgent : 'AegisArchive/1.0'),
        description: options.description || 'High-fidelity ethical web preservation and server-preserving archive'
      });
    }

    addWarcInfoRecord(info) {
      const recordId = `<urn:uuid:${generateUUID()}>`;
      const date = formatWarcDate();
      const content = [
        `software: ${info.software}`,
        `format: WARC File Format 1.1`,
        `conformance: ISO 28500:2017`,
        `operator: ${info.operator}`,
        `organization: ${info.organization}`,
        `user-agent: ${info.userAgent}`,
        `description: ${info.description}`
      ].join('\r\n') + '\r\n';

      const contentBytes = new TextEncoder().encode(content);
      const headers = [
        `WARC/1.1`,
        `WARC-Type: warcinfo`,
        `WARC-Date: ${date}`,
        `WARC-Filename: ${this.filename}`,
        `WARC-Record-ID: ${recordId}`,
        `Content-Type: application/warc-fields`,
        `Content-Length: ${contentBytes.length}`
      ].join('\r\n') + '\r\n\r\n';

      const headerBytes = new TextEncoder().encode(headers);
      const trailingBytes = new TextEncoder().encode('\r\n\r\n');

      const fullRecord = new Uint8Array(headerBytes.length + contentBytes.length + trailingBytes.length);
      fullRecord.set(headerBytes, 0);
      fullRecord.set(contentBytes, headerBytes.length);
      fullRecord.set(trailingBytes, headerBytes.length + contentBytes.length);

      this.records.push(fullRecord);
      this.recordCount += 1;
      this.currentOffset += fullRecord.length;
    }

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

    /** Writes a synthesised WARC request record (Dg); returns its record id. */
    async addRequestRecord(url, request, concurrentToId, warcDate) {
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
      await this.appendRecord(rec);
      return recordId;
    }

    async addResponseRecord(url, response, payloadUint8Array, options = {}) {
      const recordId = `<urn:uuid:${generateUUID()}>`;
      const dateObj = new Date();
      const warcDate = formatWarcDate(dateObj);
      const cdxDate = formatCdxDate(dateObj);

      const requestRecordId = options.request ? await this.addRequestRecord(url, options.request, recordId, warcDate) : null;
      const concurrentLine = requestRecordId ? [`WARC-Concurrent-To: ${requestRecordId}`] : [];

      const status = response.status || 200;
      const statusText = response.statusText || (status === 200 ? 'OK' : 'Response');
      const contentType = response.headers ? (response.headers.get('content-type') || 'application/octet-stream') : 'application/octet-stream';

      // Compute payload digest
      const payloadDigest = await sha256Hex(payloadUint8Array);
      const formattedDigest = `sha256:${payloadDigest}`;

      // Check for content-addressable deduplication (WARC Revisit Record)
      const existing = this.deduplicate ? this.payloadMap.get(payloadDigest) : null;
      const isRevisit = Boolean(existing && payloadUint8Array.length > 512);

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

      const httpHeaderBytes = new TextEncoder().encode(httpHeaderBlock);

      let recordBytes;
      const recordOffset = this.currentOffset;

      if (isRevisit) {
        // ISO 28500 revisit record (HTTP headers only, no duplicate body)
        const warcHeaders = [
          `WARC/1.1`,
          `WARC-Type: revisit`,
          `WARC-Target-URI: ${url}`,
          `WARC-Date: ${warcDate}`,
          `WARC-Record-ID: ${recordId}`,
          ...concurrentLine,
          `WARC-Refers-To: ${existing.recordId}`,
          `WARC-Refers-To-Target-URI: ${existing.url}`,
          `WARC-Refers-To-Date: ${existing.date}`,
          `WARC-Profile: http://netpreserve.org/warc/1.1/revisit/identical-payload-digest`,
          `WARC-Payload-Digest: ${formattedDigest}`,
          `Content-Type: application/http; msgtype=response`,
          `Content-Length: ${httpHeaderBytes.length}`
        ].join('\r\n') + '\r\n\r\n';

        const warcHeaderBytes = new TextEncoder().encode(warcHeaders);
        const trailingBytes = new TextEncoder().encode('\r\n\r\n');

        recordBytes = new Uint8Array(warcHeaderBytes.length + httpHeaderBytes.length + trailingBytes.length);
        recordBytes.set(warcHeaderBytes, 0);
        recordBytes.set(httpHeaderBytes, warcHeaderBytes.length);
        recordBytes.set(trailingBytes, warcHeaderBytes.length + httpHeaderBytes.length);
      } else {
        // Full response record
        const httpPayloadLength = httpHeaderBytes.length + payloadUint8Array.length;
        const warcHeaders = [
          `WARC/1.1`,
          `WARC-Type: response`,
          `WARC-Target-URI: ${url}`,
          `WARC-Date: ${warcDate}`,
          `WARC-Record-ID: ${recordId}`,
          ...concurrentLine,
          `WARC-Payload-Digest: ${formattedDigest}`,
          `Content-Type: application/http; msgtype=response`,
          `Content-Length: ${httpPayloadLength}`
        ].join('\r\n') + '\r\n\r\n';

        const warcHeaderBytes = new TextEncoder().encode(warcHeaders);
        const trailingBytes = new TextEncoder().encode('\r\n\r\n');

        recordBytes = new Uint8Array(warcHeaderBytes.length + httpPayloadLength + trailingBytes.length);
        let pos = 0;
        recordBytes.set(warcHeaderBytes, pos); pos += warcHeaderBytes.length;
        recordBytes.set(httpHeaderBytes, pos); pos += httpHeaderBytes.length;
        recordBytes.set(payloadUint8Array, pos); pos += payloadUint8Array.length;
        recordBytes.set(trailingBytes, pos);

        // Store in payload map for deduplication
        this.payloadMap.set(payloadDigest, { recordId, url, date: warcDate });
      }

      await this.appendRecord(recordBytes);

      // Generate standard 11-field CDX index entry
      const surt = toSURT(url);
      const cleanMime = (contentType.split(';')[0] || 'application/octet-stream').trim();
      const redirect = '-';
      const robotFlags = '-';
      const cdxLine = `${surt} ${cdxDate} ${url} ${cleanMime} ${status} ${payloadDigest} ${redirect} ${robotFlags} ${recordBytes.length} ${recordOffset} ${this.filename}`;
      this.cdxLines.push(cdxLine);

      return {
        recordId,
        offset: recordOffset,
        length: recordBytes.length,
        digest: payloadDigest,
        isRevisit
      };
    }

    async getWarcBlob() {
      if (this.streamer) {
        await this.streamer.close();
        return this.streamer.getBlob('application/warc');
      }
      return new Blob(this.records, { type: 'application/warc' });
    }

    getCdxContent() {
      const header = ' CDX N b a m s k r M S V g\n';
      return header + this.cdxLines.join('\n') + '\n';
    }

    getCdxBlob() {
      return new Blob([this.getCdxContent()], { type: 'text/plain' });
    }

    getStats() {
      return {
        recordCount: this.recordCount,
        totalBytes: this.currentOffset,
        deduplicatedCount: Array.from(this.payloadMap.keys()).length,
        filename: this.filename
      };
    }
  }

  WarcWriter.sha256Hex = sha256Hex;
  return WarcWriter;
}));
