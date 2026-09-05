const test = require('node:test');
const assert = require('node:assert/strict');
const WarcWriter = require('../../web/lib/warc_writer.js');
const WarcReader = require('../../web/lib/warc_reader.js');

test('WarcReader replay strips <base> and injects strict CSP (S1, AC1)', async () => {
  const writer = new WarcWriter({ filename: 't.warc' });
  const headers = () => ({ status: 200, statusText: 'OK', headers: new Headers({ 'content-type': 'text/html' }) });
  await writer.addResponseRecord(
    'http://h.test/',
    headers(),
    new TextEncoder().encode('<html><head><base href="http://live.test/"><title>t</title></head><body>x</body></html>')
  );
  const blob = await writer.getWarcBlob();
  const reader = new WarcReader();
  await reader.loadWarcBuffer(await blob.arrayBuffer());

  const out = reader.renderPage('http://h.test/');
  assert.equal(/<base/i.test(out), false);
  assert.equal(out.indexOf(WarcReader.REPLAY_CSP_META), out.indexOf('<head>') + 6);
  assert.ok(out.includes("default-src 'none'"));
});

test('WarcReader rewrites requisites to blob: and inert anchors (S2, AC2)', async () => {
  const writer = new WarcWriter({ filename: 't.warc' });
  const h = (ct) => ({ status: 200, statusText: 'OK', headers: new Headers({ 'content-type': ct }) });
  const enc = (s) => new TextEncoder().encode(s);

  await writer.addResponseRecord(
    'http://h.test/',
    h('text/html'),
    enc('<html><head><link rel="stylesheet" href="/s.css"></head><body><img src="i.png" srcset="i.png 1x"><img src="/missing.png"><a href="/p2">p2</a><script src="/j.js"></script></body></html>')
  );
  await writer.addResponseRecord('http://h.test/s.css', h('text/css'), enc('body{color:red}'));
  await writer.addResponseRecord('http://h.test/i.png', h('image/png'), new Uint8Array([137, 80, 78, 71]));

  const blob = await writer.getWarcBlob();
  const reader = new WarcReader();
  await reader.loadWarcBuffer(await blob.arrayBuffer());

  const out = reader.renderPage('http://h.test/');
  const n = (re) => (out.match(re) || []).length;

  assert.equal(n(/href="blob:/g), 1);
  assert.equal(n(/src="blob:/g), 1);
  assert.equal(n(/src="data:,"/g), 2);
  assert.ok(out.includes('data-archived-href="http://h.test/p2" href="#"'));
  assert.equal(/\ssrcset=/.test(out), false);
  assert.equal(/<base/i.test(out), false);
});
