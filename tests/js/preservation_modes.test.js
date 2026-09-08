const test = require('node:test');
const assert = require('node:assert/strict');
const modes = require('../../web/lib/preservation_modes.js');
test('modes keep originals authoritative and distinguish rendered derivatives', () => {
  assert.equal(modes.describe('preservation').rendered, false);
  assert.equal(modes.describe('offline_reading').offline, true);
  assert.equal(modes.describe('rendered_optional').rendered, true);
  assert.equal(modes.describe('rendered_optional').originalsAuthoritative, true);
});
test('unknown modes fail closed', () => assert.throws(() => modes.describe('live_application')));
