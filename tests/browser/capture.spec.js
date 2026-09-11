const { test, expect } = require('playwright/test');
const http = require('node:http');
const fs = require('node:fs/promises');
let source, origin, requests;
test.beforeAll(async ({browser}) => {
  console.log(JSON.stringify({platform:process.platform, arch:process.arch, browser:browser.version()}));
  requests = [];
  source = http.createServer((req, res) => {
    requests.push(req.url);
    if (req.url === '/') { expect(req.headers.accept).toContain('text/html'); expect(req.headers['x-preservation-agent']).toBe('AegisArchive/1.0'); }
    if (req.url === '/robots.txt') { res.writeHead(200, {'Content-Type':'text/plain'}); res.end('User-agent: *\nDisallow: /blocked\n'); return; }
    if (req.url === '/long') { res.writeHead(200, {'Content-Type':'text/html'}); res.end('<h1>Long fixture</h1>'+Array.from({length:40},(_,i)=>`<a href="/item-${i}">Item ${i}</a>`).join('')); return; }
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
  await page.locator('#wizMinDelay').fill('250');
  await page.locator('#wizMaxDelay').fill('250');
  await page.locator('#wizMaxRpm').fill('300');
  await page.getByRole('button', {name:'Apply Profile'}).click();
  await page.getByLabel('Quick capture address:').fill(origin + path);
}
test('Debug saves audit and native events before completion and survives reload without downloads', async ({page}) => {
  const downloads=[];page.on('download',item=>downloads.push(item));
  await setup(page,'/long');
  await page.getByRole('button',{name:'Debug',exact:true}).click();
  await expect(page.locator('#debugStatus')).toContainText('DEBUG ON');
  const path=await page.evaluate(()=>debugRecorder.path);
  await page.getByRole('button',{name:'🚀 Start Harvest'}).click();
  await expect(page.locator('#telemetryQueue')).not.toHaveText('0');
  await expect.poll(async()=>await fs.readFile(path,'utf8')).toContain('"event": "audit"');
  const live=await fs.readFile(path,'utf8');
  expect(live).toContain('"event": "network_stage"');
  expect(live).toContain('"event": "discovery"');
  expect(live).not.toContain('"event": "capture_complete"');
  await page.getByRole('button',{name:'⏹️ Stop'}).click();
  await expect.poll(async()=>await fs.readFile(path,'utf8')).toContain('"event": "capture_complete"');
  await page.reload();
  await expect(page.locator('#debugStatus')).toContainText(path);
  expect(downloads).toEqual([]);
});

test('Debug storage failures are visible without asking for a download', async ({page}) => {
  await setup(page);
  await page.route('**/__station/capture/debug-events',route=>route.fulfill({status:507,contentType:'application/json',body:JSON.stringify({error:'Synthetic storage failure'})}));
  await page.getByRole('button',{name:/^Debug/}).click();
  await expect(page.locator('#debugStatus')).toContainText('DEBUG SAVE FAILED');
  await expect(page.locator('#debugStatus')).not.toContainText('download');
});
test('normal UI captures a multi-page non-CORS site and exports actual responses', async ({page}) => {
  const downloads = [];
  page.on('download', item => downloads.push(item));
  await page.addInitScript(() => {
    Storage.prototype.setItem = () => { throw Error('Host storage is forbidden'); };
    navigator.storage.getDirectory = () => { throw Error('OPFS is forbidden'); };
  });
  await setup(page);
  await page.getByRole('button', {name:'🚀 Start Harvest'}).click();
  await expect(page.locator('#captureState')).toHaveText('COMPLETE — discovered resources saved');
  await expect(page.locator('#captureOutcome')).toContainText('7 responses saved');
  expect(requests).toEqual(expect.arrayContaining(['/robots.txt','/','/redirect','/second','/third','/site.css','/image.svg','/document.pdf']));
  const receipt = await page.evaluate(() => finalResults.storageReceipt);
  expect(receipt.warc_path).toContain('captures');
  const bytes=await fs.readFile(receipt.warc_path);
  const savedReceipt = JSON.parse(await fs.readFile(receipt.receipt_path, 'utf8'));
  expect(savedReceipt.archives.warc.sha256).toBe(require('node:crypto').createHash('sha256').update(bytes).digest('hex'));
  expect(savedReceipt.complete).toBe(true);
  await page.getByRole('button', {name:'📦 Show saved archive location'}).click();
  expect(downloads).toEqual([]);
  expect(bytes.toString()).toContain('WARC-Type: response');
  expect(bytes.toString()).toContain('WARC-Filename: archive.warc');
  expect(bytes.toString()).toContain('Third page');
  expect(bytes.toString()).toContain('synthetic-document');
  const replayRequests=[];
  page.on('request', request => { if (request.url().startsWith(origin)) replayRequests.push(request.url()); });
  await page.goto('/viewer.html');
  await page.locator('#warcFileInput').setInputFiles(receipt.warc_path);
  const frame=page.frameLocator('#replayFrame');
  await expect(frame.getByRole('heading', {name:'Seed page'})).toBeVisible();
  await frame.getByRole('link', {name:'Next'}).click();
  await expect(frame.getByRole('heading', {name:'Second page'})).toBeVisible();
  await frame.getByRole('link', {name:'Third'}).click();
  await expect(frame.getByRole('heading', {name:'Third page'})).toBeVisible();
  expect(replayRequests).toEqual([]);
  expect((await fs.readFile(receipt.cdx_path,'utf8')).trim().split('\n').length).toBeGreaterThanOrEqual(7);
});
test('HTTP denial is visibly a failure, not one saved page', async ({page}) => {
  await setup(page,'/denied');
  await page.getByRole('button', {name:'🚀 Start Harvest'}).click();
  await expect(page.locator('#captureState')).toHaveText('FAILED — no responses saved');
  await expect(page.locator('#captureOutcome')).toContainText('0 responses saved; 1 failed');
  await expect(page.locator('#logContainer')).toContainText('HTTP 403');
  await page.getByRole('button', {name:'📊 Diagnostic Report'}).click();
  const downloaded = page.waitForEvent('download');
  await page.getByRole('button', {name:'📥 Download JSON diagnostics'}).click();
  const diagnostic = await downloaded;
  expect(diagnostic.suggestedFilename()).toMatch(/\.json$/);
  const report = JSON.parse(await fs.readFile(await diagnostic.path(), 'utf8'));
  expect(report.outcome).toBe('failed');
  expect(report.summary.totalPagesCrawled).toBe(0);
  expect(report.events.some(event => event.status === 403)).toBe(true);
  await expect(page.locator('#logContainer')).toContainText('JSON saved on USB');

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
  const configured={...profile,politeness:{...profile.politeness,min_delay_ms:250,max_delay_ms:250,max_requests_per_minute:300},
    authentication:{mode:'browser_session',allowed_domains:['127.0.0.1'],source:JSON.stringify({cookies:[{name:'session',value:'synthetic',domain:'127.0.0.1',path:'/',expires:-1}]})}};
  await page.locator('#profileFileInput').setInputFiles({name:'synthetic-profile.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(configured))});
  await page.getByRole('button', {name:'🚀 Start Harvest'}).click();
  await expect(page.locator('#captureState')).toHaveText('COMPLETE — discovered resources saved');
  await expect(page.locator('#captureOutcome')).toContainText('1 responses saved');
});

test('pause, resume and stop preserve an explicitly incomplete archive', async ({page}) => {
  await setup(page,'/long');
  await page.getByRole('button', {name:'🚀 Start Harvest'}).click();
  await expect(page.locator('#telemetryQueue')).not.toHaveText('0');
  await page.getByRole('button', {name:'⏸️ Pause'}).click();
  await expect(page.locator('#captureState')).toHaveText('PAUSED — capture held in memory');
  await page.getByRole('button', {name:'▶️ Resume', exact:true}).click();
  await page.getByRole('button', {name:'⏹️ Stop & Finalize'}).click();
  await expect(page.locator('#captureState')).toHaveText('INCOMPLETE — some resources not saved');
  await expect(page.locator('#captureOutcome')).toContainText(/[1-9][0-9]* pending/);
  await expect(page.getByRole('button', {name:'📦 Show saved archive location'})).toBeEnabled();
  expect(await page.evaluate(() => finalResults.storageReceipt.complete)).toBe(false);
});

for (const endpoint of ['archive-chunk', 'archive-finalize']) {
  test(`USB ${endpoint} failure does not claim an archive was saved`, async ({page}) => {
    await setup(page);
    await page.route(`**/__station/capture/${endpoint}`, route => route.fulfill({
      status: 507, contentType: 'application/json',
      body: JSON.stringify({error: 'Synthetic USB write failure', diagnostic: {stage: 'storage', error_type: 'OSError'}})
    }));
    await page.getByRole('button', {name:'🚀 Start Harvest'}).click();
    await expect(page.locator('#captureState')).toHaveText('FAILED — capture interrupted');
    await expect(page.locator('#captureOutcome')).toContainText('USB write failure');
    await expect(page.getByRole('button', {name:'📦 Show saved archive location'})).toBeDisabled();
    expect(await page.evaluate(() => finalResults)).toBeNull();
    await expect(page.locator('#logContainer')).toContainText('JSON saved on USB');
    const report = await page.evaluate(() => JSON.parse(currentReportJSON));
    expect(report.outcome).toBe('failed');
    expect(report.events[0].stage).toBe('storage');
  });
}

test('reload can recover the native session without restarting the launcher', async ({page}) => {
  await setup(page,'/long');
  await page.getByRole('button', {name:'🚀 Start Harvest'}).click();
  await expect(page.locator('#telemetryQueue')).not.toHaveText('0');
  await page.reload();
  await page.getByLabel('Quick capture address:').fill(origin + '/denied');
  await page.getByRole('button', {name:'🚀 Start Harvest'}).click();
  await expect(page.locator('#captureState')).toContainText('FAILED');
  if (await page.locator('#btnRecoverNative').isVisible()) {
    await page.getByRole('button', {name:'Stop previous local capture session'}).click();
    await expect(page.locator('#btnRecoverNative')).toBeHidden();
    await page.getByRole('button', {name:'🚀 Start Harvest'}).click();
  }
  await expect(page.locator('#captureState')).toHaveText('FAILED — no responses saved');
  await expect(page.locator('#logContainer')).toContainText('HTTP 403');
});
