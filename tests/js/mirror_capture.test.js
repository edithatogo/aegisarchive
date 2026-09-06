const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {createHash} = require('node:crypto');
const fixtureDir = path.join(__dirname, '../fixtures/mirror');
const manifest = JSON.parse(fs.readFileSync(path.join(fixtureDir, 'manifest.json')));
test('frozen resource bytes agree with manifest', () => {
  assert.equal(manifest.resources.length, 9);
  for (const r of manifest.resources) assert.equal(createHash('sha256').update(fs.readFileSync(path.join(fixtureDir, r.file))).digest('hex'), r.sha256);
});
