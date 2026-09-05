const test = require('node:test');
const assert = require('node:assert/strict');
const PolitenessEngine = require('../../web/lib/politeness_engine.js');

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
