const test = require('node:test');
const assert = require('node:assert/strict');
const {validateRules, evaluateRules, discoverSitemap, scopeHosts} = require('../../web/lib/crawl_rules.js');

global.PolitenessEngine = require('../../web/lib/politeness_engine.js');
global.WarcWriter = require('../../web/lib/warc_writer.js');
global.SelfReflectionEngine = require('../../web/lib/self_reflection.js');
const CoreCrawler = require('../../web/lib/core_crawler.js');
function crawler(rules, fetchResource, extra={}) {
  const c = new CoreCrawler({target:{allowed_domains:['example.test'],crawl_rules:{version:1,rules},...extra},
    archival:{enable_opfs_streaming:false},politeness:{robots_policy:'ignore_authorised'}}, {fetchResource});
  c.politeness.acquirePermission=async()=>({aborted:false});
  return c;
}
test('crawler legacy profile matchers are bounded literal alternatives',()=>{
  assert.throws(()=>crawler([],null,{path_blacklist_regex:'(a+)+$'}));
  const c=crawler([],null,{path_blacklist_regex:'/logout|/signin'});
  assert.equal(c.isUrlInScope('https://example.test/logout'),false);
  assert.equal(c.isUrlInScope('https://example.test/public'),true);
});
test('checkpoint rejects invalid resource kinds before modifying frontier',()=>{
  const c=crawler([],null);
  assert.equal(c.importCheckpoint({version:1,profile_id:null,visited:[],queue:[{url:'https://example.test/a',depth:0,tier:1,kind:'invalid'}]}),false);
  assert.equal(c.queue.length,0);
});
test('browser applies asset-kind rules to extensionless requisites',()=>{
  const c=crawler([{id:'assets',match:{kind:'asset'},decision:{discover:false}}],null);
  c.extractLinks('<img src="/image"><a href="/page">Page</a>','https://example.test/',1,1);
  assert.deepEqual(c.queue.map(x=>x.url),['https://example.test/page']);
  assert.equal(c.resourceOutcomes.get('https://example.test/image').rule_id,'assets');
});
test('browser rejects URL exclusions before fetch and download-only never traverses',async()=>{
  const calls=[];
  const c=crawler([
    {id:'deny',match:{path_prefix:'/deny'},decision:{download:false}},
    {id:'only',match:{path_prefix:'/only'},decision:{traverse:false}}
  ],async url=>{calls.push(url);return new Response('<a href="/child">child</a>',{headers:{'content-type':'text/html'}});});
  await c.processUrl({url:'https://example.test/deny',depth:0,tier:1});
  await c.processUrl({url:'https://example.test/only',depth:0,tier:1});
  assert.deepEqual(calls,['https://example.test/only']);
  assert.equal(c.queue.length,0);
  assert.equal(c.resourceOutcomes.get('https://example.test/deny').rule_id,'deny');
});
test('browser response metadata decisions precede body reads',async()=>{
  let reads=0;
  const c=crawler([{id:'pdf',match:{mime:'application/pdf',min_bytes:10},decision:{download:false}}],async()=>({
    ok:true,status:200,headers:new Headers({'content-type':'application/pdf','content-length':'20'}),
    arrayBuffer:async()=>{reads++;return new ArrayBuffer(20);}
  }));
  await c.processUrl({url:'https://example.test/a.pdf',depth:0,tier:1});
  assert.equal(reads,0);
  assert.equal(c.resourceOutcomes.get('https://example.test/a.pdf').rule_id,'pdf');
  const unknown=crawler([{id:'size',match:{max_bytes:10},decision:{download:true}}],async()=>({
    ok:true,status:200,headers:new Headers({'content-type':'text/plain'}),arrayBuffer:async()=>{reads++;return new ArrayBuffer(0);}
  }));
  await unknown.processUrl({url:'https://example.test/a',depth:0,tier:1});
  assert.equal(reads,0);
  assert.equal(unknown.resourceOutcomes.get('https://example.test/a').reason,'rule_metadata_unavailable');
});
test('browser ambiguous or missing MIME cannot bypass an earlier deny rule',async()=>{
  for(const headers of [{},{'content-type':'text/plain, application/pdf'}]) {
    let reads=0;
    const c=crawler([{id:'pdf',match:{mime:'application/pdf'},decision:{download:false}}],async()=>({
      ok:true,status:200,headers:new Headers(headers),arrayBuffer:async()=>{reads++;return new ArrayBuffer(0);}
    }));
    await c.processUrl({url:'https://example.test/a',depth:0,tier:1});
    assert.equal(reads,0);assert.equal(c.resourceOutcomes.get('https://example.test/a').state,'excluded');
  }
});
test('native before-body denial is not reinterpreted as an empty successful capture',async()=>{
  const c=crawler([{id:'pdf',match:{mime:'application/pdf'},decision:{download:false}}],async()=>{
    const response=new Response('',{headers:{'content-type':'text/plain'}});
    response.aegisRuleDecision={discover:true,download:false,traverse:false,rule_id:'pdf',state:'needs_metadata',missing:['mime']};
    return response;
  });
  await c.processUrl({url:'https://example.test/a',depth:0,tier:1});
  assert.equal(c.resourceOutcomes.get('https://example.test/a').state,'excluded');
  assert.equal(c.auditLedger.length,0);
});
test('browser rule integration preserves aliases, query policy and sitemap cycle bounds',async()=>{
  const c=crawler([],async()=>new Response('<sitemapindex><sitemap><loc>/map.xml</loc></sitemap><sitemap><loc>/next.xml</loc></sitemap></sitemapindex>',{headers:{'content-type':'application/xml'}}),{
    domain_aliases:{'example.test':['assets.test']},sitemap_seeds:['https://example.test/map.xml'],query_policy:'preserve'
  });
  c.seedQueue();
  assert.equal(c.queue[0].kind,'sitemap');
  const task=c.queue.shift(); c.visited.add(task.url); await c.processUrl(task);
  assert.deepEqual(c.queue.map(x=>x.url),['https://example.test/next.xml']);
  assert.equal(c.isUrlInScope('https://assets.test/a'),true);
  assert.equal(c.isUrlInScope('https://unapproved.test/a'),false);
  assert.equal(c.canonicalizeUrl('https://example.test/a?utm_x=1#x'),'https://example.test/a?utm_x=1');
});

test('schema preserves ordered independent decisions', () => {
  const config = {version: 1, rules: [
    {id: 'files', match: {path_prefix: '/files/'}, decision: {download: true, traverse: false}},
    {id: 'rest', match: {}, decision: {discover: false}}
  ]};
  const before = JSON.stringify(config);
  assert.deepEqual(validateRules(config), config);
  assert.equal(JSON.stringify(config), before);
});
test('schema rejects unsafe or ambiguous rules', () => {
  for (const config of [
    {version: true, rules: []}, {version: 1, rules: [], extra: 1},
    ...[{regex: '(a+)+$'}, {max_depth: true}, {host: 'example.test.evil/'},
        {min_bytes: 4097, max_bytes: 4096}, {kind: 'script'}, {path_prefix: '/'+'x'.repeat(2048)}]
      .map(match => ({version: 1, rules: [{id: 'x', match, decision: {download: true}}]})),
    {version: 1, rules: [{id: 'x', match: {}, decision: {download: 1}}]}
  ]) assert.throws(() => validateRules(config));
});
test('schema rejects duplicates and too many rules', () => {
  const rule = {id: 'x', match: {}, decision: {download: true}};
  assert.throws(() => validateRules({version: 1, rules: [rule, rule]}));
  assert.throws(() => validateRules({version: 1, rules: Array.from({length:101}, (_,i)=>({...rule,id:String(i)}))}));
});
const resource = {url:'https://example.test/files/a.pdf',kind:'asset',depth:2};
test('first rule wins but cannot expand caller scope', () => {
  const config={version:1,rules:[
    {id:'files',match:{host:'example.test',path_prefix:'/files/'},decision:{traverse:false}},
    {id:'rest',match:{},decision:{discover:false}}]};
  assert.deepEqual(evaluateRules(config,resource,true),{discover:true,download:true,traverse:false,rule_id:'files',state:'decided',missing:[]});
  assert.equal(evaluateRules(config,resource,false).download,false);
});
test('unknown metadata cannot skip a potential deny', () => {
  const config={version:1,rules:[{id:'large',match:{min_bytes:10,mime:'application/pdf'},decision:{download:false}}]};
  const result=evaluateRules(config,resource,true);
  assert.equal(result.state,'needs_metadata');assert.equal(result.download,false);
  assert.deepEqual(result.missing,['bytes','mime']);
  assert.equal(evaluateRules(config,{...resource,bytes:10,mime:'application/pdf'},true).traverse,false);
  assert.equal(evaluateRules(config,{...resource,bytes:9},true).download,true);
});
test('invalid resources fail closed', () => {
  for(const change of [{url:'file:///tmp/a'},{url:'https://user:secret@example.test/'},{depth:true}])
    assert.throws(()=>evaluateRules({version:1,rules:[]},{...resource,...change},true));
});
test('aliases require explicit in-scope primary hosts',()=>{
  assert.deepEqual(scopeHosts(['example.test'],{'example.test':['assets.test']}),['assets.test','example.test']);
  assert.throws(()=>scopeHosts(['example.test'],{'unapproved.test':['assets.test']}));
});
test('sitemaps preserve scope and terminate cycles',()=>{
  const xml='<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.test/a?x=1&amp;y=2</loc></url><url><loc>https://example.test/a?x=1&amp;y=2</loc></url><url><loc>https://outside.test/a</loc></url></urlset>';
  const result=discoverSitemap(xml,'https://example.test/map.xml',['example.test']);
  assert.deepEqual(result.pages,['https://example.test/a?x=1&y=2']);assert.deepEqual(result.excluded,['https://outside.test/a']);
  const index='<sitemapindex><sitemap><loc>https://example.test/map.xml</loc></sitemap><sitemap><loc>https://example.test/next.xml</loc></sitemap></sitemapindex>';
  assert.deepEqual(discoverSitemap(index,'https://example.test/map.xml',['example.test']).sitemaps,['https://example.test/next.xml']);
  assert.deepEqual(discoverSitemap(index,'https://example.test/map.xml',['example.test'],['https://example.test/map.xml']).sitemaps,[]);
});
test('sitemap XML failures are explicit',()=>{
  for(const xml of ['<!DOCTYPE x [<!ENTITY x "bad">]><urlset/>','<urlset><url></urlset>','<urlset x="1"/>','<urlset><url><loc><![CDATA[/a]]></loc></url></urlset>','<urlset><url><loc>&#1;</loc></url></urlset>','<urlset>'+' '.repeat(262144)+'</urlset>'])
    assert.throws(()=>discoverSitemap(xml,'https://example.test/map.xml',['example.test']));
});

test('sitemap cycle identity ignores default ports and fragments',()=>{
  const xml='<sitemapindex>'+['https://EXAMPLE.test:443/map.xml#self','https://example.test/next.xml#one','https://example.test:443/next.xml#two','https://example.test/Next.xml?q=1'].map(url=>'<sitemap><loc>'+url+'</loc></sitemap>').join('')+'</sitemapindex>';
  assert.deepEqual(discoverSitemap(xml,'https://example.test/map.xml',['example.test']).sitemaps,['https://example.test/next.xml','https://example.test/Next.xml?q=1']);
  assert.deepEqual(discoverSitemap(xml,'https://example.test/map.xml',['example.test'],['https://example.test:443/map.xml#old']).sitemaps,[]);
});
