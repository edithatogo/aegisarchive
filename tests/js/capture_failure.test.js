const test = require('node:test');
const assert = require('node:assert/strict');
const {captureFailureReport, UsbArchiveStreamer} = require('../../web/lib/native_capture.js');
test('checkpoint failure preserves reason and truthful partial counts without private text', () => {
  const error = Error('password=secret https://user:secret@fixture.invalid/?token=secret');
  error.diagnostic = {stage:'checkpoint',error_type:'CheckpointLimitError',reason_code:'state_limit',bytes:1100000,limit_bytes:1048576};
  const crawler={visited:new Set(['a','b']),queue:[{},{}],resourceOutcomes:new Map([['a',{state:'captured'}],['b',{state:'pending'}]])};
  const report=captureFailureReport(error,crawler);
  assert.equal(report.coverage.counts.captured,1);
  assert.equal(report.coverage.counts.pending,1);
  assert.equal(report.coverage.archive_storage_verified,false);
  assert.equal(report.events[0].reason_code,'state_limit');
  assert.match(report.events[0].error_message,/1100000.*1048576/);
  assert.equal(JSON.stringify(report).includes('secret'),false);
});
test('generic native exception retains code location without arbitrary message or stack', () => {
  const error=Error('secret');
  error.diagnostic={stage:'checkpoint',error_type:'ValueError',code_file:'usb_archive.py',code_function:'encoded_state',code_line:60};
  const report=captureFailureReport(error,null);
  assert.match(report.events[0].error_message,/ValueError.*usb_archive.py:60.*encoded_state/);
  assert.equal(JSON.stringify(report).includes('secret'),false);
});
test('checkpoint transport failure gets checkpoint stage and does not advance generation',async()=>{
 const streamer=new UsbArchiveStreamer({call:async()=>{throw new TypeError('network private');}});
 streamer.generation=7;
 await assert.rejects(streamer.checkpoint({},'a'.repeat(64)),error=>error.diagnostic.stage==='checkpoint'&&error.diagnostic.error_type==='TypeError');
 assert.equal(streamer.generation,7);
});
test('archive write retains safe Windows error details in the saved report',async()=>{
 const error=Error('private message and C:\\private\\path');
 error.diagnostic={stage:'storage',error_type:'OSError',cause_type:'PermissionError',operation:'archive-chunk',errno:13,winerror:32,
   code_file:'usb_archive.py',code_function:'chunk',code_line:240};
 const streamer=new UsbArchiveStreamer({call:async()=>{throw error;}});
 await assert.rejects(streamer.writeChunk(new Uint8Array([1])),caught=>{
  const report=captureFailureReport(caught,null), event=report.events[0];
  assert.equal(event.error_type,'OSError');
  assert.equal(event.operation,'archive-chunk');
  assert.equal(event.errno,13);
  assert.equal(event.winerror,32);
  assert.equal(event.cause_type,'PermissionError');
  assert.equal(event.code_function,'chunk');
  assert.match(event.error_message,/Windows error 32/);
  assert.match(event.error_message,/file is in use/);
  assert.equal(JSON.stringify(report).includes('private'),false);
  return true;
 });
});
test('checkpoint failure retains its Windows error code in the saved report',async()=>{
 const diagnostic={stage:'checkpoint',error_type:'OSError',operation:'archive-checkpoint',errno:13,
   winerror:32,code_file:'usb_archive.py',code_function:'publish_checkpoint',code_line:315};
 const {NativeCapture}=require('../../web/lib/native_capture.js');
 const original=global.fetch;
 global.fetch=async()=>new Response(JSON.stringify({error:'PermissionError during archive-checkpoint (Windows error 32)',diagnostic}),
   {status:507,headers:{'content-type':'application/json'}});
 const streamer=new UsbArchiveStreamer(new NativeCapture('synthetic'));
 streamer.generation=7;
 try {
  await assert.rejects(streamer.checkpoint({},'a'.repeat(64)),caught=>{
   const event=captureFailureReport(caught,null).events[0];
   assert.match(caught.message,/Windows error 32/);
   assert.equal(event.stage,'checkpoint');
   assert.equal(event.operation,'archive-checkpoint');
   assert.equal(event.winerror,32);
   assert.match(event.error_message,/Windows error 32/);
   assert.equal(JSON.stringify(event).includes('private'),false);
   return true;
  });
 } finally {global.fetch=original;}
 assert.equal(streamer.generation,7);
});
test('oversized checkpoint is rejected locally before a request can lose its error response',async()=>{
 const {NativeCapture}=require('../../web/lib/native_capture.js');
 const original=global.fetch;let calls=0;
 global.fetch=async()=>{calls++;throw Error('must not send');};
 try {
  await assert.rejects(new NativeCapture('private').call('archive-checkpoint',{state:{data:'x'.repeat(33*1024*1024)}}),
    error=>error.diagnostic.reason_code==='request_limit'&&error.diagnostic.bytes>error.diagnostic.limit_bytes);
  assert.equal(calls,0);
 } finally {global.fetch=original;}
});
