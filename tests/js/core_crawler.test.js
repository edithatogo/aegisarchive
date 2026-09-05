const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

// Setup UMD globals expected by core_crawler.js
global.PolitenessEngine = require('../../web/lib/politeness_engine.js');
global.WarcWriter = require('../../web/lib/warc_writer.js');
global.SelfReflectionEngine = require('../../web/lib/self_reflection.js');
const CoreCrawler = require('../../web/lib/core_crawler.js');

test('CoreCrawler canonicalizeUrl preserves non-tracking query and trailing slashes (T7, AC10)', () => {
  const crawler = new CoreCrawler({ target: { allowed_domains: ['example.org'] } });
  const u1 = crawler.canonicalizeUrl('https://Example.org/docs/?ref=nav&utm_x=1&b=2');
  assert.equal(u1, 'https://example.org/docs/?b=2&ref=nav');
  const u2 = crawler.canonicalizeUrl('https://example.org:443/a#frag');
  assert.equal(u2, 'https://example.org/a');
});

test('CoreCrawler requisite extraction from HTML elements and srcset (T8, AC9)', () => {
  const crawler = new CoreCrawler({ target: { allowed_domains: ['h.test'] } });
  const htmlFixture = '<a href=/p1>x</a><link rel=stylesheet href="/s.css"><img src="/i.png" srcset="/i2.png 2x, /i3.png 3x"><script src=/j.js></script><iframe src="/f.html"></iframe><a href="mailto:a@b.test">m</a><a href="#top">t</a>';
  crawler.extractLinks(htmlFixture, 'http://h.test/', 1, 2);
  const urls = crawler.queue.map(q => q.url).sort();
  assert.deepEqual(urls, [
    'http://h.test/f.html',
    'http://h.test/i.png',
    'http://h.test/i2.png',
    'http://h.test/i3.png',
    'http://h.test/j.js',
    'http://h.test/p1',
    'http://h.test/s.css'
  ]);
  assert.ok(crawler.queue.every(q => q.tier === 2 && q.depth === 1));
});

test('CoreCrawler requeueForRetry on countable failures (T3, AC3)', async () => {
  const crawler = new CoreCrawler({
    target: { allowed_domains: ['h.test'] },
    politeness: { min_delay_ms: 1, max_delay_ms: 2, robots_policy: 'ignore_authorised' }
  });
  global.fetch = async () => ({ ok: false, status: 503, headers: new Headers() });
  const task = { url: 'http://h.test/a', tier: 1, depth: 0, parentUrl: 'root' };
  crawler.visited.add(task.url);
  await crawler.processUrl(task);

  assert.equal(crawler.queue.length, 1);
  assert.equal(crawler.queue[0].retries, 1);
  assert.equal(crawler.visited.has(task.url), false);

  const reQueued = crawler.requeueForRetry({ url: 'http://h.test/b', retries: 3 });
  assert.equal(reQueued, false);
  assert.equal(crawler.queue.length, 1);
});

test('CoreCrawler robots.txt respect and ignore_authorised policies (T9, AC8)', async () => {
  const calls = [];
  global.fetch = async (u) => {
    calls.push(u);
    return {
      ok: true,
      status: 200,
      text: async () => 'User-agent: *\nDisallow: /private/\nDisallow: /tmp*\n'
    };
  };

  const cRespect = new CoreCrawler({
    target: { allowed_domains: ['h.test'] },
    politeness: { min_delay_ms: 1, max_delay_ms: 2 }
  });
  assert.equal(await cRespect.isAllowedByRobots('http://h.test/public/a'), true);
  assert.equal(await cRespect.isAllowedByRobots('http://h.test/private/x'), false);
  assert.equal(await cRespect.isAllowedByRobots('http://h.test/tmpfile'), false);
  assert.equal(calls.length, 1);
  assert.equal(cRespect.auditLedger[0].mimeType, 'robots_txt');
  assert.equal(cRespect.auditLedger[0].disallow_count, 2);

  const cIgnore = new CoreCrawler({
    target: { allowed_domains: ['h.test'] },
    politeness: { min_delay_ms: 1, max_delay_ms: 2, robots_policy: 'ignore_authorised' }
  });
  assert.equal(await cIgnore.isAllowedByRobots('http://h.test/private/x'), true);
  assert.equal(calls.length, 1); // Not called again
});

test('CoreCrawler origin fetch uses cache: no-store (T5, AC5)', () => {
  const filePath = path.resolve(__dirname, '../../web/lib/core_crawler.js');
  const content = fs.readFileSync(filePath, 'utf8');
  assert.ok(content.includes("cache: 'no-store'"));
});

test('robots request precedes a fresh page gate; redirects cannot bypass it', async () => {
  const c = new CoreCrawler({target: {allowed_domains: ['h.test']}});
  const events = [];
  c.politeness.acquirePermission = async u => { events.push('gate:' + u); return {aborted: false}; };
  global.fetch = async (u, options) => {
    assert.equal(options.redirect, 'manual');
    events.push('fetch:' + u);
    return new Response(u.endsWith('/robots.txt') ? '' : 'hello', {status: 200});
  };
  await c.processUrl({url: 'http://h.test/a', tier: 1, depth: 0});
  assert.deepEqual(events, ['gate:http://h.test/robots.txt', 'fetch:http://h.test/robots.txt', 'gate:http://h.test/a', 'fetch:http://h.test/a']);
});

test('stop during robots gate retains pending task and sends no requests', async () => {
  const c = new CoreCrawler({target: {allowed_domains: ['h.test']}});
  const task = {url: 'http://h.test/a', tier: 1, depth: 0};
  c.visited.add(task.url);
  c.politeness.acquirePermission = async () => { c.stop(); return {aborted: true}; };
  global.fetch = async () => { assert.fail('request sent after stop'); };
  await c.processUrl(task);
  assert.deepEqual(c.queue, [task]);
  assert.equal(c.visited.has(task.url), false);
  assert.equal(c.robotsRules.has('http://h.test'), false);
});

test('unavailable robots policy fails closed and records server backoff', async () => {
  const c = new CoreCrawler({target: {allowed_domains: ['h.test']}});
  c.politeness.acquirePermission = async () => ({aborted: false});
  global.fetch = async () => new Response('', {status: 503, headers: {'Retry-After': '10'}});
  assert.equal(await c.isAllowedByRobots('http://h.test/a'), false);
  assert.equal(c.politeness.consecutiveErrors, 1);
  assert.ok(c.politeness.domainCooldowns.has('h.test'));
});
