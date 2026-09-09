const test = require('node:test');
const assert = require('node:assert/strict');
const engine = require('../../web/lib/self_reflection.js');
test('five failed attempts never become five saved pages or optimal health', () => {
  const auditLedger = Array.from({length:5}, () => ({url:'https://example.test/',status:0,latency_ms:500}));
  const result = engine.analyze({auditLedger});
  assert.equal(result.summary.totalPagesCrawled,0);
  assert.equal(result.summary.requestAttempts,5);
  assert.equal(result.summary.captureErrors,5);
  assert.match(result.summary.serverHealthVerdict,/Unknown/);
});
test('JSON report preserves failure evidence and strips credentials and query tokens', () => {
  const url = 'https://user:secret@example.test/page?token=secret#secret';
  const report = engine.generateJSONReport({coverage:{counts:{captured:0,failed:1},resources:[{url,state:'failed'}]},auditLedger:[{url,status:0,stage:'archive_write',error_type:'QuotaExceededError'}]}, {route:'browser',authentication:'secret'});
  assert.equal(report.outcome,'failed');
  assert.equal(report.events[0].stage,'archive_write');
  assert.equal(report.events[0].error_type,'QuotaExceededError');
  assert.equal(JSON.stringify(report).includes('secret'),false);
});
global.PolitenessEngine = require('../../web/lib/politeness_engine.js');
global.WarcWriter = require('../../web/lib/warc_writer.js');
global.SelfReflectionEngine = engine;
const CoreCrawler = require('../../web/lib/core_crawler.js');
test('archive errors are attributed to archive_write rather than transport', async () => {
 const crawler = new CoreCrawler({target:{allowed_domains:['example.test'],seed_urls:{tier_1_core:['https://example.test/']}},politeness:{robots_policy:'ignore_authorised'},archival:{enable_opfs_streaming:false}}, {fetchResource:async()=>new Response('page', {headers:{'content-type':'text/html'}})});
 crawler.politeness.acquirePermission = async()=>({aborted:false});
 crawler.requeueForRetry = ()=>{};
 crawler.warc.addResponseRecord = async()=>{throw new DOMException('private detail','QuotaExceededError');};
 await crawler.start();
 assert.equal(crawler.auditLedger.find(x=>x.status===0).stage,'archive_write');
 assert.equal(crawler.auditLedger.find(x=>x.status===0).error_type,'QuotaExceededError');
});

test('saved redirects agree with coverage', () => {
 const report = engine.analyze({auditLedger:[{url:'https://example.test/',status:302,digest:'sha256:test'}]});
 assert.equal(report.summary.totalPagesCrawled,1);
});

test('request rate includes failed retries', () => {
 const result=engine.analyze({auditLedger:[{status:0},{status:0},{status:200,digest:'x',url:'https://example.test/'}],startTime:0,endTime:60000});
 assert.equal(result.summary.crawlRateReqPerMin,3);
});
