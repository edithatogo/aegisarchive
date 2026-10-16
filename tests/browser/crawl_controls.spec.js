const {test,expect}=require('playwright/test');
const http=require('node:http');
let server,origin,requests;
test.beforeEach(async({context})=>{
  // Ephemeral test origin only; no production/browser-profile permission changes.
  await context.grantPermissions(['local-network-access'],{origin:'http://127.0.0.1:8130'});
});
async function loadCrawler(page) {
  // Isolate crawler/transport acceptance from the console's parallel static-
  // request startup. The existing station can reset cold parallel asset loads.
  await page.route('**/crawl-controls-fixture',route=>route.fulfill({contentType:'text/html',body:'<!doctype html><title>Crawl controls fixture</title>'}));
  await page.goto('/crawl-controls-fixture');
  for(const src of ['warc_writer','politeness_engine','opfs_streamer','self_reflection','mirror_resources','crawl_rules','core_crawler','native_capture']) {
    await page.addScriptTag({url:'/lib/'+src+'.js'});
  }
  expect(await page.evaluate(()=>typeof CoreCrawler)).toBe('function');
}
test.beforeAll(async()=>{
  requests=[];
  server=http.createServer((req,res)=>{
    res.setHeader('Access-Control-Allow-Origin','*');
    res.setHeader('Access-Control-Allow-Headers','X-Preservation-Agent');
    res.setHeader('Access-Control-Expose-Headers','Content-Length,Content-Type');
    if(req.method==='OPTIONS'){res.writeHead(204);res.end();return;}
    requests.push(req.url);
    const body=req.url==='/map.xml'?'<sitemapindex><sitemap><loc>/map.xml</loc></sitemap><sitemap><loc>/next.xml</loc></sitemap></sitemapindex>':
      req.url==='/next.xml'?'<urlset><url><loc>/mapped</loc></url></urlset>':
      req.url==='/only'?'<a href="/never">Never traverse</a>':
      req.url==='/a.pdf'?'synthetic pdf':
      req.url==='/'?'<a href="/deny">Denied</a><a href="/only">Download only</a><a href="/a.pdf">PDF</a>':'<h1>Mapped page</h1>';
    res.writeHead(200,{'Content-Type':req.url.endsWith('.xml')?'application/xml':req.url.endsWith('.pdf')?'application/pdf':'text/html','Content-Length':Buffer.byteLength(body)});
    res.end(body);
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  origin=`http://127.0.0.1:${server.address().port}`;
});
test.afterAll(async()=>{await new Promise(resolve=>server.close(resolve));});
test('desktop native transport enforces metadata rules before returning source bytes',async({page})=>{
  await loadCrawler(page);
  const result=await page.evaluate(async(origin)=>{
    const profile={target:{allowed_domains:['127.0.0.1'],max_pages:10,
      seed_urls:{tier_1_core:[origin+'/a.pdf']},crawl_rules:{version:1,rules:[
        {id:'pdf',match:{mime:'application/pdf'},decision:{download:false}}
      ]}},archival:{enable_opfs_streaming:false},politeness:{robots_policy:'ignore_authorised',min_delay_ms:250,max_delay_ms:250}};
    const session=await NativeCapture.start(profile);
    try {
      const crawler=new CoreCrawler(profile,{fetchResource:(url,options)=>session.fetch(url,options)});
      await crawler.start();
      return (await crawler.getFinalResults()).coverage;
    } finally {await session.close();}
  },origin);
  expect(result.counts).toMatchObject({captured:0,excluded:1,failed:0});
  expect(result.resources[0].rule_id).toBe('pdf');
});
test('browser crawler enforces rules and terminates cyclic sitemaps',async({page})=>{
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await loadCrawler(page);
  expect(errors).toEqual([]);
  expect(await page.evaluate(()=>typeof CoreCrawler)).toBe('function');
  const result=await page.evaluate(async(origin)=>{
    const crawler=new CoreCrawler({target:{allowed_domains:['127.0.0.1'],max_pages:20,max_depth:3,
      seed_urls:{tier_1_core:[origin+'/']},sitemap_seeds:[origin+'/map.xml'],
      crawl_rules:{version:1,rules:[
        {id:'deny',match:{path_prefix:'/deny'},decision:{discover:false}},
        {id:'download-only',match:{path_prefix:'/only'},decision:{traverse:false}},
        {id:'pdf',match:{mime:'application/pdf'},decision:{download:false}}
      ]}},archival:{enable_opfs_streaming:false},politeness:{robots_policy:'ignore_authorised',min_delay_ms:1,max_delay_ms:2}});
    await crawler.start();
    return (await crawler.getFinalResults()).coverage;
  },origin);
  expect(requests).not.toContain('/deny');
  expect(requests).not.toContain('/never');
  expect(requests.filter(x=>x==='/map.xml')).toHaveLength(1);
  expect(requests).toContain('/mapped');
  expect(result.resources.find(x=>x.url===origin+'/a.pdf')).toMatchObject({state:'excluded',rule_id:'pdf'});
  expect(result.counts.captured).toBe(result.resources.filter(x=>x.state==='captured').length);
  expect(result.resources.find(x=>x.url===origin+'/only')).toMatchObject({state:'captured',rule_id:'download-only'});
});
