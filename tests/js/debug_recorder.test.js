const {test} = require('node:test');
const assert = require('node:assert/strict');
const {DebugRecorder} = require('../../web/lib/debug_recorder.js');
const tick = () => new Promise(resolve => setImmediate(resolve));

test('records progressively and redacts URL credentials before sending', async () => {
  const batches=[];
  const recorder=new DebugRecorder(async (action, payload) => {
    if (action==='debug-status') return {active:false};
    if (action==='debug-start') return {client_id:'client', log_file:'debug.jsonl',next_sequence:0,saved_events:1};
    batches.push(payload);return {next_sequence:payload.sequence+payload.events.length,saved_events:5};
  });
  await recorder.enable();await tick();
  recorder.record('request',{url:'https://user:password@example.test/path?token=secret',message:'secret',body:'secret'});
  await tick();
  assert.equal(recorder.queue.length,0);
  assert.ok(JSON.stringify(batches).includes('https://example.test/path'));
  assert.ok(!JSON.stringify(batches).includes('secret'));
  assert.ok(!JSON.stringify(batches).includes('password'));
});

test('ambiguous failure retries the identical batch before new events', async () => {
  const batches=[];let fail=true;let failures=0;
  const recorder=new DebugRecorder(async (action,payload)=>{
    if(action==='debug-status')return {active:false};
    if(action==='debug-start')return {client_id:'client',log_file:'debug.jsonl',next_sequence:0};
    batches.push(JSON.stringify(payload));
    if(fail)throw Error('network');
    return {next_sequence:payload.sequence+payload.events.length,saved_events:2};
  },()=>{},()=>failures++);
  await recorder.enable();await tick();
  recorder.record('later');await tick();
  fail=false;await recorder.flush();await tick();
  assert.equal(batches[0],batches[1]);
  assert.equal(batches[0],batches[2]);
  assert.equal(recorder.queue.length,0);
  assert.ok(failures>0);
});

test('permanent storage failure remains visible after reload', async () => {
  const states=[];let pauses=0;
  const recorder=new DebugRecorder(async action=>{
    assert.equal(action,'debug-status');
    return {active:true,failed:true,log_file:'debug.jsonl'};
  },state=>states.push(state),()=>pauses++);
  await recorder.enable(false);
  assert.equal(recorder.terminal,true);assert.equal(pauses,1);
  assert.equal(states[0].permanent,true);assert.equal(states[0].path,'debug.jsonl');
});

test('disk failure stops retrying and preserves unacknowledged batch', async () => {
  let calls=0;let state;
  const recorder=new DebugRecorder(async (action)=>{
    if(action==='debug-status')return {active:false};
    if(action==='debug-start')return {client_id:'client',log_file:'debug.jsonl',next_sequence:0};
    calls++;throw Object.assign(Error('storage'),{diagnostic:{stage:'storage'}});
  },value=>state=value);
  await recorder.enable();await tick();await recorder.flush();
  assert.equal(calls,1);assert.equal(recorder.queue.length,1);
  assert.equal(state.permanent,true);
});

test('queue overflow is explicit and calls the capture pause hook', () => {
  let state;let paused=0;
  const recorder=new DebugRecorder(()=>{},value=>state=value,()=>paused++);
  recorder.active=true;recorder.sending=true;
  for(let i=0;i<1025;i++)recorder.record('progress');
  assert.equal(recorder.queue.length,1024);
  assert.equal(state.overflow,true);assert.equal(paused,1);
});
