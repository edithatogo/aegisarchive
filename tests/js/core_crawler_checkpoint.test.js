const test = require('node:test');
const assert = require('node:assert/strict');
global.PolitenessEngine = require('../../web/lib/politeness_engine.js');
global.WarcWriter = require('../../web/lib/warc_writer.js');
global.SelfReflectionEngine = require('../../web/lib/self_reflection.js');
const CoreCrawler = require('../../web/lib/core_crawler.js');

test('CoreCrawler exportCheckpoint and importCheckpoint round-trip (S6, AC6)', () => {
  let checkpointEmitted = null;
  const c = new CoreCrawler(
    { profile_id: 'p1', target: { allowed_domains: ['h.test'] } },
    { onCheckpoint: (cp) => { checkpointEmitted = cp; } }
  );

  c.queue.push({ url: 'http://h.test/a', tier: 1, depth: 0, parentUrl: 'root' });
  c.visited.add('http://h.test/b');

  const cp = c.exportCheckpoint();
  assert.equal(cp.version, 1);
  assert.equal(cp.profile_id, 'p1');
  assert.equal(cp.queue.length, 1);
  assert.equal(cp.visited.length, 1);

  const d = new CoreCrawler({ profile_id: 'p1', target: { allowed_domains: ['h.test'] } });
  assert.equal(d.importCheckpoint(cp), true);
  assert.equal(d.queue.length, 1);
  assert.ok(d.visited.has('http://h.test/b'));
  assert.equal(d.importCheckpoint({ version: 2 }), false);
  assert.equal(d.importCheckpoint(null), false);
  assert.equal(d.importCheckpoint({ version: 1, queue: 'invalid' }), false);

  c.stop();
  assert.ok(checkpointEmitted !== null);
  assert.equal(checkpointEmitted.queue.length, 1);
});

test('CoreCrawler emits onCheckpoint(null) when queue drains on completion (S6, AC6)', async () => {
  const checkpoints = [];
  const crawler = new CoreCrawler(
    {
      profile_id: 'drain_test',
      target: {
        allowed_domains: ['h.test'],
        seed_urls: { tier_1_core: ['http://h.test/leaf'] }
      },
      politeness: { min_delay_ms: 1, max_delay_ms: 2 }
    },
    {
      onCheckpoint: (cp) => checkpoints.push(cp)
    }
  );

  global.fetch = async () => ({
    ok: true,
    status: 200,
    statusText: 'OK',
    headers: new Headers({ 'content-type': 'text/html' }),
    text: async () => '<html><body>No links here</body></html>',
    arrayBuffer: async () => new TextEncoder().encode('<html><body>No links here</body></html>').buffer
  });

  await crawler.start();

  assert.ok(checkpoints.length >= 1);
  assert.equal(checkpoints[checkpoints.length - 1], null);
});

test('checkpoint cannot inject out-of-scope URLs or a different profile', () => {
  const c = new CoreCrawler({profile_id: 'a', target: {allowed_domains: ['h.test']}});
  const cp = {version: 1, profile_id: 'a', visited: [], queue: [{url: 'http://other.test/', tier: 1, depth: 0}]};
  assert.equal(c.importCheckpoint(cp), false);
  cp.queue[0].url = 'http://h.test/'; cp.profile_id = 'b';
  assert.equal(c.importCheckpoint(cp), false);
});
