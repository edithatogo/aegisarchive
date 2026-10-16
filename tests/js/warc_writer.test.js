const test = require('node:test');
const assert = require('node:assert/strict');
const child_process = require('node:child_process');
const WarcWriter = require('../../web/lib/warc_writer.js');

test('WarcWriter header hygiene strips encoding/framing and updates Content-Length (W1, AC1)', async () => {
  const writer = new WarcWriter({ filename: 't.warc' });
  const payload = new TextEncoder().encode('hello');
  const headers = new Headers({
    'content-encoding': 'gzip',
    'transfer-encoding': 'chunked',
    'content-length': '99',
    'content-type': 'text/plain'
  });
  await writer.addResponseRecord('http://h.test/', { status: 200, statusText: 'OK', headers }, payload);
  const block = Buffer.from(writer.records[1]).toString('latin1');
  assert.equal(block.includes('content-encoding'), false);
  assert.equal(block.includes('transfer-encoding'), false);
  assert.equal(block.includes('Content-Length: 5\r\n'), true);
});

test('WarcWriter CDX 11-field record length field S and offset (W2, AC2)', async () => {
  const writer = new WarcWriter({ filename: 't.warc' });
  const headers = new Headers({ 'content-type': 'text/plain' });
  await writer.addResponseRecord('http://h.test/', { status: 200, statusText: 'OK', headers }, new TextEncoder().encode('hello'));
  const cdx = writer.getCdxContent();
  const lines = cdx.trim().split('\n');
  assert.equal(lines[0].trim(), 'CDX N b a m s k r M S V g');
  const parts = lines[1].split(/\s+/);
  assert.equal(parts.length, 11);
  assert.equal(parts[8], String(writer.records[1].length));
  assert.equal(parts[9], String(writer.records[0].length));
});

test('durable writer restore retains offsets, CDX and deduplication without another warcinfo', async () => {
  const first = new WarcWriter({filename: 'archive.warc'});
  const saved = [];
  const stream = {writeChunk: async bytes => saved.push(Buffer.from(bytes))};
  await first.attachStreamer(stream);
  const payload = new TextEncoder().encode('retained '.repeat(100));
  const response = () => ({status:200, headers:new Headers({'content-type':'text/plain'})});
  await first.addResponseRecord('http://h.test/first', response(), payload);
  const state = first.exportState();
  const prefix = Buffer.concat(saved);
  const resumed = new WarcWriter();
  const suffix = [];
  resumed.restoreState(JSON.parse(JSON.stringify(state)), {
    offsets:{warc:prefix.length,cdx:0}, writeChunk:async bytes => suffix.push(Buffer.from(bytes))
  });
  assert.equal(resumed.currentOffset, prefix.length);
  assert.equal(resumed.getCdxContent(), first.getCdxContent());
  assert.equal(resumed.records.length, 0);
  const record = await resumed.addResponseRecord('http://h.test/second', response(), payload);
  assert.equal(record.isRevisit, true);
  assert.equal(record.offset, prefix.length);
  assert.equal((Buffer.concat([prefix,...suffix]).toString().match(/WARC-Type: warcinfo/g)||[]).length,1);
  assert.throws(() => new WarcWriter().restoreState(state,{offsets:{warc:prefix.length+1,cdx:0}}));
  assert.throws(() => new WarcWriter().restoreState({...state,filename:'../escape.warc'},stream));
  assert.throws(() => new WarcWriter().restoreState({...state,currentOffset:-1},stream));
});

test('WarcWriter sha256Hex known digest and fail-closed when crypto.subtle missing (W3, AC3)', async () => {
  const digest = await WarcWriter.sha256Hex(new TextEncoder().encode('hello'));
  assert.equal(digest, '2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824');

  const out = child_process.execFileSync(
    process.execPath,
    ['-e', "Object.defineProperty(globalThis,'crypto',{value:{},configurable:true});const W=require('./web/lib/warc_writer.js');W.sha256Hex(new Uint8Array([1])).then(()=>process.exit(1),e=>{process.stdout.write(e.message);process.exit(0);})"],
    { encoding: 'utf8' }
  );
  assert.equal(out, 'WebCrypto SHA-256 is unavailable; refusing to write an unverifiable digest');
});

test('WarcWriter WARC-Refers-To on revisit records (W4, AC4)', async () => {
  const writer = new WarcWriter({ filename: 't.warc' });
  const payload = new TextEncoder().encode('x'.repeat(600));
  const makeHeaders = () => ({ status: 200, statusText: 'OK', headers: new Headers({ 'content-type': 'text/plain' }) });
  const r1 = await writer.addResponseRecord('http://h.test/a', makeHeaders(), payload);
  const r2 = await writer.addResponseRecord('http://h.test/b', makeHeaders(), payload);
  assert.equal(r2.isRevisit, true);
  const block = new TextDecoder().decode(writer.records[2]);
  assert.equal(block.includes('WARC-Refers-To: ' + r1.recordId), true);
});

test('WarcWriter synthesised request record with WARC-Concurrent-To and CDX offset (W6, AC7)', async () => {
  const writer = new WarcWriter({ filename: 't.warc' });
  await writer.addResponseRecord(
    'http://h.test/p?q=1',
    { status: 200, statusText: 'OK', headers: new Headers({ 'content-type': 'text/html' }) },
    new TextEncoder().encode('hello'),
    { request: { method: 'GET', headers: { 'Accept': 'text/html' } } }
  );
  assert.equal(writer.records.length, 3);
  const all = Buffer.concat(writer.records.map(r => Buffer.from(r))).toString('latin1');
  const req = Buffer.from(writer.records[1]).toString('latin1');
  assert.equal((all.match(/WARC-Type: request/g) || []).length, 1);
  assert.equal((all.match(/WARC-Concurrent-To: /g) || []).length, 2);
  assert.equal(req.includes('GET /p?q=1 HTTP/1.1\r\nHost: h.test\r\nAccept: text/html\r\n\r\n'), true);

  const cdxLines = writer.getCdxContent().trim().split('\n');
  assert.equal(cdxLines.length, 2);
  const parts = cdxLines[1].split(/\s+/);
  const expectedOffset = writer.records[0].length + writer.records[1].length;
  assert.equal(Number(parts[9]), expectedOffset);
  assert.equal(Number(parts[8]), writer.records[2].length);
});
