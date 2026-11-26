const { test: base, expect } = require('playwright/test');
const { execFileSync, spawn } = require('node:child_process');
const { once } = require('node:events');
const fs = require('node:fs/promises');
const http = require('node:http');
const os = require('node:os');
const path = require('node:path');

const python = process.env.AEGIS_TEST_PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
const root = path.resolve(__dirname, '../..');

const fixture = String.raw`
from contextlib import closing
import gzip
from pathlib import Path
import sys
from cli.aegis_cli import PythonWarcWriter

target, origin, label = sys.argv[1:]
a = Path(target).with_suffix('') if target.endswith('.gz') else Path(target)
def page(name, body):
    writer.write_response(origin + '/' + name, 200, {'Content-Type':'text/html'}, body.encode())
with closing(PythonWarcWriter(str(a))) as writer:
    page('seed', f'''
      <h1>{label}</h1><link rel="stylesheet" href="saved.css">
      <a href="redirect">Next</a>
      <a href="missing" target="_blank" ping="{origin}/ping">Missing page</a>
      <img src="{origin}/not-captured">
      <meta http-equiv="refresh" content="0;url={origin}/refresh">
      <form action="{origin}/submit"><input name="text"></form>
      <iframe src="{origin}/frame"></iframe>
      <script>document.querySelector('h1').textContent='Script ran';</script>
    ''')
    page('second', '<h1>Second archived page</h1>')
    writer.write_response(origin + '/redirect', 302, {'Location':'/second'}, b'')
    writer.write_response(origin + '/saved.css', 200, {'Content-Type':'text/css'},
                          f'@import "{origin}/remote.css"; h1 {{color:rgb(10,20,30)}}'.encode())
if target.endswith('.gz'):
    Path(target).write_bytes(gzip.compress(a.read_bytes(), mtime=0))
`;

const test = base.extend({
  replay: async ({}, use) => {
    const folder = await fs.mkdtemp(path.join(os.tmpdir(), 'aegis-offline-'));
    const requests = [];
    const source = http.createServer((request, response) => {
      requests.push(request.url);
      response.end('Live fixture');
    });
    await new Promise(resolve => source.listen(0, '127.0.0.1', resolve));
    const origin = 'http://127.0.0.1:' + source.address().port;
    const processes = [];
    async function launch(filename, label) {
      const archive = path.join(folder, filename);
      execFileSync(python, ['-c', fixture, archive, origin, label], {cwd:root, timeout:15000});
      const child = spawn(python, ['-m', 'cli.replay_serve', archive], {cwd:root});
      processes.push(child);
      const closed = once(child, 'exit');
      let stderr = '';
      child.stderr.on('data', bytes => { stderr += bytes; });
      const address = await new Promise((resolve, reject) => {
        let stdout = '';
        child.on('error', reject);
        child.on('exit', code => reject(new Error('Replay server exited ' + code + ': ' + stderr)));
        child.stdout.on('data', bytes => {
          stdout += bytes;
          if (stdout.includes('\n')) resolve(new URL(stdout.trim()));
        });
      });
      return {archive, address, child, closed};
    }
    try {
      await use({launch, requests, origin});
    } finally {
      await Promise.all(processes.map(async child => {
        if (child.exitCode === null && child.signalCode === null) {
          const exit = once(child, 'exit');
          child.kill();
          await exit;
        }
      }));
      await new Promise(resolve => source.close(resolve));
      await fs.rm(folder, {recursive:true, force:true});
    }
  },
});

test('worker replay isolation serves only the selected archive and clears it on stop', async ({page, context, replay}) => {
  const running = await replay.launch('main.warc', 'Saved page');
  const {address} = running;
  const raw = 'http://127.0.0.1:' + address.port + address.pathname;
  expect((await page.request.get(raw + 'archive')).status()).toBe(421);
  expect((await page.request.get(raw + 'unlisted', {headers:{Host:address.host}})).status()).toBe(404);
  expect((await page.request.post(raw + 'stop', {
    headers:{Host:address.host, Origin:replay.origin},
  })).status()).toBe(403);

  const station = await context.newPage();
  await station.goto('/index.html');
  expect(await station.evaluate(() => navigator.serviceWorker.controller)).toBeNull();
  const missingAsset = page.waitForResponse(response => response.url().includes('not-captured') &&
    response.status() === 404 && response.fromServiceWorker());
  await page.goto(address.href);
  const frame = page.frameLocator('#replayFrame');
  const heading = frame.getByRole('heading', {name:'Saved page'});
  await expect(heading).toBeVisible();
  await expect(heading).toHaveCSS('color', 'rgb(10, 20, 30)');
  await missingAsset;
  expect(await page.evaluate(() => navigator.serviceWorker.controller.scriptURL)).toBe(address.href + 'worker.js');
  expect(await station.evaluate(() => navigator.serviceWorker.controller)).toBeNull();
  expect(await page.evaluate(async url => {
    try { await fetch(url); return false; } catch (_) { return true; }
  }, replay.origin + '/attempt')).toBe(true);
  await expect(frame.locator('iframe,script,form')).toHaveCount(0);
  await frame.getByRole('link', {name:'Missing page'}).click();
  await expect(page.getByRole('status')).toContainText('Missing archived resource');
  await frame.getByRole('link', {name:'Next'}).click();
  await expect(frame.getByRole('heading', {name:'Second archived page'})).toBeVisible();
  const secondTab = await context.newPage();
  await secondTab.goto(address.href);
  await expect(secondTab.frameLocator('#replayFrame').getByRole('heading', {name:'Saved page'})).toBeVisible();
  expect(replay.requests).toEqual([]);
  await page.getByRole('button', {name:'Stop replay'}).click();
  await expect(page.getByRole('status')).toContainText('Replay stopped');
  await expect.poll(() => page.evaluate(async () => (await navigator.serviceWorker.getRegistrations()).length)).toBe(0);
  await expect(page.locator('#replayFrame')).toBeHidden();
  await expect(page.locator('#pages option')).toHaveCount(0);
  await expect(secondTab.getByRole('status')).toContainText('Replay stopped');
  await expect(secondTab.locator('#replayFrame')).toBeHidden();
  expect((await running.closed)[0]).toBe(0);
  await station.close();
});

test('worker replay starts on a fresh origin after an unclean exit and keeps the viewer fallback', async ({page, context, replay}) => {
  const ended = await replay.launch('old.warc', 'Old session');
  await page.goto(ended.address.href);
  await expect(page.frameLocator('#replayFrame').getByRole('heading', {name:'Old session'})).toBeVisible();
  ended.child.kill();
  await ended.closed;
  expect(await page.evaluate(async () => (await navigator.serviceWorker.getRegistrations()).length)).toBe(1);

  const next = await replay.launch('fresh.warc.gz', 'New session');
  expect(next.address.origin).not.toBe(ended.address.origin);
  const fresh = await context.newPage();
  await fresh.goto(next.address.href);
  await expect(fresh.frameLocator('#replayFrame').getByRole('heading', {name:'New session'})).toBeVisible();
  expect(await fresh.evaluate(() => navigator.serviceWorker.controller.scriptURL)).toBe(next.address.href + 'worker.js');
  await fresh.getByRole('button', {name:'Stop replay'}).click();
  await expect(fresh.getByRole('status')).toContainText('Replay stopped');

  const fallback = await context.newPage();
  const unsupported = await replay.launch('fallback.warc', 'Fallback viewer');
  await fallback.addInitScript(() => {
    Object.defineProperty(navigator, 'serviceWorker', {value:undefined});
  });
  await fallback.goto(unsupported.address.href);
  await expect(fallback.getByRole('status')).toContainText('Offline WARC Viewer');
  await fallback.goto('/viewer.html');
  await fallback.locator('#warcFileInput').setInputFiles(unsupported.archive);
  await expect(fallback.frameLocator('#replayFrame').getByRole('heading', {name:'Fallback viewer'})).toBeVisible();
  expect(replay.requests).toEqual([]);
});
