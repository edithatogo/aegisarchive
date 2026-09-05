/**
 * AegisArchive - Origin Private File System (OPFS) Streaming Storage Engine
 * 
 * Provides memory-safe disk streaming for large multi-gigabyte archives.
 * Streams chunks directly to disk to prevent browser tab out-of-memory crashes.
 * 
 * Licensed under the Apache License, Version 2.0.
 */
(function (root, factory) {
  if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.OpfsStreamer = factory();
  }
}(typeof self !== 'undefined' ? self : this, function () {

  class OpfsStreamer {
    constructor(filename = 'archive.warc') {
      this.filename = filename;
      this.opfsRoot = null;
      this.fileHandle = null;
      this.writable = null;
      this.totalBytesWritten = 0;
      this.isOpfsSupported = false;
      this.memoryFallbackChunks = [];
    }

    async init() {
      if (typeof navigator !== 'undefined' && navigator.storage && navigator.storage.getDirectory) {
        try {
          this.opfsRoot = await navigator.storage.getDirectory();
          this.fileHandle = await this.opfsRoot.getFileHandle(this.filename, { create: true });
          if (this.fileHandle.createWritable) {
            this.writable = await this.fileHandle.createWritable();
            this.isOpfsSupported = true;
            return true;
          }
        } catch (e) {
          console.warn('[AegisArchive] OPFS unavailable in this environment; using streaming memory fallback:', e);
        }
      }
      this.isOpfsSupported = false;
      return false;
    }

    async writeChunk(uint8Array) {
      this.totalBytesWritten += uint8Array.length;
      if (this.isOpfsSupported && this.writable) {
        await this.writable.write(uint8Array);
      } else {
        this.memoryFallbackChunks.push(uint8Array);
      }
    }

    async close() {
      if (this.isOpfsSupported && this.writable) {
        await this.writable.close();
        this.writable = null;
      }
    }

    async getBlob(contentType = 'application/warc') {
      if (this.isOpfsSupported && this.fileHandle) {
        const file = await this.fileHandle.getFile();
        return file;
      }
      return new Blob(this.memoryFallbackChunks, { type: contentType });
    }

    async exportToUserDirectory(targetDirectoryHandle) {
      await this.close();
      const blob = await this.getBlob();
      if (targetDirectoryHandle && targetDirectoryHandle.getFileHandle) {
        const destFileHandle = await targetDirectoryHandle.getFileHandle(this.filename, { create: true });
        const destWritable = await destFileHandle.createWritable();
        await destWritable.write(blob);
        await destWritable.close();
        return true;
      }
      return false;
    }

    getTotalBytes() {
      return this.totalBytesWritten;
    }
  }

  return OpfsStreamer;
}));
