const { test, expect } = require('playwright/test');
const http = require('node:http');
const fs = require('node:fs/promises');
let source, origin, requests;
test.beforeAll(async () => {
  requests = [];
  source = http.createServer((req, res) => {
    requests.push(req.url);
    if (req.url === '/robots.txt') { res.writeHead(200, {'Content-Type':'text/plain'}); res.end('User-agent: *\nDisallow: /blocked\n'); return; }
    if (req.url === '/protected') { res.writeHead(req.headers.cookie === 'session=synthetic' ? 200 : 401, {'Content-Type':'text/html'}); res.end('<h1>Protected fixture</h1>'); return; }
    if (req.url === '/denied') { res.writeHead(403); res.end('Access denied'); return; }
    if (req.url === '/redirect') { res.writeHead(302, {Location:'/second'}); res.end(); return; }
    if (req.url === '/outside') { res.writeHead(302, {Location:'http://localhost:1/never'}); res.end(); return; }
    if (req.url === '/site.css') { res.writeHead(200, {'Content-Type':'text/css'}); res.end('body{color:rgb(1,2,3)}'); return; }
    if (req.url === '/image.svg') { res.writeHead(200, {'Content-Type':'image/svg+xml'}); res.end('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>'); return; }
    if (req.url === '/document.pdf') { res.writeHead(200, {'Content-Type':'application/pdf'}); res.end('%PDF-1.4\nsynthetic-document\n%%EOF'); return; }
    res.writeHead(200, {'Content-Type':'text/html'});
    res.end(req.url === '/second' ? '<h1>Second page</h1><a href="/third">Third</a>' : req.url === '/third' ? '<h1>Third page</h1><a href="/">Home</a>' : '<h1>Seed page</h1><a href="/redirect">Next</a><link rel="stylesheet" href="/site.css"><img src="/image.svg"><a href="/document.pdf">Document</a>');
  });
  await new Promise(resolve => source.listen(0, '127.0.0.1', resolve));
  origin = `http://127.0.0.1:${source.address().port}`;
});
test.afterAll(async () => { await new Promise(resolve => source.close(resolve)); });
async function setup(page, path='/') {
  await page.goto('/index.html');
  await page.getByRole('button', {name:'⚙️ Configure Profile'}).click();
  await page.locator('#wizMinDelay').fill('1');
  await page.locator('#wizMaxDelay').fill('1');
  await page.locator('#wizMaxRpm').fill('600');
  await page.getByRole('button', {name:'Apply Profile'}).click();
  await page.getByLabel('Quick capture address:').fill(origin + path);
}
test('normal UI captures a multi-page non-CORS site and exports actual responses', async ({page}) => {
  await setup(page);
  await page.getByRole('button', {name:'🚀 Start Harvest'}).click();
  await expect(page.locator('#captureState')).toHaveText('COMPLETE — discovered resources saved');
  await expect(page.locator('#captureOutcome')).toContainText('7 responses saved');
  expect(requests).toEqual(expect.arrayContaining(['/robots.txt','/','/redirect','/second','/third','/site.css','/image.svg','/document.pdf']));
  const downloads=[];page.on('download', d => downloads.push(d));
  await page.getByRole('button', {name:'📦 Download WARC + CDX'}).click();
  await expect.poll(() => downloads.length).toBe(2);
  const warc=downloads.find(d=>d.suggestedFilename().endsWith('.warc'));
  const bytes=await fs.readFile(await warc.path());
  expect(bytes.toString()).toContain('WARC-Type: response');
  expect(bytes.toString()).toContain('Third page');
  expect(bytes.toString()).toContain('synthetic-document');
  const replayRequests=[];
  page.on('request', request => { if (request.url().startsWith(origin)) replayRequests.push(request.url()); });
  await page.goto('/viewer.html');
  await page.locator('#warcFileInput').setInputFiles(await warc.path());
  const frame=page.frameLocator('#replayFrame');
  await expect(frame.getByRole('heading', {name:'Seed page'})).toBeVisible();
  await frame.getByRole('link', {name:'Next'}).click();
  await expect(frame.getByRole('heading', {name:'Second page'})).toBeVisible();
  await frame.getByRole('link', {name:'Third'}).click();
  await expect(frame.getByRole('heading', {name:'Third page'})).toBeVisible();
  expect(replayRequests).toEqual([]);
  const cdx=downloads.find(d=>d.suggestedFilename().endsWith('.cdx'));
  expect((await fs.readFile(await cdx.path(),'utf8')).trim().split('\n').length).toBeGreaterThanOrEqual(7);
});
test('HTTP denial is visibly a failure, not one saved page', async ({page}) => {
  await setup(page,'/denied');
  await page.getByRole('button', {name:'🚀 Start Harvest'}).click();
  await expect(page.locator('#captureState')).toHaveText('FAILED — no responses saved');
  await expect(page.locator('#captureOutcome')).toContainText('0 responses saved; 1 failed');
  await expect(page.locator('#logContainer')).toContainText('HTTP 403');
});
test('robots exclusion is explicit and the authorised option is optional', async ({page}) => {
  await setup(page,'/blocked');
  await page.getByRole('button', {name:'🚀 Start Harvest'}).click();
  await expect(page.locator('#captureState')).toHaveText('FAILED — no responses saved');
  await expect(page.locator('#captureOutcome')).toContainText('1 excluded');
  await page.getByLabel('Robots policy:').selectOption('ignore_authorised');
  await page.getByRole('button', {name:'🚀 Start Harvest'}).click();
  await expect(page.locator('#captureState')).toHaveText('COMPLETE — discovered resources saved');
});

test('explicit imported session is optional and enables a protected fixture', async ({page}) => {
  await setup(page,'/protected');
  await page.getByRole('button', {name:'🚀 Start Harvest'}).click();
  await expect(page.locator('#captureState')).toHaveText('FAILED — no responses saved');
  await expect(page.locator('#logContainer')).toContainText('HTTP 401');
  const profile=require('../../profiles/default_polite.json');
  const configured={...profile,politeness:{...profile.politeness,min_delay_ms:1,max_delay_ms:1,max_requests_per_minute:600},
    authentication:{mode:'browser_session',allowed_domains:['127.0.0.1'],source:JSON.stringify({cookies:[{name:'session',value:'synthetic',domain:'127.0.0.1',path:'/',expires:-1}]})}};
  await page.locator('#profileFileInput').setInputFiles({name:'synthetic-profile.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(configured))});
  await page.getByRole('button', {name:'🚀 Start Harvest'}).click();
  await expect(page.locator('#captureState')).toHaveText('COMPLETE — discovered resources saved');
  await expect(page.locator('#captureOutcome')).toContainText('1 responses saved');
});
