const test = require('node:test');
const assert = require('node:assert/strict');
const PolitenessEngine = require('../../web/lib/politeness_engine.js');

test('durable pacing preserves deadlines, empty bucket and circuit', async t => {
  let now = 1000000;
  t.mock.method(Date, 'now', () => now);
  const config = {min_delay_ms:100,max_delay_ms:100};
  const engine = new PolitenessEngine(config);
  engine.tokens = 0;
  for (let i=0;i<3;i++) engine.recordFailure('http://h.test/',429,'120');
  const state = JSON.parse(JSON.stringify(engine.exportState()));
  now -= 10000;
  const restored = new PolitenessEngine(config);
  restored.restoreState(state);
  assert.equal(restored.tokens,0);
  assert.equal(restored.lastTokenRefill,now);
  assert.ok(restored.domainCooldowns.get('h.test') >= 1120000);
  assert.equal(restored.circuitState,'TRIPPED');
  const waits=[];
  restored.sleep=async ms=>{waits.push(ms);return false;};
  assert.equal((await restored.acquirePermission('http://h.test/')).aborted,true);
  assert.ok(waits[0]>=60000);
  restored.domainCooldowns.set('h.test',2000000);
  restored.restoreState(state);
  assert.equal(restored.domainCooldowns.get('h.test'),2000000);
});

test('malformed and incompatible pacing restore never partially mutates', t => {
  t.mock.method(Date,'now',()=>1000000);
  const engine=new PolitenessEngine();
  const original=engine.exportState();
  for (const [field,value] of [['tokens',NaN],['consecutive_errors',true],
    ['warmup_samples',[Infinity]],['version',2]]) {
    const state=structuredClone(original);state[field]=value;
    assert.throws(()=>engine.restoreState(state));
    assert.deepEqual(engine.exportState(),original);
  }
  const state=structuredClone(original);state.config.burst_limit++;
  assert.throws(()=>engine.restoreState(state));
});

test('forward restore retains absolute deadlines and saved adaptive state', async t => {
  let now=1000000;
  t.mock.method(Date,'now',()=>now);
  const config={burst_limit:1,max_requests_per_minute:1,min_delay_ms:100,max_delay_ms:100};
  const engine=new PolitenessEngine(config);
  engine.recordSuccess('http://h.test/',300);
  for (let i=0;i<3;i++) engine.recordFailure('http://h.test/',503,'120');
  engine.tokens=0;engine.nextPermissionAt=1130000;
  const state=engine.exportState();now+=10000;
  const restored=new PolitenessEngine(config);restored.restoreState(state);
  assert.equal(restored.domainCooldowns.get('h.test'),1120000);
  assert.equal(restored.nextPermissionAt,1130000);
  assert.equal(restored.ewmaLatencyMs,300);
  assert.deepEqual(restored.warmupSamples,[300]);
  assert.equal(restored.currentBackoffDelayMs,engine.currentBackoffDelayMs);
  const waits=[];
  restored.sleep=async ms=>{waits.push(ms);now+=ms;return true;};
  assert.equal((await restored.acquirePermission('http://h.test/')).aborted,false);
  assert.equal(waits[0],50000);assert.ok(now>=1130000);
  assert.equal(restored.circuitState,'HALF_OPEN');
  Object.assign(state,{saved_at_ms:now,last_refill_ms:now,circuit_state:'NOMINAL',
    circuit_until_ms:null,domain_cooldowns:{}});
  const fresh=new PolitenessEngine(config);fresh.restoreState(state);
  const tokenWaits=[];fresh.sleep=async ms=>{tokenWaits.push(ms);return false;};
  assert.equal((await fresh.acquirePermission('http://h.test/')).aborted,true);
  assert.equal(tokenWaits[0],60000);
});

test('PolitenessEngine EWMA baseline warm-up and drift (T1, AC1)', () => {
  const engine = new PolitenessEngine({});
  engine.recordSuccess('http://h.test/', 5);
  assert.equal(engine.baselineLatencyMs, null);

  for (let i = 0; i < 9; i++) {
    engine.recordSuccess('http://h.test/', 300);
  }
  assert.equal(engine.baselineLatencyMs, 300);
  assert.equal(engine.warmupSamples.length, 10);

  engine.recordSuccess('http://h.test/', 1000);
  assert.equal(engine.baselineLatencyMs, 314);
});

test('PolitenessEngine failure counting only for 0, 429, 5xx (T2, AC2)', () => {
  const engine = new PolitenessEngine({});
  for (let i = 0; i < 3; i++) {
    engine.recordFailure('http://h.test/', 404);
  }
  assert.equal(engine.circuitState, PolitenessEngine.CircuitState.NOMINAL);
  assert.equal(engine.consecutiveErrors, 0);

  for (let i = 0; i < 3; i++) {
    engine.recordFailure('http://h.test/', 503);
  }
  assert.equal(engine.circuitState, PolitenessEngine.CircuitState.TRIPPED);
  assert.equal(PolitenessEngine.isCountableFailure(0), true);
  assert.equal(PolitenessEngine.isCountableFailure(429), true);
  assert.equal(PolitenessEngine.isCountableFailure(500), true);
  assert.equal(PolitenessEngine.isCountableFailure(403), false);
  assert.equal(PolitenessEngine.isCountableFailure(404), false);
});

test('PolitenessEngine Retry-After cap (T4, AC4)', () => {
  const engine = new PolitenessEngine({ cooldown_seconds: 60 });
  engine.recordFailure('http://h.test/', 429, '999999');
  const now = Date.now();
  const wakeEpoch = engine.domainCooldowns.get('h.test');
  assert.ok(wakeEpoch);
  const remaining = wakeEpoch - now;
  assert.ok(remaining <= 600000);
  assert.ok(remaining > 500000);
});

test('PolitenessEngine abort() resolves acquirePermission quickly (T4, AC4)', async () => {
  const engine = new PolitenessEngine({ cooldown_seconds: 60 });
  engine.recordFailure('http://h.test/', 429, '999999');
  const t0 = Date.now();
  setTimeout(() => engine.abort(), 50);
  const gate = await engine.acquirePermission('http://h.test/');
  const elapsed = Date.now() - t0;
  assert.equal(gate.aborted, true);
  assert.ok(elapsed < 1000);
});

test('PolitenessEngine sleep() resolves true when not aborted (T4, AC4)', async () => {
  const engine = new PolitenessEngine({});
  const ok = await engine.sleep(1);
  assert.equal(ok, true);
});

test('output slots remain paced when permission calls overlap', async t => {
  t.mock.method(Date, 'now', () => 1000);
  const engine = new PolitenessEngine({min_delay_ms: 10, max_delay_ms: 10});
  const delays = [];
  engine.sleep = async ms => { delays.push(ms); return true; };
  await Promise.all([engine.acquirePermission('http://h.test/'), engine.acquirePermission('http://h.test/')]);
  assert.deepEqual(delays, [10, 20]);
  assert.ok(Number.isFinite(engine.parseRetryAfter('9'.repeat(5000))));
});
