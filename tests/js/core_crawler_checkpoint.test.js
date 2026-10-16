const test = require('node:test');
const assert = require('node:assert/strict');
global.PolitenessEngine = require('../../web/lib/politeness_engine.js');
global.WarcWriter = require('../../web/lib/warc_writer.js');
global.SelfReflectionEngine = require('../../web/lib/self_reflection.js');
const CoreCrawler = require('../../web/lib/core_crawler.js');

test('durable checkpoints wait for settled tasks and retain writer/frontier state', {timeout:5000}, async () => {
  const profile={profile_id:'durable',target:{allowed_domains:['h.test'],seed_urls:{tier_1_core:['http://h.test/a']}}};
  const stream={isUsb:true,offsets:{warc:0,cdx:0},init:async()=>true,
    writeChunk:async bytes=>{stream.offsets.warc+=bytes.length;}};
  let release, saved;
  const barrier=new Promise(resolve=>{release=resolve;});
  const checkpoints=[];
  const crawler=new CoreCrawler(profile,{streamer:stream,onRecoveryCheckpoint:async state=>{
    checkpoints.push(state);saved=state;await barrier;
  }});
  crawler.processUrl=async task=>{
    assert.throws(()=>crawler.exportRecoveryState(),/active request/);
    await crawler.warc.addResponseRecord(task.url,{status:200,headers:new Headers()},new TextEncoder().encode('retained'));
    crawler.resourceOutcomes.set(task.url,{url:task.url,state:'captured'});
    crawler.documents.push({url:task.url,title:'Retained'});
  };
  crawler.getFinalResults=async()=>({});
  let finished=false;
  let failure;
  const running=crawler.start().then(()=>{finished=true;},error=>{failure=error;finished=true;});
  while(!saved && !finished) await new Promise(resolve=>setImmediate(resolve));
  if(failure) throw failure;
  assert.equal(finished,false);
  assert.equal(saved.version,2);
  assert.equal(saved.writer.currentOffset,stream.offsets.warc);
  assert.deepEqual(saved.frontier.visited,['http://h.test/a']);
  assert.equal(saved.documents[0].title,'Retained');
  const restored=new CoreCrawler(profile,{streamer:stream});
  restored.importRecoveryState(saved);
  assert.deepEqual([...restored.visited],['http://h.test/a']);
  assert.equal(restored.documents[0].title,'Retained');
  assert.equal(restored.resourceOutcomes.get('http://h.test/a').state,'captured');
  assert.equal(restored.streamerAttached,true);
  assert.equal(restored.warc.records.length,0);
  release();await running;
  assert.equal(checkpoints.at(-1),null);
});

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
