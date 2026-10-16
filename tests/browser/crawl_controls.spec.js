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
function receiptFixture() {
  return {schema_version:1,scope:'discovered_static_resource_graph',scope_hosts:['example.test'],complete:false,
    counts:{captured:2,failed:1,excluded:1,pending:1,unsupported:0},discovered:5,limitations:[],
    archives:{warc:{sha256:'a'.repeat(64),bytes:100},cdx:{sha256:'b'.repeat(64),bytes:20}},
    resources:[
      {url:'https://example.test/',state:'captured',status:200,bytes:3,sha256:'c'.repeat(64),declared_bytes:3},
      {url:'https://example.test/redirect',parentUrl:'https://example.test/',state:'captured',status:302,redirect_to:'https://outside.test/',bytes:3,sha256:'c'.repeat(64)},
      {url:'https://example.test/private',parentUrl:'https://example.test/',state:'failed',status:403,reason:'<img src=x onerror="window.pwned=1">'},
      {url:'https://outside.test/',parentUrl:'https://example.test/redirect',state:'excluded',reason:'scope'},
      {url:'https://example.test/pending',state:'pending',reason:'page_limit'}],
    link_edges:[{source:'https://example.test/',target:'https://example.test/private'},
      {source:'https://example.test/redirect',target:'https://outside.test/'}]};
}
test('report reconciles receipt assertions, escapes source labels and exports a bound report',async({page})=>{
  await page.goto('/reports.html');
  await page.locator('#receiptFile').setInputFiles({name:'capture.coverage.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(receiptFixture()))});
  await expect(page.locator('#summary')).toContainText('2 captured');
  await expect(page.locator('#reportIdentity')).toContainText('not archive verification');
  expect(await page.locator('#resources img').count()).toBe(0);
  expect(await page.evaluate(()=>window.pwned)).toBeUndefined();
  const downloadPromise=page.waitForEvent('download');
  await page.locator('#exportReport').click();
  const download=await downloadPromise;
  const fs=require('node:fs/promises');
  const report=JSON.parse(await fs.readFile(await download.path(),'utf8'));
  expect(report.capture_receipt_sha256).toMatch(/^[a-f0-9]{64}$/);
  expect(report.storage.captured_payload_bytes).toBe(6);
  expect(report.storage.archive_bytes).toBe(120);
  expect(report.failures).toHaveLength(1);
  expect(report.missing_resources).toHaveLength(2);
  expect(report.duplicates).toHaveLength(1);
});
test('receipt tampering is rejected and previews are deterministic without network',async({page})=>{
  await page.goto('/reports.html');
  const validation=await page.evaluate(async receipt=>{
    const valid=await AegisReport.buildReport(receipt);
    let badCount=false,badIdentity=false;
    try {await AegisReport.buildReport({...receipt,discovered:999});} catch(_){badCount=true;}
    try {await AegisReport.buildReport(receipt,'0'.repeat(64));} catch(_){badIdentity=true;}
    return {badCount,badIdentity,identity:valid.capture_receipt_sha256};
  },receiptFixture());
  expect(validation.badCount).toBe(true);expect(validation.badIdentity).toBe(true);
  let requests=0;page.on('request',()=>requests++);
  await page.locator('#rulesInput').fill(JSON.stringify({version:1,rules:[{id:'deny',match:{path_prefix:'/private'},decision:{download:false}}]}));
  await page.locator('#hostsInput').fill('example.test');
  await page.locator('#candidatesInput').fill(JSON.stringify([{url:'https://example.test/private',kind:'page',depth:0}]));
  await page.locator('#previewButton').click();
  const first=await page.locator('#previewOutput').textContent();
  expect(JSON.parse(first)[0].decision.download).toBe(false);
  await page.locator('#previewButton').click();
  expect(await page.locator('#previewOutput').textContent()).toBe(first);
  expect(requests).toBe(0);
});
test('Python and browser reports agree on receipt identity and reconciled data',async({page})=>{
  const receipt=receiptFixture();receipt.notes={'😀':'café 😀','\ue000':'unicode key order'};
  const {execFileSync}=require('node:child_process');
  const expected=JSON.parse(execFileSync(process.env.AEGIS_TEST_PYTHON || 'python3',['-c',
    'import json,sys; from cli.crawl_rules import build_report; print(json.dumps(build_report(json.load(sys.stdin)),ensure_ascii=False))'],{input:JSON.stringify(receipt),encoding:'utf8'}));
  await page.goto('/reports.html');
  expect(await page.evaluate(receipt=>AegisReport.buildReport(receipt),receipt)).toEqual(expected);
});
test('existing fractional timestamp receipts bind exact source JSON bytes',async({page})=>{
  const receipt=receiptFixture();receipt.robots_provenance={fetched_at:1792134000.123456};
  const text=JSON.stringify(receipt,null,2)+'\n';
  const digest=require('node:crypto').createHash('sha256').update(text).digest('hex');
  const {execFileSync}=require('node:child_process');
  const expected=JSON.parse(execFileSync(process.env.AEGIS_TEST_PYTHON || 'python3',['-c',
    'import json,sys; from cli.crawl_rules import build_report; t=sys.stdin.read(); print(json.dumps(build_report(json.loads(t),receipt_text=t)))'],{input:text,encoding:'utf8'}));
  await page.goto('/reports.html');
  const actual=await page.evaluate(({receipt,text})=>AegisReport.buildReport(receipt,null,text),{receipt,text});
  expect(actual).toEqual(expected);expect(actual.capture_receipt_sha256).toBe(digest);
  expect(actual.receipt_identity_format).toBe('source_json_utf8');
});
test('link graphs filter internal/external edges and export inert receipt-bound SVG and JSON',async({page})=>{
  const receipt=receiptFixture();
  const malicious='https://example.test/<svg/onload=alert(1)>';
  receipt.resources[2].url=malicious;receipt.link_edges[0].target=malicious;
  await page.goto('/reports.html');
  await page.locator('#receiptFile').setInputFiles({name:'graph.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(receipt))});
  await expect(page.locator('#summary')).toContainText('2 captured');
  await page.locator('#graphFilter').selectOption('external');
  expect(await page.locator('#graph').textContent()).toContain('outside.test');
  expect(await page.locator('#graph').textContent()).not.toContain('onload');
  await page.locator('#graphFilter').selectOption('internal');
  expect(await page.locator('#graph').textContent()).not.toContain('outside.test');
  const svgDownload=page.waitForEvent('download');await page.locator('#exportGraphSvg').click();
  const fs=require('node:fs/promises');const svg=await fs.readFile(await (await svgDownload).path(),'utf8');
  const parsed=await page.evaluate(svg=>{
    const doc=new DOMParser().parseFromString(svg,'image/svg+xml');
    return {bad:doc.querySelectorAll('parsererror,script,foreignObject,image,a').length,
      events:[...doc.querySelectorAll('*')].flatMap(x=>[...x.attributes]).filter(x=>/^on/i.test(x.name)).length,
      label:doc.documentElement.textContent};
  },svg);
  expect(parsed.bad).toBe(0);expect(parsed.events).toBe(0);expect(parsed.label).toContain(malicious);
  const jsonDownload=page.waitForEvent('download');await page.locator('#exportGraphJson').click();
  const graph=JSON.parse(await fs.readFile(await (await jsonDownload).path(),'utf8'));
  expect(graph.capture_receipt_sha256).toMatch(/^[a-f0-9]{64}$/);
  expect(graph.filter).toBe('internal');expect(graph.edges).toHaveLength(1);
});
test('graph rendering bounds are explicit and unknown scope cannot be classified',async({page})=>{
  await page.goto('/reports.html');
  const result=await page.evaluate(async receipt=>{
    const edges=Array.from({length:501},(_,i)=>({source:receipt.resources[0].url,target:'https://example.test/item-'+i}));
    receipt.link_edges=edges;
    receipt.resources.push(...edges.map(x=>({url:x.target,state:'pending'})));
    receipt.counts.pending+=edges.length;receipt.discovered=receipt.resources.length;
    const report=await AegisReport.buildReport(receipt);
    const graph=AegisReport.graphData(report,'internal'),svg=AegisReport.graphSvg(graph);
    const unknown={...report,receipt:{...report.receipt,scope_hosts:undefined}};
    let denied=false;try{AegisReport.graphData(unknown,'internal');}catch(_){denied=true;}
    return {svg,edgeCount:graph.edges.length,denied};
  },receiptFixture());
  expect(result.edgeCount).toBe(501);expect(result.svg).toContain('500 of 501');expect(result.denied).toBe(true);
});
test('a delayed receipt URL cannot replace a newer local file selection',async({page})=>{
  let release;const pending=new Promise(resolve=>release=resolve);
  const older=receiptFixture();older.notes='older URL receipt';
  await page.route(url=>url.pathname==='/slow-receipt.json',async route=>{await pending;await route.fulfill({json:older});});
  await page.goto('/reports.html?receipt=/slow-receipt.json',{waitUntil:'domcontentloaded'});
  await page.locator('#receiptFile').setInputFiles({name:'new.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(receiptFixture()))});
  await expect(page.locator('#summary')).toContainText('2 captured');
  const identity=await page.locator('#reportIdentity').textContent();
  const response=page.waitForResponse(response=>new URL(response.url()).pathname==='/slow-receipt.json');release();await response;
  await page.evaluate(()=>AegisReport.sourceLoad);
  expect(await page.locator('#reportIdentity').textContent()).toBe(identity);
});
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
