const test = require('node:test');
const assert = require('node:assert/strict');
const WarcWriter = require('../../web/lib/warc_writer.js');
const WarcReader = require('../../web/lib/warc_reader.js');

test('WarcReader parseCdx 11 fields extracts record length and offset (W2, AC2)', async () => {
  const writer = new WarcWriter({ filename: 't.warc' });
  const headers = new Headers({ 'content-type': 'text/plain' });
  await writer.addResponseRecord('http://h.test/', { status: 200, statusText: 'OK', headers }, new TextEncoder().encode('hello'));
  const cdx = writer.getCdxContent();

  const reader = new WarcReader();
  const entries = reader.parseCdx(cdx);
  assert.equal(entries.length, 1);
  const e = entries[0];
  const cdxLineParts = cdx.trim().split('\n')[1].split(/\s+/);
  assert.equal(e.length, parseInt(cdxLineParts[8], 10));
  assert.equal(e.offset, parseInt(cdxLineParts[9], 10));
  assert.equal(e.url, 'http://h.test/');
  assert.equal(e.status, 200);
});

test('WarcReader resolves revisit records end-to-end (W5, AC5)', async () => {
  const writer = new WarcWriter({ filename: 't.warc' });
  const payload = new TextEncoder().encode('x'.repeat(600));
  const makeHeaders = () => ({ status: 200, statusText: 'OK', headers: new Headers({ 'content-type': 'text/plain' }) });

  await writer.addResponseRecord('http://h.test/a', makeHeaders(), payload);
  await writer.addResponseRecord('http://h.test/b', makeHeaders(), payload);

  const blob = await writer.getWarcBlob();
  const buffer = await blob.arrayBuffer();

  const reader = new WarcReader();
  const summary = await reader.loadWarcBuffer(buffer);
  assert.equal(summary.totalRecords, 2);

  const recA = reader.getRecord('http://h.test/a');
  assert.equal(recA.isRevisit, false);
  assert.equal(recA.bodyBytes.length, 600);

  const recB = reader.getRecord('http://h.test/b');
  assert.equal(recB.isRevisit, true);
  assert.equal(recB.bodyBytes.length, 600);
  assert.equal(recB.refersTo, 'http://h.test/a');
  assert.equal(recB.mimeType, 'text/plain');
  assert.equal(recB.unresolved, false);
});

test('reader keeps case-sensitive paths and trailing slashes distinct; resets between files', async () => {
  const writer = new WarcWriter();
  const urls = ['http://h.test/A', 'http://h.test/a', 'http://h.test/a/'];
  for (const url of urls) await writer.addResponseRecord(url, {status: 200, headers: new Headers()}, new TextEncoder().encode(url));
  const reader = new WarcReader();
  const result = await reader.loadWarcBuffer(await (await writer.getWarcBlob()).arrayBuffer());
  assert.equal(result.totalRecords, 3);
  for (const url of urls) assert.equal(new TextDecoder().decode(reader.getRecord(url).bodyBytes), url);
  await reader.loadWarcBuffer(await (await new WarcWriter().getWarcBlob()).arrayBuffer());
  assert.equal(reader.getRecord(urls[0]), null);
});

test('reader stops safely on negative, oversized and truncated record lengths', async () => {
  for (const length of ['-40', '99999999999999999999999', '20']) {
    const reader = new WarcReader();
    const bytes = new TextEncoder().encode(`WARC/1.1\r\nWARC-Type: response\r\nContent-Length: ${length}\r\n\r\nx`);
    const result = await reader.loadWarcBuffer(bytes.buffer);
    assert.equal(result.totalRecords, 0);
    assert.equal(result.warnings.length, 1);
  }
});
