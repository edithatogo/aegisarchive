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
const ALPHABET = "abcXYZ019:/?#[]@!$&()*+,;=%._~ -\\<>\"\x27\u00e9\u4e2d\n\t";
const randomString = (max = 48) => {
  const n = Math.floor(rnd() * max);
  let s = "";
  for (let i = 0; i < n; i++) s += ALPHABET[Math.floor(rnd() * ALPHABET.length)];
  return s;
};
const randomBytes = (max = 512) => {
  const n = Math.floor(rnd() * max);
  const u = new Uint8Array(n);
  for (let i = 0; i < n; i++) u[i] = Math.floor(rnd() * 256);
  return u;
};
const profile = { target: { allowed_domains: ["example.com"], seed_urls: ["https://example.com/"] } };

test("canonicalizeUrl never throws and returns string or null", () => {
  const crawler = new CoreCrawler(profile, {});
  for (let i = 0; i < RUNS; i++) {
    const out = crawler.canonicalizeUrl(randomString(), rnd() < 0.5 ? "https://example.com/a/b" : null);
    assert.ok(out === null || typeof out === "string", `run ${i}: ${typeof out}`);
  }
});

test("isUrlInScope never throws and returns boolean", () => {
  const crawler = new CoreCrawler(profile, {});
  for (let i = 0; i < RUNS; i++) {
    const out = crawler.isUrlInScope(rnd() < 0.3 ? "https://example.com/" + randomString() : randomString());
    assert.equal(typeof out, "boolean", `run ${i}`);
  }
});

test("parseRetryAfter returns null/undefined or a non-negative finite ms value", () => {
  const engine = new PolitenessEngine({});
  for (let i = 0; i < RUNS; i++) {
    const out = engine.parseRetryAfter(randomString(20));
    assert.ok(out == null || (Number.isFinite(out) && out >= 0), `run ${i}: ${out}`);
  }
});

test("WarcReader.loadWarcBuffer accepts random bytes without throwing", async () => {
  const header = new TextEncoder().encode("WARC/1.1\r\nWARC-Type: response\r\nContent-Length: ");
  for (let i = 0; i < RUNS; i++) {
    let bytes = randomBytes();
    if (rnd() < 0.5) {
      const len = new TextEncoder().encode(["x", "-5", "999999", "", "1e3"][i % 5] + "\r\n\r\n");
      const merged = new Uint8Array(header.length + len.length + bytes.length);
      merged.set(header); merged.set(len, header.length); merged.set(bytes, header.length + len.length);
      bytes = merged;
    }
    await new WarcReader().loadWarcBuffer(bytes.buffer);
  }
});
