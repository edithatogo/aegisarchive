const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {createHash} = require('node:crypto');
const fixtureDir = path.join(__dirname, '../fixtures/mirror');
const manifest = JSON.parse(fs.readFileSync(path.join(fixtureDir, 'manifest.json')));
test('frozen resource bytes agree with manifest', () => {
  assert.equal(manifest.resources.length, 9);
  for (const r of manifest.resources) assert.equal(createHash('sha256').update(fs.readFileSync(path.join(fixtureDir, r.file))).digest('hex'), r.sha256);
});

test('HTML discovery parity vectors', () => {
  const {discover} = require('../../web/lib/mirror_resources.js');
  for (const v of JSON.parse(fs.readFileSync(path.join(fixtureDir, 'discovery.json')))) {
    assert.deepEqual(discover(v.text, v.mime, v.url).resources.map(x => x.url), v.expected);
  }
});

global.PolitenessEngine = require('../../web/lib/politeness_engine.js');
global.WarcWriter = require('../../web/lib/warc_writer.js');
global.SelfReflectionEngine = require('../../web/lib/self_reflection.js');
const CoreCrawler = require('../../web/lib/core_crawler.js');
test('browser engine captures the frozen graph including CSS and readable redirects', async () => {
  const original = global.fetch;
  const hits = [];
  const crawler = new CoreCrawler({target:{allowed_domains:['mirror.test'],seed_urls:{tier_1_core:['http://mirror.test/']},max_depth:5},politeness:{robots_policy:'ignore_authorised'},archival:{enable_opfs_streaming:false}});
  crawler.politeness.acquirePermission = async () => ({aborted:false});
  global.fetch = async url => {
    const u = new URL(url); const key = u.pathname + u.search; hits.push(key);
    const r = manifest.resources.find(x => x.path === key);
    if (!r) return new Response('',{status:404});
    const headers = {'content-type':r.mime}; if (r.location) headers.location = r.location;
    return new Response(fs.readFileSync(path.join(fixtureDir,r.file)),{status:r.status,headers});
  };
  try {
    await crawler.start();
    const entries = crawler.auditLedger.filter(x => x.digest);
    assert.deepEqual(Object.fromEntries(entries.map(x => [new URL(x.url).pathname + new URL(x.url).search,x.digest.replace(/^sha256:/,'')])),Object.fromEntries(manifest.resources.map(x => [x.path,x.sha256])));
    assert.equal(hits.length,9);
  } finally {global.fetch = original;}
});

test('coverage distinguishes missing, excluded and opaque resources', async () => {
  const original = global.fetch;
  const crawler = new CoreCrawler({target:{allowed_domains:['mirror.test'],seed_urls:{tier_1_core:['http://mirror.test/']},max_depth:2},politeness:{robots_policy:'ignore_authorised'},archival:{enable_opfs_streaming:false}});
  crawler.politeness.acquirePermission = async () => ({aborted:false});
  global.fetch = async url => {
    if (url.endsWith('/')) return new Response('<img src=/missing><img src=https://outside.invalid/x><a href=/opaque>o</a>',{headers:{'content-type':'text/html'}});
    if (url.endsWith('/opaque')) return {type:'opaqueredirect',status:0};
    return new Response('',{status:404});
  };
  try {
    await crawler.start();
    const r = await crawler.getFinalResults();
    assert.equal(r.coverage.complete,false);
    assert.deepEqual(r.coverage.counts,{captured:1,excluded:1,failed:1,pending:0,unsupported:1});
    assert.equal(r.coverage.archives.warc.sha256,createHash('sha256').update(Buffer.from(await r.warcBlob.arrayBuffer())).digest('hex'));
  } finally {global.fetch = original;}
});

test('no seeds and page ceilings never report complete', async () => {
  const empty = new CoreCrawler({target:{allowed_domains:['mirror.test']},politeness:{robots_policy:'ignore_authorised'}});
  assert.equal((await empty.getFinalResults()).coverage.complete,false);
  empty.enqueueReference('http://mirror.test/a',null,0,1);
  assert.equal((await empty.getFinalResults()).coverage.counts.pending,1);
});
