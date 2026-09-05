const test = require('node:test');
const assert = require('node:assert/strict');
global.PolitenessEngine = require('../../web/lib/politeness_engine.js');
global.WarcWriter = require('../../web/lib/warc_writer.js');
global.OpfsStreamer = require('../../web/lib/opfs_streamer.js');
global.SelfReflectionEngine = require('../../web/lib/self_reflection.js');
const CoreCrawler = require('../../web/lib/core_crawler.js');

test('WarcWriter standalone without streamer produces valid blob (S5, AC5)', async () => {
  const writer = new global.WarcWriter({ filename: 't.warc' });
  const blob = await writer.getWarcBlob();
  assert.equal(blob.size, writer.currentOffset);
  assert.equal(writer.getStats().recordCount, 1);
});

test('WarcWriter attaches OpfsStreamer and flushes in-memory records (S5, AC5)', async () => {
  const streamer = new global.OpfsStreamer('t.warc');
  await streamer.init();

  const writer = new global.WarcWriter({ filename: 't.warc' });
  assert.equal(writer.records.length, 1);
  assert.equal(writer.recordCount, 1);

  await writer.attachStreamer(streamer);
  assert.equal(writer.records.length, 0);
  assert.equal(writer.streamer, streamer);

  const headers = new Headers({ 'content-type': 'text/plain' });
  await writer.addResponseRecord('http://h.test/a', { status: 200, statusText: 'OK', headers }, new TextEncoder().encode('abc'));

  assert.equal(writer.records.length, 0);
  assert.equal(writer.recordCount, 2);

  const blob = await writer.getWarcBlob();
  assert.equal(blob.size, writer.currentOffset);
});

test('CoreCrawler streams records via OpfsStreamer end-to-end (S5, AC5)', async () => {
  const crawler = new CoreCrawler({
    target: {
      allowed_domains: ['h.test'],
      seed_urls: { tier_1_core: ['http://h.test/'] }
    },
    politeness: { min_delay_ms: 1, max_delay_ms: 2 }
  });

  global.fetch = async () => ({
    ok: true,
    status: 200,
    statusText: 'OK',
    headers: new Headers({ 'content-type': 'text/html' }),
    text: async () => '',
    arrayBuffer: async () => new TextEncoder().encode('<p>hi</p>').buffer
  });

  const completePromise = new Promise((resolve) => {
    crawler.callbacks.onComplete = resolve;
  });

  await crawler.start();
  const results = await completePromise;

  assert.equal(crawler.streamerAttached, true);
  assert.equal(results.warcBlob.size, crawler.warc.currentOffset);
  assert.equal(crawler.warc.records.length, 0);
  assert.ok(results.warcStats.recordCount >= 2);
});
